"""Fine-tune a code-aware transformer as commit-intent classifier. Saves backend/models/intent.
Usage: python train_intent.py commits.csv [microsoft/codebert-base]   (GPU: free Colab/Kaggle is enough)"""
import sys, pandas as pd, numpy as np
from datasets import Dataset
from sklearn.metrics import f1_score
from transformers import AutoModelForSequenceClassification, AutoTokenizer, Trainer, TrainingArguments

df = pd.read_csv(sys.argv[1]); base = sys.argv[2] if len(sys.argv) > 2 else "microsoft/codebert-base"
labels = sorted(df.label.unique()); l2i = {l: i for i, l in enumerate(labels)}
repos = sorted(df.repo.unique()); test = df[df.repo == repos[-1]]; train = df[df.repo != repos[-1]]
tok = AutoTokenizer.from_pretrained(base)
enc = lambda d: Dataset.from_dict({"text": d.text.tolist(), "label": [l2i[x] for x in d.label]}).map(
    lambda b: tok(b["text"], truncation=True, padding="max_length", max_length=128), batched=True)
model = AutoModelForSequenceClassification.from_pretrained(base, num_labels=len(labels), id2label=dict(enumerate(labels)), label2id=l2i)
f1 = lambda p: {"macro_f1": f1_score(p.label_ids, np.argmax(p.predictions, -1), average="macro")}
t = Trainer(model=model, args=TrainingArguments("out_intent", num_train_epochs=3, per_device_train_batch_size=32,
            learning_rate=3e-5, eval_strategy="epoch", save_strategy="no", report_to=[]),
            train_dataset=enc(train), eval_dataset=enc(test), compute_metrics=f1)
t.train(); print(t.evaluate())
model.save_pretrained("../backend/models/intent"); tok.save_pretrained("../backend/models/intent")
