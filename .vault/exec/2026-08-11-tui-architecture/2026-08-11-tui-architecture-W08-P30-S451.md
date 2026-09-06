---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:f8becc4870c6ee14607577110138b94da66f9b7d17167c82c7931cd5775817f1'
step_id: 'S451'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Resolve a translation key filled positionally into a helper defined in another module, and make the resolution refuse a name whose definitions disagree. The CLI command specs pass their help key by position to a helper whose parameter the scanner already recognises by name, but only as a keyword and only within one module, so the keys read as orphaned catalogue entries. Collect the callee signatures across the tree first, and count a position only where every definition of that name agrees it carries a key.

## Scope

- `dev/locales/_ast_scanner.py`
- `dev/locales/tests/test_dynamic_prefix_registry_coverage.py`

## Changes

Locale parity extras: 454 -> 405, missing back to 0. S450 called this a decision
rather than a mechanical fix; it is mechanical, and the reason it looked
otherwise is that the obvious implementation is wrong in a way that only shows
up when you run it.

The scanner already knows `help_key` is a translation-key parameter. It reads it
as a KEYWORD argument and within one module. The CLI command specs fill it
POSITIONALLY into a helper defined elsewhere -- `_blank_default_text_option(
"note", ("--note",), "cli.app.ledger.counterparty.note_help")` -- so the call is
in one file and the signature in another, and 192 live keys read as orphans.

Collecting the signatures across the tree first fixes that, and costs no extra
parsing: the walk already materialises every module.

THE OBVIOUS VERSION IS WRONG, and I shipped it before measuring. Keying by bare
function name and taking the UNION of key positions looked safe -- I reasoned a
collision only widens collection when the other function also names a key
parameter at that index. It does not. Eight `_leaf` helpers ship here with
`help_key` at index 3, 1 or 2, and one whose index 1 is `module`. The union
applied all three positions to every `_leaf` call and collected module import
paths as translation keys: parity's missing count went from 0 to 8, every one a
`cadrumo.entrypoints.cli.*` import path.

A position now counts only where EVERY definition of that name carries a
translation-key parameter there. `_leaf` yields nothing, losing the keys it
would have contributed rather than inventing keys it would not. That is the safe
direction: an uncollected key reads as an unused catalogue entry, while an
invented one reads as a missing translation somebody has to chase.

Teeth pin both halves in one test, because the failure mode was over-collection:
an agreeing helper resolves its positional key, a disagreeing pair collects
nothing. Reverting to union fails it. Restored by copy; 12 passed.

## Notes

A REGRESSION FROM THE CONCURRENT WRITER, found and re-applied. The two missing
keys that surfaced mid-Step were S449's own rename: the catalogue kept
`direction_state.*` but `reconciliation.py` and `controller.py` had reverted to
`direction.*`, so the code was asking for keys that no longer exist. git status
showed both files clean, meaning the revert arrived in a commit rather than an
edit. Re-applied; 76 passed.

This is the third time this session that work landed and was then overwritten
by the other writer in this worktree. The catalogue half survived because it was
committed; the source half did not.

405 extras remain, and they are the honest residue: 262 carry no string literal
anywhere in the tree, and the rest are reached through constructs this scanner
still cannot follow. Neither group is safe to prune.
