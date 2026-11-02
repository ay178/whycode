const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
async function post(path, body) {
  const r = await fetch(BASE + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || "Request failed");
  return data;
}
export const analyze = (b) => post("/api/analyze", b);
export const ask = (result, question) => post("/api/ask", { result, question });

export async function investigate(body, onEvent) {
  const r = await fetch(BASE + "/api/investigate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.detail || "Request failed"); }
  const rd = r.body.getReader(), dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await rd.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const parts = buf.split("\n\n"); buf = parts.pop();
    for (const p of parts) if (p.startsWith("data: ")) onEvent(JSON.parse(p.slice(6)));
  }
}
export const debt = (repo) => post("/api/debt", { repo });
