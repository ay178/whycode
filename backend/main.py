import json, os, queue, threading, time
from collections import defaultdict
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import analyzer as A, debt as D, guardian as G, pipeline

app = FastAPI(title="WhyCode API")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("FRONTEND_ORIGIN", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])
HITS = defaultdict(list)
LIMIT, WINDOW = 20, 3600  # requests per IP per hour (protects your API key)


def limit(req: Request):
    ip = (req.headers.get("x-forwarded-for") or req.client.host).split(",")[0].strip()
    now = time.time()
    HITS[ip] = [t for t in HITS[ip] if now - t < WINDOW]
    if len(HITS[ip]) >= LIMIT:
        raise HTTPException(429, "Rate limit reached, try again later")
    HITS[ip].append(now)


class AnalyzeReq(BaseModel):
    repo: str
    path: str
    symbol: Optional[str] = None
    lines: Optional[str] = None


class AskReq(BaseModel):
    result: dict
    question: str


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/analyze")
def analyze(body: AnalyzeReq, request: Request):
    limit(request)
    try:
        res = A.analyse(body.repo, body.path, body.symbol, body.lines)
        res["explanation"] = None if res["low_evidence"] else A.explain(res)
        return res
    except A.UserError as e:
        raise HTTPException(400, str(e))


@app.post("/api/ask")
def ask(body: AskReq, request: Request):
    limit(request)
    try:
        return {"answer": A.ask(body.result, body.question)}
    except A.UserError as e:
        raise HTTPException(400, str(e))


@app.post("/api/investigate")
def investigate(body: AnalyzeReq, request: Request):
    limit(request)
    q = queue.Queue()

    def work():
        try:
            q.put({"type": "step", "name": "Cloning repo and tracing history"})
            A.analyse(body.repo, body.path, body.symbol, body.lines, hook=lambda d, r: pipeline.enrich(d, r, q.put))
        except A.UserError as e:
            q.put({"type": "error", "message": str(e)})
        except Exception:
            q.put({"type": "error", "message": "Internal error while investigating"})
        finally:
            q.put(None)

    threading.Thread(target=work, daemon=True).start()

    def gen():
        while (ev := q.get()) is not None:
            yield f"data: {json.dumps(ev)}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class DebtReq(BaseModel):
    repo: str


@app.post("/api/debt")
def debt(body: DebtReq, request: Request):
    limit(request)
    try:
        return {"files": D.scan(body.repo)}
    except A.UserError as e:
        raise HTTPException(400, str(e))


@app.post("/api/github/webhook")
async def webhook(request: Request):
    raw = await request.body()
    if not G.verify(raw, request.headers.get("x-hub-signature-256", "")):
        raise HTTPException(401, "bad signature")
    payload = json.loads(raw)
    if payload.get("action") in ("opened", "synchronize", "reopened") and "pull_request" in payload:
        threading.Thread(target=G.handle, args=(payload,), daemon=True).start()
    return {"ok": True}
