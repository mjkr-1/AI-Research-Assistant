const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

const state = {
  lastArticle: null,
};

let toastTimer = null;
function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 2200);
}

async function api(url, options) {
  const res = await fetch(url, options);
  let data = {};
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function spinner(label) {
  const box = el("div", "loading");
  box.append(el("div", "spinner"), el("span", null, label || "Loading…"));
  return box;
}

function errorBox(message) {
  return el("div", "error-box", message);
}

/* ---------- tabs ---------- */
$$(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    $$(".tab").forEach((t) => t.classList.toggle("active", t === tab));
    $$(".panel").forEach((p) => {
      const show = p.id === `tab-${tab.dataset.tab}`;
      p.hidden = !show;
      p.classList.toggle("active", show);
    });
  });
});

function goTab(name) {
  const tab = $(`.tab[data-tab="${name}"]`);
  if (tab) tab.click();
}

/* ---------- status ---------- */
async function loadStatus() {
  try {
    const s = await api("/api/status");
    const badge = $("#status-badge");
    if (s.api_key_set) {
      badge.textContent = `Ready · ${s.daily_remaining} calls left`;
      badge.className = "badge ok";
    } else {
      badge.textContent = "API key missing";
      badge.className = "badge warn";
    }
  } catch (_) {
    const badge = $("#status-badge");
    badge.textContent = "Server unreachable";
    badge.className = "badge warn";
  }
}

/* ---------- research ---------- */
function renderArticle(result) {
  const card = el("div", "article");
  card.append(el("h3", null, result.question));

  const chips = el("div");
  for (const step of result.history || []) chips.append(el("span", "chip", step));
  if (result.review) chips.append(el("span", "chip review", result.review.feedback));
  card.append(chips, el("div", "body", result.article));
  return card;
}

async function renderHistory() {
  const wrap = $("#research-results");
  const old = wrap.querySelector("#history-list") || wrap.querySelector("#history-wrap");
  if (old) old.remove();
  try {
    const items = await api("/api/history");
    if (!items.length) return;
    const section = el("section");
    section.id = "history-wrap";
    section.append(el("h3", null, "Past Articles"));
    const list = el("ul");
    list.id = "history-list";
    for (const item of items) {
      const li = el("li");
      li.append(
        el("div", null, item.question),
        el("div", "date", new Date(item.created_at || Date.now()).toLocaleString())
      );
      li.addEventListener("click", () => {
        const box = renderArticle({ ...item, history: [], review: null });
        const existing = wrap.querySelector(".article");
        if (existing) existing.remove();
        wrap.prepend(box);
      });
      list.append(li);
    }
    section.append(list);
    wrap.append(section);
  } catch (_) {}
}

$("#research-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = $("#question").value.trim();
  if (!question) return;
  const wrap = $("#research-results");
  wrap.replaceChildren(spinner("Researching — this can take a minute…"));
  try {
    const result = await api("/api/research", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    state.lastArticle = { question, article: result.article };
    wrap.replaceChildren(renderArticle(result));
    loadStatus();
    renderHistory();
  } catch (err) {
    wrap.replaceChildren(errorBox(err.message));
  }
});

$("#clear-history").addEventListener("click", async () => {
  try {
    const res = await fetch("/api/history", { method: "DELETE" });
    if (res.ok) toast("History cleared");
    renderHistory();
  } catch (_) {}
});

/* ---------- literature ---------- */
function paperCard(paper) {
  const card = el("div", "paper");
  card.append(el("h3", null, paper.title || "Untitled"));

  const metaBits = [];
  if (paper.authors && paper.authors.length) metaBits.push(paper.authors.slice(0, 3).join(", ") + (paper.authors.length > 3 ? " et al." : ""));
  if (paper.year) metaBits.push(paper.year);
  if (paper.venue) metaBits.push(paper.venue);
  metaBits.push(paper.source);
  card.append(el("div", "meta", metaBits.join(" · ")));
  if (paper.abstract) card.append(el("div", "abstract", paper.abstract));

  const actions = el("div", "actions");
  const citeBtn = el("button", "ghost", "Cite");
  citeBtn.addEventListener("click", () => {
    prefillCitation(paper);
    goTab("citations");
    toast("Paper loaded into citation generator");
  });
  actions.append(citeBtn);
  if (paper.url) {
    const a = el("button", "ghost", "Open source");
    a.addEventListener("click", () => window.open(paper.url, "_blank"));
    actions.append(a);
  }
  card.append(actions);
  return card;
}

$("#literature-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const query = $("#lit-query").value.trim();
  if (!query) return;
  const wrap = $("#lit-results");
  wrap.replaceChildren(spinner("Searching academic databases…"));
  try {
    const data = await api(`/api/literature?q=${encodeURIComponent(query)}`);
    if (!data.results.length) {
      wrap.replaceChildren(el("p", "muted", "No results found. Try different keywords."));
      return;
    }
    wrap.replaceChildren(...data.results.map(paperCard));
    if (data.notes && data.notes.length) {
      wrap.append(el("p", "muted", `Note: ${data.notes.join("; ")}`));
    }
  } catch (err) {
    wrap.replaceChildren(errorBox(err.message));
  }
});

/* ---------- citations ---------- */
function prefillCitation(paper) {
  $("#cit-kind").value = "journal";
  $("#cit-title").value = paper.title || "";
  $("#cit-authors").value = (paper.authors || []).join(", ");
  $("#cit-year").value = paper.year || "";
  $("#cit-venue").value = paper.venue || "";
  $("#cit-url").value = paper.url || "";
  $("#cit-doi").value = paper.doi || "";
  $("#cit-volume").value = "";
  $("#cit-issue").value = "";
  $("#cit-pages").value = "";
  $("#cit-city").value = "";
  $("#cit-publisher").value = "";
  syncKindFields();
}

function syncKindFields() {
  const kind = $("#cit-kind").value;
  $("#cit-journal-fields").hidden = kind !== "journal";
  $("#cit-book-fields").hidden = kind !== "book";
  const venueLabel = document.querySelector('label[for="cit-venue"]');
  if (venueLabel) venueLabel.textContent = kind === "website" ? "Site name" : "Journal name";
}

$("#cit-kind").addEventListener("change", syncKindFields);
$("#cit-style").addEventListener("change", () => {
  $("#cit-copy").hidden = true;
  const out = $("#cit-output");
  if (out.firstElementChild && !out.firstElementChild.classList.contains("error-box")) out.replaceChildren();
});

$("#cit-generate").addEventListener("click", async () => {
  const fields = {
    title: $("#cit-title").value.trim(),
    year: $("#cit-year").value,
    venue: $("#cit-venue").value.trim(),
    volume: $("#cit-volume").value.trim(),
    issue: $("#cit-issue").value.trim(),
    pages: $("#cit-pages").value.trim(),
    city: $("#cit-city").value.trim(),
    publisher: $("#cit-publisher").value.trim(),
    url: $("#cit-url").value.trim(),
    doi: $("#cit-doi").value.trim(),
  };
  const authors = $("#cit-authors").value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  const out = $("#cit-output");
  out.replaceChildren(spinner("Generating citation…"));
  try {
    const body = { style: $("#cit-style").value, kind: $("#cit-kind").value, fields };
    if (authors.length) body.authors = authors;
    if (fields.doi && !fields.title) {
      delete body.fields;
      body.doi = fields.doi;
    }
    const data = await api("/api/citation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const box = el("div", "citation-box");
    box.append(el("pre", null, data.citation));
    out.replaceChildren(box);
    $("#cit-copy").hidden = false;
  } catch (err) {
    out.replaceChildren(errorBox(err.message));
  }
});

$("#cit-copy").addEventListener("click", async () => {
  const text = $("#cit-output").querySelector("pre")?.textContent || "";
  try {
    await navigator.clipboard.writeText(text);
    toast("Copied to clipboard");
  } catch (_) {
    toast("Could not copy automatically");
  }
});

/* ---------- plagiarism ---------- */
function gaugeColor(score) {
  return score >= 70 ? "var(--ok)" : score >= 45 ? "var(--warn)" : "var(--danger)";
}

function renderPlagiarism(data) {
  const wrap = $("#plag-results");
  const card = el("div", "card");

  const gwrap = el("div", "gauge-wrap");
  const gauge = el("div", "gauge");
  gauge.style.setProperty("--pct", data.score);
  gauge.innerHTML = `
    <svg width="130" height="130" viewBox="0 0 130 130">
      <circle class="track" cx="65" cy="65" r="60" fill="none" stroke-width="10"/>
      <circle class="bar" cx="65" cy="65" r="60" fill="none" stroke-width="10"
        style="stroke:${gaugeColor(data.score)}"/>
    </svg>`;
  gauge.append(el("div", "label", `${data.score}`));
  gwrap.append(gauge);

  const right = el("div");
  const verdict = el("div", "verdict", data.verdict);
  verdict.classList.add(data.score >= 70 ? "ok" : data.score >= 45 ? "warn" : "bad");
  const note = el("p", "muted", "Heuristic similarity estimate — not a definitive plagiarism verdict.");
  right.append(verdict, note);
  gwrap.append(right);
  card.append(gwrap);

  const stats = el("div", "stat");
  const addStat = (label, value) => {
    const s = el("div");
    s.append(el("b", null, String(value)), el("span", null, label));
    stats.append(s);
  };
  addStat("Sources compared", data.stats.documents_compared);
  addStat("Sentences checked", data.stats.sentences_checked);
  addStat("Closest similarity", `${data.stats.closest_similarity}%`);
  card.append(stats);

  if (data.findings.length) {
    card.append(el("h3", null, "Potentially similar passages"));
    for (const f of data.findings) {
      const box = el("div", "finding");
      box.append(el("div", "src", `Matches ${f.matches} phrases · ${f.source}`), el("div", null, `“${f.snippet}”`));
      card.append(box);
    }
  }

  if (data.phrase_hits.length) {
    card.append(el("p", "muted", "Common phrases detected:"));
    const chips = el("div", "phrases");
    data.phrase_hits.forEach((p) => chips.append(el("span", null, p)));
    card.append(chips);
  }

  if (data.notes && data.notes.length) {
    card.append(el("p", "muted", `Notes: ${data.notes.join("; ")}`));
  }
  wrap.replaceChildren(card);
}

$("#plagiarism-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = $("#plag-text").value.trim();
  if (!text) return;
  const wrap = $("#plag-results");
  wrap.replaceChildren(spinner("Checking originality — comparing against sources…"));
  try {
    const data = await api("/api/plagiarism", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, question: state.lastArticle?.question || "" }),
    });
    renderPlagiarism(data);
  } catch (err) {
    wrap.replaceChildren(errorBox(err.message));
  }
});

$("#plag-last").addEventListener("click", () => {
  if (!state.lastArticle) {
    toast("Run a research first to use its article");
    return;
  }
  $("#plag-text").value = state.lastArticle.article;
  toast("Last article loaded");
});

syncKindFields();
loadStatus();
renderHistory();
