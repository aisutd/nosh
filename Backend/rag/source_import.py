"""Repair recipe records from publisher JSON-LD; preview by default.

Run from Backend: python -m rag.source_import --url URL
Add --apply to persist successful imports. Blocked/ambiguous pages are reported,
never guessed. --html PATH reads a saved publisher page for a single URL.
"""
import argparse
import csv
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import ssl
import tempfile
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import certifi
from rag.store import DEFAULT_CSV_PATH

DEFAULT_REPAIRS_PATH = DEFAULT_CSV_PATH.with_name("source_repairs.json")
MAX_PAGE_BYTES = 5_000_000


class SourceImportError(ValueError):
    pass


class StructuredDataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.blocks = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            kind = dict(attrs).get("type", "").split(";", 1)[0].strip().lower()
            if kind == "application/ld+json":
                self.current = []

    def handle_data(self, data):
        if self.current is not None:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.current is not None:
            self.blocks.append("".join(self.current))
            self.current = None


class PlainTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag in {"br", "p", "li", "div"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"p", "li", "div"}:
            self.parts.append(" ")


def clean_text(value):
    if not isinstance(value, str):
        raise SourceImportError("Expected text in recipe data")
    parser = PlainTextParser()
    parser.feed(value)
    text = re.sub(r"\s+", " ", unescape("".join(parser.parts))).strip()
    if not text:
        raise SourceImportError("Empty recipe text")
    return text


def has_type(node, name):
    kinds = node.get("@type", [])
    if isinstance(kinds, str):
        kinds = [kinds]
    return isinstance(kinds, list) and any(
        isinstance(kind, str) and kind.rstrip("/").split("/")[-1] == name for kind in kinds)


def recipe_nodes(value):
    if isinstance(value, list):
        for node in value:
            yield from recipe_nodes(node)
    elif isinstance(value, dict):
        if has_type(value, "Recipe"):
            yield value
        else:
            for child in value.values():
                if isinstance(child, (dict, list)):
                    yield from recipe_nodes(child)


def flatten_items(value, *, instructions=False):
    """Traverse every section in order; reject unsupported entries, not skip them."""
    if isinstance(value, str):
        return [clean_text(line) for line in value.splitlines() if line.strip()]
    if isinstance(value, list):
        if not value:
            raise SourceImportError("Empty ingredient or instruction group")
        return [line for item in value for line in flatten_items(item, instructions=instructions)]
    if isinstance(value, dict):
        if "itemListElement" in value:
            return flatten_items(value["itemListElement"], instructions=instructions)
        if "item" in value:
            return flatten_items(value["item"], instructions=instructions)
        if instructions and has_type(value, "HowToStep") and isinstance(value.get("text"), str):
            return flatten_items(value["text"], instructions=True)
    raise SourceImportError("Unsupported ingredient/instruction entry; manual review required")


def extract_recipe(html, expected_name):
    parser = StructuredDataParser()
    parser.feed(html)
    candidates = []
    for block in parser.blocks:
        try:
            decoded = json.loads(block)
        except (ValueError, TypeError):
            continue
        for node in recipe_nodes(decoded):
            try:
                if clean_text(node.get("name")).casefold() == clean_text(expected_name).casefold():
                    candidates.append(node)
            except SourceImportError:
                continue
    # Some publishers repeat identical JSON-LD; do not confuse that with two recipes.
    candidates = list({json.dumps(n, sort_keys=True): n for n in candidates}.values())
    if len(candidates) != 1:
        raise SourceImportError("Expected one structured recipe matching the stored title")
    node = candidates[0]
    ingredients = flatten_items(node.get("recipeIngredient"))
    directions = flatten_items(node.get("recipeInstructions"), instructions=True)
    if not ingredients or not directions:
        raise SourceImportError("Source has no usable ingredients or directions")
    # Never deduplicate: sugar, water, etc. can be measured separately per section.
    return {"ingredient_lines": ingredients, "instruction_steps": directions}


def fetch_html(url):
    parsed = urlsplit(url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username:
        raise SourceImportError("Expected a public HTTP(S) recipe URL")
    request = Request(url, headers={"User-Agent": "NOSH-Recipe-Import/1.0", "Accept": "text/html"})
    context = ssl.create_default_context(cafile=certifi.where())
    with urlopen(request, timeout=30, context=context) as response:
        data = response.read(MAX_PAGE_BYTES + 1)
        if len(data) > MAX_PAGE_BYTES:
            raise SourceImportError("Source page exceeds size limit")
        return data.decode(response.headers.get_content_charset() or "utf-8")


def load_repairs(path=DEFAULT_REPAIRS_PATH):
    path = Path(path)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("recipes"), dict):
        raise SourceImportError("Unsupported source repair file")
    return data["recipes"]


def apply_repair(row, repairs):
    """Shared by preprocessing and indexing so a dataset refresh keeps repairs."""
    row = dict(row)
    repair = repairs.get(str(row.get("url", "")).strip())
    if repair:
        for field in ("ingredient_lines", "instruction_steps"):
            if not isinstance(repair.get(field), list) or not repair[field] or not all(
                isinstance(value, str) and value.strip() for value in repair[field]
            ):
                raise SourceImportError("Invalid persisted source repair")
        row["ingredients"] = ", ".join(repair["ingredient_lines"])
        row["directions"] = "\n".join(repair["instruction_steps"])
    row["chunk"] = (f"Recipe: {row['recipe_name']}\nIngredients: {row['ingredients']}\n"
                    f"Directions: {row['directions']}")
    return row


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".source-import-", delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def repair_sources(csv_path, urls, *, repairs_path=DEFAULT_REPAIRS_PATH, apply=False, fetcher=fetch_html):
    with Path(csv_path).open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    by_url = {}
    for row in rows:
        by_url.setdefault(row.get("url", "").strip(), row)
    repairs = load_repairs(repairs_path)
    report = []
    for url in dict.fromkeys(urls):
        if url not in by_url:
            report.append({"url": url, "status": "unverified", "reason": "URL is not in the dataset"})
            continue
        row = by_url[url]
        try:
            extracted = extract_recipe(fetcher(url), row["recipe_name"])
            entry = {**extracted, "recipe_name": row["recipe_name"], "source_url": url,
                     "imported_at": datetime.now(timezone.utc).isoformat()}
            changed = any(repairs.get(url, {}).get(k) != extracted[k] for k in extracted)
            if changed:
                repairs[url] = entry
            report.append({"url": url, "status": "updated" if apply and changed else "preview" if changed else "unchanged",
                           "old_ingredients": row["ingredients"], **extracted})
        except (SourceImportError, URLError, OSError, UnicodeError, RecursionError) as exc:
            report.append({"url": url, "status": "unverified", "reason": str(exc)})
            if isinstance(exc, HTTPError):
                exc.close()
    if apply and any(item["status"] == "updated" for item in report):
        atomic_write(repairs_path, json.dumps({"version": 1, "recipes": repairs}, indent=2, ensure_ascii=False) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--repairs", type=Path, default=DEFAULT_REPAIRS_PATH)
    parser.add_argument("--url", action="append", required=True, help="Dataset source URL; repeat for multiple recipes")
    parser.add_argument("--html", type=Path, help="Saved source HTML, for one URL only")
    parser.add_argument("--apply", action="store_true", help="Persist successful imports; otherwise preview only")
    args = parser.parse_args()
    if args.html and len(args.url) != 1:
        parser.error("--html requires exactly one --url")
    fetcher = fetch_html
    if args.html:
        if args.html.stat().st_size > MAX_PAGE_BYTES:
            parser.error("Source page exceeds size limit")
        html = args.html.read_text(encoding="utf-8")
        fetcher = lambda url: html
    report = repair_sources(args.csv, args.url, repairs_path=args.repairs, apply=args.apply, fetcher=fetcher)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if any(item["status"] == "unverified" for item in report) else 0


if __name__ == "__main__":
    raise SystemExit(main())
