# Joshua Welsh - Personal Website
This is the source code for my personal website, built with [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/).

## About
This website showcases my research work, publications, talks, and resources in the field of translational medicine, with a focus on:
- Extracellular vesicle research
- Flow cytometry development and standardization
- Biomedical instrumentation
- Software development for reproducible research

## Development

Install the locked dependencies and start the local preview:

```bash
uv sync
./dev.sh serve
```

Build the static website into `site/`:

```bash
./dev.sh build
```

## Scholar publication updates

The local `google-scholar` Docker app exports `../google-scholar/exports/scholar-dashboard.json`
after its daily sync. GitHub Pages cannot access that local file, so the Mac hosting
Docker publishes changes from this repository.

To import the latest export and preview changes without writing files:

```bash
python3 scripts/sync_scholar_export.py --dry-run
```

The importer updates citation metrics and appends well-formed new publications to
`docs/publications.md`. Existing citations remain untouched. Scholar records without
an author, year, or usable link are reported as deferred so incomplete citations do
not appear on the website. Reviewed corrections for incomplete Scholar records live
in `scripts/scholar_publication_overrides.json`. If the app only completes an
author-only fallback sync, unchanged metrics do not create another site commit.

After this repository's setup changes are committed and pushed, install the hourly
macOS job on the Docker host:

```bash
bash scripts/install_scholar_schedule.sh
```

The installer creates a private checkout under
`~/Library/Application Support/personal-website-scholar/repo`, because macOS blocks
background jobs from reading a checkout in `Documents`. The job reads the export
through Docker, fetches `main`, imports it, runs a strict MkDocs build, and commits
and pushes only the generated publication Markdown and JSON. The existing Pages
workflow deploys that push. It skips runs when its checkout contains other edits and
logs to `~/Library/Logs/personal-website-scholar.log`. Git SSH access to the `origin`
remote must work without an interactive prompt for scheduled pushes.
