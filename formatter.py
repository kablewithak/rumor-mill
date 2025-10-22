from typing import Dict, Optional

def to_markdown(picks: Dict[str, Dict], date: Optional[str] = None) -> str:
    header = f"# Rumor Mill — Daily Digest ({date})\n" if date else "# Rumor Mill — Daily Digest\n"
    lines = [header]

    for domain in ("ai", "finance", "science"):
        p = picks.get(domain)
        if not p:
            continue

        srcs = p.get("sources") or []
        count = len(srcs)

        lines.append(f"## {domain.upper()}")

        title = p.get("title", "(no title)")
        conf = float(p.get("confidence", 0.0))
        lines.append(f"**{title}**  *(Confidence: {conf:.2f})*")

        summary = p.get("summary")
        if summary:
            lines.append(summary)

        rationale = p.get("rationale")
        if rationale:
            lines.append(f"*Why it looks like a rumor:* {rationale}")

        if count:
            bullets = "\n".join(
                f"- [{s.get('title','link')}]({s.get('url','')})" for s in srcs[:3]
            )
            lines.append(f"Sources: {count} link{'s' if count != 1 else ''}.\n{bullets}")

        lines.append("")

    return "\n".join(lines)
