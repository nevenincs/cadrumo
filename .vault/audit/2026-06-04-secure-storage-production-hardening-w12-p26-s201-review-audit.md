---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S201]]'
---

# `secure-storage-production-hardening` `W12.P26.S201` Review

## S201-001 | PASS | Observation repository stays secure-bound and runtime-owned

`CalculationObservationRepository` and `IvaWalletDecisionRepository` both inherit
`SecureBoundRepository` and declare registered secure-object namespace,
sensitivity, schema, and payload type contracts. Default construction therefore
continues to resolve the active-profile runtime repository through the shared
secure-bound storage path.

The production edit is deliberately small: the wallet decision repository now
uses the centralized `UTF_8_ENCODING` constant for hashed-key input, audit-event
payload serialization, and history payload decoding.

## S201-002 | PASS | Wallet decisions now share the runtime migration gates

`test_runtime_migrated_repositories.py` now includes
`IvaWalletDecisionRepository` latest-decision and decision-history reads in the
missing active-session refusal parametrization, route/session mismatch refusal
parametrization, and active-profile isolation flow. The isolation gate writes
real `IvaCompensationReconciliationDecision` domain objects into bucket A and
bucket B runtime contexts, verifies bucket B cannot see bucket A before writing,
and verifies bucket A still reads only its original latest decision and immutable
history event.

This closes the S201 coverage gap without fakes, mocks, monkeypatches, skipped
tests, xfails, or mirrored storage logic.

## S201-003 | PASS | Locale audit blocker was cleared through the required CLI

The required locale audit initially failed because
`application.calculations.iva_compensation.errors.modelo_303_only` and
`application.calculations.iva_compensation.errors.seed_conflict` were absent from
the concrete locale catalogues. The missing leaves are consumed by the IVA
compensation history code reviewed in the immediately preceding row, so this
blocked the S201 validation gate even though it was not introduced by the wallet
decision edit.

The four locale catalogues were updated only through
`python -m aeat.locales set`, per the locale-work mandate. The same
`python -m aeat.locales audit` gate now reports `ok` for Catalan, English,
Spanish, and Hungarian.

## S201-004 | PASS | Convention hygiene

No new exception classes, broad exception handlers, silent exception swallowing,
naked environment access, direct settings bypass, raw secure-object repository
construction, user-facing string surface, `noqa`, `pragma`, monkeypatch, fake,
mock, skip, xfail, or tautological test was introduced in the S201 code slice.

Validation:

- `uv run --no-sync ruff check src/aeat/application/calculations/_observations_repository.py src/aeat/application/calculations/test_observations_repository.py src/aeat/application/calculations/test_observations_repository_roundtrip.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py` passed.
- `uv run --no-sync pytest src/aeat/application/calculations/test_observations_repository.py src/aeat/application/calculations/test_observations_repository_roundtrip.py -q` passed with 23 tests.
- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "iva_wallet_decision or calculation_observations or application_repository_defaults_isolate_active_profile_writes" -q` passed with 7 selected tests.
- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -q` passed with 83 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: `vaultspec-code-reviewer` review returned two LOW findings. The
first finding observed that the initial runtime gate covered only latest wallet
decisions and did not explicitly call `load_decision_history()` for the immutable
history namespace. That finding is resolved by the final test update described
above. The second finding noted locale catalogue scope and YAML formatting churn;
that is accepted as CLI-managed validation-blocker cleanup because locale work
was required to use `python -m aeat.locales`, and the post-update locale audit is
clean.

Disposition: close `AFR-099`.
