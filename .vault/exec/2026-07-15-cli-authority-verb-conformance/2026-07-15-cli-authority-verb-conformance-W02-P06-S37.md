---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-16'
modified: '2026-07-16'
body_hash: 'sha256:91befe08136337bc5a2c48c60b4a6de99d9f4313a025e15dd6e98bdc75d6e35d'
step_id: 'S37'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Atomically replace broad auth clear across backend and live CLI contracts with typed target-scoped logout_operator_auth and reset_operator_auth, complete provider session coverage, safe secret and lock cleanup, distinct schemas and events, exact contract/risk/help/write metadata, four-locale help, and real workflow and command tests without a compatibility wrapper

## Scope

- `src/cadrumo/application/auth/_operator_results.py`
- `src/cadrumo/application/auth/_operator_scope.py`
- `src/cadrumo/application/auth/_sessions.py`
- `src/cadrumo/application/auth/_acquisition_lock.py`
- `src/cadrumo/application/auth/_operator.py`
- `src/cadrumo/application/auth/__init__.py`
- `src/cadrumo/application/tests/test_cli_workflow_verification.py`
- `src/cadrumo/application/auth/tests/test_operator_storage_session.py`
- `src/cadrumo/entrypoints/cli/_config/_auth.py`
- `src/cadrumo/entrypoints/cli/_config_payloads.py`
- `src/cadrumo/application/storage_write_policy.py`
- `src/cadrumo/application/operator_surface/_contract.py`
- `src/cadrumo/application/operator_surface/_risk_table.py`
- `src/cadrumo/application/operator_surface/_help.py`
- `src/cadrumo/core/errors/registry/_application_part1.py`
- `src/cadrumo/locales/en.yml`
- `src/cadrumo/locales/es.yml`
- `src/cadrumo/locales/ca.yml`
- `src/cadrumo/locales/hu.yml`
- `src/cadrumo/entrypoints/cli/_config/tests/test_auth_round5_surface.py`
- `src/cadrumo/entrypoints/cli/tests/test_destructive_verbs_require_yes.py`
- `src/cadrumo/entrypoints/cli/tests/test_output_language_parity.py`
- `src/cadrumo/entrypoints/cli/tests/test_workflow_surface.py`

## Description

- Replace the broad auth-clear result and facade with distinct, strict, secret-free logout and reset contracts.
- Resolve explicit provider, all-provider, configured-provider, and explicit target-bucket scopes without switching the global active pointer.
- Delete provider sessions and locks through exact bucket routes, including the production Cl@ve Permanente session stem.
- Preserve provider and certificate configuration on logout; remove configuration, certificate registrations, and canonical secure-storage secrets on reset.
- Suppress duplicate state writes and events on idempotent reruns, and emit events only for providers whose artefacts or configuration changed.
- Replace the CLI command, schemas, operator contract, risk metadata, write policy, help inventory, and four-locale reference text without a compatibility alias.
- Add real encrypted-storage, ambient-session restoration, token-root, event, reserved-provider, schema, language, and destructive-confirmation coverage.

## Outcome

- `aeat config auth logout` now terminates local provider sessions without removing provider configuration or locks.
- `aeat config auth reset` now performs confirmed provider-custody cleanup and reports only actual effects.
- Explicit bucket B operations restore an ambient bucket A session unchanged.
- Known reserved providers are valid idempotent targets; omitted scope without configured state and conflicting `--provider` plus `--all` are typed localized refusals.
- The executable application and CLI source tree contains no old auth-clear facade, payload, command registration, risk key, or write-policy key.
- Focused verification passed: 13 auth/workflow tests, 22 auth CLI and confirmation tests, 6 output-language tests, 149 schema/operator-contract tests, 17 registry tests, four locale audits, Ruff, and all five import-linter contracts.

## Immutable composite delivery

The original S37 cutover was not delivered as an isolated commit. It was
distributed across operator-directed mixed flush commits. History is preserved
as landed; the closed-world attribution rule below assigns S37 ownership only
to the named paths or hunks. Every other path or hunk in a mixed commit is
explicitly excluded from S37 ownership.

| Commit | S37 attribution | Co-flushed exclusion |
|---|---|---|
| `1c59f64326` | `src/cadrumo/application/auth/__init__.py`; `_acquisition_lock.py`; `_certificate_sources.py` auth-reset wording hunk; `_operator.py`; `_operator_results.py`; `_operator_scope.py`; `_sessions.py`; `auth/tests/test_operator_storage_session.py`; `application/operator_surface/_help.py`; `application/storage_write_policy.py`; `application/tests/test_cli_workflow_verification.py`; auth hunks in `application/operator_surface/_contract.py` and `_risk_table.py` | Ledger, registry, user-profile, and operator-surface test paths; profile-lock hunks in `_contract.py` and `_risk_table.py` |
| `c247f94f97` | `src/cadrumo/entrypoints/cli/_config/_auth.py`; `_config/tests/test_auth_round5_surface.py`; `_config_payloads.py`; `entrypoints/cli/tests/test_destructive_verbs_require_yes.py`; `test_output_language_parity.py`; `test_workflow_surface.py` | Every other CLI, certificate, custody, modelo, registry, ledger, generic test, and MCP path in the commit |
| `3ac3fb25e1` | Auth error-registration hunks in `src/cadrumo/core/errors/registry/_application_part1.py` | Terminology, master-key, other error-registry, core-resource, corpus, and domain-registry paths |
| `374d1d7e39` | Auth provider/scope errors, logout/reset help, corrupt-session guidance, retired clear-key removal, and operator-help auth hunks in `src/cadrumo/locales/ca.yml`, `en.yml`, `es.yml`, and `hu.yml` | All other hunks in those shared catalogues; `src/cadrumo/locales/cli.py` in full |
| `33f7998ac3` | No S37-owned path or hunk | Generic CLI runner and data-size-budget work. This commit remains listed only because it belongs to the reviewed flush chronology. |
| `001004ee2f` | Full S37 execution record; S37 closure/scope and duplicate-downstream-row hunks in `.vault/plan/2026-07-15-cli-authority-verb-conformance-plan.md` | Every other Vault path; every unrelated campaign/governance hunk in the shared plan |
| `1a8ee75547` | All 27 changed paths: revision-aware secure-object persistence, atomic workflow/event writes, auth cleanup intent and mutation span, central live-session serialization, CLI/help/locales, import-linter cleanup, and real recovery/concurrency tests | None |

This manifest is path-exact for commits whose files are exclusively S37-owned.
For `_contract.py`, `_risk_table.py`, the four locale catalogues, and the shared
plan, attribution is intentionally hunk-level because those files also carried
unrelated work in the same immutable commit.

The exact corrective-commit path manifest for `1a8ee75547` is:

- `.importlinter`
- `src/cadrumo/adapters/persistence/profile/buckets.py`
- `src/cadrumo/adapters/persistence/storage/sql/_secure_object_records.py`
- `src/cadrumo/adapters/persistence/storage/sql/_secure_object_row_codec.py`
- `src/cadrumo/adapters/persistence/storage/sql/secure_objects.py`
- `src/cadrumo/adapters/persistence/storage/sql/tests/test_secure_objects_part1.py`
- `src/cadrumo/application/auth/__init__.py`
- `src/cadrumo/application/auth/_certificate_sources_operator.py`
- `src/cadrumo/application/auth/_models.py`
- `src/cadrumo/application/auth/_mutation.py`
- `src/cadrumo/application/auth/_operator.py`
- `src/cadrumo/application/auth/_operator_results.py`
- `src/cadrumo/application/auth/_operator_scope.py`
- `src/cadrumo/application/auth/_sessions.py`
- `src/cadrumo/application/auth/tests/test_operator_storage_session.py`
- `src/cadrumo/application/auth/tests/test_operator_transaction_recovery.py`
- `src/cadrumo/application/workflow/_persistence.py`
- `src/cadrumo/core/__init__.py`
- `src/cadrumo/core/errors/registry/_application_part1.py`
- `src/cadrumo/core/secure_object_write.py`
- `src/cadrumo/domain/buckets/_event.py`
- `src/cadrumo/entrypoints/cli/_config/_auth.py`
- `src/cadrumo/entrypoints/cli/_config/tests/test_auth_round5_surface.py`
- `src/cadrumo/locales/ca.yml`
- `src/cadrumo/locales/en.yml`
- `src/cadrumo/locales/es.yml`
- `src/cadrumo/locales/hu.yml`

## Corrective remediation

Commit `1a8ee75547` closes the runtime findings raised after the initial
cutover:

- `WorkflowStateRepository` now performs bounded revision-aware
  compare-and-swap updates, including concurrent first-write collisions.
- Workflow state and append-only bucket events commit in one SQL unit of work.
- Logout and reset persist a secret-free cleanup intent before external
  deletion and resume the same operation after interruption.
- One reentrant per-bucket auth mutation span serializes configure, live session
  acquisition, certificate source and secret mutation, logout, and reset.
- A pending cleanup intent rejects non-resume auth writers, including the
  central session service used by live application reads.
- Stable operation identifiers and timestamps make recovery events
  deterministic and exactly-once.

Independent verification after remediation passed:

- Complete authentication application suite: 146 tests.
- Real recovery and concurrency suite: 8 tests.
- Supervisor high-risk auth, storage, and CLI slice: 37 tests.
- Supervisor central-session slice: 5 tests.
- Workflow, secure-object, and error-registry focused suite: 76 tests.
- Locale and i18n suite: 36 tests.
- Namespace and write-policy suite: 36 tests.
- Import-linter: 3,427 files, 16,219 dependencies, five contracts kept, zero
  broken.
- Focused Ruff, `compileall`, `git diff --check`, and the feature-scoped Vault
  check passed.

## S37 audit-derived pre-release gates

S37 logout/reset runtime and delivery attribution are complete. The following
additional gates were discovered or reaffirmed by the S37 audit and remain
binding before release:

- `W02.P05.S62-S64` must verify and commit removal of the direct `AuthState()`
  replacement present in the committed S37 baseline at
  `src/cadrumo/application/config_reset.py`, composing target-scoped
  `reset_operator_auth`. Uncommitted candidate work is not closure evidence.
- `W02.P07.S48` and `W02.P07.S51`, with CLI proof in `W04.P13.S118`, must make
  ordinary certificate-secret set/remove crash-resumable with a secret-free
  durable intent or outbox. A failed event commit must not leave a completed
  credential mutation with a missing or incorrectly classified audit event.
- Assigned terminology and generated-reference steps must remove remaining
  historical spellings from generated artefacts and refresh semantic search.

This is not the repository's complete remaining-work inventory. The full
campaign plan remains authoritative, including direct S37 verification
`W02.P06.S43-S46`, the complete certificate-authority phase
`W02.P07.S47-S52`, their CLI and contract consumers, and the W05/W06
conformance and release gates.

## Notes

- A transient Windows file-replace lock interrupted one Hungarian locale-manager write. Retrying the remaining manager operations completed successfully; no locale file was edited manually.
- The first CLI pytest invocations selected no tests because project defaults select the unit marker. Re-running the same focused files with the integration marker produced the passing results recorded above.
- Certificate keyring removal, the broad `config reset` composition, and
  certificate-secret event recovery remain outside S37 under their assigned
  downstream plan work.
