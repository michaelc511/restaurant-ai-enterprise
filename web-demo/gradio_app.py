import gradio as gr
import requests

API_URL = "http://127.0.0.1:8000"

available_cuisines = ["sushi", "steak", "italian"]


def ask_menu(cuisine, question):
    resp = requests.post(f"{API_URL}/ask", json={"cuisine": cuisine, "question": question})
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        return data["error"], "", ""

    debug_text = ""
    if "usage" in data:  # F6/F11: only present when DEBUG_MODE is on server-side
        usage = data["usage"]
        totals = data["session_totals"]
        debug_text = (
            f"[F6] This call — prompt: {usage['prompt_tokens']}, completion: {usage['completion_tokens']}, "
            f"total: {usage['total_tokens']} | Cost: ${usage['total_cost_usd']:.6f}\n"
            f"[F11] Session total (DB) — prompt: {totals['prompt_tokens']}, completion: {totals['completion_tokens']}, "
            f"total: {totals['total_tokens']} | Cost: ${totals['total_cost_usd']:.6f}"
        )

    return data["answer"], data["top_match"], debug_text


def get_specials(day):
    # F8: hits menu_api.py's /specials endpoint directly - core/sheets.py's live Google Sheet data,
    # not the RAG chain, so this never touches menus/ or FAISS.
    resp = requests.get(f"{API_URL}/specials", params={"day": day} if day else {})
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        return data["error"]
    if not data["specials"]:
        return "No active specials found."
    return "\n".join(
        f"[{row['Day']}] {row['Dish Name']} ({row['Price']}) - {row['Description']}"
        for row in data["specials"]
    )


def get_hours(cuisine):
    # F8: goes through /ask, same as typing "what are your hours today?" in the Ask box -
    # regular hours live in the PDF menu, so this needs the RAG chain, not a raw /hours call
    # (that endpoint only returns Google Sheet exceptions/events, never the standard weekly hours).
    resp = requests.post(f"{API_URL}/ask", json={"cuisine": cuisine, "question": "What are your hours today?"})
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        return data["error"]
    return data["answer"]


with gr.Blocks(title="Menu RAG Demo") as demo:
    gr.Markdown("# Menu RAG Demo")

    cuisine_input = gr.Dropdown(label="Cuisine", choices=available_cuisines, value="sushi")
    question_input = gr.Textbox(label="Question", value="What rolls are on the menu?", lines=2)
    ask_btn = gr.Button("Ask")
    answer_output = gr.Textbox(label="Answer")
    top_match_output = gr.Textbox(label="Top Matching Chunk", lines=4)
    debug_output = gr.Textbox(label="Debug Metrics (F6 tokens/cost + F11 DB totals)", lines=4)

    ask_btn.click(ask_menu, inputs=[cuisine_input, question_input],
                  outputs=[answer_output, top_match_output, debug_output])

    gr.Markdown("## Restaurant Ops (F8 - live Google Sheet, not the RAG chain)")
    day_input = gr.Textbox(label="Day (optional, e.g. Fri - leave blank for all)")
    specials_btn = gr.Button("Get Daily Specials")
    specials_output = gr.Textbox(label="Daily Specials", lines=6)
    specials_btn.click(get_specials, inputs=[day_input], outputs=[specials_output])

    hours_btn = gr.Button("Get Today's Hours")
    hours_output = gr.Textbox(label="Today's Hours", lines=4)
    hours_btn.click(get_hours, inputs=[cuisine_input], outputs=[hours_output])

if __name__ == "__main__":
    demo.launch(inbrowser=True)
