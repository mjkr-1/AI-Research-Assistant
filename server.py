import os
import threading
import webbrowser

from flask import Flask, jsonify, render_template, request

import chat_llm
import citation
import plagiarism
import sources

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
lock = threading.Lock()


def _api_key_set():
    return bool(chat_llm.api_key)


@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/status")
def status():
    memory = chat_llm.load_memory()
    return jsonify({
        "api_key_set": _api_key_set(),
        "model": chat_llm.model,
        "daily_remaining": chat_llm.daily_limiter.remaining,
        "history_count": len(memory.get("history", [])),
    })


@app.post("/api/research")
def research():
    if not _api_key_set():
        return jsonify({"error": "OPENROUTER_API_KEY is not set."}), 503
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "Missing 'question' field."}), 400
    if len(question) > 2000:
        return jsonify({"error": "Question too long (max 2000 chars)."}), 400

    with lock:
        result = chat_llm.orchestrator(question)

    if result["error"]:
        return jsonify({"error": result["error"]}), 502
    return jsonify({
        "question": result["question"],
        "article": result["article"],
        "review": result["review"],
        "history": result["history"],
    })


@app.get("/api/history")
def history():
    memory = chat_llm.load_memory()
    return jsonify(memory.get("history", []))


@app.delete("/api/history")
def clear_history():
    with lock:
        memory = chat_llm.load_memory()
        memory["history"] = []
        chat_llm.save_memory(memory)
    return jsonify({"ok": True})


@app.get("/api/literature")
def literature():
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify({"error": "Missing 'q' query parameter."}), 400
    if len(query) > 300:
        return jsonify({"error": "Search query too long (max 300 chars)."}), 400
    try:
        results, notes = sources.search_literature(query, 5)
    except Exception as e:
        return jsonify({"error": f"Literature search failed: {e}"}), 502
    return jsonify({"results": results, "notes": notes})


@app.post("/api/citation")
def make_citation():
    data = request.get_json(silent=True) or {}
    style = (data.get("style") or "APA").strip().title()
    doi = (data.get("doi") or "").strip()
    index = data.get("index")
    if doi:
        try:
            paper = sources.fetch_doi(doi)
            return jsonify({"citation": citation.citation_from_paper(paper, style, index)})
        except Exception as e:
            return jsonify({"error": f"DOI lookup failed: {e}"}), 502
    fields = data.get("fields") or {}
    if not fields.get("authors") and isinstance(data.get("authors"), list):
        fields["authors"] = data["authors"]
    try:
        result = citation.generate_citation(style, data.get("kind") or "journal", fields, index)
        return jsonify({"citation": result})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.post("/api/plagiarism")
def run_plagiarism():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Missing 'text' field."}), 400
    if len(text) > 50000:
        return jsonify({"error": "Text too long (max 50000 chars)."}), 400
    try:
        result = plagiarism.check_plagiarism(
            text,
            question=(data.get("question") or "").strip() or None,
            include_literature=bool(data.get("include_literature", True)),
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "Request too large."}), 413


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    url = f"http://127.0.0.1:{port}/"
    print(f"AI Research Agent running at {url}")
    if _api_key_set():
        print("API key detected.")
    else:
        print("Warning: no API key available; /api/research will fail.")
    threading.Timer(1.0, webbrowser.open, args=[url]).start()
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
