---
tags:
  - '#audit'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:26f6181f4539b7f7abcee170b695cc490a130cf4ac47f952ea11f1ba45772586'
related: []
---

# `semantic-consolidation` audit: `production scan surface definitions`

## The finding

`cadrumo.tests._inventory.production_python_files` documents itself as the
shared definition: test modules, `conftest.py` files and the bundled `_data`
tree are excluded "so structural production ratchets share one definition of
their scan surface."

They do not share it. **55 functions across `src/` and `dev/` independently walk
`*.py` and apply their own filters.** The claim in that docstring is true of the
function and false of the codebase.

Reported by another session as a pair -- `_inventory.production_python_files`
against `dev/source_connectivity/discovery._production_python_files` -- with the
caveat that the count came from looking for one behaviour rather than sweeping.
The caveat was right: it is a family, not a pair.

## The disagreements have teeth

Measured against the current tree:

| what a walker may or may not exclude | files it changes |
| --- | --- |
| the bundled `_data` tree | 4 `.py` files |
| `conftest.py` | 29 files |
| `__init__.py` | 284 files |

A walker that does not exclude `_data` reads bundled corpus code as production.
One that does not exclude `conftest.py` reads test infrastructure as production.
One that excludes `__init__.py` -- as `discovery._production_python_files` does
-- cannot see any namespace at all, which for the semantic-consolidation
campaign is precisely the surface under change.

That last one matters beyond tidiness: a ratchet built on a walker that skips
`__init__.py` would have reported this campaign's namespace retirements as
invisible.

## Not every walker is a defect

The 55 divide. Some scope deliberately to a subtree -- custody modules, TUI
modules, payload modules -- and a narrower surface is their point. Those are not
re-declarations of "production"; they are different questions that happen to
share a mechanism.

The defect is the walkers that mean the WHOLE production surface and answer
differently. Consolidating the scoped ones onto a shared definition would be the
opposite error: collapsing distinct questions because they look alike, which is
what this campaign exists to prevent.

## The untracked-file hazard, and why it is sharper than it looks

The reporting session noted that no walker excludes untracked files, so a
scratch file in the package root is read as production, and that a probe had
already crashed on one.

The tree currently holds **56 untracked `.py` files under `src/cadrumo`**, and
most are this campaign's own: `selection.py`, `text_extraction.py`,
`contract.py`, `policies.py`, `records.py` and the other modules created by
relocating code out of namespaces. They are legitimate production modules that
happen not to be committed yet.

So the hazard is not only that scratch files look like production. It is that a
walker cannot distinguish a scratch file from a real new module, and in a shared
worktree mid-campaign the untracked set is dominated by the latter. Any
exclusion keyed on tracked-ness would have hidden this campaign's own output
from every ratchet that uses it.

The reporting session declined to fix it and gave the reason: a name convention
guesses at what agents call their scratch files, and a git-tracked filter
couples a pure AST walker to a checkout. Both objections hold, and the second is
strengthened by the measurement above.

## What this needs

A designed answer for the shared surface, then adoption by the walkers that mean
"production" -- not by all 55. The scoped walkers should keep their scopes and
say so.

One constraint worth stating before anyone reaches for it: pointing
`dev/source_connectivity/discovery.py` at `cadrumo.tests._inventory` creates a
`dev -> cadrumo.tests` edge, and `cadrumo.tests` is currently the trigger for
nine armed import-linter pins that name the bare package and will stop matching
if its `__init__` goes inert. That is not a reason to avoid the consolidation,
but it belongs in the same change.

## Design input: reachability was tested and is not sufficient

The obvious third option, after name conventions and git-tracked filters were
both ruled out, is REACHABILITY: a scratch probe nobody imports is unreachable,
while a relocated module whose consumers were repointed is reachable. It fixes
the exact failure the other two get wrong.

It was measured rather than assumed. Of **1,911 production modules, 49 are never
imported anywhere** under `src/` or `dev/`.

Forty-five are CLI command modules, loaded on demand by the command-spec
registry rather than imported. The remaining four are each reachable by another
declaration mechanism:

| module | how it is actually reached |
| --- | --- |
| `adapters/outbound/aeat/export/errors.py` | both classes declared in the error-code registry |
| `domain/fincas/source_readiness.py` | 30 references by name |
| `adapters/persistence/storage/custody/_kdf_worker.py` | 12 references by name |
| `domain/renta/_first_slice_routing_integrity.py` | 2 references by name |

So a reachability rule keyed on static imports would flag 49 legitimate modules
and, applied as a filter, would silently REMOVE them from every ratchet that
uses it. That is the same false-clean failure as the git-tracked filter, on a
different axis.

### What the measurement does support

Reachability works as a rule if "reached" includes declaration mechanisms:
statically imported, enrolled in the command-spec registry, declared in the
error-code registry, or named in a declaration this codebase already validates.
Every one of the 49 satisfies that wider rule, and a scratch probe satisfies
none of it.

That also suggests the check should REFUSE rather than filter. An orphan is
either a scratch file or a module whose enrolment is missing -- both are worth a
loud failure naming the file, and neither is worth silently including or
silently dropping.

### A finding the census produced on the way

`AeatExportFormatError` and `ExportError` have no consumers anywhere in the
tree. Retiring the `aeat/export` facade did not orphan them: all five of that
facade's consumers imported only the renderer, so the two errors were already
unreferenced and the facade was concealing it.

They are NOT dead code. Both are declared in the error-code registry, which
makes them stated capability, and a registry entry measures identically to an
unused class from the outside. Recorded, not removed.
