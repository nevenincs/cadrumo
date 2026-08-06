---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:fde621beec5213e63831cd3b70ea14da24a15a21b16d7a7113a33d3fc68d0ad0'
step_id: 'S56'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# pin the two detector branches whose individual mutation flips nothing with fixtures for an interpolated device path and an interpolated mid-path segment, and either delete the two redundant branches or correct the docstring that credits one with protection a different mechanism delivers

## Scope

- `dev/import_hygiene_scan.py`

## Description

- Plant an f-string device-path fixture in the boundary gate covering both the fully-constant `f"/dev/null"` and the realistic `f"/dev/{name}"`, whose interpolation sits after the device path and must not license it either.
- Plant a mid-path fixture, `f"{root}-sandbox/dev/notes.json"`, naming a `dev` directory one level below a sibling tree rather than this repository's.
- Delete the call-join reader's dead argument guard, since `any` over an empty sequence is already false.
- Keep the absolute-path guard and rewrite the docstring that credited it with the device-path protection the segment-equality rule actually delivers, naming the single future widening the guard does cover.
- Record the new isolating fixtures and the two redundancy rulings in the gate module's own anti-tautology standard.

## Outcome

Both branches are now discriminating. Measured through a `sys.path`-overlay plus a subprocess pytest run at `-n0`: an in-process patch reports a false clean here because the default options carry `-n auto` and the xdist workers re-import the real module, which cost the originating review three false results. An identity-control overlay carrying no mutation reproduced `23 passed` before any mutation verdict was trusted, and the harness aborts unless the imported module resolves inside the overlay.

Dropping the preceding-interpolation requirement moves `f"/dev/null"` from zero hits to one and `f"/dev/{n}"` from zero to one, and fails exactly one test, the new f-string device-path proof: `1 failed, 22 passed`. Dropping the empty-leading-segment requirement moves the mid-path probe from zero hits to one and fails exactly one test, the new mid-path proof: `1 failed, 22 passed`. The clean run is `23 passed` and the four gates consuming the scanner run `64 passed in 199.61s`, exit 0, with the two new tests collected under the default selector.

The two redundancy rulings are measured rather than asserted. Deleting the absolute-path guard alone produces no behavioural delta on any probe and no failure, confirming it is unreachable as protection today. Widening the relative-marker skip to swallow the empty segment while the guard stands also produces no delta and no failure. Doing both together makes the shipped `/dev/tty` read score a hit and reds three tests including the live-tree gate. The redundancy is therefore conditional, not absolute, so the guard is kept and its docstring corrected; a straight deletion would have left the gate one plausible refactor away from firing on correct shipped code. Re-adding the deleted argument guard produces no delta on any probe, confirming it was dead.

## Notes

Semantic-search discovery was explicitly waived by the operator for this Step: the semantic index is broken and its service stopped, so the service was neither started nor queried. Grounding was whole-file reads of the detector and the boundary gate plus targeted pattern search.

The first overlay attempt resolved imports back to the real module because the interpreter's own working-directory entry outranks the overlay path; the harness's resolved-path assertion caught it rather than reporting a false clean. The overlay now pre-registers the mutant under its dotted name at interpreter startup, which any worker process inherits.

The overlay copy also had to have the scanner's repository root pinned back to the real checkout. The scanner derives that root from its own file location, so the copy resolved it into the scratch directory and could not read the packaging config, reddening the two live-tree tests under every mutation as a constant harness offset rather than as signal.

One pre-existing type diagnostic sits in the scanner at an unrelated symbol-export function; it is byte-identical at the previous commit and the project type gate scopes its checker to the shipped tree, so the file is not covered by it. Not absorbed, not caused here.
