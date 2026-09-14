---
tags:
  - '#adr'
  - '#gate-integrity-adjudication'
date: '2026-09-02'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:25206a0f9eba71499ecc1c381d239c8077617b6d2e43fc92ae8bb5e086aa2063'
related:
  - "[[2026-09-02-gate-integrity-adjudication-tui-entrypoint-contracts-adr]]"
  - '[[2026-09-02-gate-integrity-adjudication-research]]'
  - '[[2026-09-14-gate-integrity-adjudication-pre-commit-hook-reconsideration-research]]'
  - '[[2026-09-14-gate-integrity-adjudication-pre-commit-hook-runtime-reference]]'
---
# `gate-integrity-adjudication` adr: `commit-time hooks stay uninstalled and repair stays explicit and path-scoped` | (**status:** `accepted`)

## Problem Statement

The accepted decision keeps mechanical gates out of commit time because
staged-content hook execution can manipulate concurrent worktree state. The
decision is reopened only to determine whether fast Ruff and ty repair can
satisfy that safety boundary while remaining non-blocking for residual
diagnostics.

The renewed evidence shows that an installed `prek` hook cannot combine
mutation, no stash/restore, and a successful hook result. This amendment
preserves the accepted direction and concretizes the safe repair surface
outside commit time rather than creating a second decision record.

## Considerations

- Installed `prek` execution cannot satisfy the required no-stash and
  non-failing-mutation contract; see
  `2026-09-14-gate-integrity-adjudication-pre-commit-hook-reconsideration-research`
  and
  `2026-09-14-gate-integrity-adjudication-pre-commit-hook-runtime-reference`.
- A caller-owned-path action can provide fast mechanical repair without taking
  ownership of unrelated files or Git state; see the related research.
- Project-locked local tools avoid a second formatter, linter, or type-tool
  implementation; see the related reference and `2026-09-11-justfile-design-adr`.
- Direct ty repair is a mechanical aid, not the repository's authoritative
  type verdict; see the related research.
- “Fast” requires an admission threshold rather than a qualitative promise;
  see the related research and reference.
- Just, CI, `prek`, and setup must express one consistent ownership boundary.

## Considered options

**Install mutating `prek` hooks and suppress diagnostic failures.** Rejected.
Tool-level exit flags cannot suppress `prek` failure after file mutation, and
staged-content execution retains the prohibited save/restore mechanism.

**Install verify-only `prek` hooks.** Rejected. Removing mutation does not
remove staged-content isolation or its Git-state hazard.

**Introduce a native index-only Git hook.** Rejected for this decision. It is a
separate subsystem requiring concurrency, partial-staging, recovery, and
performance proofs that the current grounding does not provide.

**Retain only whole-tree repair commands.** Rejected as the near-commit
workflow. Their scope can include files the caller does not own, and runtime is
not bounded by the proposed change.

**Keep hooks uninstalled and expose explicit path-scoped repair.** Chosen. It
preserves the worktree-safety boundary while providing the fast mechanical
feedback sought by the reconsideration.

## Constraints

- Project setup, `prek`, and the repair action install no pre-commit hook.
- The repair action requires explicit caller-owned paths. It validates that
  every path is inside the current worktree, selects only supported Python
  files, and never expands scope to the whole tree.
- The action does not read or mutate the Git index, stage files, stash changes,
  restore files, rewrite refs, or otherwise alter Git state.
- The action performs no synchronization, installation, download, or network
  work. It invokes project-locked tools through `uv run --no-sync`.
- Eligibility requires a representative warm p95 no greater than two seconds.
  Work exceeding that ceiling is removed or split, never admitted as a
  whole-tree or long-running commit-time step.
- Residual lint or type diagnostics are advisory for repair and do not make a
  completed repair fail. Invalid input, path refusal, configuration, I/O,
  process-launch, and internal tool failures remain visible and non-zero.
- Ty repair requires isolated detector tests proving supported mutation,
  no-op behavior, residual-diagnostic behavior, and confinement to supplied
  fixture paths. The shared worktree is never a detector fixture.
- The complete type gate remains the authoritative CI verdict. Path-scoped ty
  repair does not claim type-check success.

## Implementation

One quality-tooling owner validates and normalizes the explicit paths once,
then passes the same eligible set through this fixed sequence:

1. `ruff check --fix`
2. `ty check --fix`
3. `ruff format`

Diagnostic-exit suppression applies only where residual findings must stay
advisory. Operational failures retain their native meaning and fail the
aggregate. Formatting remains last because earlier repairs can create
formatting work.

The root Just surface exposes a focused repair entrypoint beneath the accepted
`fix-code` contract and delegates sequencing and exit handling to the single
quality owner. It requires path arguments and neither queries nor changes Git.

CI never runs the mutating action as a gate. It runs the isolated repair
contract and ty detector tests, while existing full lint, formatting, and
multi-checker type gates retain verdict authority. Performance eligibility is
demonstrated by a warm benchmark rather than inferred from one-file timing.

`prek` remains an uninstalled manual replay configuration, not an installation
or repair authority. Its stale no-stash claim is removed, remote Ruff ownership
is replaced with the locked local tool, and mutating repair is not enrolled in
a hook stage.

Repository setup neither installs hooks nor changes `core.hooksPath`. Dormant
installation code and setup claims implying automatic installation are retired
or corrected. CI, Just, replay, setup, tests, and contributor guidance are
reconciled together.

## Rationale

This is the only evaluated design satisfying every binding condition without a
new Git subsystem. Explicit paths make ownership an affirmative caller choice;
locked no-sync execution and one owner prevent Just, replay, and CI from
drifting.

The two-second warm p95 ceiling prevents convenience from becoming an
unbounded gate. Advisory residual diagnostics keep repair useful, while
operational failures remain visible so skipped or broken work is not reported
as success. CI retains full type authority because path-scoped ty does not
exercise the complete checker population.

## Consequences

Contributors gain a fast repair loop over files they explicitly own, with lint
repair followed by type repair and final formatting. They must review and stage
the intended result themselves.

Commits remain unblocked by project-installed hooks. A contributor may commit
residual diagnostics if they ignore local output and CI; that trade-off
preserves concurrent worktree safety.

Ty repair carries no authority until its isolated safety tests pass. If they
cannot prove a narrow mutation contract, the ty step stays unavailable while
Ruff repair remains usable.

The benchmark becomes maintained eligibility evidence. A regression above two
seconds removes or splits work rather than relaxing the ceiling. Any future
installed or index-only hook reverses this boundary and requires supersession.
