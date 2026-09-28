import unittest

from scripts.sync_scholar_export import (
    apply_overrides,
    format_entry,
    meaningful_data,
    update_publications,
)


MARKDOWN = '''# Publications
<canvas data-jw-chart='{"labels": ["2024"], "values": [1]}'></canvas>

## 2024

<div class="jw-pub-item" data-jw-type="publication" data-jw-year="2024" markdown>
1. Curated AA (2024), **Existing study**, J Extracell Vesicles, doi: 10.1234/existing [[website](https://doi.org/10.1234/existing)]
</div>
'''


def work(**overrides):
    record = {
        "title": "New extracellular vesicle study",
        "authors": "Joshua A Welsh and Vera A. Tang",
        "venue": "Journal of extracellular vesicles",
        "year": 2026,
        "website_type": "publication",
        "doi": "10.1234/new",
        "pub_url": "https://doi.org/10.1234/new",
        "total_citations": 5,
    }
    record.update(overrides)
    return record


class ScholarImportTests(unittest.TestCase):
    def test_adds_complete_entry_in_existing_style_and_keeps_curated_entry(self):
        updated, added, deferred = update_publications(MARKDOWN, [work()])
        self.assertEqual(added, ["New extracellular vesicle study"])
        self.assertEqual(deferred, [])
        self.assertIn("Curated AA (2024), **Existing study**", updated)
        self.assertIn("Welsh JA, Tang VA (2026), **New extracellular vesicle study**, J Extracell Vesicles", updated)
        self.assertLess(updated.index("## 2026"), updated.index("## 2024"))
        self.assertIn('"labels": ["2024", "2026"], "values": [1, 1]', updated)
        repeated, added_again, _ = update_publications(updated, [work()])
        self.assertEqual(repeated, updated)
        self.assertEqual(added_again, [])

    def test_doi_and_sparse_duplicates_do_not_hide_complete_record(self):
        records = [
            work(title="Alternate title", year=2025, doi="10.1234/existing"),
            work(authors="", doi=None, pub_url=""),
            work(),
        ]
        updated, added, deferred = update_publications(MARKDOWN, records)
        self.assertEqual(added, ["New extracellular vesicle study"])
        self.assertEqual(deferred, [])
        self.assertNotIn("Alternate title", updated)

    def test_incomplete_and_unsafe_records_are_deferred(self):
        records = [work(doi=None, pub_url=""), work(title="Another study", doi=None, pub_url="javascript:alert(1)")]
        updated, added, deferred = update_publications(MARKDOWN, records)
        self.assertEqual(added, [])
        self.assertEqual(len(deferred), 2)
        self.assertEqual(updated, MARKDOWN)

    def test_fallback_timestamp_alone_does_not_change_public_data(self):
        first = {"profile": {"total_citations": 10, "last_synced": "2026-09-26"},
                 "citation_history": [], "publication_counts": {}, "publications": [],
                 "generated_at": "2026-09-26", "sync_log": []}
        second = {**first, "profile": {**first["profile"], "last_synced": "2026-09-27"},
                  "generated_at": "2026-09-27", "sync_log": [{"status": "fallback"}]}
        self.assertEqual(meaningful_data(first), meaningful_data(second))

    def test_formats_patent_without_changing_publication_type(self):
        entry = format_entry(work(website_type="patent", doi=None, pub_url="https://patents.google.com/patent/US123"))
        self.assertIn('data-jw-type="patent"', entry)
        self.assertIn("**New extracellular vesicle study**", entry)

    def test_reviewed_override_fills_a_known_scholar_gap(self):
        missing = work(
            title="Sex differences in urinary extracellular vesicles originating from the genitourinary system in health and disease",
            doi=None,
            pub_url="",
            venue="",
        )
        enriched = apply_overrides([missing])[0]
        self.assertEqual(enriched["doi"], "10.1152/ajprenal.00402.2025")
        self.assertTrue(enriched["pub_url"].startswith("https://doi.org/"))


if __name__ == "__main__":
    unittest.main()
