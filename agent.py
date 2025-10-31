import os
import re
from typing import List, Dict, Any
import json as _json
import re as _re
from config import KEYWORDS, SUPPRESS_DUP_SUMMARY

try:
    import anthropic  # Anthropic SDK
except Exception:
    anthropic = None

from dotenv import load_dotenv
load_dotenv()

from agent_client import AnthropicAgentClient


def _extract_json(text: str) -> str:
    if not text:
        return ""
    m = _re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text, _re.I)
    if m:
        return m.group(1).strip()

    start = text.find("{")
    end   = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return ""

    candidate = text[start:end+1].strip()

    depth = 0
    for ch in candidate:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return ""
    if depth != 0:
        return ""

    return candidate



ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")

def _anthropic_client():
    if not anthropic or not ANTHROPIC_API_KEY:
        return None
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)



def _tokens(s: str) -> set:
    s = re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower())
    return {w for w in s.split() if len(w) > 2}

def _overlap(a: set, b: set) -> float:
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
    def _host(url: str) -> str:
        m = re.search(r"https?://([^/]+)", (url or "").lower())
        return m.group(1) if m else ""

    candidates = items[:12]
    title_tokens = [_tokens(it["title"]) for it in candidates]

    clusters, reps = [], []
    for i, tok_i in enumerate(title_tokens):
        placed = False
        for idx, rep in enumerate(reps):
            if _overlap(tok_i, title_tokens[rep]) >= 0.6:
                clusters[idx].append(i)
                placed = True
                break
        if not placed:
            clusters.append([i])
            reps.append(i)

    out = []
    for cluster in clusters:
        rep_idx = max(cluster, key=lambda j: candidates[j].get("rumor_score", 0.0))
        group = [candidates[j] for j in cluster]
        rep = candidates[rep_idx]
        out.append(
            {
                "rep": {
                    "title": rep["title"],
                    "url": rep.get("link", ""),
                    "host": _host(rep.get("link", "")),
                },
                "members": [
                    {
                        "title": g["title"],
                        "url": g.get("link", ""),
                        "host": _host(g.get("link", "")),
                    }
                    for g in group
                ],
            }
        )
    return out



def _make_summary(title: str, snippet: str) -> str:
    t_clean = _strip_site(title).rstrip(".")
    s_first = _first_sentence(_strip_site(snippet))

    if SUPPRESS_DUP_SUMMARY and s_first:
        t60 = t_clean.lower()[:60]
        sf = s_first.lower()
        if sf.startswith(t60) or t_clean.lower() in sf:
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



def _heuristic_pick_one(domain: str, scored_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not scored_items:
        return {
            "title": "(no candidates)",
            "summary": "No relevant items were available for this domain.",
            "rationale": "Insufficient input.",
            "confidence": 0.5,
            "sources": [],
        }

    top = max(scored_items, key=lambda it: it.get("rumor_score", 0.0))
    title = top.get("title", "(untitled)")
    snippet = top.get("summary", "")
    rationale = _rationale(f"{title} {snippet}")
    confidence = _confidence_from_rumor(top.get("rumor_score", 0.0))

    seen, sources = set(), []
    top_host = ""
    m = re.search(r"https?://([^/]+)", (top.get("link", "") or "").lower())
    if m:
        top_host = m.group(1)

    for g in scored_items:
        if g.get("title") in seen:
            continue
        same_host = False
        gm = re.search(r"https?://([^/]+)", (g.get("link", "") or "").lower())
        if gm and top_host and gm.group(1) == top_host:
            same_host = True
        similar = _jaccard(title, g.get("title", "")) >= 0.5
        if same_host or similar:
            seen.add(g["title"])
            sources.append({"title": g["title"], "url": g.get("link", "")})
        if len(sources) == 3:
            break

    return {
        "title": title,
        "summary": _make_summary(title, snippet),
        "rationale": rationale,
        "confidence": confidence,
        "sources": sources or [{"title": title, "url": top.get("link", "")}],
    }



def _ask_claude(system: str, user: str, max_tokens: int = 120) -> str:
    """
    Call Anthropic; return the concatenated text blocks.
    If SDK/reply is odd, return a JSON-stringified fallback so _extract_json can still try.
    """
    client = _anthropic_client()
    if not client:
        return ""

    try:
        resp = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            temperature=0.2,
        )
    except Exception as e:
        print(f"[agent] Anthropic error: {e}")
        return ""

    texts = []
    for block in getattr(resp, "content", []) or []:
        t = getattr(block, "text", None)
        if t:
            texts.append(t)

    if texts:
        return "\n".join(texts).strip()

    try:
        return _json.dumps(resp.__dict__, default=str)
    except Exception:
        return ""



def pick_one(domain: str, scored_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Ask Claude to choose one item via index; we build the final object locally.
    """
    if not scored_items:
        return {
            "title": "(no candidates)",
            "summary": "No relevant items were available for this domain.",
            "rationale": "Insufficient input.",
            "confidence": 0.5,
            "sources": [],
        }

    plan_prompt = (
        "You are a rumors analyst. Given a list of recent items (title + source + snippet), "
        "choose ONE that best fits 'rumor-ish' (leak, reportedly, insider) for the domain. "
        "Prefer recent, credible sources; avoid low-signal mirror spam."
    )

    # Provide compact list with indices so the model can choose succinctly
    lines = []
    for i, it in enumerate(scored_items[:15]):
        t = (it.get('title') or '')[:180].replace('\n',' ')
        s = (it.get('summary') or '')[:180].replace('\n',' ')
        lines.append(f"{i}. {t}  ||  {s}")
    user = f"Domain: {domain}\nItems (index. title || snippet):\n" + "\n".join(lines)

    # Tiny JSON schema: index + rationale + confidence
    agent_json = _ask_claude(
        system=(
            "Return ONLY a single minified JSON object on ONE LINE. No prose, no code fences.\n"
            'Schema: {"idx": number, "rationale": string, "confidence": number}\n'
            "Use regular ASCII quotes (\"). idx must be an integer 0..14."
        ),
        user=plan_prompt + "\n\n" + user,
        max_tokens=int(os.getenv("MAX_AGENT_TOKENS_CHOOSE", "120")),
    )

    print("[agent] preview:", (agent_json or "")[:200].replace("\n", " "))

    # ---- Parse agent JSON safely -------------------------------------------
    clean = (agent_json or "").strip()
    if clean.startswith("```"):
        clean = _re.sub(r"^```(?:json)?\s*|\s*```$", "", clean, flags=_re.I).strip()

    payload = _extract_json(clean) or (clean if clean.startswith("{") and clean.endswith("}") else "")

    try:
        if not payload:
            raise ValueError("no json payload")
        msg = _json.loads(payload)

        # normalise confidence to 0..1
        raw_conf = msg.get("confidence", 0.7)
        try:
            conf = float(raw_conf)
        except Exception:
            conf = 0.7
        if conf > 1.0:
            conf = conf / 10.0 if conf <= 10 else conf / 100.0
        conf = max(0.0, min(1.0, conf))

        rationale = (msg.get("rationale") or "").strip()

        # index-based OR explicit fields
        idx = None
        if "idx" in msg:
            try:
                idx = int(msg["idx"])
            except Exception:
                idx = None

        if idx is not None and 0 <= idx < len(scored_items):
            chosen  = scored_items[idx]
            title   = chosen.get("title", "(untitled)")
            snippet = chosen.get("summary", "")
            sources = [{"title": title or "link", "url": chosen.get("link","")}]
        else:
            title   = (msg.get("title") or "(untitled)").strip()
            snippet = ""
            srcs    = msg.get("sources") or []
            sources = []
            for s in srcs[:3]:
                t = (s.get("title") or "link").strip()
                u = (s.get("url") or "").strip()
                if u:
                    sources.append({"title": t, "url": u})
            if not sources:
                sources = [{"title": title or "link", "url": ""}]

        pick = {
            "title": title,
            "summary": _make_summary(title, snippet),
            "rationale": rationale or _rationale(f"{title} {snippet}"),
            "confidence": conf,
            "sources": sources,
        }

        print(f"[agent] used Claude for domain={domain}")
        return pick

    except Exception as e:
        print(f"[agent] JSON parse failed → fallback: {e}")
        return _heuristic_pick_one(domain, scored_items)

# === Agent adapter entrypoint (Anthropic transport today; Claude-agent-sdk later) ===
def choose_with_agent(domain: str, candidates: list, k: int = 3):
    """
    Use AnthropicAgentClient to select up to k items.
    Returns: [{'idx': int, 'rationale': str, 'confidence': float}, ...]
    """
    import os
    model = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
    max_tok = int(os.getenv("MAX_AGENT_TOKENS_CHOOSE", "120"))

    client = AnthropicAgentClient(model=model, max_tokens=max_tok)
    picks = client.choose(domain=domain, items=candidates, k=k)

    # Defensive: ensure structure & bounds
    out = []
    for p in (picks or [])[:k]:
        if not isinstance(p, dict):
            continue
        idx = p.get("idx")
        if isinstance(idx, int) and 0 <= idx < len(candidates):
            out.append({
                "idx": idx,
                "rationale": (p.get("rationale") or "").strip(),
                "confidence": float(p.get("confidence", 0.5)),
            })
    return out

