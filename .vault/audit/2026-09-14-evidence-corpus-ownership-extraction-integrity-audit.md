---
tags:
  - '#audit'
  - '#evidence-corpus-ownership'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:e9f225c9a31cfeed1872cf037747a93f70e6d7231023e7700027e587f8b08c88'
related:
  - "[[2026-09-14-evidence-corpus-ownership-reference]]"
---

# `evidence-corpus-ownership` audit: `Evidence corpus extraction and cache integrity`

## Scope

Reviewed the bounded extraction and runtime-index changes in `dev/docs/preprocess`, `.vaultragpreprocess.toml`, and `application/corpus_search/runtime.py` against the accepted corpus-provenance decisions and the evidence-corpus ownership reference. The review focused on XML redaction separation and selection, exact attribution identity, malformed-input refusal, and atomic index invalidation/publication. No extraction, registry compilation, or broad test suite was run.



Implementation validation: `uv run --no-sync pytest dev/docs/preprocess/tests src/cadrumo/application/corpus_search/tests -q --no-cov` completed with exit 1: 135 passed and three pre-existing annual-Orden failures. The failures are `test_annex_instructions_become_atomic_citation_units`, `test_iva_instructions_and_activity_tables_become_atomic_citation_units` (DANA selected by a Lorca-shaped parser), and `test_2022_iva_units_preserve_the_legacy_table_shape_and_lorca_reduction` (changed derived anchor). An earlier intermediate run exposed two XML fallback regressions; both were fixed before this final run. Targeted Ruff and `git diff --check` exit 0.

Mechanical checks: all 61 XML response source hashes remained unchanged after canonical extraction; output has 116 units with each version separately segmented, including ordinal provisions. Both affected authored legal references pass `verify_legal_reference_grounding`. All 105 refreshed PDF sidecars pass generic hash/locality/rendered-text validation and current attribution equality; PDF units are unchanged. Among 478 existing normative HTML sidecar sources, 475 equal current canonical extractor output exactly. The 2022, 2023 and 2024 annual-Orden outputs were deliberately preserved because their current producer changes units or refuses extraction. They are not certified current.

Removed the unenrolled text extractor, its dedicated tests, its import target and its unused source-kind enum. These are tracked deletions recoverable from Git; no primary source evidence was deleted in this extraction pass. Runtime corpus-search caches now invalidate on exact source-path/content identity and publish rebuilt SQLite indexes under a writer lock using atomic replacement.



The owning import-target generator ran with exit 0 and `assert_all_target_sets_current` passed, retaining concurrently introduced modules. `uv run --no-sync vaultspec-core vault check all --json` exited 1 on broader vault diagnostics (including scaffold annotations, document-body warnings and an unrelated ungrounded ADR); structure, frontmatter, modified stamps and encoding checks reported no diagnostics. No broad vault repair was applied.

## Findings

### xml-version-locator-identity | low | Version locator identity remains a follow-on limitation

`article_response_units` segments every BOE response version independently and carries the source `id_norma` plus raw `fecha_vigencia` metadata in its title and section without treating that date as inferred legal effect. Equivalent structural subunits in different versions still share a path-and-anchor `corpus_ref`. This does not permit implicit historical selection: the existing compiler guard refuses raw multi-redaction sources before anchor resolution, no registry legal reference cites the current multi-version population, and cited single-version XML retains its source anchor. It does mean runtime callers must use the returned title or section to distinguish historical search hits until a typed version locator contract exists.

The existing annual-parser refusal and changed-anchor population remain an integration residual outside this bounded review.

## Recommendations

Treat typed historical-version locator identity as follow-on architecture work. Preserve source-stated fragment anchors and the compiler's fail-closed multi-redaction guard; do not invent fragment aliases or permit a consumer to select a historical version without applicable-law context. A future contract should carry version identity separately and prove that two versions containing the same ordinal subunit remain distinguishable end to end.
