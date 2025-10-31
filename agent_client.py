from abc import ABC, abstractmethod
from typing import List, Dict, Any

class AgentClient(ABC):
    @abstractmethod
    def choose(self, domain: str, items: list, k: int = 3) -> List[Dict[str, Any]]:
        """Return up to k picks as [{'idx': int, 'rationale': str, 'confidence': float}, ...]."""
        ...

class AnthropicAgentClient(AgentClient):
    def __init__(self, model: str, max_tokens: int):
        # Import anthropic lazily to avoid hard dependency at module import time
        from anthropic import Anthropic
        import os
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = model
        self.max_tokens = max_tokens

    def _prompt(self, domain: str, items: list, k: int) -> str:
        def _san(s: str) -> str:
            return (s or "").replace("\n", " ")[:180]
        lines: List[str] = []
        for i, it in enumerate(items):
            t = _san(it.get("title", ""))
            sn = _san(it.get("snippet") or it.get("summary") or "")
            lines.append(f"{i}. {t} || {sn}")
        catalog = "\n".join(lines)
        return (
            "You are selecting RUMOR-LIKE headlines (unconfirmed/early reports) for a daily brief.\n"
            f"Domain: {domain}\n"
            "Return ONLY minified JSON on ONE LINE, no prose.\n"
            f"Pick up to {k} items by their index. Schema:\n"
            '{"picks":[{"idx":INT,"rationale":STRING,"confidence":NUMBER}], "notes":STRING}\n'
            "Confidence must be 0..1 (if not, scale as needed). Prefer diversity and credible sources.\n"
            "CATALOG:\n" + catalog + "\n"
            "OUTPUT:"
        )

    def _extract_json(self, text: str) -> dict:
        """Brace/fence tolerant JSON extractor (no dependency on agent.py to avoid circular import)."""
        import re, json as _json
        if not text:
            return {}
        # Remove fences if present
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I).strip()
        # Try fenced json
        m = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text, re.I)
        if m:
            try:
                return _json.loads(m.group(1).strip())
            except Exception:
                pass
        # Try outermost braces
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start:end+1].strip()
            depth = 0
            for ch in candidate:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth < 0:
                        return {}
            if depth == 0:
                try:
                    return _json.loads(candidate)
                except Exception:
                    return {}
        return {}

    def _normalize_conf(self, x) -> float:
        try:
            v = float(x)
        except Exception:
            return 0.5
        if v > 1 and v <= 10:
            v /= 10.0
        elif v > 10:
            v /= 100.0
        return max(0.0, min(1.0, v))

    def choose(self, domain: str, items: list, k: int = 3) -> List[Dict[str, Any]]:
        from pathlib import Path
        # Build prompt
        prompt = self._prompt(domain, items, k)
        # Call Anthropic
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=0.2,
            system="Return JSON only. One line. No commentary.",
            messages=[{"role":"user","content":prompt}],
        )
        # Collect raw text
        raw = "".join([c.text for c in (getattr(msg, "content", []) or []) if getattr(c, "type", "") == "text"])
        # Save preview for debugging
        Path("artifacts").mkdir(exist_ok=True)
        Path("artifacts/last_agent_raw.txt").write_text(raw or "", encoding="utf-8")

        data = self._extract_json(raw)
        picks = data.get("picks", []) if isinstance(data, dict) else []

        out: List[Dict[str, Any]] = []
        for p in picks[:k]:
            if not isinstance(p, dict):
                continue
            idx = p.get("idx")
            if isinstance(idx, int) and 0 <= idx < len(items):
                out.append({
                    "idx": idx,
                    "rationale": (p.get("rationale") or "").strip(),
                    "confidence": self._normalize_conf(p.get("confidence", 0.5)),
                })
        # de-dup idx, preserve order
        seen = set()
        deduped: List[Dict[str, Any]] = []
        for q in out:
            if q["idx"] in seen:
                continue
            seen.add(q["idx"])
            deduped.append(q)
        return deduped
