---
tags:
  - '#exec'
  - '#retenciones-perceptor-count'
date: '2026-06-24'
modified: '2026-06-24'
step_id: 'S02'
related:
  - "[[2026-06-24-retenciones-perceptor-count-plan]]"
---




# Persist records in a bucket-scoped encrypted secure-object namespace via SecureObjectRepository, populated from the same input path that feeds the pull aggregate_per_modelo observations

## Scope

- `src/aeat/application/aggregation`

## Description

- Phase P01 (S01 record + S02 store/wiring + S03 tests) landed atomically by teammate r2-autonomo-130-eoy as commit 2b46d156dc178672e4cbded98768c394323f0df0 (6 files, 498/5, tight pathspec; foreign WIP #18 _calculation_actions.py + #19 _export.py verified excluded).
- S01: reused the validated RetencionObservation (no fork) inside _RetencionObservationEnvelopePayload (+ modelo/filing_year/period keying).
- S02: new RETENCION_OBSERVATIONS_NAMESPACE (FINANCIAL, object key sha256-hashes the perceptor NIF — plaintext NIF only in the encrypted payload, never an id) + RetencionObservationRepository (save/load/iter + replace_observations set-replace) + persist_retencion_observations shared write helper; (b) wiring: the CLI aggregate verb calls the helper for RETENCIONES_MODELOS (incl. M180) after building observations, aggregate_per_modelo stays PURE.
- S03: 7 tests — encrypted roundtrip (all fields non-default), distinct NIF/scheme rows, NIF-never-cleartext, period-scope, anti-tautology, replace-semantics (drop-a-perceptor -> no stale row), helper-writes->load.

## Outcome

The dedicated distinct-NIF per-perceptor store exists and is the single source both surfaces read (pull writes via the shared helper; the P02 resolver will read). Secure-storage gate passed (coordinator review): sha256-NIF key + encrypted payload honour sensitive-financial-data-secure-storage-only. The coordinator's replace-not-append correctness flag is fully addressed (replace-on-empty included, so a re-pull dropping a perceptor cannot strand a stale row / silently over-count). Gates green: 7 P01 + 35 namespace-registry + 114 aggregation-suite + 23 CLI backend-boundary, ruff clean. P01.S01/S02/S03 closed.

## Notes

- (b) populate decision: aggregation kept pure; the persist lives in ONE shared application helper called by the CLI entrypoint, so store-completeness is structural (a future producer calls the same helper) rather than per-entrypoint discipline. P02 (resolver + BindingSourceKind + enrollment) follows: the resolver/enum build in-tree now, but the merge_source_resolutions / _BUCKET_AGGREGATION_OWNED_SOURCES enrollment lives in _calculation_actions.py (#18 stranded peer WIP) so the P02 commit is held atomic until that file frees. Empty-store no-silent advisory carried into P02.
