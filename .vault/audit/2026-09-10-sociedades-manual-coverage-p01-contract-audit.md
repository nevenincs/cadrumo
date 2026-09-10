---
tags:
  - '#audit'
  - '#sociedades-manual-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:68074b39cf25e4f663d7c88e6690b8e11218249f3edbd6736352b27966ca912f'
related:
  - "[[2026-09-10-sociedades-manual-coverage-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace sociedades-manual-coverage with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `sociedades-manual-coverage` audit: `p01 contract`

## Scope

Reviewed `P01.S01` against the accepted annual-manual coverage ADR and its temporal-coverage research. Examined the coverage schema, catalogue loader, bundled Sociedades ledger, and focused catalogue tests. The review also ran the focused lint gate and a scratch-root loader probe.

## Findings

### mandatory-ledger | high | The coverage declaration can be removed without a loader refusal

The accepted ADR requires an observable disposition for every supported filing year. `load_shared_catalogues` calls `_validate_sociedades_annual_manual_coverage`, but that function returns when its `catalogue` argument is `None`; `RegistryCatalogues` also makes the field optional. A scratch registry containing only `[supported_filing_years]` loaded successfully and returned `None`. Require the declaration after the canonical supported-year declaration, and add a refusal test for its absence.

### quality-gate | medium | The changed contract files fail the repository lint gate

Focused `ruff check` reports three errors: unsorted imports in `loader.py` and `test_supported_filing_years_catalogue.py`, plus prohibited `assert` usage in `_validate_sociedades_annual_manual_coverage`. This leaves the step unable to satisfy the normal static-quality gate.

### remediation-verification | low | Previous high and medium findings are resolved

The shared-catalogue boundary now refuses a missing annual-manual coverage declaration before construction, and the new negative regression test proves that refusal. The prior assertion is an explicit error path and imports are formatted. Focused `ruff check` passed, and the negative test passed in 8.45 seconds.

### official-locator-transport | medium | The CLI redacts an official locator to its host and loses the audit link

The application projection preserves the 2026 disposition locator through its JSON dump, but the real localized CLI JSON emits only `https://sede.agenciatributaria.gob.es`. The global CLI redaction profile drops every URL path, including this public AEAT archive locator. That defeats the ADR requirement that the unpublished disposition retain an official archive locator on the production operator surface. Give public registry authority locators an explicit safe transport treatment and add an end-to-end assertion for the complete URL.

### locator-remediation-verification | low | The official-locator transport finding is resolved

The redaction exception is limited to the typed `official_locator` key, preserves the complete AEAT archive URL, and leaves a sibling arbitrary URL host-redacted. The CLI integration regression asserts the complete locator, and focused lint passes. A direct CLI invocation could not finish in the shared dirty worktree because unrelated legal-corpus anchors currently fail registry validation; that external failure does not alter the locator-path result.

## Recommendations

Make the Sociedades coverage catalogue mandatory at the shared-catalogue boundary, then add regression cases for absence, duplicate declarations, a year-set mismatch, an unknown source, a non-manual source, and an inexact annual interval. Apply the formatter and replace the assertion with an explicit refusal path.
