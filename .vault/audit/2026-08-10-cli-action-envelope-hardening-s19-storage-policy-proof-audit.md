---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:375c0165e99ae36bb03ad2923cecdb5694aa9a562cfaad28e981dbcbd442cd32'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-adr]]"
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# `cli-action-envelope-hardening` audit: `S19 storage-policy exact scenario proof`

## Scope

Audited the `W03.P05.S19` remediation in
`src/cadrumo/application/tests/test_storage_write_policy.py` against the
current storage-write-policy producer and the strict operator-action models.
The review covered all seven current policy classifications, the two refusing
routes, fixed condition/evidence/action literals, complete missing-binding
serialization including null source fields, allowed verdict absence,
conditionality, action-versus-no-recovery exclusivity, and the settings
environment identities.

The matrix keeps the expected refusal contracts independent of the producer:
it does not mirror route classification or verdict-building logic, uses no
mock, fake, stub, patch, monkeypatch, skip, or xfail mechanism, and does not
perform the clean-root recovery-and-retry journey reserved for `W03.P05.S20`.

Current verification passed: the focused suite reported 16 passed in 7.43
seconds; the exact reconciliation selector reported one passed in 3.66
seconds; Ruff check, Ruff format check, and basedpyright completed cleanly.

## Findings

### production-derived-scenario-denominator | high | Closed: every live policy classification requires one proof row

Status: closed. `_STORAGE_WRITE_POLICY_SCENARIOS` now uses the canonical
`StorageWritePolicyCode.value` as each scenario key, rejects duplicate keys,
and requires its exact key set to equal the live enum's value set. Each matrix
row also asserts that its key equals the independently fixed expected `code`
literal before comparing the full serialized decision. The reported mutation
probe added `unproved_classification` temporarily and made the reconciliation
selector fail; the production module is now unchanged in the working tree.
This prevents a new policy branch from becoming unproved while preserving the
non-tautological fixed output contract.

## Recommendations

- Closed: retain the exact scenario-key reconciliation and fixed serialized
  contract literals for future policy classifications. Keep clean-root recovery
  dispatch and retry out of this test module until `W03.P05.S20` owns that
  proof.
