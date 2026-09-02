---
tags:
  - '#adr'
  - '#gate-integrity-adjudication'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:1ee8362787bb7a99b209035c6ca81ce7be97fbd30df388dd81f9150d11d76b9c'
related:
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]"
  - "[[2026-09-02-cli-distribution-consolidation-adr]]"
  - '[[2026-09-02-gate-integrity-adjudication-research]]'
---

# `gate-integrity-adjudication` adr: `the CLI-to-TUI import edges are a code defect, not a stale contract` | (**status:** `accepted`)

## Problem Statement

Two import contracts report broken: the backend and sibling prohibition on
depending on the dedicated TUI, and the prohibition on the TUI depending on a
sibling entrypoint. The standing reading is that both encode a
pre-consolidation architecture and were contradicted when the separate TUI
console script was retired, so the contracts should be relaxed or retired to
let the aggregate static gate reach a clean exit.

That reading has to be adjudicated rather than acted on, because the two
prohibitions are the only structural guarantee that the full-screen surface
stays an outermost process entrypoint. Relaxing a contract because a violation
appeared is the failure mode the project's own gate discipline names, and it is
indistinguishable, from the exit status alone, from repairing the code.

## Considerations

- The dependency direction is current, not superseded: `2026-08-11-tui-architecture-adr`
  D11 states that no backend package, CLI or MCP entrypoint, shared test utility, or
  development tool may import, load, re-export, annotate against, or register from the
  TUI, and names packaging metadata and out-of-process execution as the only external
  references.
- `2026-09-02-unreachable-capability-tui-navigation-join-adr` restates it as a hard
  constraint of the accepted design: the join must not introduce a CLI-to-TUI import
  edge, and the root request starts the session as a child interpreter.
- The consolidation did not create an import edge. `src/cadrumo/entrypoints/cli/_tui_session.py`
  names the TUI as a module string, spawns it with `python -m`, and its docstring states
  that out-of-process execution is the sanctioned way for one entrypoint to reach the
  other. It is the consolidation's implementation and it keeps both contracts.
- The reported violations are elsewhere. `cli._modelo_work_review_cli` imports
  `tui.modelo.view.work_review`, and `cli._modelo_work_select_cli` imports
  `tui.components.host`, `tui.modelo.routes`, `tui.modelo.view.controller` and
  `tui.modelo.view.work_select`. Both construct Textual applications and call `run()`
  inside the CLI process. That is the CLI consuming the TUI as a reusable frontend
  library, which is the exact thing the prohibition exists to prevent.
- Those imports arrived with the modelo work-surface lane, not with the consolidation
  commit that retired the second console script.
- The sibling-direction breach is a single test edge:
  `tui.tests.test_installed_entrypoint` imports `cli._tui_session` to assert that the
  command the CLI builds is the module-execution surface. Production reach in that
  direction remains zero.
- `.importlinter` already distinguishes production edges from test edges: the
  launcher-only wiring contract carries explicit test allowances with the recorded
  reason that they are not production code.

## Considered options

**Relax or retire both prohibitions.** Rejected. It would ratify an in-process
dependency that two accepted records forbid, and would remove the only mechanical
guarantee behind the out-of-process boundary at the moment that boundary is being
breached.

**Add a named exception for the session bridge.** Rejected as misdirected. The session
bridge does not violate anything; an exception naming it would suppress nothing, and if
drawn broadly enough to cover the real edges it would silently license the whole
CLI-to-TUI direction.

**Baseline the production edges as known violations.** Rejected. A baseline converts a
live architectural regression into accepted background, and these two edges are
precisely the class the contract was written to catch.

**Keep the production prohibition intact and narrow the sibling contract to production
reach.** Chosen. The production direction stays a hard prohibition with no allowance;
the sibling contract gains a single named test allowance matching the file-local
precedent, because the edge it reports is a contract proof rather than a dependency.

## Constraints

- The TUI tree is in-flight work owned by another lane. Repairing the two CLI modules
  requires the module-execution surface to accept a routing request and return a
  selection result, which is TUI-side work this record does not perform.
- The two CLI modules pass live objects into the screens they open and read a chosen
  work-unit identifier back out. Neither crossing survives a naive move to a child
  process, so the repair is a protocol rather than a call-site edit.
- The aggregate static gate cannot reach a clean exit from this record alone: the
  layered-architecture contract is independently broken across a large
  application-to-adapters population that this decision does not touch.

## Implementation

The two production prohibitions stand unchanged and unweakened. The CLI-to-TUI edges
reported against them remain reported, and are handed to the lane that owns the TUI
tree as a defect rather than absorbed as a baseline.

The sibling contract is narrowed in one dimension only. Its subject becomes the TUI's
production modules, with the entrypoint-proof test module named as an explicit
allowance carrying its reason inline. This matches how the launcher-only wiring contract
in the same file already separates production wiring from test construction, and it
preserves the property the contract was written for: the production reach from the TUI
to a sibling entrypoint stays zero and stays guarded.

The repair the production edges need is stated here so the owning lane can execute it
without re-deriving the constraint. The full-screen destinations those two commands open
are reached by extending the module-execution surface to accept the command path already
accepted as the routing request, and by returning the selection outcome over the child's
exit status or its structured output, so the CLI names no TUI symbol.

## Rationale

The decisive fact is that the prohibition is not a leftover. Two records accepted on the
same day as the consolidation restate it, one of them as an explicit constraint on the
very join the consolidation created. A contract that a current accepted decision
requires is not evidence of stale design when it reports a violation; it is the design
working.

The session bridge settles the counter-argument on its own. If consolidation had made
the boundary unkeepable, the module that implements consolidation could not keep it. It
does keep it, in the same tree, for the same surface, which shows the in-process imports
are a choice the work-surface lane made rather than a consequence the consolidation
forced.

The test allowance wins over both a broader redraw and a refusal to touch the file
because it is the smallest change that leaves every guarantee intact. The edge it admits
runs in the opposite direction from the risk, exists only to assert the boundary, and
has a same-file precedent with a recorded rationale.

## Consequences

The production prohibition keeps its teeth, and the two reported edges stay visible as
what they are. The cost is that this contract continues to report broken until the
owning lane lands the routing protocol, so the aggregate gate stays red on this axis and
nobody can mistake red for done.

The sibling contract stops reporting a proof as a violation, which removes the pressure
to weaken it for the wrong reason. Its production subject is unchanged, so a real
sideways dependency from a TUI module would still fail.

A reader arriving at the broken report later is now told, in the record, which edges are
defects and which direction the repair runs, rather than re-deriving it from a contract
whose comment no longer matches the tree.
