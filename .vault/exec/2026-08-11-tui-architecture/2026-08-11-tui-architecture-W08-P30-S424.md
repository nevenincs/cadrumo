---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:b64ab5359611889cdc48d9158347234da000fdf42bfcfc4bfac11dbcc82fa961'
step_id: 'S424'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Sweep every projection and gate still shaped by the retired redaction assumption. DECIDED 2026-09-04. Find each model documented as safe, redacted, or 'without values', each screen docstring promising never to reconstruct a payload, and each test asserting that operator data is ABSENT from a rendered surface. Re-derive the models from the accepted visibility record and rewrite or delete those gates -- a gate asserting the retired policy will otherwise block the fix and read as a safety property while doing it. Gates asserting absence from a log, an exception, a cache, a temporary file or an off-host payload are UNAFFECTED and stay required; do not weaken them while removing the others.

## Scope

- `src/cadrumo/application/ and src/cadrumo/entrypoints/tui/`

## Changes

- `M` `src/cadrumo/application/ledger/workspace.py`
- `M` `src/cadrumo/application/aeat_sync/workspace.py`
- `M` `src/cadrumo/application/modelo/declarations_calendar.py`
- `M` `src/cadrumo/entrypoints/tui/ledger/reconciliation.py`
- `M` `src/cadrumo/entrypoints/tui/ledger/tests/test_ledger_slice3.py`
- `verify:` `pytest -n0 -m '' tui/ledger/tests application/ledger/tests/test_workspace.py` -> `pass` (85)

## Notes

Step left OPEN: the sweep found one unblocked defect, fixed it, and the rest of
what it names is blocked or is framing debt. Recording which is which.

FIXED. `LedgerInvoiceReconciliationRefV1` reported `amount_match` and
`counterparty_match` as bare booleans. A `True` asks the operator to confirm a
link while hiding the two amounts that supposedly agree; a `False` reports a
disagreement without saying between what and what. A suggestion is a claim the
operator is meant to ADJUDICATE, and both values are local records the session
is already authenticated for, in scope at the projection site -- discarded, not
protected. The ref now carries invoice total, transaction amount and both
counterparties, and the screen prints them beside the verdict. The gate uses
the fixture row whose counterparties differ ("Cliente Omega SA" against "Omega
SA"), the case where a bare "no" cannot be told from a formatting difference.
Teeth proven by removing the values from the rendered line.

BLOCKED, unchanged. Census values: no producer outside fixtures, AEAT side
never captured until a pull (S408). Declaration result amounts on the
declarations and revisions lists: `casilla_values` holds the computed outputs,
but WHICH casilla is the result is not declared anywhere in the registry --
only ad-hoc per-modelo constants exist (`_M130_RESULTADO_FINAL_CASILLA = "19"`,
`_M200_ACCOUNTING_RESULT_CASILLA = "00501"`), covering two modelos. Showing a
guessed result on a filing-facing list is worse than showing none, so this
stays unsupported pending a registry-declared result casilla. That constant
scattering is itself a `aeat-calculation-grounding` finding.

CHECKED AND CLEARED, so the sweep is not re-run over them: PDF, log and
authenticator redaction (diagnostics can travel where an authenticated session
cannot, and the decision explicitly leaves them); `ModeloEditMutationResultReceiptV1`
(a compare-and-swap receipt, not a display surface); the modelo work wizard
(shows the casilla and an empty input -- fresh entry, not withholding).

FRAMING corrected where the prose asserted the retired policy as a property:
the census row no longer calls its missing values a safety feature, and the
declarations calendar is no longer described as "redacted" when it carries
every date and state it is about.
