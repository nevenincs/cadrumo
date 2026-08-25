---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:ae41f7b882c052f21e03fc40899eebb6738855b09f8f64fe93c053f896d69237'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
  - "[[2026-08-25-tui-architecture-s160-approved-amendment-architecture-review-audit]]"
  - "[[2026-08-25-tui-architecture-s160-native-work-capture-owner-atomicity-reconciliation-audit]]"
  - "[[2026-08-25-tui-architecture-workspace-v1-contract-reference]]"
  - "[[2026-08-25-tui-architecture-s128-workspace-projection-composition-reference]]"
---
# `tui-architecture` audit: `S160 plan amendment review`

## Scope

Independent read-only review of plan-amendment commit `5f0c4c0847547954938239fc154af5e5af9ef4ed` against the current accepted Workspace ADR, architecture-remediation PASS audit `849e59bb93584d4e5322bacb0416c34b8d3f8283`, the S160 reconciliation audit, the closed S125/S126 contracts, the S128 composition reference, the live plan, and current HEAD `cfe008d7348d1a956d4c7513059fb27bd63c42ec`. No plan or source file was changed.

Discovery led with Vaultspec RAG over the Workspace decision, S160 audit/reference cluster, native WORK capture, and composition seam. The code index reported one missing published section, so no absence conclusion relies on semantic search. Whole-file reads and exact `rg` then covered the pointer record and IO owner, pointer transaction and all direct production callers, both singleton persistence kernels, work repository protocol/adapter, pure and parallel work selectors, every live consumer of the raw registry-revision helper, S125/S126 epoch fields, S159 native capture/currentness, the eight owner rows, S167 registration, and S128 composition.

The CLI plan checker reports only `PLAN022`: canonical IDs are not monotonic in display order. That warning is intentional because CLI insertion preserved append-only IDs S168-S174 while placing them before S160. The tier, display paths, row grammar, two-state checkboxes, 7-wave/24-phase structure, and 174-step count are valid. The dependency topology also passes: S172 owns epoch schema v2, S173 corrects S159's comparison domain, S160-S166 each require a native opaque domain, S167 waits for all eight corrected owners plus S126 v2, and S128 waits transitively for the corrected S125 axes, S159/S160-S167, and the S174 pure assertion. No compatibility reader is authorized by those rows.

## Findings

### pointer-cutover-scope | high | S168 omits the strict pointer-record owner, core facade, and an exact consumer inventory

The durable transition revision and absent tombstone change the current on-disk pointer grammar, whose strict schema and deterministic TOML serializer live in `src/cadrumo/core/_bucket_pointer.py:47`, `:50`, `:74`, and `:77`. S168 names only `_bucket_pointer_io.py`, the application transaction/facade, generic "production pointer consumers," and tests. It does not name the schema owner or `src/cadrumo/core/__init__.py`, which must atomically promote the new core record/coordinate surface. Implementing a second record parser in IO would create the forbidden parallel grammar; leaving the v1 record untouched cannot persist an absent selection plus monotonic revision.

The exact direct-reader census also reaches `src/cadrumo/core/config.py:1009`, `src/cadrumo/application/storage_write_policy.py:42`, `src/cadrumo/application/config_reset.py:10`, and `src/cadrumo/application/auth/_operator_scope.py:85`. Transaction-shape consumers occur in `src/cadrumo/application/workflow/_profile_health.py:541`, `src/cadrumo/application/config_reset.py:102`, `src/cadrumo/application/user_profile/_login_session.py:664`, `src/cadrumo/application/user_profile/_lifecycle.py:206`, `src/cadrumo/application/user_profile/_custody_service.py:641`, `src/cadrumo/application/user_profile/_custody_repository.py:196`, and `src/cadrumo/entrypoints/cli/_config/_profile_delete.py:135`. The generic phrase in the row is not an exact one-step/one-commit scope and can silently omit a reader while still claiming "zero dual mutation paths."

### revision-assertion-teardown | high | S174 cannot delete the raw-loader helper within its listed files

S174 lists `_calculation_helpers.py`, `_work_addressing.py`, `work_review_projection.py`, and `_calculate_input.py`, but the live helper is imported and invoked by `src/cadrumo/application/modelo/_external_import_actions.py:93` and `:222`, `src/cadrumo/application/modelo/_quickfile.py:64` and `:254`, and `src/cadrumo/application/modelo/_work_lifecycle.py:410` and `:412`. It is also exported by the canonical facade at `src/cadrumo/application/modelo/__init__.py:547` and `:986`.

S170 may converge the external-import selector, but it precedes the S173 registry-coordinate correction and S174 pure assertion and does not authorize migrating revision identity. Quickfile, work lifecycle, and the facade appear in none of S168-S174. Therefore deleting `resolve_registry_revision_for_work_target` in S174 either breaks live imports, leaves a forbidden raw-loader/compatibility bridge, or expands the commit beyond its declared file scope.

### native-owner-facades | high | Three Modelo-native rows omit their required atomic facade promotion

The accepted owner seam requires every native capture/current-coordinate pair to be public through its canonical owner facade in the same atomic change. S159, S160, S163, and S165 name or encompass their facades, but S161 names only `work_review_projection.py`, S164 only private `_calculation_actions.py`, and S166 only private `_workspace_manifest.py`; S167 names only `_workspace_producers.py`. Deferring these exports to S167 or S129 would split native implementation from promotion and leave the registration consuming a private surface or require a bridge. Each of S161, S164, and S166 must include `src/cadrumo/application/modelo/__init__.py` and its public-surface proof in its own atomic row.

## Recommendations

Amend S168 through the plan CLI without changing its one-commit cutover: explicitly add the strict pointer record owner, core facade, every direct reader and transaction-shape consumer above, and their focused tests. Preserve one current record and one transaction; do not stage a v1/v2 reader, alias, or temporary adapter.

Amend S174 through the plan CLI to include `_external_import_actions.py`, `_quickfile.py`, `_work_lifecycle.py`, and `application/modelo/__init__.py` plus their focused tests. The same commit must remove the raw-loader helper, its facade export, every import/call, asserted-ID selection, and stale docstring references.

Amend S161, S164, and S166 so each native surface is promoted through `cadrumo.application.modelo` in its implementing commit. Re-run `vaultspec-core vault plan check`; the deliberate PLAN022 warning may remain, but the exact census must show no unnamed pointer consumer, raw revision-helper consumer, private-only native surface, shim, alias, fallback, compatibility reader, or non-`__init__` bridge.

## Disposition

FAIL. S169-S173 are cohesive prerequisite commits and the comparison-domain and S167/S128 dependency order is correct, but S168 and S174 are not closed atomic cutovers and three native-owner rows omit mandatory facade promotion. The plan must be revised before S168 execution; no source implementation is authorized by this review.

## Remediation review

Exact plan-only remediation commit `ec5c87210f33cda9f59815d675d8ce30e3bf65be` was re-reviewed against the three HIGH findings above. The focused review reused the recorded exact source census, compared every required path and teardown obligation with the amended rows, confirmed the commit changes only the plan, and reran the CLI plan checker. The historical FAIL remains the disposition for amendment commit `5f0c4c0847547954938239fc154af5e5af9ef4ed`; this section records only the remediation result.

### S168 pointer cutover

CLOSED. S168 now names the strict record owner, IO owner, core facade, transaction owner and facade, all four direct readers, and all seven transaction-shape consumers from the exact census. It requires their atomic migration, focused record/facade/reader/transaction concurrency proof, one absent-or-selected record, monotonic transition revision, and explicit deletion of dual readers/writers, compatibility readers, shims, aliases, fallbacks, and re-export bridges.

### S174 revision assertion teardown

CLOSED. S174 now names `_external_import_actions.py`, `_quickfile.py`, `_work_lifecycle.py`, and `application/modelo/__init__.py` alongside the original assertion consumers, adds the two CLI consumers, requires same-commit facade promotion, and explicitly deletes `resolve_registry_revision_for_work_target`, its facade export, `load_registry_tree`, asserted-ID selection, stale docstrings, and parallel work-path registry reads without a bridge.

### Native-owner facade promotion

CLOSED. S161, S164, and S166 each now include `application/modelo/__init__.py`, same-commit promotion through the sole canonical `cadrumo.application.modelo` facade, public-surface parity tests, and explicit refusal of private-only or non-facade bridge paths before S167 registration.

### Remediation verdict

PASS. Commit `ec5c87210f33cda9f59815d675d8ce30e3bf65be` closes all three recorded HIGH findings without changing step order, dependencies, comparison domains, or one-step/one-commit granularity. `vaultspec-core vault plan check` reports only the already-adjudicated intentional `PLAN022` display-order warning. S168-S174 are now sufficiently scoped for execution under the accepted ADR and referenced contracts.
