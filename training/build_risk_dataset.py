"""SZZ-lite dataset. Positive = line ranges a later bug-fix commit deleted/changed (they were buggy at the parent).
Negative = random non-overlapping ranges of the same size in the same file at the same parent.
Features come from backend/ml/features.py, so training == serving.
Usage: python build_risk_dataset.py repos.txt risk.csv [max_fixes_per_repo]"""
import csv, os, random, re, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from ml.features import extract, NAMES, FIX, _git

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? ")


def removed_hunks(d, sha):
    out, path = [], None
    for l in _git(d, "diff", "-U0", f"{sha}^", sha, t=120).splitlines():
        if l.startswith("--- a/"): path = l[6:]
        elif l.startswith("--- "): path = None
        m = HUNK.match(l)
        if m and path and path.endswith((".py", ".js", ".ts", ".go", ".java", ".rb", ".rs", ".c", ".cpp")):
            a, n = int(m.group(1)), int(m.group(2) or 1)
            if 0 < n <= 60: out.append((path, a, a + n - 1))
    return out


def main(repos, out, cap=150):
    random.seed(7)
    rows = []
    for url in open(repos).read().split():
        d = tempfile.mkdtemp()
        subprocess.run(["git", "clone", "-q", "--filter=blob:none", "--no-checkout", url, d], check=True)
        fixes = [x.split("\x1f")[0] for x in _git(d, "log", "-n", "3000", "--no-merges", "--format=%H%x1f%s").splitlines()
                 if len(x.split("\x1f")) > 1 and FIX.search(x.split("\x1f")[1])][:cap]
        for sha in fixes:
            for path, a, b in removed_hunks(d, sha)[:3]:
                try:
                    pos = extract(d, path, a, b, rev=f"{sha}^")
                    total = len(_git(d, "show", f"{sha}^:{path}").splitlines())
                    if total <= (b - a + 1) + 2 or pos["n_commits"] == 0: continue
                    for _ in range(10):  # find a non-overlapping negative window
                        s = random.randint(1, total - (b - a)); 
                        if s + (b - a) < a or s > b: break
                    neg = extract(d, path, s, s + (b - a), rev=f"{sha}^")
                    rows += [{**pos, "label": 1, "repo": url}, {**neg, "label": 0, "repo": url}]
                except Exception:
                    continue
        shutil.rmtree(d, ignore_errors=True)
        print(url, len(rows))
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=NAMES + ["label", "repo"]); w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 150)
