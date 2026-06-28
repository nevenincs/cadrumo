---
tags:
  - '#exec'
  - '#audits-resolution'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-audits-resolution-plan]]"
  - "[[2026-05-13-eliminate-shims-audit]]"
---

# audits-resolution group-a step-4

## scope

Plan row A4: tighten the broad `pytest.raises(Exception)` at
`src/aeat/adapters/persistence/storage/sql/_test_constraints.py:81`.

## change

Replaced `pytest.raises(Exception)` with
`pytest.raises(IntegrityError, match=r"CHECK constraint failed:
ck_portals_auth_method")`. The exception type was identified by an
exploratory probe: SQLite's CHECK violation surfaces through
`sqlalchemy.exc.IntegrityError` with the constraint name in the
message. Added the `IntegrityError` import alongside the existing
`text` import.

## verification

`pytest src/aeat/adapters/persistence/storage/sql/_test_constraints.py -q`
green with 5 passed.

`grep -n 'pytest.raises(Exception)' src/aeat/adapters/persistence/storage/sql/_test_constraints.py`
returns nothing.
