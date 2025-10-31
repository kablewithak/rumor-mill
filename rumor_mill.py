import argparse
import pathlib
import datetime
import json
import os

from dotenv import load_dotenv
from tqdm import tqdm

from collectors import collect_from_sources
from ranker import score_and_dedupe, filter_by_domain
from agent import pick_one, cluster_for_trace, choose_with_agent
from formatter import to_markdown
from config import DOMAINS, MAX_ITEMS


def main():
    load_dotenv()

    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="today", help="today or YYYY-MM-DD")
    ap.add_argument("--domains", nargs="*", default=["ai"])
    ap.add_argument("--dry-run", action="store_true", help="run everything but do not write files")
    ap.add_argument("--verbose", action="store_true", help="extra logs (counts + sample titles)")
    ap.add_argument("--log-file", default=None, help="optional: write a run log to this file")
    ap.add_argument("--picks", type=int, default=3, help="Number of AI stories to select (top-k)")
    args = ap.parse_args()

    if args.log_file:
        p = pathlib.Path(args.log_file)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("", encoding="utf-8")

    date = datetime.date.today().isoformat() if args.date == "today" else args.date

    outdir = pathlib.Path("artifacts")
    outdir.mkdir(exist_ok=True)
    outfile = outdir / f"{date}.md"
    jsonfile = outdir / f"{date}.raw.json"
    clustersfile = outdir / f"{date}.clusters.json"

    def log(msg: str):
        print(msg)
        if args.log_file:
            with open(args.log_file, "a", encoding="utf-8") as f:
                f.write(msg + "\n")

    # === helper: convert agent indices into final objects and compose a single Markdown block ===
    def _materialize_ai_picks(candidates: list, picks_list: list) -> list:
        out = []
        for p in (picks_list or []):
            idx = p.get("idx")
            if not isinstance(idx, int) or idx < 0 or idx >= len(candidates):
                continue
            it = candidates[idx]
            out.append({
                "title": it.get("title", "(untitled)"),
                "summary": it.get("summary") or it.get("snippet") or "",
                "rationale": (p.get("rationale") or "").strip(),
                "confidence": float(p.get("confidence", 0.5)),
                "link": it.get("link", ""),
                "source": it.get("source", ""),
            })
        return out

    picks = {}
    raw_dump = {}
    clusters_dump = {}

    for d in args.domains:
        try:
            urls = DOMAINS.get(d, [])
            if not urls:
                log(f"[{d}] WARNING: no sources configured")
                continue
            raw = []
            for u in tqdm(urls, desc=f"Fetching {d}"):
                raw.extend(
                    collect_from_sources(
                        [u],
                        cap=max(1, MAX_ITEMS // max(1, len(urls)))
                    )
                )

            before = len(raw)
            raw = filter_by_domain(d, raw)
            after = len(raw)
            log(f"[{d}] filtered {before} → {after}")

            if args.verbose:
                for sample in raw[:3]:
                    log(f"  - {sample['title']}")

            raw_dump[d] = raw

            scored = score_and_dedupe(raw)
            clusters_dump[d] = cluster_for_trace(scored)

            use_agent = (os.getenv("USE_AGENT", "").lower() in {"1", "true", "yes", "y"})
            if d == "ai" and use_agent:
                agent_sel = choose_with_agent(domain="ai", candidates=scored, k=args.picks)
                final_ai = _materialize_ai_picks(scored, agent_sel)
                if final_ai:
                    # Compose into a single pick dict so formatter doesn't need changes
                    lines = []
                    total_conf = 0.0
                    for n, it in enumerate(final_ai, 1):
                        title = it["title"]
                        rationale = it.get("rationale", "")
                        conf = float(it.get("confidence", 0.0) or 0.0)
                        link = it.get("link", "")
                        total_conf += conf
                        lines.append(f"{n}. {title} — {rationale} (conf {conf:.2f})  {link}")
                    avg_conf = round(total_conf / max(1, len(final_ai)), 2)
                    picks[d] = {
                        "title": f"AI — Today’s {len(final_ai)} rumors",
                        "summary": "\n".join(lines),
                        "rationale": "Agentic top-k selection composed into a single block.",
                        "confidence": avg_conf,
                        "sources": [{"title": it["title"], "url": it.get("link", "")} for it in final_ai[:3]],
                    }
                else:
                    log(f"[{d}] agent returned no picks; falling back to heuristic")
                    pick = pick_one(d, scored)
                    if pick:
                        picks[d] = pick
            else:
                pick = pick_one(d, scored)
                if pick:
                    picks[d] = pick
                else:
                    log(f"[{d}] WARNING: no representative pick after scoring")

        except Exception as e:
            log(f"[{d}] ERROR: {e}")
            continue
        if not picks:
            log("[fatal] no domains succeeded; exiting 2")
            raise SystemExit(2)

        if not any(bool(v) for v in picks.values()):
            log("[fatal] picks is present but empty-ish; exiting 2")
            raise SystemExit(2)
    
    md = to_markdown(picks, date=date)

    if not args.dry_run:
        outfile.write_text(md, encoding="utf-8")
        jsonfile.write_text(json.dumps(raw_dump, ensure_ascii=False, indent=2), encoding="utf-8")
        clustersfile.write_text(json.dumps(clusters_dump, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"[write] {outfile}")
        log(f"[write] {jsonfile}")
        log(f"[write] {clustersfile}")
    else:
        log("(dry-run: not writing files)")

    print(md)


if __name__ == "__main__":
    main()
