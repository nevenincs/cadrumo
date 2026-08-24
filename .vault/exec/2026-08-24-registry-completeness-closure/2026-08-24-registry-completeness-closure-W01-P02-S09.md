---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:7507fe306aad07e38e6ea30d2714e07c7d34c0165fa3c4add1dd1bef3c402c0f'
step_id: 'S09'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace registry-completeness-closure with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S09 and 2026-08-24-registry-completeness-closure-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Compose the filing-export limb from exact layout capability and official-byte evidence and ## Scope

- `src/cadrumo/application/registry/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Compose the filing-export limb from exact layout capability and official-byte evidence

## Scope

- `src/cadrumo/application/registry/`

## Description

- Add `FilingExportCoverageReport` and its fail-closed composer to the registry application facade.
- Enumerate every loaded modelo/revision and obtain filing-grade law-selected snapshots without injecting a revision identifier.
- Refuse a revision below filing grade, unreviewed filing evidence, failed snapshot selection, missing layout evidence, cross-limb disagreement, or stale source bytes with an explicit owner disposition.
- Rehash every materialized layout's `layout_authority` source with `verify_source_file` before admitting export capability.
- Add focused authority-backed tests for retained below-grade refusals, pending-review filing evidence, and changed official-byte digests.
- Generate the application API stub and refresh the registry API index entry.

## Outcome

- The closure limb retains the complete registry denominator. Model existence alone cannot produce filing capability: M036 remains a `below_filing_grade` refusal while filing-grade revisions require reviewed, law-selected evidence.
- Successful rows identify the canonical snapshot authority and source-byte digest; materialized layout sources are reverified from the source root. Any mismatch is a `stale_evidence` refusal rather than a filing claim.
- `uv run --no-sync pytest -n 0 -q src/cadrumo/application/registry/tests/test_filing_export_coverage.py` passed: 3 tests in 28.64 seconds.
- `uv run --no-sync ruff check src/cadrumo/application/registry/_filing_export_coverage.py src/cadrumo/application/registry/__init__.py src/cadrumo/application/registry/tests/test_filing_export_coverage.py` passed.
- `uv run --no-sync ty check src/cadrumo/application/registry/_filing_export_coverage.py` passed.
- `uv run --no-sync python -m dev.docs.apidocs scaffold --check` reported no drift.

## Notes

- No registry catalogue, revision grade, period, export layout, or source-reference fixture was changed. The limb consumes existing validated authority and evidence only.
