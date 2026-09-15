import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

import certifi
from rate_limiter import RateLimiter

memory_file = "memory.json"
endpoint = "https://openrouter.ai/api/v1/chat/completions"
model = "nvidia/nemotron-3-ultra-550b-a55b:free"
ssl_context = ssl.create_default_context(cafile=certifi.where())

daily_limiter = RateLimiter(max_calls=200, period=86400, state_file="rate_state.json")
minute_limiter = RateLimiter(max_calls=20, period=60)

api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key:
                        os.environ.setdefault(key, value)
        except OSError:
            pass
        api_key = os.environ.get("OPENROUTER_API_KEY")


def chat(prompt, retries=3):
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Add it to a .env file next to "
            "chat_llm.py, e.g.: OPENROUTER_API_KEY=sk-or-v1-..."
        )

    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2000
    }).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    request = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")

    for attempt in range(retries):
        daily_limiter.wait()
        minute_limiter.wait()
        try:
            with urllib.request.urlopen(request, timeout=60, context=ssl_context) as response:
                result = json.loads(response.read().decode("utf-8"))
            message = result["choices"][0]["message"]
            content = message.get("content")
            if not content:
                content = message.get("reasoning", "")
            if not content:
                raise RuntimeError("Model returned empty response")
            return content
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(min(2 ** attempt, 30))
                continue
            if e.code in (500, 502, 503, 529) and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"HTTP {e.code}: {e.read().decode()}")
        except urllib.error.URLError as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Connection error: {e.reason}")


def create_memory():
    return {"user": {}, "preferences": {}, "history": [], "knowledge": []}


def load_memory():
    if not os.path.exists(memory_file):
        return create_memory()
    try:
        with open(memory_file, "r", encoding="utf-8") as file:
            memory = json.load(file)
            memory.setdefault("user", {})
            memory.setdefault("preferences", {})
            memory.setdefault("history", [])
            memory.setdefault("knowledge", [])
        return memory
    except (json.JSONDecodeError, OSError):
        return create_memory()


def save_memory(memory):
    with open(memory_file, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=4)


def research_agent(state):
    prompt = f"""
    You are a Research paper assistant.
    Research this topic:
    {state["question"]}
    """
    try:
        state["research"] = chat(prompt)
        state["history"].append("Research completed")
    except RuntimeError as e:
        state["error"] = f"Research failed: {e}"
    return state


def write_agent(state):
    prompt = f"""
    You are a Writer Agent.
    Convert the following research into an article.
    {state["research"]}
    """
    try:
        state["article"] = chat(prompt)
        state["history"].append("Article written")
    except RuntimeError as e:
        state["error"] = f"Writing failed: {e}"
    return state


def reviewer_agent(state):
    article = state["article"]
    error_markers = ("HTTP Error", "Connection error", "Error:", "Model returned empty")
    if not article or len(article) < 60 or any(marker in article for marker in error_markers):
        state["review"] = {"okay": False, "feedback": "Generated article rejected"}
    else:
        state["review"] = {"okay": True, "feedback": "Generated article accepted"}
    state["history"].append("Review completed")
    return state


def orchestrator(question):
    state = {
        "question": question,
        "research": "",
        "article": "",
        "review": {},
        "history": [],
        "error": None
    }

    state = research_agent(state)
    if state["error"]:
        return state
    state = write_agent(state)
    if state["error"]:
        return state
    state = reviewer_agent(state)

    memory = load_memory()
    if state["review"].get("okay"):
        memory["history"].append({
            "question": state["question"],
            "article": state["article"]
        })
        save_memory(memory)

    return state


if __name__ == "__main__":
    question = " ".join(sys.argv[1:])
    if not question:
        question = "What are the latest advancements in AI research?"
    result = orchestrator(question)
    if result["error"]:
        print(result["error"])
    else:
        print(result["article"])
        print("Review:", result["review"])
