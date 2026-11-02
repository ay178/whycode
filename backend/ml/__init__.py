import math, os
from .risk import RiskModel
from .nli import NLIGuard
from .surprise import Surprise
from .intent import Intent
from .retrieval import Retriever

RISK, NLI, SURPRISE, INTENT = RiskModel(), NLIGuard(), Surprise(), Intent()
_cal = None
_p = os.path.join(os.path.dirname(__file__), "..", "models", "calibrator.joblib")
if os.path.exists(_p):
    try:
        import joblib
        _cal = joblib.load(_p)
    except Exception:
        pass


def calibrate(res, support):
    """Confidence from evidence (bodies, tickets, comments, NLI support, history depth). Swap in models/calibrator.joblib."""
    bodies = sum(1 for c in res["commits"] if c["body"])
    refs = len({r for c in res["commits"] for r in c["refs"]})
    x = [min(bodies, 3), min(refs, 2), min(len(res["comments"]), 2), support, int(len(res["commits"]) >= 2)]
    p = None
    if _cal is not None:
        try:
            p = float(_cal.predict_proba([x])[0][1])
        except Exception:
            pass
    if p is None:
        p = 1 / (1 + math.exp(-(-1.5 + .8 * x[0] + .5 * x[1] + .6 * x[2] + 1.2 * x[3] + .4 * x[4])))
    return round(p, 3), "high" if p >= .7 else "medium" if p >= .4 else "low"
