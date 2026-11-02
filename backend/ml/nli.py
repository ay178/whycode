"""Hallucination guard: is a claim entailed by its evidence? NLI cross-encoder if ML_ENABLED=1, else lexical overlap."""
import os, re
_STOP = set("the a an of to and or is in on for with that this it as be by was are from at not".split())
_w = lambda t: {x for x in re.findall(r"[a-z0-9_]+", t.lower()) if x not in _STOP and len(x) > 2}


class NLIGuard:
    def __init__(self):
        self.pipe = None
        if os.getenv("ML_ENABLED") == "1":
            try:
                from transformers import pipeline
                path = os.path.join(os.path.dirname(__file__), "..", "models", "nli")
                self.pipe = pipeline("text-classification", top_k=None,
                                     model=path if os.path.isdir(path) else os.getenv("NLI_MODEL", "cross-encoder/nli-deberta-v3-small"))
            except Exception:
                pass

    def verify(self, claim, evidence):
        if self.pipe and evidence.strip():
            try:
                out = self.pipe({"text": evidence[:1800], "text_pair": claim[:400]}, truncation=True)
                out = out[0] if isinstance(out[0], list) else out
                sc = {o["label"].lower(): o["score"] for o in out}
                lab = max(sc, key=sc.get)
                lab = {"entailment": "supported", "contradiction": "contradicted"}.get(lab, "neutral")
                return {"label": lab, "score": round(sc.get("entailment", 0), 3), "engine": "nli"}
            except Exception:
                pass
        c, e = _w(claim), _w(evidence)
        r = len(c & e) / len(c) if c else 0
        return {"label": "supported" if r >= .5 else "neutral" if r >= .25 else "contradicted" if False else "neutral",
                "score": round(r, 3), "engine": "lexical"}
