# ranker.py
from typing import List, Dict
from config import KEYWORDS, DOMAIN_KEYWORDS, DOMAIN_EXCLUDES, BAD_DOMAINS
from collectors import make_id

def rumor_score(text: str) -> float:
    t = text.lower()
    hits = sum(1 for k in KEYWORDS if k in t)
    return min(1.0, hits / 3.0)  # normalize to 0..1

def _matches_domain(domain: str, text: str) -> bool:
    t = text.lower()
    must = DOMAIN_KEYWORDS.get(domain, [])
    if must and not any(k in t for k in must):
        return False
    bad = DOMAIN_EXCLUDES.get(domain, [])
    if any(k in t for k in bad):
        return False
    return True

def _is_bad(link: str) -> bool:
    if not BAD_DOMAINS:
        return False
    host = (link or "").lower()
    return any(bad in host for bad in BAD_DOMAINS)

def score_and_dedupe(items: List[Dict]) -> List[Dict]:
    """Assign rumor_score and remove duplicates by id."""
    seen = set()
    scored = []
    for it in items:
        if _is_bad(it.get("link", "")):
         continue
        uid = make_id(it)
        if uid in seen:
            continue
        seen.add(uid)
        text = f'{it["title"]} {it.get("summary","")}'
        it["rumor_score"] = rumor_score(text)
        scored.append(it)
    scored.sort(key=lambda x: x["rumor_score"], reverse=True)
    return scored

def filter_by_domain(domain: str, items: List[Dict]) -> List[Dict]:
    """Keep only items whose text matches the domain guard words and not the excludes."""
    out = []
    for it in items:
        text = f'{it["title"]} {it.get("summary","")}'
        if _matches_domain(domain, text):
            out.append(it)
    return out
