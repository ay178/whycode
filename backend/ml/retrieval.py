"""Hybrid retrieval: BM25 (+ embeddings) then cross-encoder rerank. Models load only if ML_ENABLED=1."""
import math, os, re
from collections import Counter
_tok = lambda t: re.findall(r"[a-z0-9_]+", t.lower())
_cache = {}


def _model(key, factory):
    if key not in _cache:
        try:
            _cache[key] = factory() if os.getenv("ML_ENABLED") == "1" else None
        except Exception:
            _cache[key] = None
    return _cache[key]


def _embedder():
    from sentence_transformers import SentenceTransformer
    p = os.path.join(os.path.dirname(__file__), "..", "models", "embedder")
    return SentenceTransformer(p if os.path.isdir(p) else os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5"))


def _reranker():
    from sentence_transformers import CrossEncoder
    p = os.path.join(os.path.dirname(__file__), "..", "models", "reranker")
    return CrossEncoder(p if os.path.isdir(p) else os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"))


class Retriever:
    def __init__(self, docs):
        self.docs, self.tok = docs, [_tok(d["text"]) for d in docs]
        N = len(docs)
        df = Counter(t for ts in self.tok for t in set(ts))
        self.idf = {t: math.log(1 + (N - n + .5) / (n + .5)) for t, n in df.items()}
        self.avg = sum(map(len, self.tok)) / max(N, 1)
        self.m, self.emb = _model("emb", _embedder), None
        if self.m and docs:
            self.emb = self.m.encode([d["text"] for d in docs], normalize_embeddings=True)

    def search(self, q, k=5):
        qt, sc = _tok(q), []
        for ts in self.tok:
            tf, s = Counter(ts), 0.0
            for t in qt:
                if t in tf:
                    s += self.idf[t] * tf[t] * 2.2 / (tf[t] + 1.2 * (.25 + .75 * len(ts) / (self.avg or 1)))
            sc.append(s)
        if self.emb is not None:
            sims = self.emb @ self.m.encode([q], normalize_embeddings=True)[0]
            mx = max(sc) or 1
            sc = [.5 * a / mx + .5 * float(b) for a, b in zip(sc, sims)]
        idx = sorted(range(len(sc)), key=lambda i: -sc[i])[:max(k * 4, k)]
        ce = _model("ce", _reranker)
        if ce and idx:
            rs = ce.predict([(q, self.docs[i]["text"]) for i in idx])
            idx = [i for _, i in sorted(zip(rs, idx), key=lambda x: -x[0])]
        return [{**self.docs[i], "score": round(float(sc[i]), 3)} for i in idx[:k] if sc[i] > 0]
