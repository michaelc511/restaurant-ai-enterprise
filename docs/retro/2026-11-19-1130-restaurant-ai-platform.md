# App retro: restaurant-ai-platform

2026-11-19 11:30 · Type: pause retro (maintenance session, not a Phase 11 build) · Branch `feature/f3.1-call-staff-fallback` · Not committed, not deployed

## What we set out to do
Mike tested the bot locally and reported wrong or unhelpful answers: happy hour, where the fish is
from, seating/ambiance/date-spot questions, vegan options and the Dragon Roll.

## What changed
| Area | Before | After |
|---|---|---|
| Missing info (F3.1, F13.2) | "I don't have that information." | Shares any partial facts, then "please give our staff a call…" |
| Dining-experience questions (F19) | Rejected as off-topic | Answered or handed off to staff |
| Off-topic message (F19) | "I can help with questions about the menu…" | "I'm only able to help with questions about our restaurant… please contact our staff…" |
| Orchestrator verifier (F13) | Rejected the staff hand-off, retried until it gave up | Accepts "contact staff" |
| Happy hour (F8) | Routed to the hours tab; `Tues - Fri` never matched | Routed to specials; day ranges work; Hours column shown |
| Chunking (F3) | 500-char cuts; 24 of 28 sushi chunks ended mid-dish | One dish per chunk |
| Keyword search (F18) | Case-sensitive ("dragon" ≠ "Dragon") | Case- and punctuation-insensitive |
| Terminal mode | Had to type a cuisine and pick an engine | Enter → sushi + LangGraph; ↑/↓ history |

Sheet data was also cleaned up with Mike: specials hours now sit inside opening hours, Monday
(closed) special removed, Sapporo allergen `Gluten`, prices formatted `$5.00`.

## Results
- `pytest`: 103 → 121 passing.
- Evals (langgraph): 7/15 on `main` → 12/16. No question that passed on `main` fails now.
- Dragon Roll: correct toppings on all three engines, any casing.

## Still open
1. Fly has `SHEETS_ENABLED=false` and no sheet credentials, so specials/happy hour don't work in production yet.
2. Orchestrator: Saturday happy hour and Friday hours get the staff hand-off (Friday also fails on `main`).
3. Context-precision evals: Friday hours, cash and delivery still under 0.6.
4. Happy-hour descriptions in the sheet are thin ("Beer", "Edamame").
5. `features.html` sections for F3, F3.1, F8, F13, F18, F19 not updated yet.
6. Commit, ship and deploy (from this branch only; Fly copies the local index).
