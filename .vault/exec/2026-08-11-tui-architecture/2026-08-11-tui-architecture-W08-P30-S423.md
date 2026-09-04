---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:223fef5782b8e7aebaa4f82d409d27939add039619e962a60782ad2a071ecfe0'
step_id: 'S423'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Index and display real labels in the workbench search snapshot. DECIDED 2026-09-04: the installed search documents carry closed enums, addresses and secret-wrapped identity bases only, so a palette result cannot be identified without opening its destination. Carry the operator-facing label and the values a searcher would type, and render them in the palette. This also removes the reason the identity basis was ever a SecretStr in a surface the operator owns.

## Scope

- `src/cadrumo/application/search/installed_workbench.py and src/cadrumo/entrypoints/tui/search.py`

## Changes

- `M` `src/cadrumo/application/search/workbench.py`
- `M` `src/cadrumo/application/search/installed_workbench.py`
- `M` `src/cadrumo/application/search/tests/test_installed_workbench.py`
- `verify:` `pytest -n0 -m '' application/search/tests tui/tests/test_search.py tui/ledger/tests` -> `pass` (40 + 92)

## Notes

The palette indexed `kind`, `label_key`, `status` and the natural address, and
nothing else. An operator could find "ledger entry" but not "Suministros Delta
SL" -- the only part of the record anyone actually remembers. That made the
palette a table of contents rather than a way to find something.

`WorkbenchSearchDocument` now carries `content_terms`, matched alongside the
enum names, and ledger entries populate it with counterparty, description,
date, amount and currency. The transaction id is deliberately NOT matchable and
stays a secret identity basis excluded from serialization: it is machine
addressing, and nobody types 64 hex characters into a palette. That split is
the point of the change, not an exception to it.

The model docstring claimed there is "no raw search term" as an invariant; it
now states what is carried and why, so the next reader is not told the opposite
of what the code does.

No gate noticed the change -- 39 passed before and after -- which matches the
gate-integrity finding that the search-snapshot test was vacuous. A gate was
added: searching the counterparty, the description and the amount each finds
the entry, and searching the raw 64-character id finds nothing. Teeth proven by
dropping `content_terms` from the matched terms; the gate names the query that
finds nothing. Restored by copy.
