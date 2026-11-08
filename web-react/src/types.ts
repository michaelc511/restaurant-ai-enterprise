// F5: response shapes from engine_api.py - kept in one place so a backend change shows up as a type error.

export interface CollectionsResponse {
  domain: string;
  label: string;
  collections: string[];
}

export interface Usage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  total_cost_usd: number;
}

export interface Trace {
  retriever_ms: number;
  llm_ms: number;
  total_ms: number;
  errors: number;
  calls: number;
}

export interface AskResponse {
  cuisine: string;
  answer: string;
  top_match: string;
  engine?: string; // absent when F8/F19 answered before any engine ran
  usage?: Usage; // F6: only when METRICS is on
  trace?: Trace; // F9: only when METRICS is on
}

export interface ErrorResponse {
  error: string;
}

export type SheetRow = Record<string, string | number>;
