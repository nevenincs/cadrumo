---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:0bf87043bff16a6956523c9aedca8f4951480c4239cff6623cb79b8dee94baef'
step_id: 'S447'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Stop the locale scanner claiming a registry's lookup tokens as translation keys, and reunite the storage error subtree with the module path the code cites. A locale-key mapping is keyed by whatever the runtime selects on -- a route identity, a catalogue action id -- and only its values are locale keys; collecting the whole literal demanded translations for identifiers no catalogue should carry. Separately, the storage factory error subtree lost a leading underscore, so seven keys were reported missing and their twins extra.

## Scope

- `dev/locales/_ast_scanner.py`
- `dev/locales/tests/test_dynamic_prefix_registry_coverage.py`
- `src/cadrumo/locales/*/`

## Changes

Locale parity missing keys: 33 -> 5. Two causes, both established from the
scanner's own output rather than guessed at, and the one I expected going in was
not the one that mattered.

WHAT I EXPECTED AND DROPPED. S442 named PEP 695 type aliases as the reason the
scanner cannot see certain declarations, and teaching it ast.TypeAlias was the
obvious next move. Measured first: only 5 modules declare dotted literals in a
type alias, 24 keys total, and several are module paths -- application.modelo.
workspace, domain.calculations.registry -- not locale keys at all. Collecting
them would have ADDED false positives to the missing side while fixing nothing.
The aliases also carry type names rather than the _LOCALE_KEYS convention the
Assign path is gated on, so a faithful extension would have collected nothing.
Dropped.

THE ACTUAL CAUSE IS THE OPPOSITE SHAPE. The scanner reads a constant named with
the _LOCALE_KEYS suffix and then trusts every dotted literal nested under its
value. For a MAPPING that is wrong in a specific way: it is keyed by whatever
the runtime selects on, and only the values are locale keys. In search.py the
keys are TUI routes and catalogue action ids -- workbench.home,
operator.profile.edit -- and they are dotted enough to pass for keys. The parity
gate was demanding translations for 24 identifiers no catalogue should carry.

Collection now takes a dict's values and leaves its keys. Every other shape --
tuple, list, bare string -- has no such distinction and is collected whole as
before, which is the half the new gate pins alongside the exclusion.

SEPARATELY, seven keys were a subtree rename nobody followed. The code cites
adapters.outbound.storage._factory (the module is _factory.py, private) while
the catalogue carried storage.factory. Each missing key had its extra twin
exactly, so this was a relocation and not a loss, and the owning `move` verb
carried all 28 leaves across the four catalogues with nothing overwritten.

Teeth on the collection change: restoring whole-dict collection fails the new
gate on both route identity and action id. Restored by copy; 12 passed.

## Notes

5 missing keys remain: ledger.classify, ledger.link, ledger.review,
ledger.evidence.review.list and tui.ledger.reconciliation.direction. The first
four are command keys collected from ledger/action_guards.py and are the same
identifier-not-a-key shape, but they come through a different construct than the
mapping fixed here, so they need their own look rather than an extension of this
rule by assumption.

454 extras are untouched and remain the larger half, dominated by cli.config
(139), tui.declarations (117) and tui.aeat_sync (116). Nothing here licenses
pruning them: scaffold would delete every key no namespace covers, and the
enum-driven ones are built by concatenation at runtime.
