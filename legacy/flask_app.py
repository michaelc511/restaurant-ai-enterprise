from flask import Flask, request, jsonify
from menu_api import qa_chains, available_cuisines

app = Flask(__name__)


@app.post("/ask")
def ask():
    data = request.get_json(silent=True) or {}
    cuisine = data.get("cuisine", "").strip().lower()
    question = data.get("question", "")

    if cuisine not in qa_chains:
        return jsonify({"error": f"Unknown cuisine. Choose one of {available_cuisines}"}), 400

    result = qa_chains[cuisine].invoke({"query": question})
    return jsonify({
        "cuisine": cuisine,
        "answer": result["result"],
        "top_match": result["source_documents"][0].page_content,
    })


if __name__ == "__main__":
    app.run(port=5000, debug=True)
