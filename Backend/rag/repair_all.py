"""Import every unique dataset source, checkpointing repairs and a review report."""
import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time

from rag.source_import import (
    DEFAULT_CSV_PATH, DEFAULT_REPAIRS_PATH, SourceImportError,
    apply_repair, atomic_write, fetch_html, load_repairs, repair_sources,
)

DEFAULT_REPORT_PATH = DEFAULT_REPAIRS_PATH.with_name("source_repair_report.json")


def repair_all(csv_path=DEFAULT_CSV_PATH, *, repairs_path=DEFAULT_REPAIRS_PATH,
               report_path=DEFAULT_REPORT_PATH, apply=False, refresh=False,
               delay=2.0, limit=None, fetcher=fetch_html, sleeper=time.sleep,
               progress=None):
    """Resume from persisted repairs; failed imports are retried on the next run.

    Preview never marks a recipe repaired. Refresh explicitly re-fetches existing
    repairs. Reports describe this run and are atomically checkpointed per recipe.
    """
    if not math.isfinite(delay) or delay < 0:
        raise ValueError("delay must be a finite nonnegative number")
    if limit is not None and limit < 1:
        raise ValueError("limit must be positive")
    paths = [Path(p).resolve() for p in (csv_path, repairs_path, report_path)]
    if len(set(paths)) != len(paths):
        raise ValueError("CSV, repairs, and report must use different paths")
    with Path(csv_path).open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    by_url = {}
    for row in rows:
        by_url.setdefault(row.get("url", "").strip(), []).append(row)
    repairs = load_repairs(repairs_path)
    report = {"version": 1, "started_at": datetime.now(timezone.utc).isoformat(),
              "mode": "apply" if apply else "preview", "complete": False,
              "total_sources": len(by_url), "attempted": 0, "results": []}

    def checkpoint():
        report["counts"] = {}
        for item in report["results"]:
            status = item["status"]
            report["counts"][status] = report["counts"].get(status, 0) + 1
        atomic_write(report_path, json.dumps(report, indent=2, ensure_ascii=False) + "\n")

    checkpoint()
    for url, grouped_rows in by_url.items():
        row = grouped_rows[0]
        if not url or len({r["recipe_name"].strip().casefold() for r in grouped_rows}) != 1:
            item = {"url": url, "status": "unverified",
                    "reason": "Missing URL or conflicting dataset titles for the same URL"}
        elif not refresh and url in repairs:
            # Only trust resumable entries whose data and recipe identity validate.
            entry = repairs[url]
            apply_repair(row, repairs)
            if entry.get("recipe_name") != row["recipe_name"] or entry.get("source_url") != url:
                raise SourceImportError(f"Persisted repair identity mismatch: {url}")
            item = {"url": url, "status": "skipped", "reason": "Already repaired"}
        else:
            if limit is not None and report["attempted"] >= limit:
                break
            if report["attempted"]:
                sleeper(delay)
            report["attempted"] += 1
            # Single-source calls persist each success before moving to the next URL.
            item = repair_sources(csv_path, [url], repairs_path=repairs_path,
                                  apply=apply, fetcher=fetcher)[0]
        report["results"].append({"recipe_name": row.get("recipe_name", ""), **item})
        checkpoint()
        if progress:
            progress(report["results"][-1])
    report["complete"] = len(report["results"]) == len(by_url)
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    checkpoint()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--repairs", type=Path, default=DEFAULT_REPAIRS_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--apply", action="store_true", help="Save successful repairs; default is preview")
    parser.add_argument("--refresh", action="store_true", help="Re-fetch even previously repaired sources")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds between source requests (default: 2)")
    parser.add_argument("--limit", type=int, help="Maximum source requests for a trial run")
    args = parser.parse_args()
    try:
        report = repair_all(args.csv, repairs_path=args.repairs, report_path=args.report,
                            apply=args.apply, refresh=args.refresh, delay=args.delay, limit=args.limit,
                            progress=lambda item: print(f"{item['status']}: {item['recipe_name']}", flush=True))
    except KeyboardInterrupt:
        print("Interrupted. Completed repairs are saved; rerun the same command to resume.")
        return 130
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Repair failed: {exc}\n")
    print(json.dumps({"complete": report["complete"], "counts": report["counts"],
                      "report": str(args.report)}, indent=2))
    return 1 if report["counts"].get("unverified") else 0


if __name__ == "__main__":
    raise SystemExit(main())
