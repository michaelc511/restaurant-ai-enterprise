import requests
import streamlit as st

API_URL = "http://127.0.0.1:8000"

available_cuisines = ["sushi", "steak", "italian"]

st.title("Menu RAG Demo")

cuisine = st.selectbox("Cuisine", available_cuisines)
question = st.text_area("Question", "What rolls are on the menu?")

if st.button("Ask"):
    with st.spinner("Generating..."):
        resp = requests.post(f"{API_URL}/ask", json={"cuisine": cuisine, "question": question})
        resp.raise_for_status()
        data = resp.json()

    if "error" in data:
        st.error(data["error"])
    else:
        st.write("Answer:", data["answer"])
        st.write("Top Matching Chunk:", data["top_match"])

        if "usage" in data:  # F6/F11: only present when DEBUG_MODE is on server-side
            usage = data["usage"]
            totals = data["session_totals"]
            with st.expander("Debug Metrics (F6 tokens/cost + F11 DB totals)", expanded=True):
                st.write(
                    f"[F6] This call — prompt: {usage['prompt_tokens']}, completion: {usage['completion_tokens']}, "
                    f"total: {usage['total_tokens']} | Cost: ${usage['total_cost_usd']:.6f}"
                )
                st.write(
                    f"[F11] Session total (DB) — prompt: {totals['prompt_tokens']}, "
                    f"completion: {totals['completion_tokens']}, total: {totals['total_tokens']} | "
                    f"Cost: ${totals['total_cost_usd']:.6f}"
                )

st.header("Restaurant Ops (F8 - live Google Sheet, not the RAG chain)")

day = st.text_input("Day (optional, e.g. Fri - leave blank for all)")
if st.button("Get Daily Specials"):
    # F8: hits menu_api.py's /specials endpoint directly - core/sheets.py's live Google Sheet data.
    resp = requests.get(f"{API_URL}/specials", params={"day": day} if day else {})
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        st.error(data["error"])
    elif not data["specials"]:
        st.write("No active specials found.")
    else:
        for row in data["specials"]:
            st.write(f"[{row['Day']}] {row['Dish Name']} ({row['Price']}) - {row['Description']}")

if st.button("Get Today's Hours"):
    # F8: goes through /ask, same as typing "what are your hours today?" in the Ask box above -
    # regular hours live in the PDF menu, so this needs the RAG chain, not a raw /hours call
    # (that endpoint only returns Google Sheet exceptions/events, never the standard weekly hours).
    resp = requests.post(f"{API_URL}/ask", json={"cuisine": cuisine, "question": "What are your hours today?"})
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        st.error(data["error"])
    else:
        st.write(data["answer"])
