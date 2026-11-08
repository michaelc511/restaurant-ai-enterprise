// F5: the customer site's one call: ask engine_api.py about a restaurant's menu. Customers always get
// the LangGraph engine (F13); the hidden debug panel (?debug=1) can switch engine and restaurant.
export const ENGINES = [ // F12/F13: same keys and labels as web-react and engine_api.py's CLI menu
  { key: "plain_rag", label: "Plain RAG" },
  { key: "langgraph", label: "LangGraph" },
  { key: "orchestrator", label: "Agentic RAG LG" },
] as const;
export type EngineKey = (typeof ENGINES)[number]["key"];
export const DEFAULT_ENGINE: EngineKey = "langgraph";

export interface AskResult {
  answer: string;
  engine?: string;
  topMatch?: string;
  usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number; total_cost_usd: number }; // F6
  trace?: { retriever_ms: number; llm_ms: number; total_ms: number; errors: number; calls: number }; // F9
  clientMs: number;
}

export async function askMenu(question: string, sessionId: string, cuisine: string, engine: EngineKey): Promise<AskResult> {
  const started = performance.now();
  const resp = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cuisine, question, engine, session_id: sessionId }),
  });
  if (!resp.ok) {
    let detail = "";
    try {
      detail = ((await resp.json()) as { error?: string }).error ?? ""; // F21: 429 carries the limit message
    } catch {
      // not JSON
    }
    throw new Error(detail || (resp.status === 429 ? "We're busy right now. Please try again in a minute." : `Server error (${resp.status}).`));
  }
  const data = (await resp.json()) as {
    answer?: string; engine?: string; error?: string; top_match?: string; usage?: AskResult["usage"] | string; trace?: AskResult["trace"];
  };
  if (data.error) throw new Error(data.error);
  return {
    answer: data.answer ?? "",
    engine: data.engine,
    topMatch: data.top_match,
    usage: typeof data.usage === "object" ? data.usage : undefined,
    trace: data.trace,
    clientMs: Math.round(performance.now() - started),
  };
}

// F7: one chat session per browser and restaurant, so follow-up questions keep their context.
export function browserSessionId(cuisine: string): string {
  const key = "menu.session";
  let base: string;
  try {
    base = localStorage.getItem(key) ?? "";
    if (!base) {
      base = `web-${Math.random().toString(36).slice(2, 10)}`;
      localStorage.setItem(key, base);
    }
  } catch {
    base = `web-${Math.random().toString(36).slice(2, 10)}`;
  }
  return `${base}-${cuisine}`;
}

// Debug mode: ?debug=1 turns the panel on (remembered for this browser tab), ?debug=0 turns it off;
// the invisible footer switch calls setDebug.
export function setDebug(on: boolean): void {
  try {
    if (on) sessionStorage.setItem("menu.debug", "1");
    else sessionStorage.removeItem("menu.debug");
  } catch {
    // storage blocked: the switch still works for this page view
  }
}

export function debugEnabled(): boolean {
  const key = "menu.debug";
  const param = new URLSearchParams(location.search).get("debug");
  try {
    if (param === "1") sessionStorage.setItem(key, "1");
    if (param === "0") sessionStorage.removeItem(key);
    return sessionStorage.getItem(key) === "1";
  } catch {
    return param === "1";
  }
}
