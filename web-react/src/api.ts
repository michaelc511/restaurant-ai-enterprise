// F5: thin fetch wrappers over engine_api.py, reached through Vite's /api proxy (vite.config.ts).
import type { AskResponse, CollectionsResponse, ErrorResponse, SheetRow } from "./types";

// F12/F13: engine keys engine_api.py accepts, labeled the same as its CLI menu
export const ENGINES = [
  { key: "plain_rag", label: "Plain RAG" },
  { key: "langgraph", label: "LangGraph" },
  { key: "orchestrator", label: "Agentic RAG LG" },
] as const;

export type EngineKey = (typeof ENGINES)[number]["key"];

async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`/api${path}`, init);
  if (!resp.ok) throw new Error(`${path} failed: HTTP ${resp.status}`);
  const data = (await resp.json()) as T | ErrorResponse;
  if (typeof data === "object" && data !== null && "error" in data) throw new Error(data.error);
  return data as T;
}

export function getCollections(): Promise<CollectionsResponse> {
  return getJson<CollectionsResponse>("/collections");
}

export function ask(cuisine: string, question: string, engine: EngineKey, sessionId: string): Promise<AskResponse> {
  return getJson<AskResponse>("/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cuisine, question, engine, session_id: sessionId }),
  });
}

export async function getSpecials(day?: string): Promise<SheetRow[]> {
  const query = day ? `?day=${encodeURIComponent(day)}` : "";
  return (await getJson<{ specials: SheetRow[] }>(`/specials${query}`)).specials;
}
