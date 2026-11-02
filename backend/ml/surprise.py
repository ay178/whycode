"""Per-line 'surprise' (0..1). Code LM perplexity if ML_ENABLED=1, else a heuristic."""
import bisect, os, re
_H = [(r"\b\d{3,}\b|0x[0-9a-f]+", .3), (r"HACK|XXX|FIXME|TODO|workaround", .5), (r"sleep\(|retry|except\s*:|except Exception|pass$", .35),
      (r"noqa|type:\s*ignore|nosec|eslint-disable", .4), (r"\bglobal\b|\beval\(|\bexec\(", .4)]


class Surprise:
    def __init__(self):
        self.lm = None
        if os.getenv("ML_ENABLED") == "1":
            try:
                from transformers import AutoModelForCausalLM, AutoTokenizer
                p = os.path.join(os.path.dirname(__file__), "..", "models", "surprise")
                name = p if os.path.isdir(p) else os.getenv("SURPRISE_MODEL", "bigcode/tiny_starcoder_py")
                self.tok, self.lm = AutoTokenizer.from_pretrained(name), AutoModelForCausalLM.from_pretrained(name).eval()
            except Exception:
                self.lm = None

    def scores(self, lines):
        if self.lm and lines:
            try:
                import torch
                text = "\n".join(lines)
                enc = self.tok(text, return_offsets_mapping=True, return_tensors="pt", truncation=True, max_length=1024)
                offs = enc.pop("offset_mapping")[0, 1:]
                with torch.no_grad():
                    lg = self.lm(**enc).logits[0, :-1]
                nll = -torch.log_softmax(lg, -1).gather(1, enc["input_ids"][0, 1:, None])[:, 0]
                starts, pos = [], 0
                for l in lines:
                    starts.append(pos); pos += len(l) + 1
                per = [[] for _ in lines]
                for (a, _), v in zip(offs.tolist(), nll.tolist()):
                    per[max(bisect.bisect_right(starts, a) - 1, 0)].append(v)
                m = [sum(x) / len(x) if x else 0 for x in per]
                lo, hi = min(m), max(m)
                return [(v - lo) / (hi - lo or 1) for v in m]
            except Exception:
                pass
        out = []
        for l in lines:
            s = sum(w for rx, w in _H if re.search(rx, l, re.I)) + min(.2, (len(l) - len(l.lstrip())) / 40)
            out.append(min(s, 1.0))
        return out
