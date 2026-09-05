---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:9b3daaf1491f11272005ade527d77c4aa8f5f9a3d6b77151f539388b9a29c9da'
step_id: 'S443'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Restore the required/optional badge keys to a constant the locale scanner can see. Both flow frontends selected the badge key behind a variable and handed that variable to tr(), so no literal reached the call site and neither key was collected; a catalogue strip would prune both as orphans and the badge would raise on a key with no visible reference. Centralise the pair in a module-level constant carrying the scanner's naming convention, in the shared copy module both frontends already import.

## Scope

- `src/cadrumo/application/flows/copy.py`
- `src/cadrumo/application/flows/line_frontend.py`
- `src/cadrumo/entrypoints/tui/flows/app.py`

## Changes

The gate's own docstring described the fix that was missing. It says the badge
keys "are centralised in a `*_LOCALE_KEYS` constant that the AST constant-registry
collector picks up" -- and no such constant existed. Both frontends had inlined
the choice instead:

    badge_key = "flows.progress.required" if entry.page.required else "flows.progress.optional"
    ... tr(badge_key)

The scanner reads a literal inside `tr()`, and it reads module-level constants
whose name carries the convention. It does not follow a variable, so neither key
was collected from either site. That is worse than a missing translation: a
catalogue strip prunes an uncollected key as an orphan, and the badge then
raises at render time on a key nothing appears to reference.

The pair now lives in `application/flows/copy.py`, which both frontends already
import -- the shared render-time copy home, so neither frontend owns a key the
other also spends. Keyed by the boolean it selects on, so the call sites index
rather than branch.

The constant's NAME is load-bearing rather than descriptive, and the docstring
says so, because that is the part a later reader would otherwise tidy away.
Teeth prove it: renaming PAGE_REQUIREMENT_LOCALE_KEYS to
PAGE_REQUIREMENT_BADGES -- a rename that changes no behaviour and reads better
-- fails the gate. Restored by copy; 155 passed across the gate module and both
flow suites.

## Notes

This is the same scanner machinery S442 found behind the 463 parity extras, and
it is the tractable half of it. The other half is different in kind: the
destination keys are declared in a `type X = Literal[...]` alias, which the
scanner cannot see because it walks `ast.Assign` and a PEP 695 alias is an
`ast.TypeAlias`. Fixing that means teaching the scanner a new node type rather
than moving a declaration into a convention that already exists, so it is not
folded in here.

The one failure left in this gate module is
test_language_override_sites_match_the_sanctioned_inventory, which is a
different target and untouched.
