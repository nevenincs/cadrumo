---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:d4e8d8da097780d5b98ec57bd2980822cba6c939d12a0abcb69756a911350da1'
step_id: 'S66'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Replace preflight remediation prose with locale-neutral facts and typed precondition verdicts

## Scope

- `src/cadrumo/application/preflight.py`
- `src/cadrumo/application/tests/test_preflight.py`
- `src/cadrumo/entrypoints/cli/_config/_check_payloads.py`
- `src/cadrumo/entrypoints/cli/_config/_check_cli.py`
- `src/cadrumo/entrypoints/cli/_config/tests/test_check_preflight.py`
- `src/cadrumo/entrypoints/cli/_config/tests/test_s89_action_conformance.py`

## Description

- Re-ground preflight producer predicates and config-check consumers with semantic and exact search.
- Replace producer-owned detail and remediation prose with closed condition identities, locale-neutral facts, and invariant-checked precondition verdicts.
- Give each unhealthy row either a canonical action reference or an explicit no-recovery outcome at the application boundary.
- Preserve the producer facts and exact resolved action or outcome through the config-check payload and text renderer without compatibility fields.
- Exercise healthy and unhealthy rows plus JSON and text rendering across every supported locale with real production imports.

## Outcome

- `PreflightCheck` now rejects unhealthy rows without a typed verdict and healthy rows carrying a failed verdict.
- Auth-provider and storage-initialization failures reference canonical operator actions; failures without a safe recovery action carry `operator_decision` explicitly.
- Registry, portal, storage, corpus, Windows-path, and auth observations are machine facts rather than source-language prose or flattened exceptions.
- `CheckPreflightPayload` preserves the exact facts and resolved precondition result; it no longer redeclares a second outcome field or invents a fallback outcome.
- No runtime remediation command, English default, renderer-owned action inference, or compatibility field remains in the migrated path.
- S66 and the dependent S89 remain open for independent review and ledger closure.

## Verification

- Application preflight unit tests: 18 passed.
- Config-check integration and all-locale action conformance tests: 12 passed.
- Ruff check passed for all six changed production and test files; Ruff formatting is canonical.
- Python compilation passed for the three production modules.
- Focused `basedpyright` is clean for the application producer; the config module retains pre-existing strict diagnostics around CLI registration and dynamically typed capability rows.

## Notes

- S89 is the shared downstream consumer dependency. Its execution record now reflects lossless preservation of the S66 contract instead of the temporary prose-dropping behavior.
- No locale catalogue change was required because all new producer values are locale-neutral schema facts and canonical action identities.
