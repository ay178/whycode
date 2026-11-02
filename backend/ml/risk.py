"""Change-risk model. Uses models/risk.joblib (XGBoost) if present; else a transparent heuristic."""
import math, os
from .features import NAMES

W = {"n_fix": .55, "n_workaround": .6, "n_commits": .25, "n_authors": .2, "fix_ratio": .8,
     "n_markers": .3, "has_test_ref": -.7, "max_indent": .12, "days_since_change": -.15}
_s = lambda k, v: math.log1p((v / 30) if k in ("age_days", "days_since_change") else v)


class RiskModel:
    def __init__(self):
        self.model = None
        p = os.path.join(os.path.dirname(__file__), "..", "models", "risk.joblib")
        if os.path.exists(p):
            try:
                import joblib
                self.model = joblib.load(p)
            except Exception:
                pass

    def predict(self, f):
        if self.model is not None:
            try:  # native XGBoost contributions = SHAP-style attributions, no extra dependency
                import numpy as np, xgboost as xgb
                X = np.array([[f[k] for k in NAMES]])
                prob = float(self.model.predict_proba(X)[0][1])
                c = self.model.get_booster().predict(xgb.DMatrix(X, feature_names=NAMES), pred_contribs=True)[0][:-1]
                return self._pack(prob, [{"name": k, "impact": float(v), "value": round(f[k], 2)} for k, v in zip(NAMES, c)], "xgboost")
            except Exception:
                pass
        z = -1.4 + sum(W[k] * _s(k, f[k]) for k in W)
        return self._pack(1 / (1 + math.exp(-z)),
                          [{"name": k, "impact": W[k] * _s(k, f[k]), "value": round(f[k], 2)} for k in W], "heuristic")

    @staticmethod
    def _pack(p, fac, src):
        fac.sort(key=lambda x: -abs(x["impact"]))
        return {"prob": round(p, 3), "factors": fac[:5], "source": src}
