"""Features shared by training (training/*.py) and serving. Keep NAMES identical in both."""
import re, subprocess
FIX = re.compile(r"\b(fix(es|ed)?|bug|hotfix|regression|crash|patch)\b", re.I)
WORK = re.compile(r"\b(workaround|hack|temporary|temp|legacy|compat\w*|backward)\b", re.I)
NAMES = ["age_days", "days_since_change", "n_commits", "n_authors", "n_fix", "n_workaround",
         "n_lines", "n_markers", "avg_msg_len", "has_test_ref", "max_indent", "fix_ratio"]


def _git(d, *a, t=90):
    try:
        r = subprocess.run(["git", *a], cwd=d, capture_output=True, text=True, timeout=t)
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def extract(d, path, s, e, symbol=None, rev="HEAD"):
    log = _git(d, "log", "-L", f"{s},{e}:{path}", "-s", "--format=%at%x1f%an%x1f%s%x1f%b%x1e", rev)
    recs = []
    for chunk in log.split("\x1e"):
        p = chunk.strip().split("\x1f")
        if len(p) >= 3 and p[0].isdigit():
            recs.append((int(p[0]), p[1], p[2], p[3] if len(p) > 3 else ""))
    ts = [r[0] for r in recs]
    now = int(_git(d, "show", "-s", "--format=%at", rev).strip() or 0) or (max(ts) if ts else 0)
    msgs = [f"{r[2]} {r[3]}" for r in recs]
    n = len(recs)
    nf = sum(bool(FIX.search(m)) for m in msgs)
    src = _git(d, "show", f"{rev}:{path}").splitlines()[s - 1:e]
    has_test = int(bool(symbol and _git(d, "grep", "-l", "-w", symbol, rev, "--", "*test*")))
    return {"age_days": (now - min(ts)) / 86400 if ts else 0,
            "days_since_change": (now - max(ts)) / 86400 if ts else 0,
            "n_commits": n, "n_authors": len({r[1] for r in recs}), "n_fix": nf,
            "n_workaround": sum(bool(WORK.search(m)) for m in msgs), "n_lines": e - s + 1,
            "n_markers": sum(bool(re.search(r"TODO|FIXME|HACK|XXX", l)) for l in src),
            "avg_msg_len": sum(len(m) for m in msgs) / n if n else 0, "has_test_ref": has_test,
            "max_indent": max([len(l) - len(l.lstrip()) for l in src if l.strip()] or [0]) // 4,
            "fix_ratio": nf / n if n else 0}
