"""Commit intent tagger. Fine-tuned model in models/intent if ML_ENABLED=1, else regex baseline."""
import os, re
SIGNALS = {
    "bug fix": r"\b(fix(es|ed)?|bug|hotfix|regression|crash|patch)\b",
    "workaround": r"\b(workaround|hack|temporary|temp|legacy|compat\w*|backward)\b",
    "performance": r"\b(perf\w*|optimi[sz]e\w*|speed|faster|cache|latency)\b",
    "security": r"\b(security|cve|vuln\w*|sanitiz\w*|xss|csrf|auth\w*)\b",
    "revert": r"\b(revert\w*|rollback)\b",
    "refactor": r"\b(refactor\w*|cleanup|clean up|rename\w*|restructure)\b",
    "feature": r"\b(add(s|ed)?|feat\w*|implement\w*|introduce\w*|support)\b",
    "requirement": r"\b(requirement|spec|compliance|regulat\w*|policy|customer|client)\b",
}


class Intent:
    def __init__(self):
        self.pipe = None
        p = os.path.join(os.path.dirname(__file__), "..", "models", "intent")
        if os.getenv("ML_ENABLED") == "1" and os.path.isdir(p):
            try:
                from transformers import pipeline
                self.pipe = pipeline("text-classification", model=p, top_k=3)
            except Exception:
                pass

    def tags(self, text):
        if self.pipe:
            try:
                out = self.pipe(text[:1000], truncation=True)
                out = out[0] if isinstance(out[0], list) else out
                return [o["label"] for o in out if o["score"] >= .35 and o["label"] != "other"]
            except Exception:
                pass
        t = text.lower()
        return [k for k, rx in SIGNALS.items() if re.search(rx, t)]
