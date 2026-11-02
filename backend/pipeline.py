"""Runs inside analyse() while the clone still exists: ML scoring -> retrieval -> agent -> NLI -> calibration."""
import analyzer as A, agent
from ml import RISK, NLI, SURPRISE, Retriever, calibrate
from ml.features import extract, _git


def enrich(d, res, emit):
    s, e = res["range"]
    emit({"type": "step", "name": f"History traced: {len(res['commits'])} commit(s) touch this code"})
    res["risk"] = RISK.predict(extract(d, res["path"], s, e, symbol=res.get("symbol")))
    emit({"type": "step", "name": f"Risk model ({res['risk']['source']}): {round(res['risk']['prob'] * 100)}% change risk"})
    for l, v in zip(res["excerpt"], SURPRISE.scores([x["text"] for x in res["excerpt"]])):
        l["s"] = round(v, 2)
    emit({"type": "step", "name": "Surprise heatmap computed"})
    docs = [{"id": c["sha"], "kind": "range-commit", "text": f"{c['subject']} {c['body']}"} for c in res["commits"]]
    docs += [{"id": f"L{c['line']}", "kind": "comment", "text": c["text"]} for c in res["comments"]]
    seen = {x["id"] for x in docs}
    for row in _git(d, "log", "-n", "300", "--format=%h%x1f%s%x1f%b%x1e").split("\x1e"):
        p = row.strip().split("\x1f")
        if len(p) >= 2 and p[0][:8] not in seen:
            docs.append({"id": p[0], "kind": "repo-commit", "text": f"{p[1]} {p[2] if len(p) > 2 else ''}"})
    ret = Retriever(docs)
    res["evidence_ranked"] = ret.search(f"why {res.get('symbol') or ''} {res['code'][:300]}", 5)
    emit({"type": "step", "name": f"Indexed {len(docs)} evidence documents ({'hybrid' if ret.emb is not None else 'BM25'} retrieval)"})
    res["explanation"], support = None, 0.0
    if not res["low_evidence"]:
        emit({"type": "step", "name": "Agent investigating…"})
        ex = agent.run(d, res, ret, emit)
        by = {c["sha"]: f"{c['subject']} {c['body']}" for c in res["commits"]}
        comments = " ".join(c["text"] for c in res["comments"])
        for r in ex["key_reasons"]:
            r["verdict"] = NLI.verify(f"{r.get('reason', '')}. {r.get('evidence', '')}", " ".join(by.get(x, "") for x in r["shas"]) + " " + comments)
        ex["verified_ratio"] = round(sum(r["verdict"]["label"] == "supported" for r in ex["key_reasons"]) / len(ex["key_reasons"]), 2) if ex["key_reasons"] else 0
        res["explanation"], support = ex, ex["verified_ratio"]
        emit({"type": "step", "name": f"NLI guard verified {round(support * 100)}% of claims"})
    res["confidence_score"], level = calibrate(res, support)
    if not res["low_evidence"]:
        res["confidence"] = level
    emit({"type": "result", "data": res})
