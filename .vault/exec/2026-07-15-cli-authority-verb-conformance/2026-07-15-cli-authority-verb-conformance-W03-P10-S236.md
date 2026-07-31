---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:ce6a5a33a7c8cbca9223936886a65f52805c896c0859d83cff76052440b0b65f'
step_id: 'S236'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Remove EvidenceBundleService replay, its public export, and backend tests while preserving evidence check and unrelated observability replay facilities

## Scope

- `src/cadrumo/application/evidence/_service.py`
- `src/cadrumo/application/evidence/__init__.py`
- `src/cadrumo/application/evidence/tests/test_evidence.py`

## Description

This Step is already satisfied at HEAD; the record documents the landed state verified against HEAD, independently re-verified after an earlier audit pass flagged it as unaudited due to unreliable search tooling. Commit `87f49c5d2f` removed the duplicate evidence-replay path in the same window as the ledger-evidence-atomicity campaign's P03.

- Remove `EvidenceBundleService.replay`: `check` under a second, weaker verb name.
- Remove the `modelo audit replay` CLI command and its `ModeloAuditReplayResult` schema registration, retitling the audit group help to (show/check/export).
- Remove the orphaned `cli.app.modelo.audit.replay_help` locale scaffold key.
- Remove the backend replay test from `test_evidence.py`.
- Preserve `EvidenceBundleService.check` and the unrelated observability parity-replay facility (`core.observability._replay.replay_run`), which is a distinct concept: offline replay of a recorded `RunTrace` against a fingerprint-gated environment, not an evidence-bundle verb.

## Outcome

`src/cadrumo/application/evidence/_service.py` defines only `build`, `show`, `check`, and `export` on `EvidenceBundleService`; no `replay` method exists. `__init__.py`'s `__all__` exports `EvidenceBundleRepository`, `EvidenceBundleService`, and `EvidenceBundleVerificationReport` with no replay-result schema. `test_evidence.py` carries no test referencing a `replay` method or result. `src/cadrumo/entrypoints/cli/_modelo_audit_cli.py` has no `replay` command, and `src/cadrumo/entrypoints/cli/tests/test_audit_verbs.py` carries two real-behaviour, non-tautological removal-proof tests: `test_audit_replay_command_is_removed` (invokes `aeat app modelo audit replay <id>` against the live Typer app and asserts refusal) and `test_audit_replay_result_schema_is_not_registered` (asserts `"modelo.audit.replay" not in SCHEMA_REGISTRY`). `src/cadrumo/core/observability/_replay.py` still defines `replay_run`, confirming the unrelated observability replay facility was preserved as the Step requires.

Independently re-verified against HEAD by direct source read of all three scoped files plus the CLI command module and the removal-proof test, not by grep alone: the service module, the facade `__all__`, and the CLI surface all confirm zero `replay` surface for evidence bundles, and the observability replay facility is confirmed present and untouched. No further removal work was required.

Gate: `uv run --no-sync pytest -m "" src/cadrumo/application/evidence/tests/test_evidence.py src/cadrumo/entrypoints/cli/tests/test_audit_verbs.py` reports 25 passed.

## Notes

This record was authored after the removal had already landed; it documents the verified state rather than performing new implementation work. This Step was not confirmed by an earlier audit pass due to unreliable search tooling in that pass; this record supersedes that gap with a direct source-level re-verification against current HEAD, distinguishing the evidence-bundle replay (removed) from the observability parity-replay facility (preserved, a genuinely distinct concept sharing only the word "replay").
