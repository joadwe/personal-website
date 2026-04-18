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

from scholarly import scholarly, ProxyGenerator

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCHOLAR_ID = os.environ.get("SCHOLAR_ID", "DzpMNxoAAAAJ")
PUBS_FILE = Path(__file__).resolve().parent.parent / "docs" / "publications.md"
TITLE_SIMILARITY_THRESHOLD = 0.85  # fuzzy match threshold for title comparison
MAX_RETRIES = 3
RETRY_DELAY = 30  # seconds


def setup_proxy() -> None:
    """Configure a proxy to avoid Google Scholar rate-limiting."""
    pg = ProxyGenerator()

    # Option 1: Use ScraperAPI if a key is provided (most reliable)
    scraper_key = os.environ.get("SCRAPER_API_KEY")
    if scraper_key:
        log.info("Using ScraperAPI proxy.")
        pg.ScraperAPI(scraper_key)
        scholarly.use_proxy(pg)
        return

    # Option 2: Use free rotating proxies
    log.info("Using FreeProxy (no ScraperAPI key set).")
    success = pg.FreeProxies()
    if success:
        scholarly.use_proxy(pg)
    else:
        log.warning("FreeProxy setup failed; proceeding without proxy.")

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

# Journal abbreviation map — add entries as needed
JOURNAL_ABBREVS: dict[str, str] = {
    "journal of extracellular vesicles": "J Extracell Vesicles",
    "journal of extracellular biology": "J Extracell Biol",
    "cytometry part a": "Cytometry A",
    "cell reports methods": "Cell Rep Methods",
    "nano letters": "Nano Lett",
    "journal of thrombosis and haemostasis": "J Thromb Haemost",
    "frontiers in cellular and developmental biology": "Front Cell Dev Biol",
    "frontiers in immunology": "Front Immunol",
    "lab on a chip": "Lab Chip",
    "nanoscale": "Nanoscale",
    "current protocols in cytometry": "Curr Protoc Cytom",
    "plos pathogens": "PLoS Pathog",
    "neuro-oncology": "Neuro Oncol",
    "journal of leukocyte biology": "J Leukoc Biol",
    "sensors": "Sensors (Basel)",
    "biosensors": "Biosensors (Basel)",
    "viruses": "Viruses",
    "iscience": "iScience",
    "bioinformatics": "Bioinformatics",
    "cell": "Cell",
    "journal of clinical investigation": "J Clin Invest",
    "extracellular vesicles and circulating nucleic acids": "Extracell Vesicles Circ Nucleic Acids",
}


def abbreviate_journal(journal: str) -> str:
    """Try to abbreviate a journal name using the lookup table."""
    key = journal.strip().lower()
    return JOURNAL_ABBREVS.get(key, journal)


def name_to_initials(full_name: str) -> str:
    """
    Convert 'Joshua Aden Welsh' → 'Welsh JA'.
    Handles particles like 'van der Pol', 'de Rond', etc.
    """
    full_name = full_name.strip()
    if not full_name:
        return full_name

    # If already in 'LastName IN' format (no lowercase first-name-length words
    # at the start), return as-is
    parts = full_name.split()
    if len(parts) <= 1:
        return full_name
    if len(parts) == 2 and len(parts[1]) <= 3 and parts[1] == parts[1].upper():
        return full_name  # Already "Welsh JA" format

    # Known surname particles (lowercase)
    particles = {"van", "von", "de", "del", "der", "den", "el", "la", "le",
                 "di", "da", "dos", "das", "du", "'t"}

    # Walk from the end to find where the surname starts.
    # Surname = last word + any preceding lowercase particles.
    # Everything before that = given names.
    surname_start = len(parts) - 1
    while surname_start > 1 and parts[surname_start - 1].lower() in particles:
        surname_start -= 1

    given_parts = parts[:surname_start]
    surname_parts = parts[surname_start:]

    if not given_parts:
        return full_name  # Can't parse, return as-is

    surname = " ".join(surname_parts)
    initials = "".join(p[0].upper() for p in given_parts if p)
    return f"{surname} {initials}"


def format_authors(authors: str) -> str:
    """
    Convert Scholar author string to 'LastName IN, LastName IN' format.
    Input may be 'Joshua Welsh and Jennifer Jones' or
    'Joshua Welsh, Jennifer Jones' or already abbreviated.
    """
    # Normalize separators
    authors = authors.replace(" and ", ", ")

    author_list = [a.strip() for a in authors.split(",") if a.strip()]
    converted = [name_to_initials(a) for a in author_list]

    result = ", ".join(converted)
    # Ensure trailing period
    if not result.endswith("."):
        result += "."
    return result


# ---------------------------------------------------------------------------
# Publication type classification
# ---------------------------------------------------------------------------
def classify_publication(pub: dict) -> str:
    """
    Determine the type of a Scholar entry:
    'patent', 'preprint', 'protocol', or 'publication'.
    """
    bib = pub.get("bib", {})
    title = bib.get("title", "").lower()
    journal = bib.get("journal", bib.get("venue", "")).lower()
    pub_url = str(pub.get("pub_url", "")).lower()
    eprint_url = str(pub.get("eprint_url", "")).lower()

    # Patents — Google Patents URL or patent-like title keywords
    if "patents.google.com" in pub_url or "patents.google.com" in eprint_url:
        return "patent"
    if any(kw in title for kw in ["patent", "us patent"]):
        return "patent"

    # Protocols — protocols.io
    if "protocols.io" in pub_url or "protocols.io" in eprint_url:
        return "protocol"
    if "protocols.io" in journal:
        return "protocol"

    # Preprints — bioRxiv, medRxiv, arXiv, SSRN, preprints.org
    preprint_indicators = ["biorxiv", "medrxiv", "arxiv", "ssrn", "preprints"]
    if any(ind in journal for ind in preprint_indicators):
        return "preprint"
    if any(ind in pub_url for ind in preprint_indicators):
        return "preprint"

    return "publication"


# ---------------------------------------------------------------------------
# Formatters per type
# ---------------------------------------------------------------------------
def format_publication_entry(pub: dict, entry_number: int) -> str:
    """Route to the correct formatter based on detected type."""
    pub_type = classify_publication(pub)

    if pub_type == "patent":
        return _format_patent(pub, entry_number)
    if pub_type == "protocol":
        return _format_protocol(pub, entry_number)
    if pub_type == "preprint":
        return _format_preprint(pub, entry_number)
    return _format_article(pub, entry_number)


def _format_article(pub: dict, entry_number: int) -> str:
    """Format a journal article in the site's manual style."""
    bib = pub.get("bib", {})
    title = bib.get("title", "Untitled")
    authors = format_authors(bib.get("author", "Unknown"))
    year = bib.get("pub_year", "Unknown")
    journal = bib.get("journal", bib.get("venue", bib.get("conference", "")))
    volume = bib.get("volume", "")
    number = bib.get("number", "")
    pages = bib.get("pages", "")

    # Abbreviate journal name
    if journal:
        journal = abbreviate_journal(journal)

    # Build journal/volume/pages block:  "J Extracell Vesicles. 13(2):e12416"
    journal_block = ""
    if journal:
        journal_block = journal
        if volume:
            if journal_block and not journal_block.endswith("."):
                journal_block += "."
            journal_block += f" {volume}"
            if number:
                journal_block += f"({number})"
            if pages:
                journal_block += f":{pages}"
        elif pages:
            journal_block += f" {pages}"

    # DOI
    doi = extract_doi(str(pub.get("pub_url", "")))
    if not doi:
        doi = extract_doi(str(bib))
    if not doi:
        doi = extract_doi(str(pub))

    # Build link
    link = ""
    if doi:
        link = f'doi: {doi} \\[ [website](https://doi.org/{doi}){{:target="_blank"}}]'
    elif pub.get("pub_url"):
        link = f'\\[ [website]({pub["pub_url"]}){{:target="_blank"}}]'

    # Assemble:  Authors, **Title**, JournalBlock, YYYY, doi: X \[ [website](...)]
    parts = [authors, f"**{title}**"]
    if journal_block:
        parts.append(journal_block)
    if year and year != "Unknown":
        parts.append(str(year))
    if link:
        parts.append(link)

    citation = ", ".join(parts)

    return (
        f'<div class="jw-pub-item" data-jw-type="publication" '
        f'data-jw-year="{year}" markdown>\n'
        f"{entry_number}. {citation}\n"
        f"</div>"
    )


def _format_preprint(pub: dict, entry_number: int) -> str:
    """Format a preprint (bioRxiv, medRxiv, etc.)."""
    bib = pub.get("bib", {})
    title = bib.get("title", "Untitled")
    authors = format_authors(bib.get("author", "Unknown"))
    year = bib.get("pub_year", "Unknown")
    journal = bib.get("journal", bib.get("venue", ""))

    # Normalize server name
    server = "bioRxiv"
    jl = journal.lower() if journal else ""
    if "medrxiv" in jl:
        server = "medRxiv"
    elif "arxiv" in jl:
        server = "arXiv"

    doi = extract_doi(str(pub.get("pub_url", "")))
    if not doi:
        doi = extract_doi(str(bib))
    if not doi:
        doi = extract_doi(str(pub))

    link = ""
    if doi:
        link = f'DOI: {doi} \\[[website](https://doi.org/{doi}){{:target="_blank"}}]'
    elif pub.get("pub_url"):
        link = f'\\[[website]({pub["pub_url"]}){{:target="_blank"}}]'

    parts = [authors, f"**{title}**", server]
    if year and year != "Unknown":
        parts.append(str(year))
    if link:
        parts.append(link)

    citation = ", ".join(parts)

    return (
        f'<div class="jw-pub-item" data-jw-type="publication" '
        f'data-jw-year="{year}" markdown>\n'
        f"{entry_number}. {citation}\n"
        f"</div>"
    )


def _format_protocol(pub: dict, entry_number: int) -> str:
    """Format a protocols.io entry. Numbered separately (always 1.)."""
    bib = pub.get("bib", {})
    title = bib.get("title", "Untitled")
    authors = format_authors(bib.get("author", "Unknown"))
    year = bib.get("pub_year", "Unknown")

    url = pub.get("pub_url") or pub.get("eprint_url", "")

    link = ""
    if url:
        link = f'[[website]({url}){{:target="_blank"}}]'

    parts = [authors, f"**{title}**"]
    if year and year != "Unknown":
        parts.append(str(year))
    if link:
        parts.append(link)

    citation = ", ".join(parts)

    return (
        f'<div class="jw-pub-item" data-jw-type="protocol" '
        f'data-jw-year="{year}" markdown>\n'
        f"1. {citation}\n"
        f"</div>"
    )


def _format_patent(pub: dict, entry_number: int) -> str:
    """Format a patent entry."""
    bib = pub.get("bib", {})
    title = bib.get("title", "Untitled")
    authors = format_authors(bib.get("author", "Unknown"))
    year = bib.get("pub_year", "Unknown")

    url = pub.get("pub_url") or pub.get("eprint_url", "")
    # Try to get Google Patents URL
    if not url or "patents.google.com" not in url:
        eprint = str(pub.get("eprint_url", ""))
        if "patents.google.com" in eprint:
            url = eprint

    link = ""
    if url:
        link = f'[[website]({url}){{:target="_blank"}}]'

    parts = [authors, f"**{title}**"]
    if link:
        parts.append(link)

    citation = ", ".join(parts)

    return (
        f'<div class="jw-pub-item" data-jw-type="patent" '
        f'data-jw-year="{year}" markdown>\n'
        f"1. {citation}\n"
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
            # Find the end of this year section (next ## heading or EOF)
            heading_idx = year_sections[year]
            insert_idx = heading_idx + 1
            while insert_idx < len(lines):
                if re.match(r"^## \d{4}\s*$", lines[insert_idx]):
                    break
                insert_idx += 1
            # Back up past trailing blank lines
            while insert_idx > 0 and lines[insert_idx - 1].strip() == "":
                insert_idx -= 1
            # Insert after last entry in this year section
            new_block = "\n\n" + entries_text
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

    setup_proxy()

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
