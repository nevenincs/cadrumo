---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:9ebfbb4067839e58b1c8eff5ebad0c007faede42ff900ee7fef76bd05d3e5ae7'
step_id: 'S455'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Confirm a locale-key registry through the boundary wrapper that reads it, since flow confirmation consulted only tr and its import aliases while every surface is asked to route copy through its own helper, so a registry read through declarations_copy or aeat_sync_copy was never confirmed and every key in it read as an orphan; shape alone still does not confirm

## Scope

- `dev/locales/_ast_scanner.py`
- `dev/locales/tests/test_dynamic_prefix_registry_coverage.py`

## Changes

Parity extras: 308 -> 293. Of the 46 extras whose FULL dotted key was present
as a source literal -- the hardest evidence in the residue, since the key is
provably written down -- 15 were this.

A dict or row table shaped as a key registry is admitted only once it is proved
to REACH a translator; shape alone is deliberately insufficient, because this
codebase carries same-shaped tables (a casilla reconciliation map, a machine
routing table) that never translate. That proof called
`_translation_call_names`, which knows `tr`, `t`, and aliased imports of them --
and nothing else.

S453 taught the CALL-SITE resolver about tree-wide boundary wrappers. The
confirmation path never learned it, so:

    _AVAILABILITY_KEYS = {DeclarationsWorkspaceAvailability.STALE: "..."}
    return declarations_copy(_AVAILABILITY_KEYS[value])

was shape-matched, read into the translator, and still unconfirmed. Same root
cause as S453 one layer down, and the same shape of harm: following the
project's own boundary convention is what made the keys invisible.

`wrappers` is now threaded through `_extract_locale_constant_keys` into both
flow-confirmation helpers and both sink walkers, defaulted empty so the existing
direct callers are unchanged.

Teeth: dropping `wrappers` from the dict-sink call fails the new gate. Restored
by copy. The gate pins the negative in the same module -- a same-shaped table
nothing reads stays unconfirmed even where a wrapper exists -- so the widening
cannot be mistaken for accepting shape alone.

## Notes

TARGET 2 IS NOT CLOSED, and it is now BLOCKED on a decision I should not make
alone. See the blocker below; 293 extras also remain.

BLOCKER -- `tui.ledger.reconciliation.direction`. The missing side of parity is
no longer zero: all four locales lack
`tui.ledger.reconciliation.direction.invoice_only` and `.transaction_only`.
The cause is a standing disagreement between two writers on one surface:

- the committed TUI code asks for `direction` AND `direction.invoice_only`, so
  `direction` is both a leaf and a namespace root;
- the catalogue holds the children under `direction_state`, which is the shape
  `test_no_key_shadows_a_namespace` requires.

Adding the two keys as the code spells them makes MY gate fail; renaming the
code to match the catalogue is a change that has been reverted by the other
writer five times. Both gates cannot pass on the current pair, so this needs an
owner decision on which spelling the surface uses, not a sixth unilateral
rename.

PRE-EXISTING, NOT FROM THIS STEP: `test_committed_catalogues_carry_no_em_dash`
fails on 36 values under `tui.home.*` and `tui.aeat_sync.value.none`, authored
by the concurrent TUI/sync commits (`0021d50cfe`, `957c0c212c`), and
`test_language_flag_help_honesty` fails independently. Neither touches the keys
this step or S454 authored.
