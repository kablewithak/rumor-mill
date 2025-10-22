from typing import List, Dict
import re
from config import KEYWORDS, SUPPRESS_DUP_SUMMARY

def _tokens(s: str) -> set:
    s = re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower())
    return {w for w in s.split() if len(w) > 2}

def _overlap(a: set, b: set) -> float:
    """Token-set overlap used for clustering titles."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)

def _jaccard(a: str, b: str) -> float:
    A, B = _tokens(a), _tokens(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)

_SITE_TAIL = re.compile(
    r"\s*(?:[-–—]\s*)?(?:www\.)?(?:[a-z0-9-]+\.)+(?:com|net|org|co|io|ai|gov|edu)\s*$",
    re.I,
)

def _strip_site(s: str) -> str:
    return _SITE_TAIL.sub("", (s or "").strip())

def _first_sentence(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", s)
    return parts[0].strip()

def cluster_for_trace(items: List[Dict]) -> List[Dict]:
    """
    Build near-duplicate clusters from titles, for audit logs only.
    Returns: [{"rep": {...}, "members":[...]}]
    """
    def _host(url: str) -> str:
        m = re.search(r"https?://([^/]+)", (url or "").lower())
        return m.group(1) if m else ""

    candidates = items[:12]
    title_tokens = [_tokens(it["title"]) for it in candidates]

    clusters, rep_indices = [], []
    for i, tok_i in enumerate(title_tokens):
        placed = False
        for idx, rep in enumerate(rep_indices):
            if _overlap(tok_i, title_tokens[rep]) >= 0.6:
                clusters[idx].append(i); placed = True; break
        if not placed:
            clusters.append([i]); rep_indices.append(i)

    out = []
    for cluster in clusters:
        rep_idx = max(cluster, key=lambda j: candidates[j].get("rumor_score", 0.0))
        group = [candidates[j] for j in cluster]
        rep = candidates[rep_idx]
        out.append({
            "rep":   {"title": rep["title"], "url": rep["link"], "host": _host(rep.get("link",""))},
            "members": [{"title": g["title"], "url": g["link"], "host": _host(g.get("link",""))} for g in group]
        })
    return out

def _make_summary(title: str, snippet: str) -> str:
    """Two clean sentences; avoid echoing the headline when SUPPRESS_DUP_SUMMARY is True."""
    t_clean = _strip_site(title).rstrip(".")
    s_first = _first_sentence(_strip_site(snippet))

    if SUPPRESS_DUP_SUMMARY and s_first:
        t40 = t_clean.lower()[:60] 
        sf  = s_first.lower()
        if sf.startswith(t40) or t_clean.lower() in sf:
            s_first = ""
        elif _jaccard(t_clean, s_first) >= 0.45:
            s_first = ""


    if s_first:
        return f"{t_clean}. {s_first}"
    return f"{t_clean}. Coverage is emerging; details remain unconfirmed."

def _rationale(text: str) -> str:
    tl = text.lower()
    hits = [k for k in KEYWORDS if k in tl]
    if hits:
        return f"Keyword signals: {', '.join(hits[:3])}."
    return "Language suggests speculation or unconfirmed sourcing."

def _confidence_from_rumor(rumor_score: float) -> float:
    conf = 1.0 - min(1.0, rumor_score) * 0.9
    return round(max(0.05, conf), 2)

def pick_one(domain: str, items: List[Dict]) -> Dict:
    candidates = items[:12]

    clusters = []
    rep_indices = []
    title_tokens = [_tokens(it["title"]) for it in candidates]

    for i, tok_i in enumerate(title_tokens):
        placed = False
        for idx, rep in enumerate(rep_indices):
            if _overlap(tok_i, title_tokens[rep]) >= 0.6:
                clusters[idx].append(i)
                placed = True
                break
        if not placed:
            clusters.append([i])
            rep_indices.append(i)

    picks = []
    for cluster in clusters:
        best = max(cluster, key=lambda j: candidates[j].get("rumor_score", 0))
        group = [candidates[j] for j in cluster]
        picks.append((candidates[best], group))

    picks.sort(key=lambda x: x[0].get("rumor_score", 0), reverse=True)
    if not picks:
        return {
            "title": "(no candidates)",
            "summary": "No relevant items were available for this domain.",
            "rationale": "Insufficient input.",
            "confidence": 0.5,
            "sources": []
        }

    top, group = picks[0]
    title = top["title"]
    snippet = top.get("summary", "")
    rationale = _rationale(f"{title} {snippet}")
    confidence = _confidence_from_rumor(top.get("rumor_score", 0.0))

    seen_titles = set()
    sources = []
    for g in group:
        if g["title"] in seen_titles:
            continue
        seen_titles.add(g["title"])
        sources.append({"title": g["title"], "url": g["link"]})
        if len(sources) == 3:
            break

    return {
        "title": title,
        "summary": _make_summary(title, snippet),
        "rationale": rationale,
        "confidence": confidence,
        "sources": sources
    }
