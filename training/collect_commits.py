"""Weakly-labelled commit messages for the intent classifier. Usage: python collect_commits.py repos.txt commits.csv
Labels come from Conventional-Commit prefixes + keyword rules. Hand-fix ~300 rows for a trustworthy test set."""
import csv, os, re, subprocess, sys, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from ml.intent import SIGNALS
PREFIX = {"fix": "bug fix", "feat": "feature", "perf": "performance", "refactor": "refactor", "revert": "revert", "sec": "security"}
rows = []
for url in open(sys.argv[1]).read().split():
    d = tempfile.mkdtemp()
    subprocess.run(["git", "clone", "-q", "--filter=blob:none", "--no-checkout", url, d], check=True)
    log = subprocess.run(["git", "log", "-n", "4000", "--no-merges", "--format=%s%x1f%b%x1e"], cwd=d, capture_output=True, text=True).stdout
    for c in log.split("\x1e"):
        p = c.strip().split("\x1f"); subj = p[0]
        if not subj: continue
        m = re.match(r"(\w+)(\(.*?\))?!?:", subj)
        lab = PREFIX.get(m.group(1).lower()) if m else None
        lab = lab or next((k for k, rx in SIGNALS.items() if re.search(rx, subj.lower())), "other")
        rows.append({"text": (subj + " " + (p[1] if len(p) > 1 else ""))[:600], "label": lab, "repo": url})
    shutil.rmtree(d, ignore_errors=True)
with open(sys.argv[2], "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["text", "label", "repo"]); w.writeheader(); w.writerows(rows)
print(len(rows), "rows")
