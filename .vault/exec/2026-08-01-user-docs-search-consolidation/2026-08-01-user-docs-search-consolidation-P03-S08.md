---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:675d00209939e55f8c84cec807f8c8de25f70a49b12aa2480e55034a85b68c5a'
step_id: 'S08'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

## Description

- Ground the per-root recall seam with vaultspec-rag semantic searches over the active ADR, plan, deployment-parity execution record, production injector, and existing built-site gate.
- Read the existing built-site parity gate and its registry-backed record projections before editing.
- Add a bounded real-projection casilla probe to the existing browser/Pagefind gate, using the casilla title and every declared localized description as query terms on every root.

## Outcome

The built-site source gate now covers both halves of the multilingual recall contract: the existing concept probe and a new casilla probe. The casilla probe reuses `_materialise_records()` and `_bounded_to_sample()`, obtains one real `casilla` `SearchRecord`, and asserts that its canonical target is returned for the title and each available `OutputLanguage` description on every `en`, `es`, `ca`, and `hu` root. It exercises the production injector's all-language content blob through the same `pagefind.js` browser path the reader uses.

This is source coverage only. It does not establish that a built artefact or deployed root currently passes, and it does not close P03.S08 because the gate has not been run and the live-root re-probe remains deferred.

## Notes

- Static verification passed with Ruff, Python AST parsing, and `git diff --check` for the scoped test file.
- No tests, builds, Pagefind compilation, browser/runtime probes, generated artifacts, live sweeps, reindexing, model downloads, or deployment were run.
- Shared worktree changes outside the scoped gate were preserved; nothing was staged, committed, reset, stashed, or cleaned.
- Grounding used the working `vaultspec-rag` CLI code-search route because the codebase alias route remains rejected; the VaultSpec semantic search also confirmed the governing locale-capability contract.

The casilla helper was tightened to select only a real bounded record carrying all four `OutputLanguage` descriptions; missing locale data now fails the probe-selection gate instead of being silently omitted.

### 2026-08-05 current source/artifact boundary re-audit

Fresh vaultspec-rag grounding over the sweep runner, committed relevance input assembler, per-root recall contract, and P03.S08 execution evidence confirms that the source seam is present: the sweep runner launders live RAG hits through the typed resolver, while the P03.S08 gate probes the production Pagefind path with a real casilla record and all available localized descriptions across the four roots.

The remaining requirement is evidence from a newly built artifact and the authorized per-root/live-root run. The committed relevance file is consumed by the Rung-2 input assembler rather than regenerated implicitly, so no source change or sweep was justified here. P03.S08 remains open. No tests, builds, Pagefind compilation, browser/runtime probes, generated artifacts, live sweeps, reindexing, model downloads, or deployment were run.

### 2026-08-06 authorized multilingual build continuation

Strict user-document builds were attempted for en, es, ca, and hu. Each stopped on the same five known sequence/product divergences before the Pagefind post-build stage: profile-setup history ordering, correct-review history expectation, Modelo 100 export authority absence, the Modelo 303 verification-report localized divergence, and the Renta assembly localized-help divergence. The locale source projection and parity tests are green, but no locale build is represented as green or deployable. The build outputs were not repaired by refreshing goldens or inventing authoritative source data.

### 2026-08-06 authorized built-site locale and per-root Pagefind proof

Fresh vaultspec-rag grounding over the localized legal-reference renderer, locale catalogue gates, and the deployment-parity source contract established the following evidence boundary.

- The production legal projection fix trims only trailing whitespace in the RST presentation of authored `required_text`; registry data is unchanged. Focused legal-renderer tests returned `2 passed`; legal anchor parity returned `3 passed`; Ruff and basedpyright returned clean.
- The real localized Sphinx user-scope matrix returned `3 passed in 320.96s`, covering es, ca, and hu. The preceding isolated docs-root failure was corrected by passing the authoritative repository root into the legal generator; the generated legal pages then passed docutils warnings-as-errors in every target locale.
- The bounded real Pagefind/deployment-parity artefact run returned `17 passed in 324.70s`. It built and read en, es, ca, and hu roots through production Pagefind, proved each root's own language index carries the corpus with count parity, exposed every decided record kind, and recalled one real concept and one real casilla by every declared language term through the browser path.
- The separate translation-completeness gate remains red in all three targets: six failures total (22 incomplete/fuzzy page catalogues and five machine-text dash-policy entries per language). The catalogue-drift checks passed. No catalogue refresh or translation authoring was performed because those failures are outside the search-consolidation renderer/injection change and would require a separate docs-localization tranche.

The built-site multilingual half is now proven. The live-root re-probe and deployment remain unperformed by authorization; P03.S08 stays open pending the deployed-root evidence owned by P04.S12/S13.
