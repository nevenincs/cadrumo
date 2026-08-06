---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:c3712f0b6198b21015e072083e421a4b1a5b43203d22a06b8ae44344b72249de'
step_id: 'S289'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Route the modelo evidence-covers-snapshot copy onto the public assert_evidence_covers_snapshot, and retire the cross-package private import the aggregation test uses to reach it

## Scope

- `src/cadrumo/application/modelo/_verification_actions.py`
- `src/cadrumo/application/aggregation/tests/test_ledger_filing_evidence.py`

## Description

- Confirmed the private `_assert_evidence_covers_snapshot` in `_verification_actions.py` had a body identical to the canonical `assert_evidence_covers_snapshot` in `application/aggregation/_ledger_filing_snapshot.py`, differing only in the raised type: the copy raised the wider `ModeloError`, the canonical raises `ModeloValidationError`.
- Promoted `assert_evidence_covers_snapshot` into the aggregation package public facade (`application/aggregation/__init__.py` import block and `__all__`), the precondition for consuming it across the package boundary.
- Deleted the private copy and routed the sole verify-flow caller through the public `assert_evidence_covers_snapshot`.
- Removed the now-dead `ModeloError`, `LedgerFilingEvidence`, and `LedgerFilingSnapshot` imports from `_verification_actions.py` left unused by the deletion.
- Retired the cross-package private import in the aggregation test: `from ...modelo._verification_actions import _assert_evidence_covers_snapshot` became `from .. import assert_evidence_covers_snapshot` (the owning package's public facade), and its two call sites were rerouted.

## Outcome

The evidence-covers-snapshot invariant now has one owner, `assert_evidence_covers_snapshot` in the aggregation package, consumed by the modelo verify flow and the aggregation test through the aggregation public facade. The cross-package private reach from the aggregation test into the modelo package is gone.

Error-type resolution (deliberate): the copy raised `ModeloError`, the canonical raises `ModeloValidationError`. `ModeloValidationError(ModeloError, ValueError)` is a strict subclass of `ModeloError`, so routing onto the canonical narrows the raised type to the more specific validation error — semantically correct for an evidence-coverage invariant violation. Every existing `except ModeloError` / `pytest.raises(ModeloError)` still catches it because subclass instances match; no caller catches the wider type and misses the narrower one.

Discovery basis: the mandated `vaultspec-rag` code index was measured untrustworthy (mid-rebuild, control probes missed), so a structural AST duplicate scan supplied the cluster and every claim was re-established by exact `rg` search and by reading both bodies and the `ModeloError`/`ModeloValidationError` class hierarchy.

Verification (HEAD `ab8f62b3770ab84e8e0d62f90131259f8303c568`):

- `uv run --no-sync ruff check` and `ruff format --check` on the three touched files — `All checks passed! 3 files already formatted`.
- `uv run --no-sync pytest src/cadrumo/application/aggregation/tests/test_ledger_filing_evidence.py src/cadrumo/application/aggregation/tests/test_ledger_filing_snapshot.py -n0 -q` — 18 collected, `18 passed in 24.37s`.
- `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_art109_activity_income_period_evidence.py -n0 -q` — 6 collected, `6 passed` (exercises the verify flow that calls the canonical).
- Mutation proof: neutralising the surviving canonical's raise (`if False and ...`) reddened both the aggregation evidence and snapshot coverage guards to `2 failed, 16 passed` with `DID NOT RAISE ModeloValidationError`; restored to `18 passed`.

## Notes

None. The deletion left three imports dead in `_verification_actions.py`; all were removed and ruff confirms no unused-import residue.
