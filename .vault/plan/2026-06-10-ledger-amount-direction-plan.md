---
tags:
  - '#plan'
  - '#ledger-amount-direction'
date: '2026-06-10'
modified: '2026-06-10'
tier: L2
related:
  - '[[2026-06-10-ledger-amount-direction-adr]]'
  - '[[2026-06-10-ledger-amount-direction-research]]'
---


# `ledger-amount-direction` `Ledger absolute-amount + direction-authority implementation` plan

### Phase `P01` - Domain model — non-negative amount gate

Add ge=0 validator to RawTransaction.amount and remove signed-amount semantics from Transaction and ManualLedgerTransactionCommand; update split-child validator and SplitChildCommand docstring.

- [x] `P01.S01` - Add ge=0 Pydantic validator to RawTransaction.amount; `rewrite docstring to 'Non-negative magnitude'; raise TransactionValidationError on violation; `src/aeat/domain/transactions/_raw_transaction.py`.
- [x] `P01.S02` - Rewrite _validate_direction_policy in ManualLedgerTransactionCommand: drop sign<->direction coupling, keep zero-amount rejection and INTERNAL_TRANSFER payload-shape check; `update test_models.py lines 136-153 to new convention; `src/aeat/application/ledger/_models.py, src/aeat/application/ledger/tests/test_models.py`.
- [x] `P01.S03` - Drop sign-equality check from _validate_split_child_amounts; `replace with direction-equality assertion (children already inherit parent.direction); update SplitChildCommand docstring to 'absolute magnitude; direction inherited from parent'; `src/aeat/application/ledger/_actions_split_merge.py, src/aeat/application/ledger/_models.py`.
- [x] `P01.S04` - Add roundtrip test for Transaction with non-negative amount + direction (save->load->equality, non-default fields populated); `add anti-tautology proof (corrupt payload to negative amount, assert ValidationError); `src/aeat/domain/transactions/tests/`.

### Phase `P02` - Import adapter — explicit direction at the parse boundary

Replace _direction_from_amount with an explicit direction from parser/provider signal; reject zero-amount on import; ensure every SourceFormat adapter produces a magnitude + direction pair and never passes sign through to the domain.

- [x] `P02.S05` - Remove _direction_from_amount from _actions_common.py; `audit every call site in _actions_import.py and replace with an explicit direction parameter threaded from the source adapter (note: value_in_eur abs() at lines 134-137 already correct, no change needed); `src/aeat/application/ledger/_actions_common.py, src/aeat/application/ledger/_actions_import.py`.
- [x] `P02.S06` - Add zero-amount rejection at the import boundary: raise ImportValidationError (or equivalent) when a parsed row has amount == 0, consistent with ManualLedgerTransactionCommand zero rejection; `src/aeat/application/ledger/_actions_import.py`.
- [x] `P02.S07` - Update every SourceFormat adapter/parser to: (a) map the bank export sign or native debit/credit signal to TransactionDirection at the parse boundary, (b) store the abs(amount) magnitude; `add INTERNAL_TRANSFER support path in the adapter contract; `src/aeat/adapters/inbound/`.
- [x] `P02.S08` - Add or update import integration tests: zero-amount row rejected; `OUTGOING row stores positive magnitude with direction=OUTGOING; INTERNAL_TRANSFER row stores absolute magnitude with direction=INTERNAL_TRANSFER; `src/aeat/application/ledger/tests/`.

### Phase `P03` - Evidence row — non-negative amount + direction

Make LedgerEvidenceRow.amount non-negative (value_in_eur already is); update roundtrip fixture and add anti-tautology proof.

- [x] `P03.S09` - Add ge=0 Pydantic validator to LedgerEvidenceRow.amount (value_in_eur already non-negative per F5); `update field docstring; `src/aeat/domain/modelos/_ledger_filing_snapshot.py`.
- [x] `P03.S10` - Update test_ledger_filing_evidence_roundtrip.py: replace amount=Decimal('-121.00')/value_in_eur=Decimal('-112.04') with magnitudes + direction=OUTGOING; `verify strict save->load->equality roundtrip; `src/aeat/domain/modelos/tests/test_ledger_filing_evidence_roundtrip.py`.
- [x] `P03.S11` - Add anti-tautology proof to evidence roundtrip: corrupt persisted payload to a negative amount, reload, assert ValidationError raised (proving the gate is live, not tautological); `src/aeat/domain/modelos/tests/test_ledger_filing_evidence_roundtrip.py`.

### Phase `P04` - CLI gate and documentation note

Add non-negativity guard to --amount in the ledger CLI with an instructive localised error; flag the import-bank-statements.md narrative rewrite as a documentation-workflow item outside this plan's code scope.

- [x] `P04.S12` - Add non-negativity guard to --amount in the ledger CLI add command: _parse_required_decimal raises with a localised instructive error naming the accepted form (non-negative magnitude + --direction OUTGOING/INCOMING); `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `P04.S13` - Add CLI integration test: --amount=-49.99 is refused with an instructive error message naming the accepted non-negative form and --direction; `--amount=49.99 --direction OUTGOING is accepted; `src/aeat/entrypoints/cli/tests/`.
- [x] `P04.S14` - Flag docs/how-to/import-bank-statements.md for narrative rewrite (drop -prefix convention, instruct magnitude + --direction); `defer to vaultspec-documentation workflow outside this plan's code scope; record as a follow-on documentation ticket; `docs/how-to/import-bank-statements.md`.

### Phase `P05` - Suite green-pass and codification

Run full pytest suite sequentially to confirm no regressions introduced by C1; codify the ledger-amount-is-absolute-direction-is-authority rule per the ADR codification candidate.

- [x] `P05.S15` - Run full pytest suite sequentially (uv run --no-sync pytest src/aeat -x -q); `confirm zero failures; fix any regressions in scope before marking plan complete; `src/aeat/`.
- [x] `P05.S16` - Codify ledger-amount-is-absolute-direction-is-authority rule per ADR codification candidate: run vaultspec-core spec rules add and populate Rule/Why/How sections; `.vaultspec/rules/rules/`.

## Description

Implements ADR decision cluster C1 from `2026-06-10-ledger-amount-direction-adr`:
replaces the current signed-amount + redundant-direction hybrid with a canonical
convention where `amount` is a **non-negative magnitude** and `direction`
(INCOMING / OUTGOING / INTERNAL_TRANSFER) is the **single authoritative flow
field**. The ADR research (F1-F11) shows direction is already the routing axis
in every aggregation engine, sign is discarded downstream, and the enforcement
gap between the import and manual paths has already produced a zero-amount
misclassification bug. This plan closes that gap with a single model-level gate
on `RawTransaction`, updates every consumer (import adapters, split-child
validator, evidence row, CLI boundary), and provides strict roundtrip + anti-
tautology tests at every persistence boundary. The docs narrative rewrite
(import-bank-statements.md) is flagged for the documentation-workflow pipeline
as a follow-on item outside this plan's code scope. Downstream clusters C5 (list
rows) and C7 (participation / evidence projections) will consume the resulting
uniform non-negative-amount + authoritative-direction contract without further
sign-convention translation.

## Steps







## Parallelization

P01 is the foundation and MUST land before all other phases. Its atomic commit
introduces the `RawTransaction.amount ge=0` gate that every subsequent phase
depends on.

P02 and P03 depend on P01 but are independent of each other and MAY be executed
in parallel once P01 is committed. Both produce self-contained atomic commits.

P04 depends only on P01 (the validator shape) and MAY run in parallel with P02
and P03. P04.S14 (docs flag) is a note-only step with no code output; it does
not block P04 or the suite gate.

P05 MUST execute last. P05.S15 (suite green-pass) gates on all prior phases
being fully committed. P05.S16 (codification) runs after the suite is green.

Cross-cluster dependency note: C3 (input localisation, a separate cluster)
tightens the CLI `--amount` regex to the non-negative pattern `^\d+(\.\d+)?$`
once this plan lands — P04.S12 is its prerequisite. C5 (list rows) and C7
(participation / evidence projections) consume the uniform non-negative +
direction contract established by P01 through P03.

## Verification

The plan is complete when all of the following hold:

- `RawTransaction.amount` carries a `ge=0` validator; constructing a
  `RawTransaction` with a negative amount raises `TransactionValidationError` on
  both the import and manual paths.
- `_direction_from_amount` is deleted and no call site remains in the import
  action; every SourceFormat adapter produces an explicit `direction` at the
  parse boundary.
- A zero-amount import row raises at the import boundary, consistent with the
  manual path.
- `LedgerEvidenceRow.amount` is non-negative; the roundtrip fixture uses
  magnitudes + `direction=OUTGOING`; the anti-tautology proof (corrupt to
  negative, assert `ValidationError`) passes.
- The CLI `--amount=-49.99` input is refused with a localised instructive error.
- `uv run --no-sync pytest src/aeat -x -q` exits clean with zero failures.
- The `ledger-amount-is-absolute-direction-is-authority` rule is codified under
  `.vaultspec/rules/rules/` and propagated via `vaultspec-core sync`.
- Every Step in P01-P05 is checked (`- [x]`).
