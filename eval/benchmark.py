"""Benchmark: does the explanation mention the known reason? Run with ML_ENABLED=0 and =1 to measure what the models add.
Make ~20 cases in benchmark.json (functions whose real reason you know). Usage (from backend/): python ../eval/benchmark.py ../eval/benchmark.json"""
import json, sys
sys.path.insert(0, ".")
import analyzer as A, pipeline

cases, hits, grounded, ver, risk = json.load(open(sys.argv[1])), 0, 0, [], []
for c in cases:
    out = {}
    try:
        A.analyse(c["repo"], c["path"], c.get("symbol"), c.get("lines"),
                  hook=lambda d, r: pipeline.enrich(d, r, lambda e: out.update(r=e["data"]) if e["type"] == "result" else None))
    except Exception as ex:
        print("FAIL", c["path"], ex); continue
    r = out["r"]; ex = r.get("explanation") or {}
    text = json.dumps(ex).lower()
    ok = any(k.lower() in text for k in c["expect_any"]); hits += ok
    grounded += bool(ex.get("grounded")); ver.append(ex.get("verified_ratio", 0)); risk.append(r["risk"]["prob"])
    print(("HIT " if ok else "MISS"), c["path"], c.get("symbol"), "conf", r["confidence"], "risk", r["risk"]["prob"])
n = max(len(cases), 1)
print(f"\nreason-hit {hits}/{n} | grounded {grounded}/{n} | mean verified {sum(ver)/n:.2f} | mean risk {sum(risk)/n:.2f}")
