---
tags:
  - '#exec'
  - '#clitui-ledger'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:39221d5a91224eee93665c6db59d834f0a9ad2b7c7061f8f0067f4a9e3989ee4'
step_id: 'S11'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
---

# Mark every TUI-applicable union and matrix row held until G3, retain component-only versus installed distinctions, and fail closed on hold drift, additions, or an unauthorized lift

## Scope

- `dev/quality/clitui_ledger_capability_matrix.py`
- `dev/quality/tests/test_clitui_ledger_capability_matrix.py`
- `.vault/reference/2026-09-04-clitui-ledger-reference.md`

## Changes

- `M` `dev/quality/clitui_ledger_capability_matrix.py`
- `M` `dev/quality/tests/test_clitui_ledger_capability_matrix.py`
- `M` `.vault/reference/2026-09-04-clitui-ledger-reference.md`
- `M` `.vault/plan/2026-09-04-clitui-ledger-plan.md`
- `M` `.vault/index/clitui-ledger.index.md`
- `A` `.vault/exec/2026-09-04-clitui-ledger/2026-09-04-clitui-ledger-W01-P03-S11.md`
- `verify:` `uv run --no-sync pytest -q -n 0 dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> pass (222 passed)
- `verify:` `uv run --no-sync ruff format --check dev/quality/clitui_ledger_capability_matrix.py dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> pass
- `verify:` `uv run --no-sync ruff check dev/quality/clitui_ledger_capability_matrix.py dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> pass
- `verify:` `uv run --no-sync ty check dev/quality/clitui_ledger_capability_matrix.py` -> pass
- `verify:` `uv run --no-sync basedpyright dev/quality/clitui_ledger_capability_matrix.py dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> pass
- `verify:` `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-09-04-clitui-ledger-plan.md --json` -> pass
- `verify:` `uv run --no-sync vaultspec-core vault feature index --feature clitui-ledger --json` -> pass
- `verify:` `uv run --no-sync vaultspec-core vault check all --feature clitui-ledger --no-hints` -> pass

## Notes

S11 was reopened after the mandatory review found that an inactive hold could close individual G4 prematurely and made ordered G4 impossible after an authorized lift. The remediation adds a typed, ordered G0--G3 accepted-closure receipt chain bound to the current denominator, matrix closure basis, and independent acceptance subject. G4 now requires a current G3 receipt, and ordered evaluation preserves a valid historical G0 closure only across the authorized hold transition while current matrix, receipt, denominator, or observed-census drift relocks it. The row partition remains 680 held TUI-applicable rows and 13 unheld TUI-not-applicable rows.

- `verify:` `uv run --no-sync pytest -q -n 0 dev/quality/tests/test_clitui_ledger_capability_matrix.py -k 'g4 or ordered_evaluation or active_pre_g3 or matrix_drift or denominator_and_observed or receipt_serialization'` -> pass (22 passed)
- `verify:` `uv run --no-sync ruff format --check dev/quality/clitui_ledger_capability_matrix.py dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> pass
- `verify:` `uv run --no-sync ruff check dev/quality/clitui_ledger_capability_matrix.py dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> pass
- `verify:` `uv run --no-sync ty check dev/quality/clitui_ledger_capability_matrix.py` -> pass
- `verify:` `uv run --no-sync basedpyright dev/quality/clitui_ledger_capability_matrix.py` -> pass
- `verify:` `uv run --no-sync pytest -q -n 0 dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> pass (231 passed)

The receipt remediation was reopened once more because the initial closure basis omitted the full acceptance attestation and left its reviewer/time claim remintable. The final contract has two explicit noncircular domains: the attestation’s pre-receipt matrix basis excludes only the attestation, receipt collection, and active-hold transition needed to avoid a cycle; the receipt’s gate-closure basis excludes only the active hold and receipt collection, and includes the entire canonical attestation. The attestation also binds the exact receipt identity/gate set, while every receipt binds the complete canonical attestation digest. Tests reject reminted attestation time, reviewer, identity, matrix basis, injected receipt reviewer, and changed receipt identity even when a matrix digest or attestation is recomputed.

- `verify:` `uv run --no-sync pytest -q -n 0 dev/quality/tests/test_clitui_ledger_capability_matrix.py -k 'g0 or g4 or ordered_evaluation or active_pre_g3 or matrix_drift or denominator_and_observed or receipt_serialization or reminted or receipt_reviewer or receipt_identity'` -> pass (61 passed)
- `verify:` `uv run --no-sync pytest -q -n 0 dev/quality/tests/test_clitui_ledger_capability_matrix.py` -> pass (237 passed)

The subsequent self-consistency review found that fully recomputing the matrix, attestation, receipt bases, and receipt identities could still fabricate authority inside one mutable envelope. S11 therefore now requires an external `LedgerAcceptanceRecordAnchorV1`, passed separately to G4 and ordered evaluation. It reuses `EvidenceCoordinateV1` and `EvidenceSubjectSnapshotV1`; the independently observed subject binds the canonical acceptance record content and exact coordinate location/revision/digest/observation time. The anchor commits the attestation digest, identity, reviewer, time, basis, denominator, and review-subject facts, so an unchanged observed authority refuses any reminted receipt or attestation. Receipt identities are exact gate-derived constants (`receipt.ledger.{gate.value}`), rather than a permissive pattern. The test suite covers missing, stale, rebound, wrong-coordinate, forged-ID, and fully recomputed time-remint attacks; valid post-G3 ordered evaluation still closes only with the current external anchor. The 680 held / 13 unheld row partition and union schema/digest are unchanged.

- `verify:` `uv run pytest dev/quality/tests/test_clitui_ledger_capability_matrix.py -q` -> pass (244 passed)
