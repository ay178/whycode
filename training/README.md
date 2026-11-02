# Training the WhyCode models (all optional: the app runs on heuristics without them)
| Model | Script | Output (put in backend/models/) | Metric |
|---|---|---|---|
| Change-risk (XGBoost, SZZ-lite labels) | build_risk_dataset.py, train_risk.py | risk.joblib | held-out-repo AUC, Brier |
| Commit intent (CodeBERT fine-tune) | collect_commits.py, train_intent.py | intent/ | macro-F1 vs regex baseline |
| Hallucination guard (NLI) | works pretrained; train_nli.py optional | nli/ | accuracy on hand-labelled claims |
| Embedder / reranker / surprise LM | pretrained defaults via env vars | embedder/, reranker/, surprise/ (optional) | benchmark hit-rate |
Pipeline: `python build_risk_dataset.py repos.txt risk.csv && python train_risk.py risk.csv` (about 5-10 repos, CPU is fine).
Intent/NLI need a GPU (free Colab/Kaggle). Then run eval/benchmark.py with ML_ENABLED=0 and 1 and put the table in your pitch.
Serving: set ML_ENABLED=1 and build the backend with `--build-arg INSTALL_ML=1` on a host with >=2GB RAM (not Render free).
