---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:ca57be077a03c866f65f3386f6fa41d3d432934680a99809a1eb54b8ee263894'
step_id: 'S91'
related:
  - "[[2026-08-11-tui-interface-plan]]"
  - "[[2026-08-11-tui-interface-W06-P12c-S90]]"
---

# Prove the final current-HEAD producer, writer, route, destination, action, command-capability, denominator, and receipt fixed point has zero duplicate authorities, aliases, unclassified candidates, stale exclusions, or transitional TUI rows

## Scope

- `dev/tests/test_modelo_workspace_fixed_point.py`

## Changes

- `A` `dev/tests/test_modelo_workspace_fixed_point.py`
- `verify:` `pytest test_modelo_workspace_fixed_point.py` -> `6 passed`

## Notes

BUILT ON THE EXISTING SCANNER, NOT A SECOND CENSUS. The fixed point is a
declarative `CanonicalAuthoritySpec` handed to `scan_canonical_authority` --
the same scanner the work-selection fixed point uses. Writing a parallel census
here would have created a duplicate authority inside a gate whose entire
subject is duplicate authorities.

TWO SHIPPED AUTHORITIES ARE DECLARED: the destination table in `routes.py` and
the action dispatch table in `actions.py`. The DENOMINATOR IS DELIBERATELY NOT A
TARGET -- it lives in `dev/quality`, outside the shipped package, and `src` may
not import it, so an import census over it would have nothing to census. Its
singularity is asserted instead by running its own retained validator, reused
rather than restated for the same reason.

A REAL CONSTRAINT INTERACTION, WORTH KEEPING BECAUSE IT WILL RECUR. The scanner
resolves its corpus through `git ls-files`. This worktree forbids git
operations, so newly authored modules are UNTRACKED and therefore invisible to
it -- every symbol the spec declared canonical was reported `missing canonical
definition`, which reads exactly like a module that failed to define them. It
is a property of the corpus, not a defect in the module or the scanner.

The fix is scoped rather than blanket: the scan paths are tracked files UNIONED
WITH THIS COHORT'S OWN TREE. Admitting untracked files generally would pull a
peer's in-flight work into this gate's denominator, which is precisely the
contaminated-artefact hazard the architecture lane records against regenerating
inventories during churn.

A SECOND SELF-INFLICTED FAULT: the namespace-inertness check counted `from
__future__ import annotations` as a bound import, so every correctly inert
namespace failed its own inertness test. A `__future__` directive binds no
project symbol -- it is a compiler instruction -- and is now excluded.

TRANSITIONAL MARKERS ARE SWEPT FROM THE SHIPPED SURFACE, with an anti-tautology
control proving the matcher can see a marker it is given. Without that control
the sweep passes identically against a scanner that opens nothing, which is the
hollow-proof shape this campaign keeps finding.
