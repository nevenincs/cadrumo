---
tags:
  - '#audit'
  - '#sociedades-manual-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:6f368fc6cf2474aaf61cdcf16c4e2132d9a9f4e8d37efb3fe89838b028a3ae75'
related:
  - "[[2026-09-10-sociedades-manual-coverage-plan]]"
---

# `sociedades-manual-coverage` audit: `p02 p03 data docs`

## Scope

Read-only review of P02.S05--S07 and P03.S08--S09 against the accepted annual-manual coverage ADR. The review covered the 2022/2023 manual artefacts, provenance and shipped corpus-text sidecars; legal-source applicability; Modelo 200 source bindings; the extraction freshness gate; and generated CLI documentation projections.

## Findings

### modelo-200-off-interval-manual-bindings | high | Annual manual references still cross their source windows

P02.S07 is not complete at the registry-entry level. The 2024 Modelo 200 revision retains `aeat-modelo-200-manual-2025` in `live_cross_references/0001-modelo-200-filed-declarations-read.toml`, although that source begins on 2025-01-01. The `2025-y-siguientes` revision contains `aeat-modelo-200-manual-2024` in 1,040 TOML files, including `application_links/0002-application-links.toml` and `casillas/c00001.toml`, although that source ends on 2024-12-31. Correcting only the revision and family-disposition headers does not prevent these production calculation, filing, review, and portal bindings from claiming off-interval annual guidance. This directly violates the plan's requirement that annual manuals never ground an out-of-window year.

### generated-cli-tree-stale | medium | The shipped interactive CLI documentation differs from the live command graph

`docs/_static/cli-tree.json` is not the serialization of the current command graph. For `aeat app registry manuals list`, its help remains "List manual parts available locally" and its manual option excludes `sociedades`; a fresh in-memory projection says "List declared annual coverage and locally available manual parts" and includes `sociedades`. The generated RST page does carry the current wording, but the static tree feeds the documentation widget, so P03.S09 has not regenerated every consumer of the live CLI surface.

### data-and-search-boundary | low | No issue found in the backfill, 2026 disposition, or raw-manual search boundary

The 2022 and 2023 PDF SHA-256 values match both their manifests and the legal registry entries, their extraction and corpus-text sidecars exist, and the manual verification command passes for both years. The coverage catalogue marks 2026 as `unpublished` with the AEAT archive locator; no 2026 PDF, source entry, or corpus directory was introduced. The full extraction freshness gate passes. Product lexical corpus search remains restricted to `corpus/normatives/html`, so the newly bundled raw manuals and their sidecars were not silently added to generic product search or Vaultspec RAG processing.

### modelo-200-off-interval-manual-bindings-resolution | low | Remediation removes every detected cross-year reference

Re-review found zero 2024 references to `aeat-modelo-200-manual-2025` and zero `2025-y-siguientes` references to `aeat-modelo-200-manual-2024`. The repair consistently replaces the affected 2025+ fragment references with the 2025 annual source and removes the 2025 reference from the 2024 authenticated-read fragment. The new `test_modelo_200_revision_fragments_never_cite_another_years_annual_manual` scans every TOML fragment in both revision trees; it passed in the focused test run.

### generated-cli-tree-stale-resolution | low | Committed documentation projection now equals the live graph

The committed `docs/_static/cli-tree.json` is byte-equal to a fresh in-memory serialization of the live CLI graph. Its manuals-list node now carries the coverage-aware help text and the `renta, iva, sociedades` identifier set. The focused CLI-tree test suite passed.

### companion-package-tracked-artifacts | low | No issue found in the staged artefacts, ignore exceptions, or pathspec repair

Both new Sociedades PDFs, their manifests and extracted surfaces, and their manual corpus-text sidecars are staged in the Git index. The two `.gitignore` exceptions are exact PDF paths beneath the existing manual-PDF deny rule; they neither re-admit another year nor change the policy for derived artefacts. The distribution test now uses Git's explicit `:(glob)` magic for each fixed corpus prefix and binary suffix, preserving the intended recursive, source-binary-only tracked set. Its companion ownership, exclusion of derived members, and full-union assertions therefore remain independent of the built wheels. The focused distribution gate and whitespace check passed.

## Recommendations

- Resolve every off-interval annual-manual `source_refs` in Modelo 200, not only the revision-level and family-disposition references, and add a regression test that scans all revision entries against source applicability.
- Regenerate `docs/_static/cli-tree.json` using the canonical full docs build projection and add or run a freshness check that compares the committed tree with the live command graph.
