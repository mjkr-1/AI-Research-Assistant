# AI Research Assistant

A Flask-based research assistant that generates researched articles, searches academic literature, builds formatted citations, and runs originality checks — all from a clean single-page web UI.

## Features

- **Research pipeline** — a multi-agent workflow (research → write → review) powered by OpenRouter's free LLM models.
- **Literature search** — queries arXiv, Semantic Scholar, and Crossref; results are deduplicated and sorted by year.
- **Citation generator** — APA, MLA, Chicago, and IEEE citations for journal articles, websites, and books, with DOI lookup.
- **Originality check** — heuristic similarity analysis against your past articles and related literature, with flagged passages and a similarity score.

## Tech Stack

- **Backend:** Python 3, Flask, gunicorn
- **Frontend:** HTML, CSS, vanilla JavaScript (no build step)
- **LLM:** OpenRouter API (`nvidia/nemotron-3-ultra-550b-a55b:free`)

## Getting Started

### Prerequisites

- Python 3.10+
- An [OpenRouter](https://openrouter.ai) API key

### Local Setup

```bash
# 1. Clone the repo
git clone https://github.com/mjkr-1/AI-Research-Assistant.git
cd AI-Research-Assistant

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure your API key
copy .env.example .env
# then edit .env and paste your key:
# OPENROUTER_API_KEY=sk-or-v1-...

# 4. Run the server
python server.py
```

Open `http://127.0.0.1:5000` in your browser (it opens automatically).

## Deploying to Render

1. Sign in at https://render.com → **New+** → **Blueprint** and connect your GitHub repo (the included `render.yaml` configures everything), or create a **Web Service** with:

   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn server:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120`

2. Add the environment variable `OPENROUTER_API_KEY` with your real key.
3. Deploy. You'll get a URL like `https://ai-research-assistant.onrender.com`.

> **Note:** On the free tier, Render spins down after ~15 minutes of inactivity and history (`memory.json`) resets on redeploy.

## API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/` | Web UI |
| `GET` | `/api/status` | API key status, model, remaining daily calls |
| `POST` | `/api/research` | Run the research pipeline (`{"question": "..."}`) |
| `GET` | `/api/literature?q=...` | Search academic literature |
| `POST` | `/api/citation` | Generate a citation |
| `POST` | `/api/plagiarism` | Run an originality check |
| `GET` / `DELETE` | `/api/history` | Read or clear past articles |

## Project Structure

```
├── server.py        # Flask app + API routes
├── chat_llm.py      # LLM calls, multi-agent research pipeline, memory
├── rate_limiter.py  # Daily/minute API rate limiting
├── sources.py       # arXiv / Semantic Scholar / Crossref search
├── citation.py      # Citation formatters (APA, MLA, Chicago, IEEE)
├── plagiarism.py    # Similarity / originality checking
├── templates/       # Frontend HTML
├── static/          # Frontend CSS + JS
├── Procfile         # Render start command
└── render.yaml      # Render blueprint config
```

## License

Distributed under the [MIT License](LICENSE). Copyright © 2026 Manoj K R.