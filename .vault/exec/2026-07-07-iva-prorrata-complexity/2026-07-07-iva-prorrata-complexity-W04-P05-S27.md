---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-08'
modified: '2026-07-17'
body_hash: 'sha256:1d4a261319653aee148a680f97592bb62494c387739e325cc8cde8abc4febf0e'
step_id: 'S27'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

# Add an is_interrupted=True entry to the encrypted-SQL prorrata register roundtrip fixture so the interrupted marker crosses the encrypted boundary under test

## Scope

- `src/aeat/adapters/persistence/profile/tests/test_prorrata_register_roundtrip.py`

## Description

- Add an `interrupted=True` (art. 105.Cinco sin-operaciones) entry to the encrypted-SQL prorrata register roundtrip fixture `_populated_register`, and assert after the encrypted save/load that the interrupted marker survives and the inactive year carries no provisional/definitive percentage.

## Outcome

The interrupted-ejercicio marker now crosses the encrypted secure-object boundary under test (previously covered only at the domain-JSON level), per aeat-roundtrip-discipline. The roundtrip suite is 4 passed under `-n0`, including the corrupt-payload and missing-field anti-tautology proofs which continue to exercise the first entry unaffected by the appended interrupted row.

## Notes

- The interrupted entry uses `regime = NINGUNA` (the inactive-year convention used by the domain-level interrupted tests); the register-model validator enforces that an interrupted entry carries no percentage/volume/provenance, so the fixture entry is a pure marker.
