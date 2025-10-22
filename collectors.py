import feedparser, hashlib, time, re, html
from typing import List, Dict

_tag_re = re.compile(r"<[^>]+>")
_ws_re = re.compile(r"\s+")

def _strip_html(s: str) -> str:
    if not s:
        return ""
    s = html.unescape(s)              # turn &nbsp; &amp; etc. into real chars
    s = _tag_re.sub(" ", s)           # drop tags
    s = _ws_re.sub(" ", s).strip()    # collapse whitespace
    return s

def fetch_feed(url: str) -> List[Dict]:
    d = feedparser.parse(url)
    items = []
    for e in d.entries[:100]:
        title = getattr(e, "title", "") or ""
        link = getattr(e, "link", "") or ""
        summary = getattr(e, "summary", "") or ""
        if not title or not link:
            continue
        items.append({
            "title": title.strip(),
            "link": link.strip(),
            "summary": _strip_html(summary),
            "published": getattr(e, "published", ""),
            "source": (getattr(d, "feed", {}) or {}).get("title", url)
        })
    return items

def collect_from_sources(urls: List[str], cap: int) -> List[Dict]:
    out = []
    for u in urls:
        out.extend(fetch_feed(u))
        time.sleep(0.3)  # be polite
    return out[:cap]

def make_id(item: Dict) -> str:
    return hashlib.md5((item["title"] + item["link"]).encode()).hexdigest()
