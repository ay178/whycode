import { useEffect, useRef, useState } from "react";
import { investigate, ask, debt } from "./api.js";
import { I } from "./icons.jsx";

const DEMO = { repo: "https://github.com/psf/requests", path: "src/requests/utils.py", symbol: "should_bypass_proxies", lines: "" };
const STEPS = ["Cloning repo", "Reading git blame", "Tracing history", "Asking AI"];
const CONF = { high: ["High confidence", "ok"], medium: ["Medium confidence", "warn"], low: ["Low confidence", "bad"] };
const initials = (n) => (n || "?").split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
const slug = (u) => u.replace(/^https:\/\/github\.com\//, "").replace(/\.git$/, "").replace(/\/$/, "");

function RiskPanel({ risk }) {
  const p = Math.round(risk.prob * 100), lvl = p >= 66 ? "bad" : p >= 33 ? "warn" : "ok";
  const mx = Math.max(...risk.factors.map((x) => Math.abs(x.impact)), 0.01);
  return (
    <section className="card">
      <div className="rp-h"><div><span className="over2">CHANGE RISK</span><div className={"pct " + lvl}>{p}%</div></div>
        <p className="mut sm">Chance that editing or deleting this code reintroduces a bug. Model: {risk.source}{risk.source === "heuristic" ? " (train the XGBoost model to replace it)" : ""}.</p></div>
      <div className="bar"><i className={lvl} style={{ width: p + "%" }} /></div>
      {risk.factors.map((x) => (
        <div key={x.name} className="fac"><span className="mono">{x.name}={x.value}</span>
          <div className="bar sm2"><i className={x.impact >= 0 ? "bad" : "ok"} style={{ width: (Math.abs(x.impact) / mx) * 100 + "%" }} /></div>
          <span className="mut sm">{x.impact >= 0 ? "raises" : "lowers"}</span></div>))}
    </section>
  );
}

function Graph({ res }) {
  const cs = res.commits.slice(0, 10), W = 760, H = 300, cx = W / 2, cy = H / 2;
  const nodes = cs.map((c, i) => { const a = (i / cs.length) * 2 * Math.PI - Math.PI / 2; return { c, x: cx + 250 * Math.cos(a), y: cy + 100 * Math.sin(a) }; });
  return (
    <section className="card"><h2 className="ftitle"><I n="commit" s={18} />Intent graph</h2>
      <svg viewBox={`0 0 ${W} ${H}`} className="graph" role="img" aria-label="Graph linking the code to its commits and tickets">
        {nodes.map(({ c, x, y }) => <line key={"l" + c.sha} x1={cx} y1={cy} x2={x} y2={y} stroke="var(--bd)" />)}
        <circle cx={cx} cy={cy} r="30" fill="var(--wbg)" stroke="var(--acc)" />
        <text x={cx} y={cy + 4} textAnchor="middle" fontSize="11" fill="var(--acc)">code</text>
        {nodes.map(({ c, x, y }) => (
          <g key={c.sha}><circle cx={x} cy={y} r="15" fill="var(--card)" stroke={c.tags.length ? "var(--acc)" : "var(--bd)"} />
            {c.refs[0] && <text x={x} y={y + 3} textAnchor="middle" fontSize="9" fill="var(--acc)">{c.refs[0]}</text>}
            <text x={x} y={y + 30} textAnchor="middle" fontSize="10" fill="var(--mut)" fontFamily="JetBrains Mono">{c.sha.slice(0, 7)}</text></g>))}
      </svg></section>
  );
}

const Logo = ({ big }) => <span className={"logo" + (big ? " big" : "")}>Why<b>Code</b><i>_</i></span>;
const Chip = ({ ref_, mono, children }) => <span className={"chip" + (ref_ ? " ref" : "") + (mono ? " mono" : "")}>{children}</span>;
const Badge = ({ level }) => { const [t, k] = CONF[level] || CONF.low; return <span className={"badge " + k}><i />{t}</span>; };
const Btn = ({ kind = "ghost", icon, spin, children, ...r }) => (
  <button className={"btn " + kind} {...r}>{icon && <I n={icon} spin={spin} />}{children}</button>
);
const Field = ({ label, hint, ...r }) => (
  <label className="field"><span>{label}</span><input {...r} />{hint && <small>{hint}</small>}</label>
);

function Shell({ children }) {
  return (
    <div className="shell">
      <header className="nav"><Logo />
        <div className="navctx"><span className="hide-m">Code history, explained.</span><span className="vis"><I n="github" s={15} />Public repositories</span></div>
      </header>
      <main className="main">{children}</main>
      <footer className="foot"><span>History, not guesses.</span><span>WhyCode / beta</span></footer>
    </div>
  );
}

function SearchForm({ f, set, onRun, onDemo, onDebt, busy, title }) {
  return (
    <form className="card form" onSubmit={onRun}>
      <h2 className="ftitle">{title || <><I n="terminal" s={18} />Start with a piece of code</>}</h2>
      <Field label="GitHub repo URL" placeholder="https://github.com/owner/repo" value={f.repo} onChange={set("repo")} required />
      <Field label="File path" placeholder="src/utils.py" value={f.path} onChange={set("path")} required />
      <Field label="Function / class name" placeholder="e.g. gateway_amount" value={f.symbol} onChange={set("symbol")} />
      <div className="or"><hr /><span>or</span><hr /></div>
      <Field label="Line range" placeholder="e.g. 40-75" value={f.lines} onChange={set("lines")} />
      <div className="row">
        <Btn kind="primary" icon={busy ? "loader" : "arrow"} spin={busy} disabled={busy}>{busy ? "Tracing history…" : "Why is it like this?"}</Btn>
        {onDemo && <Btn type="button" icon="flask" onClick={onDemo}>Fill demo</Btn>}
        {onDebt && <Btn type="button" icon="scan" onClick={onDebt}>Knowledge debt map</Btn>}
      </div>
      <p className="note">Public repositories only. Read-only access. Your code stays yours.</p>
    </form>
  );
}

export default function App() {
  const [f, setF] = useState({ repo: "", path: "", symbol: "", lines: "" });
  const [view, setView] = useState("landing");
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const [step, setStep] = useState(0);
  const [demo, setDemo] = useState(false);
  const [chat, setChat] = useState([]);
  const [q, setQ] = useState("");
  const [asking, setAsking] = useState(false);
  const [modal, setModal] = useState(false);
  const [copied, setCopied] = useState(false);
  const [events, setEvents] = useState([]);
  const [heat, setHeat] = useState(false);
  const [debtData, setDebtData] = useState(null);
  const tl = useRef(null);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  useEffect(() => {
    if (view !== "loading") return;
    setStep(0);
    const t = setInterval(() => setStep((s) => Math.min(s + 1, 3)), 2500);
    return () => clearInterval(t);
  }, [view]);

  async function run(e) {
    e?.preventDefault();
    setView("loading"); setErr(""); setChat([]); setRes(null); setEvents([]); setHeat(false);
    try {
      let got = null;
      await investigate({ repo: f.repo, path: f.path, symbol: f.symbol || null, lines: f.lines || null }, (ev) => {
        if (ev.type === "result") got = ev.data;
        else if (ev.type === "error") throw new Error(ev.message);
        else setEvents((x) => [...x, ev]);
      });
      if (!got) throw new Error("No result received");
      setRes(got); setView(got.low_evidence ? "low" : "results");
    } catch (x) { setErr(x.message); setView("error"); }
  }
  async function runDebt() {
    if (!f.repo) { setErr("Enter a GitHub repo URL first"); setView("error"); return; }
    setView("loading"); setEvents([{ type: "step", name: "Scanning repository history for knowledge debt" }]);
    try { setDebtData((await debt(f.repo)).files); setView("debt"); } catch (x) { setErr(x.message); setView("error"); }
  }
  const reset = () => { setView("landing"); setDemo(false); };

  async function send(text) {
    if (!text.trim() || asking) return;
    setAsking(true); setQ("");
    setChat((c) => [...c, { role: "you", text }]);
    try { const { answer } = await ask(res, text); setChat((c) => [...c, { role: "ai", text: answer }]); }
    catch (x) { setChat((c) => [...c, { role: "ai", text: "Error: " + x.message }]); }
    setAsking(false);
  }
  const citations = (text) => (res?.commits || []).filter((c) => text.includes(c.sha)).map((c) => c.sha);
  const riskCheck = () => (res.risky ? setModal(true) : send("I want to delete or simplify this code. What could break?"));
  const key = res?.commits.find((c) => c.tags.some((t) => ["bug fix", "workaround", "security"].includes(t))) || res?.commits[0];

  if (view === "landing") return (
    <Shell>
      <section className="intro">
        <span className="over"><i />UNDERSTAND BEFORE YOU CHANGE</span>
        <Logo big />
        <p className="tag">Ask any code why it is the way it is, answered from git history, not guesses.</p>
      </section>
      <SearchForm f={f} set={set} onRun={run} onDemo={() => { setF(DEMO); setDemo(true); }} onDebt={runDebt} />
      <section className="feats">
        {[["commit", "Evidence-based (commits, not guesses)", "Trace every answer back to the change that caused it."],
          ["shield", "Chesterton’s Fence warnings", "Understand the reason before removing the code."],
          ["scan", "Risk check before you delete", "See what could break before your next cleanup."]].map(([i, t, d]) => (
          <div key={t} className="card feat"><I n={i} s={19} /><h3>{t}</h3><p>{d}</p></div>))}
      </section>
    </Shell>
  );

  if (view === "loading") return (
    <Shell>
      <div className="top"><button className="link" onClick={reset}>← New search</button></div>
      <div className="src"><span className="mono big">{f.path}{f.symbol ? ` · ${f.symbol}` : f.lines ? `:${f.lines}` : ""}</span></div>
      <section className="card steps">
        <h2 className="ftitle">Investigation board · {slug(f.repo)}</h2>
        {events.length === 0 && <div className="step act"><span className="dot"><I n="loader" s={14} spin /></span>Cloning repo</div>}
        {events.map((ev, i) => (
          <div key={i} className={"step " + (i === events.length - 1 ? "act" : "done")}>
            <span className="dot">{i === events.length - 1 ? <I n="loader" s={14} spin /> : <I n="check" s={12} />}</span>
            {ev.type === "step" && ev.name}
            {ev.type === "tool" && <span className="mono">{ev.name}({Object.values(ev.input || {}).join(", ").slice(0, 60)})</span>}
            {ev.type === "tool_result" && <span className="mut sm">{ev.summary}</span>}
          </div>))}
      </section>
      <section className="card commit"><div className="meta"><span className="sha">a31f8c2</span><span>…</span></div>
        <div className="sk h18" /><div className="sk h40" /></section>
      <div className="code"><div className="chead"><span>{f.path}</span></div>
        {[0, 1, 2, 3, 4, 5].map((i) => <div key={i} className="cl"><span>{i + 1}</span><div className="sk h16" /></div>)}</div>
    </Shell>
  );

  if (view === "debt") return (
    <Shell>
      <div className="top"><button className="link" onClick={reset}>← New search</button></div>
      <h1 className="h1">Knowledge debt map</h1>
      <p className="mut">Files whose reasons are most likely forgotten: stale, thin commit messages, single author. Red means ask someone before changing it.</p>
      <div className="tiles">{debtData.map((x) => (
        <button key={x.path} className="card tile2" style={{ borderColor: `rgba(248,81,73,${0.2 + x.debt})` }}
          onClick={() => { setF({ ...f, path: x.path, symbol: "", lines: "" }); reset(); }}>
          <span className="mono">{x.path}</span><span className="mut sm">{x.commits} commits · {x.authors} author(s)</span>
          <div className="bar"><i className="bad" style={{ width: Math.round(x.debt * 100) + "%" }} /></div></button>))}</div>
    </Shell>
  );

  if (view === "error") return (
    <Shell>
      <div className="top"><button className="link" onClick={reset}>← New search</button></div>
      <h1 className="h1">A detour, not a dead end.</h1>
      <p className="mut">We couldn’t analyse that selection. Your search is saved below.</p>
      <section className="errcard">
        <div className="row top"><I n="alert" s={22} /><p className="emsg">{err}</p></div>
        <p className="mut sm">Check that the URL opens on GitHub without signing in. The repository must be public and available to clone.</p>
        <Btn kind="primary" icon="retry" onClick={run}>Retry</Btn>
      </section>
      <SearchForm f={f} set={set} onRun={run} title="Your search" />
      <p className="note">No code was changed. WhyCode only reads public git history.</p>
    </Shell>
  );

  const [a, b] = res.range;
  const head = (
    <>
      <div className="top"><button className="link" onClick={reset}>← New search</button>
        {demo && <span className="demo"><I n="flask" s={13} />Demo selection · live history</span>}</div>
      <p className="repo">{slug(res.repo)}</p>
      <div className="src"><span className="mono big">{res.path}:{a}-{b}</span><Badge level={res.confidence} /></div>
    </>
  );

  if (view === "low") return (
    <Shell>{head}
      <section className="card empty">
        <div className="motif"><div className="tile"><span>{"{ }"}</span><u /><u /></div><I n="search" s={58} /></div>
        <p className="big2">No solid evidence found for why this code exists. Ask the original author: {res.author}.</p>
        <p className="mut sm">The history contains the implementation, but no useful commit message, linked issue, or author comment explaining the decision. We won’t fill in the gaps.</p>
      </section>
      <section className="card author">
        <div className="row"><span className="av l">{initials(res.author)}</span><div><b>{res.author}</b><div className="mut sm">original author</div></div></div>
        <div className="sq"><span className="over2">SUGGESTED QUESTION</span><p>“{res.suggested_question}”</p></div>
        <Btn icon="copy" onClick={() => { navigator.clipboard?.writeText(res.suggested_question); setCopied(true); }}>{copied ? "Copied" : "Copy question"}</Btn>
      </section>
      <div><Btn icon="search" onClick={reset}>Try a different selection</Btn></div>
    </Shell>
  );

  const ex = res.explanation || {};
  return (
    <Shell>{head}
      <div className="chips">{Object.entries(res.reasons).map(([k, v]) => <Chip key={k}>{k} · {v}</Chip>)}</div>
      {res.risky && <div className="warn"><I n="shield" s={20} /><p>Bug-fix / workaround history. Odd-looking logic here is probably deliberate. Check the commits before cleaning it up.</p></div>}

      {res.risk && <RiskPanel risk={res.risk} />}
      {res.proof && <section className="card"><h2 className="ftitle"><I n="shieldCheck" s={18} />Counterfactual proof</h2>
        <p className="mut">{{ broke: "Deleting these lines made the test-suite fail:", no_effect: "Deleting these lines did not break any test (the logic may be untested).", disabled: "Proof is disabled on this server.", baseline_failing: res.proof.note, error: res.proof.note }[res.proof.status]}</p>
        {res.proof.output && <pre className="mono sm proofout">{res.proof.output}</pre>}</section>}
      <section className="card ai">
        <div className="aih"><I n="sparkles" s={18} /><b>AI explanation</b><span className={"ground " + (ex.grounded ? "ok" : "")}>{ex.grounded ? "Grounded" : "Partial"}{ex.verified_ratio != null && ` · ${Math.round(ex.verified_ratio * 100)}% verified`}</span></div>
        <p className="vs">{ex.verdict_summary}</p>
        {ex.verdict_detail && <p className="mut">{ex.verdict_detail}</p>}
        {ex.key_reasons?.length > 0 && <>
          <span className="over2">KEY REASONS</span>
          {ex.key_reasons.map((r, i) => (
            <div key={i} className="reason"><b>{r.reason}</b><p className="mut sm">{r.evidence}</p>
              <div className="chips">{r.verdict && <Chip>{r.verdict.label === "supported" ? "verified" : r.verdict.label === "contradicted" ? "contradicted" : "unverified"} · {Math.round(r.verdict.score * 100)}%</Chip>}{r.shas.map((s) => <Chip key={s} ref_ mono>{s}</Chip>)}{r.refs.map((x) => <Chip key={x} ref_>{x}</Chip>)}</div></div>))}
        </>}
        <div className="risk"><h3><I n="triangle" />What could break</h3><p className="mut">{ex.what_could_break}</p></div>
      </section>

      <h2 className="h2">Author notes and code</h2>
      {res.comments.map((c) => (
        <div key={c.line} className="note-c"><i /><div><div className="mono">{c.text}</div><div className="mut sm mono">Line {c.line} in {res.path}</div></div></div>))}
      <div className="code">
        <div className="chead"><span>{res.path}</span><button className="link" onClick={() => setHeat(!heat)}>{heat ? "Hide" : "Show"} surprise heatmap</button></div>
        {res.excerpt.map((l) => <div key={l.n} className={"cl" + (l.hl ? " hl" : "")} style={heat && !l.hl ? { background: `rgba(248,81,73,${(l.s || 0) * 0.4})` } : undefined}><span>{l.n}</span><code>{l.text || " "}</code></div>)}
        <div className="cfoot">Lines {a}–{a + res.excerpt.length - 1} · excerpt of {a}–{b}</div>
      </div>

      <div className="th" ref={tl}><div><h2 className="h2">History timeline</h2><p className="mut sm">{res.commits.length} commit(s) touched this code, newest first.</p></div><I n="pr" s={18} /></div>
      {res.commits.length === 0 && <p className="mut">No history found for this range.</p>}
      <div className="tlist">{res.commits.map((c) => (
        <div key={c.sha} className="ev"><div className="rail"><i /></div>
          <article className="card commit" tabIndex={0}>
            <div className="meta"><span className="sha">{c.sha}</span><span>{c.date}</span></div>
            <b>{c.subject}</b>{c.body && <p className="mut sm">{c.body}</p>}
            <div className="chips"><span className="auth"><span className="av">{initials(c.author)}</span>{c.author}</span>
              {c.tags.map((t) => <Chip key={t}>{t}</Chip>)}{c.refs.map((x) => <Chip key={x} ref_>{x}</Chip>)}</div>
          </article></div>))}</div>
      <p className="note">Showing up to 30 commits. Nothing before the first commit in this range.</p>

      <Graph res={res} />

      <h2 className="h2">Ask follow-ups / risk check</h2>
      <div className="row wrap"><Btn icon="shieldCheck" onClick={riskCheck} disabled={asking}>Risk check: if I delete this</Btn>
        <Btn icon="users" onClick={() => send("Who should I ask about this, and what should I ask them?")} disabled={asking}>Who to ask?</Btn></div>
      {chat.map((m, i) => m.role === "you"
        ? <div key={i} className="bub you"><span>YOU</span><p>{m.text}</p></div>
        : <div key={i} className="bub"><span>WHYCODE</span><p>{m.text}</p><div className="chips">{citations(m.text).map((s) => <Chip key={s} ref_ mono>{s}</Chip>)}</div></div>)}
      {asking && <div className="bub"><span>WHYCODE</span><div className="sk h16 w27" /></div>}
      <div className="composer"><input placeholder="Ask anything about this code’s history…" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send(q)} />
        <Btn kind="primary" onClick={() => send(q)} disabled={asking}>Ask</Btn></div>
      <p className="note">Answers use only the commits and comments above. If the evidence is missing, WhyCode will say so.</p>

      {modal && key && (
        <div className="scrim" onClick={() => setModal(false)}>
          <div className="modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
            <div className="mt"><span className="sym"><I n="shield" s={24} /></span><span className="over2">FENCE GUARD</span></div>
            <h2>This code was added to fix {key.refs[0] ? `incident ${key.refs[0]}` : `“${key.subject}”`}.</h2>
            <p className="mut">Removing it may bring the bug back. Review the history before you delete.</p>
            <div className="chips"><Chip ref_ mono>{key.sha}</Chip><Chip>{key.date}</Chip>{key.refs.map((x) => <Chip key={x} ref_>{x}</Chip>)}</div>
            <div className="row wrap"><Btn kind="primary" icon="commit" onClick={() => { setModal(false); tl.current?.scrollIntoView({ behavior: "smooth" }); }}>Show history</Btn>
              <Btn onClick={() => { setModal(false); send("I want to delete or simplify this code anyway. What could break?"); }}>Delete anyway</Btn></div>
            <p className="note">Last changed by {key.author} on {key.date}.</p>
          </div>
        </div>)}
    </Shell>
  );
}
