"""Knowledge-debt scan: which files have reasons nobody remembers? Plug a survival model in ml/ later; heuristic for now."""
import os, re, shutil, subprocess, tempfile, time
import analyzer as A
from collections import defaultdict


def scan(repo):
    if not A.REPO_RE.match(repo.strip()):
        raise A.UserError("Only public https://github.com/owner/repo URLs are supported")
    d = tempfile.mkdtemp(prefix="wcd_")
    try:
        try:
            subprocess.run(["git", "clone", "--quiet", "--filter=blob:none", "--no-checkout", repo.strip(), d], check=True,
                           timeout=120, capture_output=True, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        except Exception:
            raise A.UserError("Could not clone repo (private, missing, or too large?)")
        log = A.git(["log", "-n", "800", "--name-only", "--format=@@%an\x1f%at\x1f%s"], d)
        files, cur = defaultdict(lambda: {"a": set(), "t": [], "m": []}), None
        for line in log.splitlines():
            if line.startswith("@@"):
                cur = line[2:].split("\x1f")
            elif line.strip() and cur and len(cur) == 3:
                f = files[line.strip()]; f["a"].add(cur[0]); f["t"].append(int(cur[1])); f["m"].append(cur[2])
        now, out = max([max(f["t"]) for f in files.values()] or [time.time()]), []
        for p, f in files.items():
            n = len(f["t"])
            if n < 3:
                continue
            stale = min((now - max(f["t"])) / 86400 / 730, 1)
            short = sum(len(m) < 25 for m in f["m"]) / n
            fixes = sum(bool(re.search(r"fix|bug|hotfix", m, re.I)) for m in f["m"]) / n
            debt = .35 * stale + .25 * short + .25 * (1 / len(f["a"])) + .15 * fixes
            out.append({"path": p, "commits": n, "authors": len(f["a"]), "debt": round(debt, 2)})
        return sorted(out, key=lambda x: -x["debt"])[:24]
    finally:
        shutil.rmtree(d, ignore_errors=True)
