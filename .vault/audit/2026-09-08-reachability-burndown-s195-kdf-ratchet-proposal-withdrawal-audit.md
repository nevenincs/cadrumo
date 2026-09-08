---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:c85ffb4abdae153e39b44e3a0f9ed9be5f132e376a618134710b36dd78fd6f8c'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
  - "[[2026-09-04-reachability-burndown-W05-P12-S195]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
---

# `reachability-burndown` audit: `S195 KDF ratchet proposal withdrawal implementation review`

## Scope

Independent bounded review of W05.P12.S195 against the accepted profile-password-custody KDF and rotation contract. The review covered the Step row and record and the complete diff in `kdf_supervision.py` and `test_kdf_supervision.py`, with attention to removal of the proposal-only surface and preservation of enrollment calibration, supervised Argon2 derivation, unlock, and password-rotation ownership.

## Findings

No findings.

`ProfileCustodyKdfRatchetProposal`, `propose_profile_kdf_ratchet`, their sole self-test, and the now-unused private `kdf_strength` import were removed without a replacement facade or compatibility mechanism. The unused exported warm-up count name was also removed, but the live calibration algorithm still executes exactly one discarded supervised warm-up and then `PROFILE_CUSTODY_KDF_SAMPLE_COUNT` five measured samples for each eligible point. The bounded grid, resource eligibility, per-sample and total deadlines, median selection, target band, fixed eligible fallback, child supervision, sentinel verification, existing envelope parameters, unlock functions, and explicit transaction-owned password rotation paths are unchanged.

The Step Record names the exact two files and exact Ruff, focused pytest, production-metastate, residue, and reachability commands. Its live reachability result distinguishes the dirty-tree aggregate findings from the removed cluster's absence. Independent focused execution passed all 21 KDF supervision tests, and the exact removed-symbol residue scan found no remaining occurrences.

## Recommendations

Approve W05.P12.S195. No production, test, ADR, or Step Record correction is required.
