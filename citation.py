import re

import sources

STYLES = ["APA", "MLA", "Chicago", "IEEE"]
KINDS = ["journal", "website", "book"]
_STYLE_ALIASES = {"apa": "APA", "mla": "MLA", "chicago": "Chicago", "ieee": "IEEE"}

_MONTHS = ["", "January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"]


def _norm(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _authors_list(authors):
    if not authors:
        return []
    if isinstance(authors, str):
        authors = [part.strip() for part in authors.split(",")]
    out = []
    for a in authors:
        if isinstance(a, dict):
            name = f"{a.get('given', '')} {a.get('family', '')}".strip()
        else:
            name = str(a)
        name = _norm(name)
        if name:
            out.append(name)
    return out


def _parse_name(full):
    parts = _norm(full).split()
    if len(parts) >= 2:
        return parts[-1], " ".join(parts[:-1])
    return full, ""


def _apa_name(full):
    family, given = _parse_name(full)
    initials = "".join(p[0] for p in given.split() if p)
    return f"{family}, {initials}." if initials else family


def _mla_name(full):
    family, given = _parse_name(full)
    return f"{family}, {given}" if given else family


def _chicago_name(full):
    return _mla_name(full)


def _ieee_name(full):
    family, given = _parse_name(full)
    initials = ". ".join(p[0] for p in given.split() if p)
    return f"{initials}. {family}" if initials else family


def _names(names, style):
    func = {"APA": _apa_name, "MLA": _mla_name,
            "Chicago": _chicago_name, "IEEE": _ieee_name}[style]
    formatted = [func(n) for n in names if n]
    if not formatted:
        return "Anonymous"
    if len(formatted) == 1:
        return formatted[0]
    if style == "IEEE":
        if len(formatted) == 2:
            return " and ".join(formatted)
        return ", ".join(formatted[:-1]) + ", and " + formatted[-1]
    if style == "APA":
        if len(formatted) == 2:
            return " & ".join(formatted)
        if len(formatted) > 7:
            return ", ".join(formatted[:6]) + ", ... " + formatted[-1]
        return ", ".join(formatted[:-1]) + ", & " + formatted[-1]
    if len(formatted) == 2:
        return " and ".join(formatted)
    return ", ".join(formatted[:-1]) + ", and " + formatted[-1]


def _year(fields):
    try:
        year = int(fields.get("year") or 0)
        return year if year > 0 else None
    except (TypeError, ValueError):
        return None


def _date_str(fields):
    year = _year(fields)
    month = int(fields.get("month") or 0)
    day = int(fields.get("day") or 0)
    parts = []
    if month and 1 <= month <= 12:
        parts.append(_MONTHS[month])
    if day:
        parts.append(str(day))
    if year:
        parts.append(str(year))
    return " ".join(parts) if parts else "n.d."


def _access_date(fields):
    parts = []
    if fields.get("access_day"):
        parts.append(_MONTHS[min(max(int(fields["access_day"] or 0), 1), 12)])
    if fields.get("access_date_day"):
        parts.append(str(fields["access_date_day"]))
    if fields.get("access_year"):
        parts.append(str(fields["access_year"]))
    return " ".join(parts) if parts else None


def _journal_citation(style, f, index=None):
    names = _names(_authors_list(f.get("authors")), style)
    title = _norm(f.get("title"))
    venue = _norm(f.get("venue"))
    volume = _norm(f.get("volume"))
    issue = _norm(f.get("issue"))
    pages = _norm(f.get("pages"))
    doi = _norm(f.get("doi"))
    url = _norm(f.get("url"))
    year = _year(f)
    year_str = str(year) if year else "n.d."

    if style == "APA":
        result = f"{names} ({year_str}). {title}. *{venue}*"
        if volume:
            result += f", *{volume}"
            if issue:
                result += f"*({issue})"
            result += "*"
        if pages:
            result += f", {pages}"
        result += "."
        if doi:
            result += f" https://doi.org/{doi}"
        elif url:
            result += f" {url}"
        return result

    if style == "MLA":
        result = f"{names}. \u201C{title}.\u201D *{venue}*, vol. {volume}, no. {issue}, {year_str}"
        if pages:
            result += f", pp. {pages}"
        result += "."
        if doi:
            result += f" doi:{doi}."
        elif url:
            result += f" {url}."
        return result

    if style == "Chicago":
        result = f"{names}. {year_str}. \u201C{title}.\u201D *{venue}* {volume}"
        if issue:
            result += f", no. {issue}"
        if pages:
            result += f" ({year_str}): {pages}"
        else:
            result += f" ({year_str})"
        result += "."
        if doi:
            result += f" https://doi.org/{doi}."
        elif url:
            result += f" {url}."
        return result

    if style == "IEEE":
        num = f"[{index}] " if index else ""
        authors = _names(_authors_list(f.get("authors")), "IEEE")
        result = f"{num}{authors}, \u201C{title},\u201D *{venue}*"
        if volume:
            result += f", vol. {volume}"
        if issue:
            result += f", no. {issue}"
        if pages:
            result += f", pp. {pages}"
        result += f", {year_str}."
        if doi:
            result += f" doi: {doi}."
        elif url:
            result += f" [Online]. Available: {url}"
        return result


def _website_citation(style, f, index=None):
    names = _names(_authors_list(f.get("authors")), style)
    title = _norm(f.get("title"))
    site = _norm(f.get("site")) or _norm(f.get("venue"))
    url = _norm(f.get("url"))
    date = _date_str(f)
    year = _year(f)
    year_str = str(year) if year else "n.d."

    if style == "APA":
        result = f"{names} ({date}). {title}."
        if site:
            result += f" *{site}*."
        if url:
            result += f" {url}"
        return result

    if style == "MLA":
        result = f"{names}. \u201C{title}.\u201D *{site}*, {date}, {url}."
        return result

    if style == "Chicago":
        result = f"{names}. {year_str}. \u201C{title}.\u201D *{site}*."
        result += f" Accessed {_access_date(f) or 'Month Day, Year'}."
        result += f" {url}."
        return result

    if style == "IEEE":
        num = f"[{index}] " if index else ""
        authors = _names(_authors_list(f.get("authors")), "IEEE")
        result = f"{num}{authors}, \u201C{title},\u201D *{site}*."
        result += f" Accessed: {_access_date(f) or 'Month Day, Year'}. [Online]."
        result += f" Available: {url}"
        return result


def _book_citation(style, f, index=None):
    names = _names(_authors_list(f.get("authors")), style)
    title = _norm(f.get("title"))
    publisher = _norm(f.get("publisher"))
    city = _norm(f.get("city"))
    year = _year(f)
    year_str = str(year) if year else "n.d."

    if style == "APA":
        result = f"{names} ({year_str}). *{title}*."
        if publisher:
            result += f" {publisher}."
        return result

    if style == "MLA":
        result = f"{names}. *{title}*."
        if publisher:
            result += f" {publisher}, {year_str}."
        return result

    if style == "Chicago":
        result = f"{names}. {year_str}. *{title}*."
        if city and publisher:
            result += f" {city}: {publisher}."
        elif publisher:
            result += f" {publisher}."
        return result

    if style == "IEEE":
        num = f"[{index}] " if index else ""
        authors = _names(_authors_list(f.get("authors")), "IEEE")
        result = f"{num}{authors}, *{title}*."
        if city:
            result += f" {city},"
        if publisher:
            result += f" {publisher}: {year_str}."
        else:
            result += f" {year_str}."
        return result


def generate_citation(style, kind, fields, index=None):
    style = _STYLE_ALIASES.get((style or "").strip().lower(), style or "")
    kind = (kind or "journal").strip().lower()
    if style not in STYLES:
        raise ValueError(f"Unsupported style '{style}'. Choose from: {', '.join(STYLES)}.")
    if kind not in KINDS:
        raise ValueError(f"Unsupported kind '{kind}'. Choose from: {', '.join(KINDS)}.")

    if not fields.get("authors"):
        fields = dict(fields)
        fields["authors"] = []
    if not _norm(fields.get("title")) and kind != "book":
        raise ValueError("A title is required to build a citation.")

    if kind == "journal":
        return _journal_citation(style, fields, index)
    if kind == "website":
        return _website_citation(style, fields, index)
    return _book_citation(style, fields, index)


def citation_from_paper(paper, style="APA", index=None):
    fields = {
        "title": paper.get("title", ""),
        "authors": paper.get("authors", []),
        "year": paper.get("year"),
        "venue": paper.get("venue", ""),
        "doi": paper.get("doi", ""),
        "url": paper.get("url", ""),
    }
    return generate_citation(style, "journal", fields, index)


def citation_from_doi(doi, style="APA", index=None):
    paper = sources.fetch_doi(doi)
    return citation_from_paper(paper, style, index)
