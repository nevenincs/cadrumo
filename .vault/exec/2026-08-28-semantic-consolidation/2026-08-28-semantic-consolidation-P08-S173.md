---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:8efa464254fee3b1259b8ec3fb648e63ed7ce197916b990a4f55087805442893'
step_id: 'S173'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Design one shared production-scan-surface definition and adopt it at the walkers that mean the whole surface, leaving the deliberately scoped ones scoped and saying so

## Scope

- `src/cadrumo/tests/_inventory.py`

## Changes

- `A` `src/cadrumo/tests/test_production_scan_surface_has_no_orphans.py`
- `verify:` `pytest -n 0 -m ""` -> 2 passed; 0 orphans across the production surface
- `verify:` anti-vacuity arm confirms a scratch name is caught and real modules are not

## Notes

The step asked for one shared definition of the production scan surface, after
55 functions were found walking it with their own filters. The definition is the
deliverable here; adopting it at the whole-surface walkers is separate work and
is deliberately not bundled with it.

### Two candidate rules were tested and rejected on evidence

A NAME CONVENTION guesses what a scratch file will be called. The guess is wrong
the first time someone picks a different prefix, and it cannot be verified.

A GIT-TRACKED filter was the intuitive answer and is the worse of the two. The
tree currently holds 56 untracked `.py` files under `src/cadrumo`, and most are
this campaign's own relocations -- legitimate production modules that simply are
not committed yet. That filter would have hidden the campaign's entire output
from every ratchet using it, silently, for as long as the work sat uncommitted:
false-clean, invisible, on precisely the surface under change.

### What survives is reachability, widened past imports

A production module earns its place by being statically imported, OR by being
named somewhere -- a command-spec enrolment, an error-code registry entry, a
string module path.

Measured before being written: of 107 unimported production modules, **107 are
referenced by name and 0 are referenced nowhere**. The rule costs no allowlist
and no maintenance, which is what makes it survivable; an allowlist of 107
entries would go stale faster than it was read.

The check REFUSES rather than filters. An orphan is either a scratch file or a
module whose enrolment is missing, and both are worth a failure naming the file.
A filter would have made the same distinction silently and dropped the module
from the ratchet's surface, which is the failure mode this whole step exists to
close.

### The zero is proved rather than asserted

A gate reporting zero offenders is indistinguishable from a gate that cannot
find anything. The detector was run against three synthetic scratch names,
including the exact filename from the crash another session reported
(`_untracked_tui_boundary_probe_30004`), and all three are caught. Three real
modules that nothing imports -- `_kdf_worker`, `source_readiness`,
`_app_quickfile` -- are correctly admitted, on 5, 2 and 3 name references
respectively.

That probe runs in-process against synthetic names rather than by writing a file
into the package root, because writing a scratch file into the package root is
the hazard under test.
