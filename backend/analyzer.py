"""Git-history evidence extraction (no GitHub token needed: partial clone, no checkout)."""
import ast, json, os, re, shutil, subprocess, tempfile, urllib.request
from ml import INTENT
from collections import Counter

SIGNALS = {
    "bug fix": r"\b(fix(es|ed)?|bug|hotfix|regression|crash|patch)\b",
    "workaround": r"\b(workaround|hack|temporary|temp|legacy|compat\w*|backward)\b",
    "performance": r"\b(perf\w*|optimi[sz]e\w*|speed|faster|cache|latency)\b",
    "security": r"\b(security|cve|vuln\w*|sanitiz\w*|xss|csrf|auth\w*)\b",
    "revert": r"\b(revert\w*|rollback)\b",
    "refactor": r"\b(refactor\w*|cleanup|clean up|rename\w*|restructure)\b",
    "feature": r"\b(add(s|ed)?|feat\w*|implement\w*|introduce\w*|support)\b",
    "requirement": r"\b(requirement|spec|compliance|regulat\w*|policy|customer|client)\b",
}
MARKERS = r"(TODO|FIXME|HACK|XXX|NOTE|WHY|WARNING|IMPORTANT)\b"
REPO_RE = re.compile(r"^https://github\.com/[\w.-]+/[\w.-]+?(\.git)?/?$")


class UserError(Exception):
    pass


def git(args, cwd, timeout=60):
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
    if r.returncode:
        raise UserError(r.stderr.strip()[:300] or "git failed")
    return r.stdout


def find_symbol(path, src, name):
    if path.endswith(".py"):
        try:
            for n in ast.walk(ast.parse(src)):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == name:
                    return n.lineno, n.end_lineno
        except SyntaxError:
            pass
    lines = src.splitlines()
    for i, l in enumerate(lines, 1):
        if re.search(rf"\b{re.escape(name)}\b", l) and re.search(r"function|def |class |=>|\)\s*\{", l):
            depth, seen = 0, False
            for j in range(i - 1, len(lines)):
                depth += lines[j].count("{") - lines[j].count("}")
                seen = seen or "{" in lines[j]
                if seen and depth <= 0:
                    return i, j + 1
            return i, min(i + 30, len(lines))
    raise UserError(f"Symbol '{name}' not found in file")


def commit_info(d, sha):
    f = "%H%x1f%an%x1f%ad%x1f%s%x1f%b"
    h, an, date, subj, body = git(["show", "-s", f"--format={f}", "--date=short", sha], d).rstrip("\n").split("\x1f", 4)
    return {"sha": h[:8], "author": an, "date": date, "subject": subj, "body": body.strip()[:600]}


def analyse(repo, path, symbol=None, lines=None, hook=None):
    if not REPO_RE.match(repo.strip()):
        raise UserError("Only public https://github.com/owner/repo URLs are supported")
    if ".." in path or path.startswith("/") or not path.strip():
        raise UserError("Invalid file path")
    d = tempfile.mkdtemp(prefix="wc_")
    try:
        try:
            subprocess.run(["git", "clone", "--quiet", "--filter=blob:none", "--no-checkout", repo.strip(), d],
                           check=True, timeout=120, capture_output=True,
                           env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        except Exception:
            raise UserError("Could not clone repo (private, missing, or too large?)")
        try:
            src = git(["show", f"HEAD:{path}"], d)
        except UserError:
            raise UserError(f"File '{path}' not found at HEAD")
        if len(src) > 500_000:
            raise UserError("File too large (500KB max)")
        total = len(src.splitlines())
        if symbol:
            s, e = find_symbol(path, src, symbol)
        elif lines and re.match(r"^\d+-\d+$", lines):
            s, e = map(int, lines.split("-"))
        else:
            raise UserError("Give a symbol name or a line range like 10-40")
        s, e = max(1, s), min(e, total)
        if s > e:
            raise UserError("Line range out of file bounds")
        blame = git(["blame", "-w", "-M", "-C", "--porcelain", "-L", f"{s},{e}", "HEAD", "--", path], d)
        owners = Counter(m.group(1) for l in blame.splitlines() if (m := re.match(r"^([0-9a-f]{40}) \d+ \d+", l)))
        hist = list(dict.fromkeys(git(["log", "-L", f"{s},{e}:{path}", "-s", "--format=%H", "HEAD"], d, 90).split()))[:30]
        commits = []
        for sha in hist:
            c = commit_info(d, sha)
            text = f"{c['subject']} {c['body']}".lower()
            c["tags"] = INTENT.tags(text)
            c["refs"] = sorted(set(re.findall(r"(?:#|GH-|[A-Z]{2,}-)\d+", f"{c['subject']} {c['body']}")))
            c["lines_owned"] = next((n for k, n in owners.items() if k.startswith(c["sha"])), 0)
            commits.append(c)
        code_lines = src.splitlines()[s - 1:e]
        comments = [{"line": s + i, "text": l.strip()} for i, l in enumerate(code_lines) if re.search(MARKERS, l)]
        tags = Counter(t for c in commits for t in c["tags"])
        risky = bool(tags.get("bug fix") or tags.get("workaround") or tags.get("security"))
        conf = "high" if len(commits) >= 2 and any(c["body"] for c in commits) else "medium" if tags else "low"
        hl = {c["line"] for c in comments}
        excerpt = [{"n": s + i, "text": l, "hl": (s + i) in hl} for i, l in enumerate(code_lines[:40])]
        origin = commits[-1] if commits else None
        res = {"repo": repo, "path": path, "symbol": symbol, "range": [s, e], "code": "\n".join(code_lines)[:6000],
                "excerpt": excerpt, "total_lines": e - s + 1,
                "reasons": dict(tags), "risky": risky, "confidence": conf,
                "low_evidence": conf == "low" and not comments,
                "author": origin["author"] if origin else None,
                "suggested_question": f"What constraint led to this implementation in {path}? "
                                      "Is there a bug or edge case I should preserve before changing it?",
                "comments": comments, "commits": commits}
        if hook:
            hook(d, res)
        return res
    finally:
        shutil.rmtree(d, ignore_errors=True)


def claude(system, prompt, max_tokens=900):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise UserError("Server is missing ANTHROPIC_API_KEY")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps({"model": os.environ.get("WHYCODE_MODEL", "claude-sonnet-4-6"), "max_tokens": max_tokens,
                         "system": system, "messages": [{"role": "user", "content": prompt}]}).encode(),
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)["content"][0]["text"]
    except Exception as ex:
        raise UserError(f"AI call failed: {ex}")


SYSTEM = ("You are WhyCode, a code archaeologist. Explain WHY code is written the way it is using ONLY the "
          "evidence given (commits, comments, code). Cite commit SHAs in `backticks`. If evidence is weak, say so "
          "plainly and suggest who to ask (original author). Never invent reasons. Be concise.")


SCHEMA = ('Return ONLY JSON, no markdown: {"verdict_summary": "one sentence", "verdict_detail": "2-3 sentences", '
          '"key_reasons": [{"reason": "short title", "evidence": "1-2 sentences", "shas": ["8-char sha"], '
          '"refs": ["#42"]}], "what_could_break": "2-3 sentences"}. Max 3 key_reasons; every reason needs a real sha.')


def parse_explanation(raw, result):
    try:
        data = json.loads(re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip())
    except Exception:
        data = {"verdict_summary": raw[:300], "verdict_detail": "", "key_reasons": [], "what_could_break": ""}
    known = {c["sha"] for c in result["commits"]}
    reasons = data.get("key_reasons") or []
    for r in reasons:
        r["shas"] = [x[:8] for x in r.get("shas", []) if x[:8] in known]
        r["refs"] = r.get("refs", [])
    data["key_reasons"] = reasons
    data["grounded"] = bool(reasons) and all(r["shas"] for r in reasons)
    return data


def explain(result):
    p = (f"Explain why this code is like this.\n\nCODE ({result['path']}:{result['range']}):\n{result['code']}\n\n"
         f"COMMITS (newest first):\n{json.dumps(result['commits'], indent=1)}\n\nCOMMENTS:\n{result['comments']}\n\n" + SCHEMA)
    return parse_explanation(claude(SYSTEM, p, 1400), result)


def ask(result, question):
    ctx = json.dumps(result)[:20000]
    return claude(SYSTEM, f"EVIDENCE:\n{ctx}\n\nQUESTION / PROPOSED CHANGE:\n{question[:1500]}\n\n"
                          "Answer from the evidence. If it's a proposed change, assess risk (low/medium/high) and why.")
