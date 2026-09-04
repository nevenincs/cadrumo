---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:0cfe8ad79ca301f421471ca3a7b418aa209d41a2628a3fc5d71849f40c58188f'
step_id: 'S421'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Carry the transaction facts a reviewer needs on the Ledger entry reference, and render them. DECIDED 2026-09-04 by the authenticated-TUI-visibility record: LedgerWorkspaceEntryRefV1 carries a transaction id and a review status and nothing else, so the entries screen paints a twelve-character hash beside a status word and prints a standing notice that financial details remain protected. An operator cannot review an entry from a truncated hash. Widen the reference to date, amount and currency, direction, counterparty, description, classification and review status; render those columns; and DELETE the redacted notice and its locale string rather than rewording it, because it describes a policy that no longer exists.

## Scope

- `src/cadrumo/application/ledger/workspace.py`
- `src/cadrumo/entrypoints/tui/ledger/entries.py`
- `src/cadrumo/locales/`

## Changes

- `M` `src/cadrumo/application/ledger/workspace.py`
- `M` `src/cadrumo/entrypoints/tui/ledger/entries.py`
- `M` `src/cadrumo/entrypoints/tui/ledger/controller.py`
- `M` `src/cadrumo/entrypoints/tui/components/widgets.py`
- `M` `src/cadrumo/entrypoints/tui/devtools/workbench_fixtures.py`
- `M` `src/cadrumo/entrypoints/tui/ledger/tests/test_ledger_workspace.py`
- `M` `src/cadrumo/application/ledger/tests/test_workspace.py`
- `M` `src/cadrumo/application/search/tests/test_installed_workbench.py`
- `M` `src/cadrumo/locales/ca/common.yml`
- `M` `src/cadrumo/locales/en/common.yml`
- `M` `src/cadrumo/locales/es/common.yml`
- `M` `src/cadrumo/locales/hu/common.yml`
- `verify:` `pytest -n0 -m '' tui/ledger/tests application/ledger/tests/test_workspace.py application/search/tests` -> `pass` (123)

## Notes

`LedgerWorkspaceEntryRefV1` carried a transaction id and a review status; it
now carries the entry: date, amount, currency, direction, counterparty,
description and business classification. Every one of those was already on
`LedgerTransactionPayload` and was being discarded at the projection boundary.
The entries screen showed a 12-character id prefix and a status word; it now
shows the record. The `tui.ledger.entries.redacted` notice, whose Spanish text
read "safe index of entries; financial details remain protected", is deleted
from all four catalogues through the owning `dev.locales remove` verb.

Seven columns do not fit the 80-column floor, so the column SET is responsive
while the data is not: columns are taken in priority order until the width is
spent, and every one returns as the terminal widens. Three width bugs surfaced
in sequence and each is fixed at its own cause -- the budget ignored that a
header is a floor on its column, the rebuild discarded the widths the table had
already corrected (`ContentDataTable.absorb_surplus_width` is now public for
owners that rebuild), and the surplus went to the last column rather than the
description, which is the only cell an operator cannot reconstruct from the
others. A rebuild also re-resolves the cursor by row KEY, because a positional
cursor would leave the operator looking at one entry and acting on another.

Two gates asserted the retired policy and were rewritten rather than deleted.
The TUI gate now asserts each fact reaches the operator, at the widest terminal
because the column set is responsive, and still asserts the raw 64-character id
is never painted -- machine addressing, not operator data. The application gate
mixed two concerns under one name: its PATH, RAW, INVOICE-LINE, INVOICE-NUMBER
and REVIEW canaries are kept, because raw source material is out of scope
whatever the display policy, while counterparty, description and amount are now
asserted PRESENT. Teeth proven by re-redacting the amount to `***`: the gate
names the missing value and fails; restored by copy.

One finding recorded, not fixed: the stored amount is `Decimal("121.00")` and
the projection carries `"121"`. The field is present, so this step's subject is
met, but trailing precision is dropped between transaction and payload, which
the ledger contract requires to stay explicit. The gate asserts the observed
value with that discrepancy called out rather than smoothed over.
