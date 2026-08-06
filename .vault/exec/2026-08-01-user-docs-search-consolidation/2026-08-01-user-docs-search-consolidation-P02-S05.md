---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:47113f76e085f671326b463eb65847fe3b608f15bfd696558672c1edeaed618a'
step_id: 'S05'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Add the client-side cosine tier over the shipped matrix to the shared search controller so both the palette host and the search-page host rank through it inside the existing compose ladder

## Scope

- `docs/_static/cadrumo-docs.js`

## Description

- [x] Ground P02.S05 with fresh `vaultspec-rag` searches over the accepted plan/ADR and the current browser semantic seam.
- [x] Inspect matrix, manifest, bridge, bundle, dequantization, cosine, and compose-ladder paths.
- [x] Dispatch the validated LUNA Max worker for a bounded source review and concrete-defect remediation.
- [x] Confirm that the palette and inline search page share the same controller path.
- [ ] Produce the shipped matrix/bundle and acceptance evidence required to enable the tier.
- [ ] Run the authorized behavioural gates and close P02.S05 only after the tier is proven on the built surface.

## Outcome

The source implementation contains a fail-closed client semantic tier: validated bundle loading, int8 dequantization, covered-token query-vector construction, cosine scoring, acceptance thresholds, deterministic tie-breaking, bridge hydration, and composition after the structured/Pagefind path. The palette and search-page hosts use the shared controller. The LUNA Max review found no concrete source defect and changed no files.

## Notes

P02.S05 remains open because the current boundary prohibits tests, builds, browser probes, matrix/bundle generation, and deployment. Without an accepted shipped artifact and behavioural evidence, source presence is not proof that the tier is enabled or correct in the built site. Shared-worktree WIP was preserved and no broad staging or cleanup was performed.

### 2026-08-05 current source re-audit

Fresh vaultspec-rag searches over the browser semantic seam and the accepted P02.S05 plan/ADR records, followed by a full read of `docs/_static/cadrumo-docs.js` and exact symbol confirmation, show that the source tier is wired but deliberately disabled by evidence: `createSearchController` is shared by `initPalette` and `initSearchPage`; `searchPagefind` keeps the structured casilla first-refusal, then loads the validated Rung-2 bundle and appends `rung2SemanticCandidates`; bundle loading fails closed on absent configuration, malformed bytes, hash/provenance/fingerprint mismatch, or incomplete acceptance; the candidate path enforces token coverage, cosine floor, runner-up margin, bridge hydration, deterministic tie-breaking, and a five-result cap.

No source correction is justified in this slice. The missing requirements are the accepted shipped matrix/bundle, measured acceptance values, independent parity/behavioural evidence, and built-surface proof; P02.S05 remains open. A new disjoint Luna delegation could not be created because the agent-thread limit was reached, and no agent edited the owned browser source. No tests, builds, browser probes, matrix/bundle generation, model downloads, live sweeps, reindexing, deployment, or artifact release were run.

The permitted static boundary completed after the source re-audit:

- `python` AST parsing passed for `dev/docs/legal_reference.py`, `dev/docs/terminology/_legal_projection.py`, `dev/docs/terminology/_search_record.py`, `dev/docs/terminology/_unified_record.py`, and `dev/docs/pagefind_inject.py`.
- JSON parsing passed for `src/cadrumo/_data/terminology/relevance/relevance.json`.
- `node --check docs/_static/cadrumo-docs.js` passed.
- `git diff --check` passed for this execution record, and the scoped legal/browser files contain no merge-conflict markers.
- `vaultspec-core check --feature user-docs-search-consolidation --no-fix` returned `ok` with zero errors. It reported two pre-existing warnings for empty `## Scope` and `## Recommendations` sections in `.vault/audit/2026-08-05-user-docs-search-consolidation-pagefind-narrowing-audit.md`; those unrelated audit contents were preserved.

No tests, builds, runtime/browser probes, matrix generation, model or artifact downloads, live sweeps, reindexing, deployment, or artifact release were run. P02.S05 remains open because the accepted Rung-2 matrix/bundle, measured acceptance values, independent parity/behavior evidence, and built proof are still absent.

### 2026-08-05 LUNA Max controller re-audit

Fresh vaultspec-rag grounding and exact reads were followed by a bounded LUNA Max review of the shared browser controller. The review reconfirmed that `createSearchController` is shared by the palette and inline search page; structured modelo/casilla resolution remains the first refusal; the optional Rung-2 loader fails closed on missing, malformed, unauthorised, or hash/provenance-inconsistent payloads; semantic candidates enforce coverage, cosine and runner-up thresholds, bridge hydration, deterministic ordering, and the five-result cap; and compose preserves lexical precedence and display-class bands. No concrete source defect was justified, so `docs/_static/cadrumo-docs.js` was not edited. P02.S05 remains open for the accepted matrix/bundle, measured acceptance evidence, and built-surface behavioural proof. No tests, builds, browser probes, artifact generation, model downloads, sweeps, reindexing, deployment, or VaultSpec plan closure were performed.

### 2026-08-06 source-only controller cleanup

Fresh vaultspec-rag grounding over the accepted search ADR, the P02.S05 execution boundary, and an exact read of `docs/_static/cadrumo-docs.js` identified a redundant second identical `select(index)` declaration inside `createSearchController`. A LUNA Max worker removed only that duplicate from the shared controller; the first declaration remains the sole selection implementation. Parent review confirmed the focused diff contains no other file change. `node --check`, `git diff --check`, and an exact declaration-count check passed. No tests, builds, browser/runtime probes, generated artifacts, matrix/bundle generation, live sweeps, reindexing, deployment, or release activity was performed. P02.S05 remains open because the shipped artifact and behavioral/runtime evidence are still absent.
