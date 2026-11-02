"""PR Guardian (beta): comment on PRs that delete risky code. GitHub webhook -> risk check per removed hunk."""
import hashlib, hmac, json, os, re, urllib.request
import analyzer as A, pipeline

TOKEN, SECRET = os.getenv("GITHUB_TOKEN"), os.getenv("GITHUB_WEBHOOK_SECRET", "")


def verify(body: bytes, sig: str):
    good = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return bool(SECRET) and hmac.compare_digest(good, sig or "")


def _gh(url, data=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None,
                                 headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def removed_ranges(patch):
    out, old, start = [], 0, None
    for l in (patch or "").splitlines():
        m = re.match(r"@@ -(\d+)", l)
        if m:
            if start: out.append((start, old - 1)); start = None
            old = int(m.group(1)); continue
        if l.startswith("-"):
            start = start or old; old += 1
        else:
            if start: out.append((start, old - 1)); start = None
            if not l.startswith("+"): old += 1
    if start: out.append((start, old - 1))
    return out


def handle(payload):
    pr, repo = payload["pull_request"], payload["repository"]
    files = _gh(f"{repo['url']}/pulls/{pr['number']}/files?per_page=30")
    notes = []
    for f in files[:6]:
        for a, b in removed_ranges(f.get("patch"))[:2]:
            got = {}
            try:
                A.analyse(repo["html_url"], f["filename"], lines=f"{a}-{b}", hook=lambda d, r: pipeline.enrich(d, r, lambda ev: got.update(r=ev.get("data") or got.get("r"))) )
            except Exception:
                continue
            r = got.get("r")
            if r and (r["risk"]["prob"] >= .6 or r["risky"]):
                top = ", ".join(c["subject"] for c in r["commits"][:2])
                notes.append(f"- `{f['filename']}` lines {a}-{b}: **{round(r['risk']['prob'] * 100)}% change risk**. History: {top}")
    if notes:
        _gh(f"{repo['url']}/issues/{pr['number']}/comments",
            {"body": "### WhyCode Fence Guard\nThis PR deletes code with risky history. Check why it exists before merging:\n" + "\n".join(notes)})
