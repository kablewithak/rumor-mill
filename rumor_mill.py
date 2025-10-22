import argparse
import pathlib
import datetime
import json

from dotenv import load_dotenv
from tqdm import tqdm

from collectors import collect_from_sources
from ranker import score_and_dedupe, filter_by_domain
from agent import pick_one, cluster_for_trace
from formatter import to_markdown
from config import DOMAINS, MAX_ITEMS


def main():
    load_dotenv()

    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="today", help="today or YYYY-MM-DD")
    ap.add_argument("--domains", nargs="*", default=["ai", "finance", "science"])
    ap.add_argument("--dry-run", action="store_true", help="run everything but do not write files")
    ap.add_argument("--verbose", action="store_true", help="extra logs (counts + sample titles)")
    ap.add_argument("--log-file", default=None, help="optional: write a run log to this file")
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
            pick = pick_one(d, scored)
            picks[d] = pick

        except Exception as e:
            log(f"[{d}] ERROR: {e}")
            continue

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
