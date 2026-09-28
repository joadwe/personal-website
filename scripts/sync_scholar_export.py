#!/usr/bin/env python3
"""Import the local Scholar dashboard export without rewriting curated citations."""

from __future__ import annotations

import argparse
import html
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote, urlsplit


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = ROOT.parent / "google-scholar" / "exports" / "scholar-dashboard.json"
DESTINATION = ROOT / "docs" / "data" / "scholar-dashboard.json"
PUBLICATIONS = ROOT / "docs" / "publications.md"
OVERRIDES = ROOT / "scripts" / "scholar_publication_overrides.json"
SCHOLAR_ID = "DzpMNxoAAAAJ"
ITEM_RE = re.compile(r'<div class="jw-pub-item"[^>]*>.*?</div>', re.S)
TITLE_RE = re.compile(r"\*\*(.+?)\*\*", re.S)
YEAR_RE = re.compile(r"^## (\d{4})\s*$", re.M)
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\]\)\"'>]+", re.I)
CHART_RE = re.compile(r"data-jw-chart='(\{[^']+\})'")
TYPES = {"publication", "preprint", "protocol", "patent"}
JOURNALS = {
    "journal of extracellular vesicles": "J Extracell Vesicles",
    "journal of extracellular biology": "J Extracell Biol",
    "cytometry part a": "Cytometry A",
    "cell reports methods": "Cell Rep Methods",
    "frontiers in immunology": "Front Immunol",
    "current protocols in cytometry": "Curr Protoc Cytom",
}


def timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def validate_export(data: dict) -> None:
    if data.get("schema_version") != 2 or data.get("profile", {}).get("scholar_id") != SCHOLAR_ID:
        raise ValueError("Unexpected Scholar export schema or author ID")
    if not isinstance(data.get("publications"), list) or not isinstance(data.get("citation_history"), list):
        raise ValueError("Scholar export is missing publication or citation data")
    profile = data["profile"]
    if not all(isinstance(profile.get(key), int) and profile[key] >= 0
               for key in ("total_citations", "h_index", "i10_index")):
        raise ValueError("Scholar export has invalid profile metrics")
    timestamp(data["generated_at"])
    timestamp(profile["last_synced"])


def meaningful_data(data: dict) -> dict:
    """Exclude timestamps and internal sync logs so blocked retries do not publish noise."""
    profile = {key: value for key, value in data["profile"].items() if key != "last_synced"}
    return {
        "profile": profile,
        "citation_history": data["citation_history"],
        "publication_counts": data.get("publication_counts"),
        "publications": data["publications"],
    }


def apply_overrides(works: list[dict]) -> list[dict]:
    """Fill known Scholar metadata gaps from reviewed bibliographic records."""
    overrides = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    by_title = {normalized_title(title): fields for title, fields in overrides.items()}
    return [dict(work, **by_title.get(normalized_title(work.get("title") or ""), {})) for work in works]


def normalized_title(title: str) -> str:
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    return " ".join(re.findall(r"[a-z0-9]+", ascii_title.lower()))


def normalized_doi(value: str | None) -> str:
    match = DOI_RE.search(value or "")
    return match.group(0).rstrip(".,;").lower() if match else ""


def same_title(left: str, right: str) -> bool:
    a, b = normalized_title(left), normalized_title(right)
    return bool(a and b) and (a == b or SequenceMatcher(None, a, b).ratio() >= 0.84)


def existing_works(markdown: str) -> tuple[set[str], list[str]]:
    dois, titles = set(), []
    for block in ITEM_RE.findall(markdown):
        title = TITLE_RE.search(block)
        if title:
            titles.append(html.unescape(title.group(1)))
        doi = normalized_doi(block)
        if doi:
            dois.add(doi)
    return dois, titles


def safe_url(value: str | None) -> str:
    parsed = urlsplit(value or "")
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        return ""
    return quote(value or "", safe=":/?#@!$&'(*+,;=%-._~")


def complete_record(work: dict) -> bool:
    """A public citation needs an author, year and a verifiable link."""
    year = work.get("year")
    authors = work.get("authors") or ""
    return (
        isinstance(year, int)
        and 1900 <= year <= datetime.now(timezone.utc).year + 1
        and bool((work.get("title") or "").strip())
        and bool(authors.strip())
        and "welsh" in authors.lower()
        and work.get("website_type") in TYPES
        and bool(safe_url(work.get("pub_url")) or normalized_doi(work.get("doi")))
    )


def author_initials(name: str) -> str:
    words = name.strip().split()
    if len(words) < 2:
        return name.strip()
    surname_start = len(words) - 1
    particles = {"van", "von", "de", "del", "der", "den", "el", "la", "le", "di", "da", "du"}
    while surname_start > 1 and words[surname_start - 1].lower() in particles:
        surname_start -= 1
    given = "".join(word[0].upper() for word in words[:surname_start] if word[0].isalpha())
    return f"{' '.join(words[surname_start:])} {given}" if given else name.strip()


def citation_text(value: str) -> str:
    return html.escape(value, quote=False).replace("*", r"\*").replace("[", r"\[").replace("]", r"\]")


def format_entry(work: dict) -> str:
    pub_type = work["website_type"]
    year = work["year"]
    authors = re.split(r"\s+and\s+", work["authors"], flags=re.I)
    byline = ", ".join(author_initials(name) for name in authors if name.strip())
    title = citation_text(work["title"].strip())
    venue = (work.get("venue") or "").strip()
    venue = JOURNALS.get(venue.lower(), venue)
    doi = normalized_doi(work.get("doi") or work.get("pub_url"))
    url = f"https://doi.org/{doi}" if doi else safe_url(work.get("pub_url"))
    link = f'[[website]({url}){{:target="_blank"}}]'

    if pub_type == "patent":
        parts = [citation_text(byline), f"**{title}**", link]
    else:
        parts = [f"{citation_text(byline)} ({year})", f"**{title}**"]
        if venue:
            parts.append(citation_text(venue))
        if doi and pub_type != "protocol":
            parts.append(f"doi: {doi}")
        parts.append(link)
    return (
        f'<div class="jw-pub-item" data-jw-type="{pub_type}" data-jw-year="{year}" markdown>\n'
        f"1. {', '.join(parts)}\n"
        "</div>"
    )


def insert_entries(markdown: str, entries: dict[int, list[str]]) -> str:
    for year in sorted(entries, reverse=True):
        headings = list(YEAR_RE.finditer(markdown))
        block = "\n\n".join(entries[year])
        existing = next((index for index, match in enumerate(headings) if int(match.group(1)) == year), None)
        if existing is not None:
            end = headings[existing + 1].start() if existing + 1 < len(headings) else len(markdown)
            markdown = markdown[:end].rstrip("\n") + "\n\n" + block + "\n\n" + markdown[end:].lstrip("\n")
        else:
            older = next((match for match in headings if int(match.group(1)) < year), None)
            if older:
                at = older.start()
                markdown = markdown[:at].rstrip("\n") + f"\n\n## {year}\n\n{block}\n\n" + markdown[at:]
            else:
                markdown = markdown.rstrip("\n") + f"\n\n## {year}\n\n{block}\n"
    return markdown.rstrip("\n") + "\n"


def refresh_chart(markdown: str) -> str:
    chart = CHART_RE.search(markdown)
    if not chart:
        raise ValueError("Publication chart data attribute is missing")
    counts = Counter(re.findall(r'data-jw-year="(\d{4})"', markdown))
    labels = sorted(counts)
    value = json.dumps({"labels": labels, "values": [counts[year] for year in labels]})
    return markdown[:chart.start(1)] + value + markdown[chart.end(1):]


def update_publications(markdown: str, works: list[dict]) -> tuple[str, list[str], list[str]]:
    dois, titles = existing_works(markdown)
    additions: dict[int, list[str]] = {}
    added, deferred = [], []
    deferred_keys: set[str] = set()
    # Process complete records first so a sparse duplicate cannot hide a usable one.
    ordered = sorted(works, key=lambda item: (not complete_record(item), -(item.get("year") or 0), item.get("title") or ""))
    for work in ordered:
        title = (work.get("title") or "").strip()
        doi = normalized_doi(work.get("doi") or work.get("pub_url"))
        if not title or (doi and doi in dois) or any(same_title(title, known) for known in titles):
            continue
        if not complete_record(work):
            key = normalized_title(title)
            if key not in deferred_keys:
                deferred.append(title)
                deferred_keys.add(key)
            continue
        additions.setdefault(work["year"], []).append(format_entry(work))
        added.append(title)
        titles.append(title)
        if doi:
            dois.add(doi)
    if additions:
        markdown = insert_entries(markdown, additions)
    return refresh_chart(markdown), added, deferred


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    source = json.loads(args.source.read_text(encoding="utf-8"))
    validate_export(source)
    current = json.loads(DESTINATION.read_text(encoding="utf-8"))
    validate_export(current)
    if timestamp(source["profile"]["last_synced"]) < timestamp(current["profile"]["last_synced"]):
        raise ValueError("Refusing to replace the website with older Scholar profile data")
    if timestamp(source["generated_at"]) < timestamp(current["generated_at"]):
        raise ValueError("Refusing to replace the website with an older export")

    old_markdown = PUBLICATIONS.read_text(encoding="utf-8")
    markdown, added, deferred = update_publications(old_markdown, apply_overrides(source["publications"]))
    snapshot_changed = meaningful_data(source) != meaningful_data(current)
    if not args.dry_run:
        if snapshot_changed:
            DESTINATION.write_text(json.dumps(source, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if markdown != old_markdown:
            PUBLICATIONS.write_text(markdown, encoding="utf-8")
    print(f"Scholar snapshot: {'updated' if snapshot_changed else 'unchanged'}; "
          f"publications added: {len(added)}; deferred for incomplete metadata: {len(deferred)}")
    for title in added:
        print(f"  added: {title}")
    for title in deferred:
        print(f"  deferred: {title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
