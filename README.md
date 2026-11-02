# WhyCode: code history, explained
Public GitHub repo + file + function -> evidence-based AI explanation (Claude), timeline, Fence Guard warning, follow-up chat.
UI follows the Figma file (tokens: bg #0D1117, card #161B22, accent #F0B429, Inter + JetBrains Mono).

## Run locally
Backend:  `cd backend && pip install -r requirements.txt && export ANTHROPIC_API_KEY=sk-ant-... && uvicorn main:app --reload` (needs git)
Frontend: `cd frontend && cp .env.example .env && npm install && npm run dev`

## Deploy
1. Push to GitHub.
2. Render: New > Web Service > Root Directory `backend` > Runtime Docker. Env: `ANTHROPIC_API_KEY`, `FRONTEND_ORIGIN` (Vercel URL, set after step 3).
3. Vercel: Root Directory `frontend` (Vite). Env: `VITE_API_URL` = Render URL (no trailing slash).
4. Set `FRONTEND_ORIGIN` on Render to the Vercel URL and redeploy.

## API shape (`POST /api/analyze`)
`low_evidence`, `confidence`, `risky`, `reasons`, `excerpt[{n,text,hl}]`, `comments`, `commits`, `author`, `suggested_question`,
`explanation{verdict_summary, verdict_detail, key_reasons[{reason,evidence,shas,refs}], what_could_break, grounded}` (null when low evidence: no AI call is made).

## v2: what's new
- `/api/investigate` (SSE): live **investigation board**. Claude tool-use agent (search_evidence, read_commit, git_grep, run_counterfactual) with prompt caching.
- **ML layer** (`backend/ml/`): risk model (XGBoost + attributions), hybrid retrieval + cross-encoder rerank, NLI hallucination guard, code-LM surprise heatmap, intent tagger, calibrated confidence. Each falls back to a heuristic until its weights exist in `backend/models/`. See `training/README.md`.
- **Counterfactual proof** (`proof.py`): delete lines, run tests. OFF by default; enable only in an isolated sandbox.
- **PR Guardian** (`guardian.py`, `/api/github/webhook`): set GITHUB_TOKEN + GITHUB_WEBHOOK_SECRET, add a `pull_request` webhook. Beta, untested against live GitHub.
- **Knowledge debt map** (`/api/debt`), intent graph, `eval/benchmark.py`.
