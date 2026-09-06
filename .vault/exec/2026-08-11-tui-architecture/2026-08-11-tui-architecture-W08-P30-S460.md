---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:1fd2f2e2c208f66570566e79e09fdc3c8ba165de35e584a71baf5639bb44feac'
step_id: 'S460'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Follow a column table into the shared fitter it is handed to, walking comprehension generators as well as for statements and confirming every table a parameter receives rather than dropping the name as ambiguous, since one helper serves every screen and the ambiguity rule failed the common case for being common

## Scope

- `dev/locales/_ast_scanner.py`
- `dev/locales/tests/test_dynamic_prefix_registry_coverage.py`

## Changes

Parity extras: 171 -> 167. Full-literal residue 13 -> 9.

BLIND SPOT 10. Every AEAT Sync screen sizes its columns with one shared helper
rather than repeating the rule, so the table is never iterated where it is
declared -- it is HANDED OVER:

    _fit_columns(self.app.size.width, self._COLUMNS, self._VALUE_COLUMNS)

Inside the helper the parameter is iterated in a generator expression and each
row is translated. Three things hid that, and any one was enough: confirmation
walked only `for` statements, a parameter name said nothing about which table
had been passed into it, and the row reaches the translator through a closure.

Only ONE hop of binding was needed. The analysis is name-based within the
module, so once the parameter is known to hold the table, the row bound in the
helper is already followed into the nested function it is handed to.

THE AMBIGUITY RULE WAS WRONG AND THE FIRST ATTEMPT PROVED IT. Dropping a
parameter filled by several tables recovered only the one table that happened
to be unique -- it failed the common case for being common. A parameter filled
by several tables confirms ALL of them, and that is not a guess: one helper
serves every screen, so if its parameter's rows reach a translator then every
table handed to it is translated.

The key-column discipline is untouched, and the gate's negative arm holds it: a
fitter that indexes the PROSE column confirms nothing, however many tables are
handed to it.

Teeth: three defects, each restored by copy -- stop walking comprehension
generators, drop the parameter alias, and restore the ambiguity drop. Each
fails the gate.

## Notes

TARGET 2 REMAINS OPEN at 167 extras. The suite reports exactly the two failures
that preceded this step -- the parity gate itself and the shadow gate. No new
breakage.

One AEAT Sync column key is deliberately NOT closed here.
`tui.aeat_sync.column.resolution` sits in a table written INLINE at the call
site rather than bound to a name, so it is not a shape candidate at all. That
is a distinct shape -- an anonymous table -- and stretching this step to reach
it would have meant registering candidates that nothing names, which is a
different bargain from the one every rule here makes.

The shadow failure is the BLOCKER from S455, sharpened in S457: the code
declares `tui.ledger.reconciliation.direction` as a leaf and
`direction.invoice_only` beneath it, self-inconsistent by the project's own
rule. Other writer's module, rename reverted five times, waiting on an
ownership decision.

Residue: 9 full-literal, 60 tail-only, 98 no-trace. What is left full-literal is
the anonymous table above, a local assigned a conditional of two keys, and two
`frozenset` guards of safe keys.
