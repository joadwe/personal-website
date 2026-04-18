#!/usr/bin/env python3
"""
Fetch new publications from Google Scholar and append them to publications.md.

Design principles:
- ADDITIVE ONLY: existing entries are never modified or removed.
- Matching is done by DOI (primary) and title fuzzy-match (fallback).
- New publications are inserted under the correct year heading.
- The chart data-attribute is updated to reflect new counts.
- Manual entries (patents, chapters, custom edits) are fully preserved.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

from scholarly import scholarly

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCHOLAR_ID = os.environ.get("SCHOLAR_ID", "DzpMNxoAAAAJ")
PUBS_FILE = Path(__file__).resolve().parent.parent / "docs" / "publications.md"
TITLE_SIMILARITY_THRESHOLD = 0.85  # fuzzy match threshold for title comparison
MAX_RETRIES = 3
RETRY_DELAY = 30  # seconds

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def normalize_title(title: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    title = re.sub(r"[^\w\s]", "", title.lower())
    return " ".join(title.split())


def extract_doi(text: str) -> str | None:
    """Extract a DOI from a string (case-insensitive)."""
    m = re.search(r"10\.\d{4,9}/[^\s\]\)\"'>]+", text, re.IGNORECASE)
    return m.group(0).rstrip(".,;") if m else None


def titles_match(a: str, b: str) -> bool:
    """Check if two titles are similar enough to be the same publication."""
    na, nb = normalize_title(a), normalize_title(b)
    if na == nb:
        return True
    return SequenceMatcher(None, na, nb).ratio() >= TITLE_SIMILARITY_THRESHOLD


# ---------------------------------------------------------------------------
# Parse existing publications
# ---------------------------------------------------------------------------
def parse_existing_publications(md_text: str) -> tuple[set[str], list[str]]:
    """
    Return (set of lowercase DOIs, list of normalized titles) from the
    existing markdown file.
    """
    dois: set[str] = set()
    titles: list[str] = []

    # Extract DOIs
    for m in re.finditer(r"10\.\d{4,9}/[^\s\]\)\"'>]+", md_text, re.IGNORECASE):
        dois.add(m.group(0).rstrip(".,;").lower())

    # Extract bold titles (the **…** pattern used in the file)
    for m in re.finditer(r"\*\*(.+?)\*\*", md_text):
        titles.append(m.group(1))

    return dois, titles


def publication_exists(doi: str | None, title: str, existing_dois: set[str],
                       existing_titles: list[str]) -> bool:
    """Check if a publication already exists by DOI or title match."""
    if doi and doi.lower() in existing_dois:
        return True
    for existing_title in existing_titles:
        if titles_match(title, existing_title):
            return True
    return False


# ---------------------------------------------------------------------------
# Fetch from Google Scholar
# ---------------------------------------------------------------------------
def fetch_scholar_publications() -> list[dict]:
    """Fetch all publications from Google Scholar for the configured author."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.info("Fetching Google Scholar profile (attempt %d/%d)...",
                     attempt, MAX_RETRIES)
            author = scholarly.search_author_id(SCHOLAR_ID)
            author = scholarly.fill(author, sections=["publications"])
            pubs = author.get("publications", [])
            log.info("Found %d publications on Scholar.", len(pubs))
            return pubs
        except Exception as e:
            log.warning("Attempt %d failed: %s", attempt, e)
            if attempt < MAX_RETRIES:
                log.info("Retrying in %d seconds...", RETRY_DELAY)
                time.sleep(RETRY_DELAY)
            else:
                log.error("All %d attempts failed.", MAX_RETRIES)
                raise
    return []


def enrich_publication(pub: dict) -> dict:
    """Fill a publication with full details (including abstract, DOI, etc.)."""
    try:
        return scholarly.fill(pub)
    except Exception as e:
        log.warning("Could not enrich '%s': %s",
                     pub.get("bib", {}).get("title", "?"), e)
        return pub


# ---------------------------------------------------------------------------
# Format a publication entry
# ---------------------------------------------------------------------------
def format_authors(authors: str) -> str:
    """Clean up author string from Scholar."""
    # Scholar sometimes uses 'and' as separator; normalize to commas
    authors = authors.replace(" and ", ", ")
    return authors


def format_publication_entry(pub: dict, entry_number: int) -> str:
    """Format a single Scholar publication into the site's markdown format."""
    bib = pub.get("bib", {})
    title = bib.get("title", "Untitled")
    authors = format_authors(bib.get("author", "Unknown"))
    year = bib.get("pub_year", "Unknown")
    journal = bib.get("journal", bib.get("venue", bib.get("conference", "")))
    volume = bib.get("volume", "")
    number = bib.get("number", "")
    pages = bib.get("pages", "")

    # Build citation details
    details_parts = []
    if journal:
        details_parts.append(f"_{journal}_")
    if volume:
        vol_str = volume
        if number:
            vol_str += f"({number})"
        details_parts.append(vol_str)
    if pages:
        details_parts.append(pages)

    details = ", ".join(details_parts)

    # DOI
    doi = extract_doi(str(pub.get("pub_url", "")))
    if not doi:
        doi = extract_doi(str(bib))
    if not doi:
        # Try the eprint_url or other fields
        doi = extract_doi(str(pub))

    # Build DOI/link portion
    link_parts = []
    if doi:
        link_parts.append(f"doi: {doi}")
        link_parts.append(
            f'[[website](https://doi.org/{doi}){{:target="_blank"}}]')
    elif pub.get("pub_url"):
        url = pub["pub_url"]
        link_parts.append(
            f'[[website]({url}){{:target="_blank"}}]')

    doi_str = " ".join(link_parts)

    # Assemble the full citation line
    citation_parts = [f"{authors}"]
    if year and year != "Unknown":
        citation_parts[0] += f" ({year})"
    citation_parts.append(f"**{title}**")
    if details:
        citation_parts.append(details)
    if doi_str:
        citation_parts.append(doi_str)

    citation = ", ".join(citation_parts)

    return (
        f'<div class="jw-pub-item" data-jw-type="publication" '
        f'data-jw-year="{year}" markdown>\n'
        f"{entry_number}. {citation}\n"
        f"</div>"
    )


# ---------------------------------------------------------------------------
# Inject entries into the markdown
# ---------------------------------------------------------------------------
def get_year_sections(md_text: str) -> dict[str, int]:
    """
    Map year → line index of the '## YYYY' heading in the markdown.
    """
    sections: dict[str, int] = {}
    for i, line in enumerate(md_text.splitlines()):
        m = re.match(r"^## (\d{4})\s*$", line)
        if m:
            sections[m.group(1)] = i
    return sections


def find_last_pub_number(md_text: str) -> int:
    """Find the highest publication number currently in the file."""
    numbers = [int(n) for n in re.findall(
        r'data-jw-type="publication"[^>]*>\s*(\d+)\.', md_text)]
    return max(numbers) if numbers else 0


def count_pubs_per_year(md_text: str) -> Counter:
    """Count existing publications (all types) per year from the markdown."""
    counts: Counter = Counter()
    for m in re.finditer(r'data-jw-year="(\d{4})"', md_text):
        counts[m.group(1)] += 1
    return counts


def update_chart_data(md_text: str, year_counts: Counter) -> str:
    """Update the chart data-jw-chart attribute with new counts."""
    # Find the existing chart data
    chart_match = re.search(
        r"data-jw-chart='(\{[^']+\})'", md_text
    )
    if not chart_match:
        return md_text

    try:
        chart_data = json.loads(chart_match.group(1))
    except json.JSONDecodeError:
        return md_text

    labels = chart_data.get("labels", [])
    values = chart_data.get("values", [])

    # Build a map of existing chart data
    chart_map = dict(zip(labels, values))

    # Update with actual counts
    for year, count in year_counts.items():
        chart_map[year] = count

    # Sort by year
    sorted_years = sorted(chart_map.keys())
    new_labels = sorted_years
    new_values = [chart_map[y] for y in sorted_years]

    new_chart = json.dumps({"labels": new_labels, "values": new_values})
    new_attr = f"data-jw-chart='{new_chart}'"
    md_text = md_text.replace(chart_match.group(0), new_attr)
    return md_text


def insert_new_publications(md_text: str, new_pubs: list[dict]) -> str:
    """
    Insert new publications into the correct year sections.
    Returns the updated markdown text.
    """
    if not new_pubs:
        return md_text

    lines = md_text.splitlines()
    next_number = find_last_pub_number(md_text) + 1
    insertions: dict[str, list[str]] = {}  # year → list of formatted entries

    for pub in new_pubs:
        bib = pub.get("bib", {})
        year = str(bib.get("pub_year", "Unknown"))
        if year == "Unknown":
            continue

        entry = format_publication_entry(pub, next_number)
        insertions.setdefault(year, []).append(entry)
        next_number += 1

    year_sections = get_year_sections(md_text)

    # Process years from newest to oldest (insert from bottom up to preserve
    # line indices)
    for year in sorted(insertions.keys(), reverse=True):
        entries_text = "\n\n".join(insertions[year])

        if year in year_sections:
            # Find the insertion point: right after the heading + any blank line
            heading_idx = year_sections[year]
            insert_idx = heading_idx + 1
            # Skip blank lines after heading
            while insert_idx < len(lines) and lines[insert_idx].strip() == "":
                insert_idx += 1
            # Insert the new entries before existing entries for this year
            new_block = entries_text + "\n\n"
            lines.insert(insert_idx, new_block)
        else:
            # Need to create a new year section.
            # Find where to insert it (before the first year that is older).
            sorted_existing = sorted(year_sections.keys(), reverse=True)
            insert_before_year = None
            for ey in sorted_existing:
                if int(ey) < int(year):
                    insert_before_year = ey
                    break

            if insert_before_year:
                insert_idx = year_sections[insert_before_year]
            else:
                # Insert at end of file
                insert_idx = len(lines)

            new_section = f"## {year}\n\n{entries_text}\n"
            lines.insert(insert_idx, new_section)

        # Recalculate sections since line indices shifted
        md_text = "\n".join(lines)
        lines = md_text.splitlines()
        year_sections = get_year_sections(md_text)

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    if not PUBS_FILE.exists():
        log.error("Publications file not found: %s", PUBS_FILE)
        return 1

    md_text = PUBS_FILE.read_text(encoding="utf-8")

    # 1. Parse existing entries
    existing_dois, existing_titles = parse_existing_publications(md_text)
    log.info("Found %d existing DOIs, %d existing titles.",
             len(existing_dois), len(existing_titles))

    # 2. Fetch from Scholar
    scholar_pubs = fetch_scholar_publications()

    # 3. Filter to only new publications
    new_pubs = []
    for pub in scholar_pubs:
        bib = pub.get("bib", {})
        title = bib.get("title", "")
        if not title:
            continue

        # Check pub_url or bib for DOI
        doi = extract_doi(str(pub.get("pub_url", "")))
        if not doi:
            doi = extract_doi(str(bib))

        if publication_exists(doi, title, existing_dois, existing_titles):
            log.debug("Skipping (already exists): %s", title[:60])
            continue

        # Enrich to get full details
        enriched = enrich_publication(pub)
        enriched_bib = enriched.get("bib", {})
        enriched_doi = extract_doi(str(enriched))
        enriched_title = enriched_bib.get("title", title)

        # Re-check after enrichment (DOI might now be available)
        if publication_exists(enriched_doi, enriched_title,
                              existing_dois, existing_titles):
            log.debug("Skipping after enrichment (already exists): %s",
                       enriched_title[:60])
            continue

        log.info("NEW: %s", enriched_title[:80])
        new_pubs.append(enriched)

    if not new_pubs:
        log.info("No new publications found. File unchanged.")
        return 0

    log.info("Found %d new publication(s) to add.", len(new_pubs))

    # 4. Insert into markdown
    updated_md = insert_new_publications(md_text, new_pubs)

    # 5. Update chart data
    year_counts = count_pubs_per_year(updated_md)
    updated_md = update_chart_data(updated_md, year_counts)

    # 6. Write back
    PUBS_FILE.write_text(updated_md, encoding="utf-8")
    log.info("Updated %s with %d new publication(s).", PUBS_FILE.name,
             len(new_pubs))

    return 0


if __name__ == "__main__":
    sys.exit(main())
