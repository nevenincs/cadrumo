---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:abb4b34f22f6cb6c1bffd8726a95b6a3cf1e5b6c87b0718e500dc97f001c127d'
step_id: 'S457'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Read the screen column table the shape test rejected for carrying a width, read back as a class attribute and indexed rather than unpacked, keeping the key-column discipline so a prose or numeric sibling reaching the translator still confirms nothing

## Scope

- `dev/locales/_ast_scanner.py`
- `dev/locales/tests/test_dynamic_prefix_registry_coverage.py`

## Changes

Parity extras: 188 -> 182. Full-literal residue 30 -> 24.

BLIND SPOT 8, in three parts, any ONE of which hid every heading key in a
screen's column table:

    _COLUMNS: ClassVar[...] = (("date", "tui.ledger.column.date", 10), ...)
    for column in self._COLUMNS:
        cost = max(column[2], len(ledger_copy(column[1]))) + 2

* the row carries a WIDTH and the shape test demanded all-string rows, so the
  table was never a candidate at all;
* it is read back as `self._COLUMNS`, an attribute, while confirmation
  required a bare name to be iterated;
* the row is bound whole and the key taken as `column[1]`, while confirmation
  looked for an unpacked name.

The key-column discipline is untouched and is the point. A non-string cell is
carried as a POSITION that can never be a key column rather than as grounds to
reject the table -- a width is no more a key than prose is, which is exactly
the reasoning the shape test already gave for prose siblings. Confirming by
index requires the index to BE a key column, so indexing a prose sibling into
the translator still confirms nothing.

Teeth: three defects, each restored by copy -- re-require all-string rows, drop
the attribute read, and confirm on any index. Each fails the gate, and the gate
pins the prose-index negative beside the two positives.

## Notes

TARGET 2 REMAINS OPEN at 182 extras.

THE BLOCKER IS NOW SHARPER, and this step is what sharpened it.
`test_no_declared_key_is_a_prefix_of_another_declared_key` has gone red on
`tui.ledger.reconciliation.direction`. That is NOT a false positive from the
widening and not the catalogue's doing: with the reconciliation column table
finally visible, the gate can see that the CODE ITSELF declares `direction` as
a leaf and `direction.invoice_only` beneath it. The surface is self-
inconsistent by the project's own rule, independently of what any catalogue
holds.

I turned a green gate red and cannot close it. Both spellings cannot coexist,
the module belongs to the other writer, and the rename has been reverted five
times -- the last of which removed `direction_state` from the code entirely.
This needs the ownership decision recorded in S455, now with the stronger
evidence that the defect is in the declaration rather than in the translation.

Residue: 24 full-literal, 60 tail-only, 98 no-trace. The remaining full-literal
shapes are a class-attribute `heading = "..."`, a conditional `return`, and the
AEAT Sync columns, which reach the translator through a function PARAMETER and
a second helper hop -- interprocedural, unlike anything closed so far.

Unchanged and not from this step: the three `test_committed_catalogues_*`
failures.
