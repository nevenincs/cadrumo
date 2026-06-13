---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-active-profile-storage-runtime-discovery-audit]]'
  - '[[2026-05-26-secure-storage-production-hardening-W12-P20-S78]]'
  - '[[2026-05-26-secure-storage-production-hardening-W12-P20-S79]]'
  - '[[2026-05-26-secure-storage-production-hardening-W12-P20-S80]]'
  - '[[2026-05-26-secure-storage-production-hardening-W12-P20-S81]]'
---



# Active-profile storage runtime classification closeout audit

## Scope

This closeout completes W12.P20. It consolidates the rollout register and classification records created before active-profile `StorageRuntime` migration starts.

Covered classification records:

- S78 grouped the active-profile runtime discovery production index by adapter, application, domain, core, and CLI ownership.
- S79 classified direct no-argument `SecureObjectRepository()` defaults and inherited `SecureBoundRepository` defaults.
- S80 classified direct active-profile pointer, manifest, profile-bucket, and bucket-layout callers.
- S81 classified SQL route, active-profile, settings override, and master-key/session policy callers.

## Classified Surface

| Classification slice | Files or refs | Disposition set | Owning migration rows | Closeout status |
| --- | --- | --- | --- | --- |
| Runtime adoption register | `95` explicit production paths from the discovery audit | `runtime-default`, `manifest-discovery`, `bootstrap-custody`, `plaintext-exception`, `remote-mirror`, `retired` | S83-S102 | registered |
| Repository defaults | `75` default sites | `runtime-default`, `bootstrap-custody`, `test-runtime`, `retired` | S83-S87, S92-S95 | classified |
| Pointer/manifest/bucket calls | `75` direct calls on `71` distinct lines across `18` production files | `manifest-discovery`, `bootstrap-custody`, `runtime-default` | S89-S90, S96-S97 | classified |
| Route/profile/session policy | `41` production files with `140` refs; `123` test files with `377` refs | `runtime-default`, `bootstrap-custody`, `test-runtime` | S88-S95 | classified |

## Unresolved Exceptions

| Exception | Current state | Required owner | Required closeout |
| --- | --- | --- | --- |
| Legacy profile persistence adapters | `src/aeat/adapters/persistence/profile/assets.py` and `src/aeat/adapters/persistence/profile/inventory.py` still own retired `SecureObjectRepository()` defaults | S86 | remove the adapters, prove they are unreachable, or wrap them as explicit migration-only adapters before adapter migration closeout |
| Explicit-route tests | `123` test files still contain route/profile/session setup refs; many are legitimate refusal tests, many are repository roundtrips that should use a runtime profile | S92, S93, S95 | introduce sanctioned test runtime profile, migrate non-refusal tests, then list approved explicit-route tests |
| CLI transport-owned write/session policy | CLI root callback and profile lifecycle commands still own route/session/bootstrap behavior | S88, S89, S91 | move readiness/write policy to backend runtime/lifecycle services while preserving bootstrap exemptions |
| Profile lifecycle bootstrap custody | Profile create/switch/delete/repair spans intentionally retain manifest/pointer/session custody before runtime attachment | S89, S90 | keep as named lifecycle operations; prove no duplicate physical aggregate writer exists |
| Plaintext and side-store manifests | Attachment-local manifests, manual fetch manifests, export/cache/live side stores are outside active-profile manifest discovery | S96, S97, S99 | classify as secure-object migration, export-only, rebuildable cache, or accepted plaintext exception |
| Remote mirror providers | Outbound storage provider factory/local/Google Drive mirrors remain adjacent to runtime, not yet runtime-bound | S98 | bind provider selection to runtime-derived profile identity and encrypted mirror semantics |
| Namespace ownership | Secure-object namespace ownership remains distributed across repositories and repair heuristics | S20-S27, with remote mirror policy extension in S41 | introduce the namespace registry, register every discovered namespace family, replace local constants/repair heuristics with registry metadata, and enforce registry completeness |

## Owner Rows

| Owner row | Owns | Must prove |
| --- | --- | --- |
| S83 | Workflow state and bucket-event repositories | runtime-owned repository factory, active route match, missing-session refusal |
| S84 | Domain transaction, invoice, filing, submission, justificante, and modelo repositories | domain defaults no longer construct raw repositories |
| S85 | Application ledger, filing history, modelo reconciliation, calculation, usage-ratio, and calc-sheet repositories | application defaults use runtime factories and real runtime tests |
| S86 | Auth, AEAT observation, Google OAuth/session, LLM cache/usage, legacy profile persistence adapters, and outbound adapter repositories | adapter defaults are runtime-bound, legacy profile adapters are deleted or migration-wrapped, and remote mirrors are classified |
| S87 | Migrated repository family tests | active profile routing, route mismatch refusal, missing-session refusal, isolated test profile writes |
| S88 | CLI guarded write-verb policy | backend runtime policy owns refusal; CLI renders translated result |
| S89 | Profile create/switch/delete/logout storage spans | named lifecycle/runtime operations own bootstrap custody |
| S90 | Manifest discovery boundary | plaintext profile discovery remains separate from encrypted runtime attachment |
| S91 | CLI regression tests | bootstrap, explicit profile selection, environment selection, pointer selection, root fallback refusal, explicit route refusal |
| S92 | Test runtime profile helper | real isolated profile bucket, database, manifest, master-key session, runtime-bound repository |
| S93 | Explicit-route test migration | non-refusal tests leave ad hoc `aeat_database_url` setup |
| S94 | Runtime adoption guard | new production raw repository defaults and unapproved route tests are rejected |
| S95 | Test-isolation closeout | remaining explicit-route tests have approved refusal/classification ownership |
| S96-S99 | Side-store and mirror disposition | plaintext side stores and remote mirrors do not remain alternate sensitive backends |
| S100-S102 | Final rollout checks | scanner delta and final review prove every surface has one accepted disposition |
| S20-S27 | Secure-object namespace registry and enforcement | namespace ownership, sensitivity, schema, key grammar, and repair policy are registered and enforced |
| S41 | Remote mirror namespace policy fields | remote mirror policy is expressed through namespace registry entries |

## Migration Gate

Migration work may start only with these constraints:

- A production caller classified `runtime-default` must receive secure-object access through `StorageRuntime`, a runtime-owned repository factory, or an explicitly named lifecycle/runtime operation.
- A caller classified `manifest-discovery` may read plaintext profile pointer or manifest metadata, but must not unlock encrypted storage or create repositories.
- A caller classified `bootstrap-custody` must be converted into a named custody/lifecycle operation before it is treated as generally safe.
- A caller classified `test-runtime` must migrate to the sanctioned test runtime profile unless it is an approved route/session refusal test.
- A caller classified `plaintext-exception` or `remote-mirror` must not be retained without S96-S99 rationale and tests.
- A caller classified `retired` must be deleted or isolated as a migration adapter before final rollout closeout.

## Safety Notes

- No deprecated `config init` or `profile init` source guidance remains in `src/aeat` except an explicit regression-test docstring that asserts `config init` is not reintroduced.
- No `pragma` or `noqa` exception was added in this classification phase.
- No exception swallowing behavior was added. The only source edit in this phase was a docstring repair from retired init guidance to `aeat config profile create NAME`.
- No tests were added that use fakes, mocks, monkeypatch shortcuts, skips, xfails, or tautological assertions.

## Validation

- `uv run vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`
- `uv run --no-sync ruff check src/aeat/application/user_profile/_censo_errors.py`
- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py -q`
- Source scan for deprecated runtime command guidance under `src/aeat` found only the explicit `config init` regression-test docstring.
