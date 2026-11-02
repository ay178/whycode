"""OPTIONAL: fine-tune the hallucination guard on YOUR domain. The pretrained default already works without this.
CSV columns: premise (evidence text), hypothesis (claim), label in {entailment, neutral, contradiction}.
Build it by taking WhyCode explanations + their cited commits and labelling ~500 claims by hand.
Usage: python train_nli.py nli.csv"""
import sys, pandas as pd
from datasets import Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer, Trainer, TrainingArguments
base = "cross-encoder/nli-deberta-v3-small"
df = pd.read_csv(sys.argv[1]); tok = AutoTokenizer.from_pretrained(base)
model = AutoModelForSequenceClassification.from_pretrained(base)
l2i = {v.lower(): int(k) for k, v in model.config.id2label.items()}
ds = Dataset.from_dict({"p": df.premise.tolist(), "h": df.hypothesis.tolist(), "label": [l2i[x] for x in df.label]}).map(
    lambda b: tok(b["p"], b["h"], truncation=True, padding="max_length", max_length=256), batched=True)
Trainer(model=model, args=TrainingArguments("out_nli", num_train_epochs=3, per_device_train_batch_size=16, learning_rate=2e-5,
        save_strategy="no", report_to=[]), train_dataset=ds).train()
model.save_pretrained("../backend/models/nli"); tok.save_pretrained("../backend/models/nli")
