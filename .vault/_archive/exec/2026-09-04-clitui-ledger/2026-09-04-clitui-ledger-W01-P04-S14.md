---
tags:
  - '#exec'
  - '#clitui-ledger'
date: '2026-09-05'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:da7bd32a408166ee7ae0b27f6435bf1ed46eed3f60180a8ed1b461c59a5ae54b'
step_id: 'S14'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
---
# Record G0 closure only after an independent engineering review accepts the frozen matrix

## Status

- **Open in the live worktree.** The typed publication preserves the independently accepted frozen candidate, but the current Ledger TUI source observation differs from that candidate. Currentness therefore relocks G0 and every dependent gate; this record does not refresh acceptance onto the prohibited TUI bytes.

## Scope

- `.vault/reference/2026-09-04-clitui-ledger-reference.md`
- `.vaultspec/tests/clitui_ledger/test_capability_matrix.py`
- `.vault/exec/2026-09-04-clitui-ledger/2026-09-04-clitui-ledger-W01-P04-S14.md`

## Changes

- The publication now serializes the complete strict `LedgerMatrixAcceptanceAttestationV1`, `LedgerGateClosureReceiptV1`, `EvidenceSubjectSnapshotV1`, and `LedgerAcceptanceRecordAnchorV1`, including the full 694-identity union review and the normative coordinate claim.
- Tests parse those four records directly through their production models, attach the parsed attestation and receipt through normal matrix fields, and never regenerate the accepted attestation, receipt, subject, or anchor from the live matrix.
- The frozen-source evaluation reproduces the exact accepted TUI, union, denominator, matrix, attestation, receipt-basis, and external-subject bindings. A separate live evaluation proves that the current TUI drift relocks G0.
- Missing publication records, stale external subjects, and mutations of every attestation, receipt, subject, anchor, nested union-review, and coordinate field either fail strict parsing or relock G0.

## Evidence

- Accepted attestation digest: `sha256:d680107325ede5c108d35d58adf0ea64560f203e1618e5b2eb68c539e937d3fe`.
- G0 closure basis: `sha256:23f4c180707765054bae7ddb1a358fc2b2d9d159a7f81b3b6d22f7e218d81dbd`.
- Corrected full-anchor subject digest: `sha256:1ce7ea53db4c50c24040d771bf7b8c7a8cea186aa30d4251d9d091ff7dc0d682`.
- The frozen candidate closes G0 with zero blockers only when its independently observed contract source, census, union, matrix subject, receipt, acceptance subject, and anchor all match. The current checkout returns `closed=false`.
- `uv run pytest -q -n 0 .vaultspec/tests/clitui_ledger/test_capability_matrix.py -k 's14_accepted_g0 or s14_published_g0 or each_published_g0_bound_field or g0_refuses_missing_stale_or_altered_published'` -> `71 passed, 331 deselected in 418.85s`.
- `uv run basedpyright .vaultspec/tests/clitui_ledger/test_capability_matrix.py` -> `0 errors, 0 warnings, 0 notes`.

## TUI hold

The global and row-level Ledger TUI hold remains active through accepted G3 closure. No G1, G2, G3, or G4 receipt is published, and the live TUI drift is not accepted or quarantined by this Step.
