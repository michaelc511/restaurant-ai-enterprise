// F5: React + TypeScript UI over engine_api.py. Unlike the Gradio/Streamlit UIs it can pick the
// engine per question (F12/F13), and its collection dropdown comes from the active domain pack.
import { useEffect, useState } from "react";
import { ask, ENGINES, getCollections, getSpecials, type EngineKey } from "./api";
import type { AskResponse, CollectionsResponse, SheetRow } from "./types";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const SESSION_ID = `web-react-${Math.random().toString(36).slice(2, 10)}`; // F7: one memory thread per tab

interface Turn {
  question: string;
  response?: AskResponse;
  error?: string;
}

export default function App() {
  const [domain, setDomain] = useState<CollectionsResponse | null>(null);
  const [loadError, setLoadError] = useState("");
  const [collection, setCollection] = useState("");
  const [engine, setEngine] = useState<EngineKey>("plain_rag");
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getCollections()
      .then((data) => {
        setDomain(data);
        setCollection(data.collections[0] ?? "");
      })
      .catch((e: Error) => setLoadError(`${e.message} - is engine_api.py running on port 8000?`));
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const q = question.trim();
    if (!q || busy) return;
    setBusy(true);
    setQuestion("");
    try {
      const response = await ask(collection, q, engine, SESSION_ID);
      setTurns((t) => [...t, { question: q, response }]);
    } catch (err) {
      setTurns((t) => [...t, { question: q, error: (err as Error).message }]);
    } finally {
      setBusy(false);
    }
  }

  if (loadError) return <main className="page"><p className="error">{loadError}</p></main>;
  if (!domain) return <main className="page"><p>Loading…</p></main>;

  const label = domain.label.charAt(0).toUpperCase() + domain.label.slice(1);

  return (
    <main className="page">
      <header>
        <h1>RAG Assistant</h1>
        <span className="pill">domain: {domain.domain}</span>
      </header>

      <div className="controls">
        <label>
          {label}
          <select value={collection} onChange={(e) => setCollection(e.target.value)}>
            {domain.collections.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <label>
          Engine
          <select value={engine} onChange={(e) => setEngine(e.target.value as EngineKey)}>
            {ENGINES.map((en) => <option key={en.key} value={en.key}>{en.label}</option>)}
          </select>
        </label>
      </div>

      <section className="chat">
        {turns.length === 0 && <p className="muted">Ask a question about the {domain.label} documents.</p>}
        {turns.map((turn, i) => <TurnView key={i} turn={turn} />)}
        {busy && <p className="muted">Thinking…</p>}
      </section>

      <form className="ask" onSubmit={submit}>
        <input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Ask a question" disabled={busy} />
        <button type="submit" disabled={busy || !question.trim()}>Ask</button>
      </form>

      {domain.domain === "restaurant" && <Specials />}
    </main>
  );
}

function TurnView({ turn }: { turn: Turn }) {
  const r = turn.response;
  return (
    <div className="turn">
      <p className="q">{turn.question}</p>
      {turn.error && <p className="error">{turn.error}</p>}
      {r && (
        <>
          <p className="a">{r.answer}</p>
          <p className="meta">
            {r.engine ?? "answered before the engine"}
            {r.usage && ` · ${r.usage.total_tokens} tokens · $${r.usage.total_cost_usd.toFixed(5)}`}
            {r.trace && ` · ${Math.round(r.trace.total_ms)} ms`}
          </p>
          {r.top_match && (
            <details>
              <summary>Top source</summary>
              <pre>{r.top_match}</pre>
            </details>
          )}
        </>
      )}
    </div>
  );
}

function Specials() {
  // F8: live rows from the Google Sheet through engine_api.py's /specials (over MCP)
  const [day, setDay] = useState(WEEKDAYS[(new Date().getDay() + 6) % 7]);
  const [rows, setRows] = useState<SheetRow[] | null>(null);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      setRows(await getSpecials(day));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <section className="specials">
      <h2>Daily specials</h2>
      <div className="controls">
        <select value={day} onChange={(e) => setDay(e.target.value)}>
          {WEEKDAYS.map((d) => <option key={d}>{d}</option>)}
        </select>
        <button onClick={load}>Load</button>
      </div>
      {error && <p className="error">{error}</p>}
      {rows && rows.length === 0 && <p className="muted">No active specials.</p>}
      {rows && rows.length > 0 && (
        <ul>
          {rows.map((row, i) => (
            <li key={i}><strong>{row["Dish Name"]}</strong> ({row["Price"]}) — {row["Description"]}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
