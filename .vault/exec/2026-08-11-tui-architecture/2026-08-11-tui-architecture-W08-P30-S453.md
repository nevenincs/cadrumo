---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:b07554d19bd673a2e5ea6d3600085ca5e02658869ef79f1a99e225125051e71d'
step_id: 'S453'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Follow the per-surface translator boundary helpers the locale scanner could not see. Every TUI surface routes its copy through a local wrapper that forwards its key to tr, so the call sites never name the translator and every key reaching the catalogue through one read as an orphan. Resolve wrapper names across the tree to a fixpoint, admitting only a function that forwards its own first parameter, so a helper that merely calls the translator on something else is not mistaken for a key channel.

## Scope

- `dev/locales/_ast_scanner.py`
- `dev/locales/tests/test_dynamic_prefix_registry_coverage.py`

## Changes

Locale parity extras: 405 -> 316, missing still 0. 89 keys were never orphans;
the scanner simply could not see the call.

Every TUI surface routes its copy through one boundary helper -- exactly the
architecture the codebase asks for:

    def aeat_sync_copy(key: str, **values: object) -> str:
        """Resolve every operator-facing AEAT Sync string through one boundary."""
        return tr(key, **values)

So the call sites read `aeat_sync_copy("tui.aeat_sync.column.area")` and never
`tr(...)`. The scanner resolved an aliased IMPORT of `tr` but not a wrapper
defined as a function, so following the project's own boundary convention was
what made a key invisible. The better the surface was factored, the more of its
keys read as dead.

Wrapper names are now resolved across the tree to a fixpoint, since a wrapper
may be imported from elsewhere and may itself wrap a wrapper.

THE ADMISSION RULE IS THE CAREFUL PART. A function qualifies only by forwarding
its OWN first parameter as the first positional argument to something already
known to translate. `def shout(text): return tr("ui.fixed.banner") + text` calls
the translator and is not a key channel; treating it as one would collect its
arguments as keys. The gate pins that negative alongside the positive, and
proves the non-forwarding helper's own literal is still collected -- the
distinction is about the ARGUMENT, not about whether the function translates.

Teeth: dropping the forwarding requirement so any `tr` caller counts fails the
gate. Restored by copy; 24 passed.

## Notes

316 extras remain. The partition before this Step was 262 with no string
literal anywhere and 143 reachable but uncollected; this closed 89 of the
second group.

The 262 are unchanged and still not safe to prune. Three separate scanner blind
spots have now been found in this residue -- mapping lookup tokens, a guard
table's prose column, positional cross-module parameters, and now boundary
wrappers -- and each one turned keys that looked dead into keys that were
plainly alive. That is the standing argument against treating "no literal found"
as permission to delete.
