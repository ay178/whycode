"""Claude tool-use investigator. Streams its steps through emit()."""
import json, os, re, subprocess, urllib.request
import analyzer as A
from proof import counterfactual
import urllib.error

MODEL = os.environ.get("WHYCODE_MODEL", "claude-sonnet-4-6")
TOOLS = [
    {"name": "search_evidence", "description": "Hybrid-search commits and comments of this repo for text relevant to a question.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "read_commit", "description": "Read the full message and changed-file stats of a commit by SHA.",
     "input_schema": {"type": "object", "properties": {"sha": {"type": "string"}}, "required": ["sha"]}},
    {"name": "git_grep", "description": "Search the repository at HEAD for a pattern (e.g. callers, tests, ticket ids).",
     "input_schema": {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}},
    {"name": "run_counterfactual", "description": "Delete the selected lines and run the test-suite to prove what depends on them. Slow; use at most once.",
     "input_schema": {"type": "object", "properties": {}}},
]


def _call(messages, tools=True):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise A.UserError("Server is missing ANTHROPIC_API_KEY")
    body = {"model": MODEL, "max_tokens": 1500, "messages": messages,
            "system": [{"type": "text", "text": A.SYSTEM, "cache_control": {"type": "ephemeral"}}]}  # prompt caching
    if tools:
        body["tools"] = TOOLS
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(),
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.load(r)
    except Exception as ex:
        raise A.UserError(f"AI call failed: {ex}")


def _git(d, *a):
    r = subprocess.run(["git", *a], cwd=d, capture_output=True, text=True, timeout=60)
    return r.stdout.strip()


def _tool(name, inp, d, res, ret):
    if name == "search_evidence":
        return "\n".join(f"[{x['kind']} {x['id']}] {x['text'][:300]}" for x in ret.search(inp.get("query", ""), 5)) or "no matches"
    if name == "read_commit":
        sha = inp.get("sha", "")
        if not re.fullmatch(r"[0-9a-f]{7,40}", sha):
            return "invalid sha"
        return (_git(d, "show", "-s", "--format=%an %ad%n%B", "--date=short", sha) + "\n" + _git(d, "show", "--stat", "--format=", sha))[:1800]
    if name == "git_grep":
        return _git(d, "grep", "-n", "-I", "-m", "3", "-e", inp.get("pattern", "")[:100], "HEAD")[:1800] or "no matches"
    if name == "run_counterfactual":
        res["proof"] = counterfactual(d, res["path"], *res["range"])
        return json.dumps(res["proof"])
    return "unknown tool"


def run(d, res, ret, emit):
    ranked = [f"[{x['kind']} {x['id']}] {x['text'][:200]}" for x in res.get("evidence_ranked", [])]
    msgs = [{"role": "user", "content":
             f"Investigate why this code is like this.\nCODE ({res['path']}:{res['range']}):\n{res['code']}\n\n"
             f"COMMITS (newest first):\n{json.dumps(res['commits'], indent=1)}\nCOMMENTS: {res['comments']}\n"
             f"TOP RETRIEVED EVIDENCE:\n" + "\n".join(ranked) + f"\nCHANGE RISK: {res.get('risk')}\n\n"
             "Use tools only if they add evidence (max 4 calls). Then answer.\n" + A.SCHEMA}]
    for _ in range(5):
        r = _call(msgs)
        msgs.append({"role": "assistant", "content": r["content"]})
        uses = [b for b in r["content"] if b["type"] == "tool_use"]
        if not uses:
            return A.parse_explanation("".join(b.get("text", "") for b in r["content"] if b["type"] == "text"), res)
        out = []
        for b in uses:
            emit({"type": "tool", "name": b["name"], "input": b["input"]})
            ans = _tool(b["name"], b["input"], d, res, ret)
            emit({"type": "tool_result", "summary": ans.replace("\n", " ")[:140]})
            out.append({"type": "tool_result", "tool_use_id": b["id"], "content": ans[:3000]})
        msgs.append({"role": "user", "content": out})
    msgs.append({"role": "user", "content": "Give the final JSON now."})
    r = _call(msgs, tools=False)
    return A.parse_explanation("".join(b.get("text", "") for b in r["content"] if b["type"] == "text"), res)
