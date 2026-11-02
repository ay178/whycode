"""Train the change-risk XGBoost model. Splits by REPO (no leakage). Saves backend/models/risk.joblib.
Usage: python train_risk.py risk.csv"""
import os, sys, joblib, pandas as pd
from sklearn.metrics import roc_auc_score, brier_score_loss
from xgboost import XGBClassifier
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from ml.features import NAMES

df = pd.read_csv(sys.argv[1])
repos = sorted(df.repo.unique())
test_repos = repos[-max(1, len(repos) // 5):]
tr, te = df[~df.repo.isin(test_repos)], df[df.repo.isin(test_repos)]
m = XGBClassifier(n_estimators=300, max_depth=4, learning_rate=.05, subsample=.8, colsample_bytree=.8, eval_metric="auc")
m.fit(tr[NAMES], tr.label)
p = m.predict_proba(te[NAMES])[:, 1]
print(f"held-out repos={test_repos}\nAUC={roc_auc_score(te.label, p):.3f}  Brier={brier_score_loss(te.label, p):.3f}")
m.fit(df[NAMES], df.label)  # refit on everything for serving
os.makedirs("../backend/models", exist_ok=True)
joblib.dump(m, "../backend/models/risk.joblib")
print("saved backend/models/risk.joblib")
