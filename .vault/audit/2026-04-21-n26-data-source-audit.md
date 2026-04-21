---
tags:
  - '#audit'
  - '#n26-data-source'
date: '2026-04-21'
related:
  - '[[2026-04-14-n26-data-source-research]]'
  - '[[2026-04-14-n26-data-source-adr]]'
  - '[[2026-04-13-p2a-financial-provider-adr]]'
---

# `n26-data-source` Code Review

## Scope

- Branch: `feature/106-n26-research`
- PR: `#136`
- Surface: N26 research, ADR, and feature index only
- Review basis: unresolved GitHub review threads, issue `#106`, and current `main` project mandates

## Findings

No open findings remain.

The revised research and ADR now:

- replace the brittle fixed-coordinate PDF sketch with header-derived table detection
- select date parsing from the detected statement locale rather than a single ES-only format
- extract statement currency from document metadata instead of hard-coding `EUR`
- record verbatim `raw_fields` in the parser sketch and follow-up issue sketch to match the live `RawTransaction` contract
- remove the obsolete ADR-internal DOC-ONLY self-review shortcut in favor of this standalone audit artifact

## Verification

- `python C:\Users\hello\.codex\plugins\cache\openai-curated\github\b1986b3d3da5bb8a04d3cb1e69af5a29bb5c2c04\skills\gh-address-comments\scripts\fetch_comments.py` -> identified 4 unresolved actionable PR #136 review threads; all four are addressed in the updated research / ADR text
- `uv run pytest tests/test_docs.py -q` -> passed (`4 passed`)
- `uv run ruff check .` -> passed
- `uv run vaultspec-core vault feature index -f n26-data-source` -> passed; regenerated the feature index from live tags
- `uv run vaultspec-core vault list -f n26-data-source --json` -> passed; feature now resolves exactly 4 documents (`index`, `adr`, `audit`, `research`)
- `git status --short` -> PR surface is limited to `.vault/research/2026-04-14-n26-data-source-research.md`, `.vault/adr/2026-04-14-n26-data-source-adr.md`, `.vault/n26-data-source.index.md`, and `.vault/audit/2026-04-21-n26-data-source-audit.md`, plus the unrelated local-only `.vaultspec/providers.json`
- `uv run ty check src tests` -> fails in pre-existing auth files under `src/aeat/auth/`, `src/aeat/browser/`, `src/aeat/cli/doctor.py`, and `src/aeat/submission/_protocols.py`; none of those paths are in the PR #136 document diff
- `uv run vaultspec-core vault check all` -> fails on broad pre-existing vault filename/body-link/schema debt across historical documents; the new N26 audit naming issue was corrected during this recovery and the feature-specific index/list checks above pass

## Status

- Accepted for the PR #136 document surface. Remaining `ty` and vault-wide check failures are repository baseline debt outside the N26 branch diff.
