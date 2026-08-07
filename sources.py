import json
import re
import ssl
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import certifi

ssl_context = ssl.create_default_context(cafile=certifi.where())
HEADERS = {"User-Agent": "AI-Research-Agent/1.0 (research@example.com)"}

ARXIV_API = "https://export.arxiv.org/api/query"
S2_API = "https://api.semanticscholar.org/graph/v1/paper/search"
CROSSREF_API = "https://api.crossref.org/works"

_cache = {}


def _norm(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _get_json(url, params):
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(f"{url}?{query}", headers=HEADERS)
    with urllib.request.urlopen(request, timeout=25, context=ssl_context) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_bytes(url, params):
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(f"{url}?{query}", headers=HEADERS)
    with urllib.request.urlopen(request, timeout=25, context=ssl_context) as response:
        return response.read()


def search_arxiv(query, max_results=5):
    data = _get_bytes(
        ARXIV_API,
        {"search_query": f'all:"{query}"', "start": 0, "max_results": max_results},
    )
    root = ET.fromstring(data)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    results = []
    for entry in root.findall("a:entry", ns):
        title = _norm(entry.findtext("a:title", "", ns))
        summary = _norm(entry.findtext("a:summary", "", ns))
        published = _norm(entry.findtext("a:published", "", ns))
        year = int(published[:4]) if len(published) >= 4 else None
        authors = [_norm(a.findtext("a:name", "", ns)) for a in entry.findall("a:author", ns)]
        url = None
        for link in entry.findall("a:link", ns):
            if link.get("rel") == "alternate":
                url = link.get("href")
        results.append({
            "title": title,
            "authors": [a for a in authors if a],
            "year": year,
            "venue": "arXiv",
            "url": url,
            "doi": None,
            "abstract": summary,
            "source": "arXiv",
        })
    return results


def search_semantic_scholar(query, limit=5):
    data = _get_json(S2_API, {
        "query": query,
        "limit": limit,
        "fields": "title,authors,year,url,abstract,venue,externalIds",
    })
    results = []
    for item in data.get("data") or []:
        authors = [a.get("name", "") for a in item.get("authors") or []]
        ext = item.get("externalIds") or {}
        results.append({
            "title": _norm(item.get("title")),
            "authors": [a for a in authors if a],
            "year": item.get("year"),
            "venue": _norm(item.get("venue")) or "Semantic Scholar",
            "url": item.get("url"),
            "doi": ext.get("DOI"),
            "abstract": _norm(item.get("abstract")),
            "source": "Semantic Scholar",
        })
    return results


def search_crossref(query, rows=5):
    data = _get_json(CROSSREF_API, {"query": query, "rows": rows})
    results = []
    for item in data.get("message", {}).get("items") or []:
        authors = []
        for a in item.get("author") or []:
            name = f"{a.get('given', '')} {a.get('family', '')}".strip()
            if name:
                authors.append(name)
        year = None
        issued = item.get("issued", {}).get("date-parts") or []
        if issued and issued[0] and issued[0][0]:
            year = int(issued[0][0])
        venue = ""
        container = item.get("container-title") or []
        if container:
            venue = container[0]
        titles = item.get("title") or []
        results.append({
            "title": _norm(titles[0] if titles else item.get("subtitle", [""])[0] if item.get("subtitle") else ""),
            "authors": authors,
            "year": year,
            "venue": _norm(venue) or _norm(item.get("publisher")) or "Crossref",
            "url": f"https://doi.org/{item.get('DOI')}" if item.get("DOI") else None,
            "doi": item.get("DOI"),
            "abstract": "",
            "source": "Crossref",
        })
    return results


def fetch_doi(doi):
    data = _get_json(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}", {})
    item = data.get("message", {})
    authors = []
    for a in item.get("author") or []:
        name = f"{a.get('given', '')} {a.get('family', '')}".strip()
        if name:
            authors.append(name)
    year = None
    issued = item.get("issued", {}).get("date-parts") or []
    if issued and issued[0] and issued[0][0]:
        year = int(issued[0][0])
    venue = ""
    container = item.get("container-title") or []
    if container:
        venue = container[0]
    titles = item.get("title") or []
    return {
        "title": _norm(titles[0] if titles else ""),
        "authors": authors,
        "year": year,
        "venue": _norm(venue) or _norm(item.get("publisher")) or "Crossref",
        "url": f"https://doi.org/{item.get('DOI')}",
        "doi": item.get("DOI"),
        "abstract": "",
        "source": "Crossref",
    }


def search_literature(query, max_results=5):
    key = query.strip().lower()
    cached = _cache.get(key)
    if cached and time.time() - cached[0] < 600:
        return cached[1], cached[2]

    providers = [
        (search_arxiv, (query, max_results), "arXiv"),
        (search_semantic_scholar, (query, max_results), "Semantic Scholar"),
        (search_crossref, (query, max_results), "Crossref"),
    ]
    combined = []
    notes = []
    for fn, args, name in providers:
        try:
            combined.extend(fn(*args))
        except Exception as e:
            notes.append(f"{name}: {type(e).__name__}")
        time.sleep(1)

    seen = set()
    unique = []
    for paper in combined:
        title_key = _norm(paper.get("title") or "").lower()
        if not title_key or title_key in seen:
            continue
        seen.add(title_key)
        unique.append(paper)

    unique.sort(key=lambda p: p.get("year") or 0, reverse=True)
    unique = unique[:max_results * 2]
    _cache[key] = (time.time(), unique, notes)
    return unique, notes
