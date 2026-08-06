---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:1e0fdc92478f9e5a710e7bee1fc55cfae5febc21055a7ed79af67d0c92f9e2b1'
step_id: 'S29'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Strengthen the custody-carry proof for the canonical catalogue from a non-empty assertion to a strict save-export-import-load equality roundtrip with every defaultable field populated non-default, plus the anti-tautology proof that a mutated exported payload surfaces refusal or inequality

## Scope

- `src/cadrumo/application/user_profile/tests/test_custody_store_matrix.py`

## Description

- Replaced the presence check with a strict whole-model comparison across the export/import boundary.
- Gave both custody halves one shared fixture populating every optional axis with a non-default value.
- Added the anti-tautology proof in the only shape available at this boundary, and recorded why the drafted shape was not.
- Added a guard that the fixture itself has not weakened.

## Outcome

**The invoice custody proof now compares the record; it previously compared nothing but its existence.**

The old verifier asserted only that the loaded catalogue was non-empty. That passes even when the boundary drops a field and reloads its default, which is the precise blindness the roundtrip discipline names: the dropped value and the default are the same value, so the comparison cannot tell them apart.

The fixture is the load-bearing half. A carry proof is only as strong as what it populates, so every optional axis the aggregate carries is now set to a non-default value — bucket attribution, invoice class, series, the rectified number, the operation date and its role, both addresses, the linked transactions, notes, both retención fields, recargo, suplido, payment id, and both record-lifecycle stamps.

**The anti-tautology half took a different shape than the plan drafted, and the reason is a property of the system rather than a convenience.** The drafted proof mutates the exported payload, deletes a field and reloads. That is not available here: the profile export is an encrypted, recovery-wrapped archive, so there is no plaintext payload to edit without defeating the protection the export exists to provide. Reaching in to corrupt it would have meant weakening the boundary in order to test it.

So the property is proven directly. For every optional axis the fixture populates, a variant with that axis reset to its default must compare UNEQUAL to the populated record — which is exactly the state a dropped-and-re-defaulted field produces on reload. That demonstrates the comparison is sensitive to each field individually, rather than passing because most fields happen to match.

The same test also asserts the fixture does **not** leave any of those axes at its default. Without that, a fixture that weakened over time would silently narrow the proof while both tests stayed green — the failure mode this Step exists to remove, reappearing one level up.

**A premise correction the plan already carried is confirmed:** the canonical catalogue *is* carried today. Its namespace is registered with structured custody and an unresolvable namespace raises rather than dropping silently. This Step strengthens a weak proof; it did not add a missing registration.

## Verification

    uv run --no-sync pytest src/cadrumo/application/user_profile/tests/test_custody_store_matrix.py -m "integration or unit" -n 0 -q --no-header
    5 passed in 19.14s

    uv run --no-sync ruff check src/cadrumo/application/user_profile/tests/test_custody_store_matrix.py
    All checks passed!

One RED en route is worth keeping, because it shows the fixture is exercising real invariants rather than a permissive shape:

    Value error, payment_id must be a 64-character lowercase hex digest

The populated fixture is validated on construction, so every value it carries is one the aggregate actually accepts — a fixture built by bypassing validation could carry impossible values and still compare equal to itself.

## Notes

The equality-variant construction deliberately bypasses validation. That is correct for this proof: the shape being modelled is what a LOSSY boundary would hand back, and such a record need not be valid — requiring it to validate would exclude exactly the corruptions the proof is looking for.

This closes the last lane-3 row on the conservation inventory that this campaign owns directly. The remaining open row is the absence of canonical lifecycle events, which is not a custody question.
