// F5: customer-facing restaurant site for sushi, steak and italian: menu from each PDF, a link to the
// PDF itself, and an AI host that answers menu questions through engine_api.py (LangGraph engine, F13).
// ?r=steak|italian picks the restaurant (default sushi). ?debug=1 shows a private panel to switch
// restaurant and engine and see the engine, tokens, cost and timing of each answer.
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { askMenu, AskResult, browserSessionId, debugEnabled, DEFAULT_ENGINE, EngineKey, ENGINES, setDebug } from "./api";
import { AiAvatar, CuisineIcon } from "./art";
import { MenuItem, RESTAURANTS, Restaurant, restaurantFor } from "./restaurants";
import { RichText } from "./RichText";

interface Message {
  role: "guest" | "ai";
  text: string;
  error?: boolean;
  meta?: AskResult;
}

const FILTERS = ["Vegan", "Vegetarian", "Gluten-Free", "Spicy"] as const;
type Filter = (typeof FILTERS)[number];
const HEAT = new Set(["Mild", "Medium", "Spicy"]);
// F5: one icon per dietary/heat/drink tag; drink icons follow the cuisine (sake, whiskey, wine)
const TAG_ICON: Record<string, string> = {
  Vegan: "🌱", Vegetarian: "🥕", "Gluten-Free": "🌾", Pescatarian: "🐟",
  Mild: "🙂", Medium: "🔥", Spicy: "🌶", "Non-Alcoholic": "🧃",
};
const ALCOHOL_ICON: Record<string, string> = { sushi: "🍶", steak: "🥃", italian: "🍷" };
// F5: browser-tab favicon per restaurant, drawn from an emoji so no image files are needed
const FAVICON: Record<string, string> = { sushi: "🍣", steak: "🥩", italian: "🍝" };
const faviconHref = (emoji: string) =>
  `data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">${emoji}</text></svg>`)}`;
const tagIcon = (tag: string, cuisine: string) => (tag === "Alcoholic" ? ALCOHOL_ICON[cuisine] ?? "🍸" : TAG_ICON[tag]);
const LLM_LABEL = "gpt-4o-mini (OpenAI) · text-embedding-3-small"; // F2/F12: fixed in core/llm.py; Azure if only AZURE_OPENAI_API_KEY is set

const money = (n: number) => `$${n.toFixed(2)}`;

function matches(item: MenuItem, filter: Filter | null): boolean {
  if (!filter) return true;
  if (filter === "Vegetarian") return item.tags.includes("Vegetarian") || item.tags.includes("Vegan");
  return item.tags.includes(filter);
}

function greetingFor(r: Restaurant): Message[] {
  return [{ role: "ai", text: r.greeting }];
}

export default function App() {
  const [debug, setDebugState] = useState(debugEnabled);
  // F5: flips debug on/off from either mode and keeps the URL in step, so the page can be bookmarked/shared
  function toggleDebug() {
    const next = !debug;
    setDebug(next);
    setDebugState(next);
    history.replaceState(null, "", debugHref(next));
  }
  function debugHref(on: boolean): string {
    const url = new URL(location.href);
    url.searchParams.set("debug", on ? "1" : "0");
    return `${url.pathname}${url.search}${url.hash}`;
  }
  const [restaurant, setRestaurant] = useState<Restaurant>(() => restaurantFor(new URLSearchParams(location.search).get("r")));
  const [engine, setEngine] = useState<EngineKey>(DEFAULT_ENGINE);
  const [active, setActive] = useState(restaurant.sections[0].title);
  const [filter, setFilter] = useState<Filter | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>(() => greetingFor(restaurant));
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const r = restaurant;
  const info = r.info;
  const sessionId = useMemo(() => browserSessionId(r.cuisine), [r.cuisine]);
  const hoursLines = (info.hours ?? "").split("|").map((s) => s.trim()).filter(Boolean);

  useEffect(() => {
    document.title = info.name;
    let link = document.querySelector<HTMLLinkElement>("link[rel='icon']");
    if (!link) {
      link = document.createElement("link");
      link.rel = "icon";
      document.head.appendChild(link);
    }
    link.type = "image/svg+xml";
    link.href = faviconHref(FAVICON[r.cuisine] ?? "🍽");
  }, [info.name, r.cuisine]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  function switchRestaurant(cuisine: string) {
    const next = restaurantFor(cuisine);
    setRestaurant(next);
    setActive(next.sections[0].title);
    setFilter(null);
    setMessages(greetingFor(next));
    const url = new URL(location.href);
    url.searchParams.set("r", next.cuisine);
    history.replaceState(null, "", url);
  }

  const section = r.sections.find((s) => s.title === active) ?? r.sections[0];
  const items = section.items.filter((i) => matches(i, filter));
  const lastMeta = [...messages].reverse().find((m) => m.meta)?.meta;

  async function ask(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    setChatOpen(true);
    setMessages((m) => [...m, { role: "guest", text: q }]);
    setDraft("");
    setBusy(true);
    try {
      const result = await askMenu(q, sessionId, r.cuisine, engine);
      setMessages((m) => [...m, { role: "ai", text: result.answer || "Sorry, I couldn't find that on our menu.", meta: result }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "ai", text: (e as Error).message || "Something went wrong. Please try again.", error: true }]);
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void ask(draft);
  }

  const { Mark, Hero, Branch } = r;

  return (
    <div className={`site site-${r.cuisine}`} style={r.theme}>
      <header className="nav">
        <a className="brand" href="#top">
          <Mark size={30} />
          <span>{r.short}</span>
        </a>
        <nav>
          <a href="#menu">Menu</a>
          <a href="#visit">Visit</a>
          <a href={r.pdfUrl} target="_blank" rel="noopener">Menu PDF</a>
          <button type="button" className="btn small" onClick={() => setChatOpen(true)}>Ask AI</button>
        </nav>
      </header>

      {debug && (
        <section className="debug" aria-label="Debug panel">
          <b>Debug</b>
          <label>
            Restaurant
            <select value={r.cuisine} onChange={(e) => switchRestaurant(e.target.value)}>
              {RESTAURANTS.map((x) => <option key={x.cuisine} value={x.cuisine}>{x.label} · {x.info.name}</option>)}
            </select>
          </label>
          <label>
            Engine
            <select value={engine} onChange={(e) => setEngine(e.target.value as EngineKey)}>
              {ENGINES.map((x) => <option key={x.key} value={x.key}>{x.label}</option>)}
            </select>
          </label>
          <span className="debug-llm" title="Set in core/llm.py">LLM: {LLM_LABEL}</span>
          <span className="debug-last">
            {lastMeta
              ? <>Last: <code>{lastMeta.engine ?? "router (no engine)"}</code>
                {lastMeta.usage && <> · {lastMeta.usage.total_tokens} tok · ${lastMeta.usage.total_cost_usd.toFixed(5)}</>}
                {lastMeta.trace ? <> · {lastMeta.trace.total_ms} ms server</> : null} · {lastMeta.clientMs} ms total
                {lastMeta.topMatch && <> · top match: <code>{lastMeta.topMatch.slice(0, 60)}</code></>}</>
              : "Ask a question to see engine, tokens, cost and timing."}
          </span>
          <button type="button" className="debug-hide" onClick={toggleDebug}>Hide</button>
          <div className="debug-row">
            <span>Go to:</span>
            {RESTAURANTS.map((x) => (
              <a
                key={x.cuisine}
                href={`?r=${x.cuisine}&debug=1`}
                className={x.cuisine === r.cuisine ? "current" : undefined}
                onClick={(e) => { e.preventDefault(); switchRestaurant(x.cuisine); }}
              >
                {x.label}
              </a>
            ))}
            <span className="debug-help">
              How to: add <code>?debug=1</code> to the URL, or click the hidden link on the line below the allergy note at the very bottom.
              Turn off with “Hide”, the same spot, or <code>?debug=0</code>. Pick <code>?r=sushi|steak|italian</code> for a restaurant.
            </span>
          </div>
        </section>
      )}

      <main id="top">
        <section className="hero">
          <div className="hero-text">
            <p className="eyebrow">{r.place}</p>
            <h1>{info.name}</h1>
            <p className="tagline">{info.tagline}</p>
            <div className="hero-actions">
              <a className="btn" href="#menu">See the menu</a>
              <button type="button" className="btn ghost" onClick={() => { setChatOpen(true); setTimeout(() => inputRef.current?.focus(), 50); }}>
                Ask our AI host
              </button>
            </div>
            <a className="pdf-link" href={r.pdfUrl} target="_blank" rel="noopener">📄 Download the full menu (PDF)</a>
          </div>
          <div className="hero-art">
            {Branch && <Branch className="branch" />}
            <Hero className={Branch ? "board" : "board solo"} />
          </div>
        </section>

        <section className="facts" aria-label="At a glance">
          <div><b>Hours</b>{hoursLines.map((l) => <span key={l}>{l}</span>)}</div>
          <div><b>Find us</b><span>{info.address}</span></div>
          <div><b>Reservations</b><span>{info.reservations}</span></div>
        </section>

        <section id="menu" className="menu">
          <div className="section-head">
            <h2>Our Menu</h2>
            <p>Every dish and price below comes straight from our menu. Tap “Ask AI” on any dish to learn more.</p>
          </div>

          <div className="tabs" role="tablist" aria-label="Menu sections">
            {r.sections.map((s) => (
              <button key={s.title} role="tab" aria-selected={s.title === active} className={s.title === active ? "tab active" : "tab"} onClick={() => setActive(s.title)}>
                <CuisineIcon cuisine={r.cuisine} category={s.title} size={28} />
                <span>{s.title}</span>
              </button>
            ))}
          </div>

          <div className="filters" aria-label="Dietary filters">
            {FILTERS.map((f) => (
              <button key={f} type="button" aria-pressed={filter === f} className={filter === f ? "chip on" : "chip"} onClick={() => setFilter(filter === f ? null : f)}>
                <span aria-hidden="true">{tagIcon(f, r.cuisine)} </span>{f}
              </button>
            ))}
          </div>

          <div className="cards">
            {items.map((item) => (
              <article key={item.name} className="card">
                <div className="card-top">
                  <h3>{item.name}</h3>
                  <span className="price">{money(item.price)}</span>
                </div>
                <p>{item.description}</p>
                <div className="card-foot">
                  <div className="tags">
                    {item.tags.map((t) => (
                      <span key={t} className={`tag ${HEAT.has(t) ? `heat-${t.toLowerCase()}` : t.toLowerCase().replace(/[^a-z]/g, "")}`}>
                        {tagIcon(t, r.cuisine) && <span aria-hidden="true">{tagIcon(t, r.cuisine)} </span>}{t}
                      </span>
                    ))}
                  </div>
                  <button type="button" className="ask-dish" onClick={() => void ask(`Tell me about the ${item.name}.`)}>Ask AI</button>
                </div>
              </article>
            ))}
            {items.length === 0 && <p className="empty">No {filter?.toLowerCase()} dishes in {section.title}. Try another section.</p>}
          </div>
        </section>

        <section id="visit" className="visit">
          <div className="section-head">
            <h2>Plan your visit</h2>
          </div>
          <dl className="visit-grid">
            {([
              ["Address", info.address], ["Reservations", info.reservations], ["Takeout & delivery", info.takeout],
              ["Parking", info.parking], ["Payment", info.payment], ["Dress code & dining rules", info.dress],
              ["Drinks & corkage", info.alcohol],
            ] as [string, string | null][]).filter(([, v]) => v).map(([k, v]) => (
              <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
            ))}
            <div><dt>Hours</dt><dd>{hoursLines.map((l) => <span key={l}>{l}</span>)}</dd></div>
          </dl>
        </section>
      </main>

      <footer className="footer">
        <Mark size={22} />
        <span>{info.name}</span>
        <a href={r.pdfUrl} target="_blank" rel="noopener">Menu (PDF)</a>
        <span className="muted">AI answers come from our menu. Please tell your server about any allergies.</span>
        {/* F5: secret debug link on its own line below - same colour as the footer background, out of the tab
            order. A real link (?debug=1 / ?debug=0) that also toggles in place without a reload. */}
        <a
          className="secret"
          href={debugHref(!debug)}
          onClick={(e) => { e.preventDefault(); toggleDebug(); }}
          tabIndex={-1}
          aria-hidden="true"
        >
          {debug ? "debug off" : "debug on"}
        </a>
      </footer>

      {!chatOpen && (
        <button type="button" className="chat-fab" onClick={() => setChatOpen(true)} aria-label="Ask our AI host">
          <AiAvatar size={30} mark={<Mark size={22} />} /> <span>Ask about the menu</span>
        </button>
      )}

      {chatOpen && (
        <aside className="chat" aria-label="Ask our AI host">
          <div className="chat-head">
            <AiAvatar mark={<Mark size={24} />} />
            <div>
              <b>{r.hostName}</b>
              <span>Answers from our menu</span>
            </div>
            <button type="button" className="close" onClick={() => setChatOpen(false)} aria-label="Close chat">×</button>
          </div>
          <div className="chat-body" aria-live="polite">
            {messages.map((m, i) => (
              <div key={i} className={`msg ${m.role}${m.error ? " error" : ""}`}>
                {m.role === "ai" ? <RichText text={m.text} /> : m.text}
                {debug && m.meta && (
                  <small className="msg-meta">
                    {m.meta.engine ?? "router"}{m.meta.usage ? ` · ${m.meta.usage.total_tokens} tok · $${m.meta.usage.total_cost_usd.toFixed(5)}` : ""} · {m.meta.clientMs} ms
                  </small>
                )}
              </div>
            ))}
            {busy && <div className="msg ai typing" aria-label="Thinking"><span /><span /><span /></div>}
            {messages.length === 1 && !busy && (
              <div className="suggest">
                {r.suggested.map((q) => <button key={q} type="button" onClick={() => void ask(q)}>{q}</button>)}
              </div>
            )}
            <div ref={endRef} />
          </div>
          <form className="chat-input" onSubmit={onSubmit}>
            <input ref={inputRef} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Ask about a dish, price or allergy…" maxLength={500} aria-label="Your question" disabled={busy} />
            <button type="submit" className="btn small" disabled={busy || !draft.trim()}>Send</button>
          </form>
          <p className="chat-note">Powered by our menu and a LangGraph AI agent · please confirm allergies with staff</p>
        </aside>
      )}
    </div>
  );
}
