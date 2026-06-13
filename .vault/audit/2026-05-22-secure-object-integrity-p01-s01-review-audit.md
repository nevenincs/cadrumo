---
tags:
  - '#audit'
  - '#secure-object-integrity'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-config-repair-shape-adr]]'
  - '[[2026-05-14-cli-workflow-redesign-integrity-warning-stability-adr]]'
  - '[[2026-05-21-secure-object-database-drift-research]]'
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-22-secure-object-integrity-P01-S01]]'
---



# `secure-object-integrity` Code Review



P01-S01-001 | MEDIUM | Attribution context model is not safe-by-construction for bucket/profile identifiers
`RepairUnreadableRowAttribution` exposes `context_bucket_id`, `object_key_hint`, `context_note`, and `reason` as unrestricted strings while the plan and wallet grounding require unreadable-row attribution to carry only safe metadata and not print active profile bucket UUIDs, taxpayer ids, filing identifiers, private natural keys, or payload-derived context. The current list-report builder redacts active bucket context to `active_profile`, but the new attribution model itself would accept and serialize a raw bucket/profile id or natural-key hint without validation. This leaves the safety contract dependent on every future P01.S02/P01.S03 producer remembering redaction discipline instead of making unsafe attribution states unreachable at the Pydantic boundary. Replace raw context string fields with constrained safe labels or validators that reject UUID/profile/taxpayer/natural-key forms, and add invariant tests that prove rejected disclosure attempts fail validation.

Resolution: addressed in P01.S01 before plan closure. The row attribution model now restricts `context_bucket_id` to redacted labels, rejects concrete natural-key suffixes in `object_key_hint`, and rejects raw taxpayer/profile/bucket/digest identifier patterns in context text. Focused validation covers these rejection paths.

P01-S01-002 | LOW | Timestamp range fields can contradict the rows they summarize
`RepairUnreadableNamespaceAttribution` validates row count and namespace membership, but it does not validate that `first_written_at` is less than or equal to `last_written_at`, nor that populated row timestamps fall within the declared range. Because the attribution report is intended to group unreadable rows by timestamp range and likely origin, a malformed report can mislead operators about contamination windows while still passing model validation. Add model validators and focused tests for reversed ranges and row timestamps outside the declared range.

Resolution: addressed in P01.S01 before plan closure. The namespace attribution validator now rejects reversed ranges and row timestamps outside the declared range. Focused validation covers reversed range and out-of-range timestamp rejection.

## Gates Observed

- `uv run ruff check src/aeat/application/repair_integrity.py src/aeat/application/test_repair_integrity.py` passed.
- `uv run pytest src/aeat/application/test_repair_integrity.py` passed: 19 tests after remediation.

## Test Rule Review

The focused tests exercise real `SecureObjectRepository`, real SQLite engines, and real `EphemeralMasterKeyProvider` sessions. I did not find `_Fake`, `_Stub`, monkeypatch, skip, xfail, or duplicated business-logic calculation assertions in the scoped tests.

## Re-review 2026-05-22

P01-S01-001 is resolved. The remediation moved the disclosure guard into the `RepairUnreadableRowAttribution` model boundary: `context_bucket_id` is restricted to empty or `active_profile`, `object_key_hint` rejects concrete natural-key suffixes, and context text rejects taxpayer/profile/bucket/digest identifier patterns. The added focused test proves these invalid states raise `ValidationError`.

P01-S01-002 is resolved. The namespace attribution validator now rejects reversed timestamp ranges and row timestamps outside the declared range, with focused validation coverage for both failure paths.

No additional findings were opened in the scoped re-review.

Re-run gates observed:

- `uv run ruff check src/aeat/application/repair_integrity.py src/aeat/application/test_repair_integrity.py` passed.
- `uv run pytest src/aeat/application/test_repair_integrity.py` passed: 19 tests.
