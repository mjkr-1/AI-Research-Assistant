import re

import chat_llm
import sources

_STOPWORDS = frozenset("""a an the and or but if then else of in on at to for
with by from as is are was were be been being have has had do does did will
would shall should may might can could this that these those it its i you he
she they we us them me him her my your our their not no nor so too very just
also than when where which who whom whose about between into through during
before after above below up down out off over under again further once here
there all any both each few more most other some such only own same""".split())

_COMMON_PHRASES = [
    "in recent years",
    "plays a crucial role",
    "it is important to note",
    "the results show",
    "in conclusion",
    "this paper presents",
    "a wide range of",
    "on the other hand",
    "it can be observed",
    "the findings suggest",
    "according to the authors",
    "significant impact on",
    "has been widely studied",
    "the aim of this study",
    "further research is needed",
    "as shown in",
    "in this study we",
    "the rest of the paper is organized as follows",
]

_GRAM_N = 6
_MAX_DOC_TOKENS = 4000
_MAX_FINDINGS = 8


def _tokens(text):
    return re.findall(r"[a-z0-9']+", (text or "").lower())


def _ngrams(tokens, n=_GRAM_N):
    return [" ".join(tokens[i:i + n]) for i in range(max(0, len(tokens) - n + 1))]


def _content_tokens(text):
    return [t for t in _tokens(text) if t not in _STOPWORDS]


def _sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [p.strip() for p in parts if len(p.strip()) > 3]


def _memory_corpus():
    memory = chat_llm.load_memory()
    docs = []
    for entry in memory.get("history") or []:
        article = entry.get("article")
        if article and len(article.strip()) > 40:
            docs.append({"text": article, "label": "Your past article"})
    for entry in memory.get("knowledge") or []:
        text = entry.get("text") if isinstance(entry, dict) else entry
        if isinstance(text, str) and len(text.strip()) > 40:
            docs.append({"text": text, "label": "Saved knowledge"})
    return docs


def check_plagiarism(text, question=None, include_literature=True):
    text = (text or "").strip()
    if not text:
        raise ValueError("Text to check is required.")

    corpus = _memory_corpus()
    notes = []

    if include_literature and question:
        try:
            papers, provider_notes = sources.search_literature(question, 5)
            for paper in papers:
                snippet = f"{paper.get('title', '')}. {paper.get('abstract', '')}"
                if len(snippet.strip()) > 40:
                    corpus.append({
                        "text": snippet,
                        "label": f"Literature ({paper.get('source')})",
                    })
            if provider_notes:
                notes.extend(provider_notes)
        except Exception as e:
            notes.append(f"Literature search failed: {e}")

    tokens = _tokens(text)
    grams = _ngrams(tokens)
    gram_set = set(grams)
    total = len(gram_set)

    doc_ratios = []
    gram_source = {}
    for doc in corpus[:14]:
        doc_tokens = _tokens(doc["text"])[:_MAX_DOC_TOKENS]
        doc_grams = set(_ngrams(doc_tokens))
        if not doc_grams:
            continue
        overlap = len(gram_set & doc_grams)
        ratio = overlap / max(1, total)
        doc_ratios.append({"label": doc["label"], "ratio": ratio})
        for g in (gram_set & doc_grams):
            gram_source.setdefault(g, doc["label"])

    findings = []
    for sentence in _sentences(text):
        sent_tokens = _tokens(sentence)
        if len(sent_tokens) < _GRAM_N:
            continue
        sent_grams = set(_ngrams(sent_tokens))
        shared = [g for g in sent_grams if g in gram_source]
        if len(shared) >= 2:
            findings.append({
                "snippet": sentence[:220],
                "matches": len(shared),
                "source": gram_source[shared[0]],
            })

    findings.sort(key=lambda f: f["matches"], reverse=True)
    findings = findings[:_MAX_FINDINGS]

    content_tokens = _content_tokens(text)
    lower_text = text.lower()
    phrase_hits = [p for p in _COMMON_PHRASES if p in lower_text]

    highest = max((d["ratio"] for d in doc_ratios), default=0.0)
    phrase_penalty = min(len(phrase_hits) * 1.5, 15.0)
    score = max(0, min(100, round(100 - highest * 110 - phrase_penalty)))

    if score >= 90:
        verdict = "Looks original"
    elif score >= 70:
        verdict = "Mostly original"
    elif score >= 45:
        verdict = "Similarities detected"
    else:
        verdict = "High similarity"

    return {
        "score": score,
        "verdict": verdict,
        "findings": findings,
        "phrase_hits": phrase_hits,
        "sources_checked": [d["label"] for d in doc_ratios],
        "notes": notes,
        "stats": {
            "documents_compared": len(doc_ratios),
            "sentences_checked": len(_sentences(text)),
            "closest_similarity": round(highest * 100, 1),
        },
    }
