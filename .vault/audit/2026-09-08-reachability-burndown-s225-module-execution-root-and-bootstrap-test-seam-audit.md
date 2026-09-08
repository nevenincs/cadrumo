---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:faafba20e536d6b98f7b3e38eade825fc7d0aa3af94064af67a251bd061e177c'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
  - "[[2026-09-04-reachability-burndown-W05-P12-S225]]"
  - "[[2026-09-04-reachability-burndown-reference]]"
---

# `reachability-burndown` audit: `S225 module execution root and bootstrap test seam review`

## Scope

Independent review of W05.P12.S225: derived shipped `python -m` roots, detector tests, the Windows inherited-HANDLE bootstrap, relocation of `bootstrap_interpreter` into existing test support, retained subprocess security behavior, the accepted archived machine-secret ADR, cadence guidance, exact signals, and Step Record evidence.

## Findings

No critical, high, medium, or low findings.

`ShippedTreeSpec.from_repository` now derives module-execution roots from shipped non-test Python files. Every `__main__.py` remains a root; other modules qualify only when their parsed module body contains an exact single equality between `__name__` and the literal `"__main__"`. Nested comparisons and prose strings are negative controls, while package-main and guarded-module fixtures are positives. The cheap text prefilter avoids parsing files that cannot contain the marker without changing the structural decision. This does not broadly clear modules based on substrings, nested code, tests, unshipped files, or approximate comparisons.

The accepted Windows bootstrap is correctly recognized as a product root because it has a real top-level main guard and is directly executable with `python -m`. Its production functions for HANDLE-to-descriptor conversion, argv construction, and main dispatch remain. `bootstrap_interpreter` was not part of bootstrap execution; it existed solely to let subprocess tests bypass virtual-environment launchers on Windows. Moving that helper into the pre-existing test-support module removes a production test seam while leaving all security-matrix imports and calls semantically unchanged.

The retained subprocess tests still exercise platform descriptor bootstrap and recovery-descriptor behavior. No hand-maintained module list, compatibility alias, or source dependency on tests/dev was introduced. The archived accepted ADR explicitly requires the Windows inherited-HANDLE bootstrap and its descriptor security semantics, which this change preserves.

The Step Record accurately reports Ruff, 51 detector tests, two focused integration passes with 16 transparent deselections, and the exact result: 60 unreachable modules, 306 exact unused symbols, 8 orphaned tests, and 2029/2090 reachable shipped modules, with five structurally derived roots plus the workspace sibling. The signal changes are explained by recognizing the bootstrap root and relocating the test-only helper, not by widening an allowlist.

## Recommendations

Approve W05.P12.S225. Keep module-execution roots structurally derived from executable file shape, and keep interpreter-selection helpers in test or packaging support unless the product bootstrap itself consumes them.
