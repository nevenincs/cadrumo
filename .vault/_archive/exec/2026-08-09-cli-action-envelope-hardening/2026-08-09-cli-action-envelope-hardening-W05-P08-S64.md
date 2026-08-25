---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:30fb36ab939f0527407a8af6fc2eaabf5a7d8fb402211be689cb64b4d48bd98a'
step_id: 'S64'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Prove the entrypoint registry shard is taxonomy-only with no recovery authority, retaining its two historical defaults only in the S50 ledger where current fingerprints are exclusively owned by S88, S89, and S114

## Scope

- `src/cadrumo/core/errors/registry/_entrypoints.py`

## Description

- Ground the shard against the accepted ADR, immutable preimage, current-source rehoming join, and semantic discovery results.
- Prove every declared `ErrorCode` tuple contains only the canonical taxonomy fields and carries no recovery action, condition, command identity, policy, or rendered operator text.
- Reconcile the ledger only through the S50 derivation tool after the plan moved the calculate CLI path from S59 to S91.
- Generate an isolated candidate from stable plan and ledger hashes; admit the write only after the structural delta contained exactly the five approved owner transfers.

## Outcome

- Confirm nine entrypoint taxonomy tuples, each with exactly `code`, `category`, `message_key`, `retryable`, and `runbook_id`.
- Confirm nine immutable-preimage entrypoint rows, of which exactly two carry non-null historical defaults; current fingerprints partition exclusively to S88 (one), S89 (two), and S114 (two).
- Preserve all 238 historical identities, dispositions, current identities, and fingerprint identities during reconciliation; apply exactly five S59-to-S91 owner transfers for the calculate CLI producer and refresh 18 non-gating locators.
- Record the stable pre-write ledger SHA-256 `1CF48AF26B010D7BBCDD5F15A93F87D83FDDAF431E9373F6A09C4407044F4457`, plan SHA-256 `618F2930AB82C53D6BD2E8E5BDC7A44FA805F9A1E1EF4D55203BC02733708F2E`, and post-write ledger SHA-256 `04676EBB6B69F6A86A9265402D30E6ABFCCC4C9B89D55FB24983B04EBBFAE90D`.

## Verification

- `pytest -m unit src/cadrumo/core/errors/tests src/cadrumo/entrypoints/cli/tests/test_command_group_import_classification.py`: 57 passed.
- `pytest -m integration src/cadrumo/entrypoints/cli/tests/test_error_registry_contract.py`: 30 passed.
- `ruff check`, `ruff format --check`, and `basedpyright` for `src/cadrumo/core/errors/registry/_entrypoints.py`: passed.
- S50 migration check and direct rehoming validator: 238 rows validated at the stable pre-write boundary.
- `pytest dev/tests/test_error_code_default_recovery_rehoming.py`: 74 passed.

## Notes

This is canonical metadata maintenance required by the approved S59-to-S91 plan ownership correction, not a registry behavior change. After the 74-test gate, peer-owned S96 source edits shifted two non-gating locator coordinates for one Modelo error. Direct validation remains green; the deterministic byte-equality migration check is intentionally stale until S50 refreshes those peer locators. No additional ledger write was made. The separately observed raw config notice drift remains exclusively owned by S89.
