---
tags:
  - '#adr'
  - '#test-worker-count-policy'
date: '2026-07-08'
modified: '2026-07-17'
body_hash: 'sha256:03246b3ab5e9441c99a6db6202ed63db3871a628927c71628888df7dee64a7f8'
related:
  - '[[2026-07-10-test-worker-count-policy-research]]'
---

# `test-worker-count-policy` adr: `cap pytest-xdist workers via the native env var, operator-set, never a blanket default` | (**status:** `accepted`)

## Problem Statement

This shared factory worktree runs many concurrent campaign agents, and each
agent's pytest invocation inherits `-n auto` from `pyproject.toml`'s
`addopts`. Under pytest-xdist's `auto` heuristic every invocation sizes its
worker pool to the full logical core count of the machine, oblivious to the
sibling invocations already running. On this 24-core development box the
baseline load from concurrent agents alone was measured at 154 live
`python.exe` processes; three concurrent `-n auto` suite invocations on top
of that drove the machine to 230 processes and 97.8% CPU, with each run's
median wall time degrading to ~60.1s. The workers of each run were fighting
the workers of every other run for the same cores: more workers, less
throughput. The campaign needed a worker-count policy that recovers
throughput under multi-agent concurrency without slowing down the two
environments where `-n auto` is exactly right — CI and a solo developer run.

## Considerations

- pytest-xdist 3.8.0 (the version locked in `uv.lock`) natively honors the
  `PYTEST_XDIST_AUTO_NUM_WORKERS` environment variable: when set, it is
  consulted before the `psutil.cpu_count()` heuristic that `-n auto`
  otherwise falls back to. No plugin, hook, or `addopts` change is required
  for the cap to take effect — the mechanism already ships in the pinned
  dependency.
- The concurrency penalty and the solo penalty point in opposite directions.
  Measured on this box (real runs, not simulated): three concurrent
  invocations capped to 4 workers each dropped the machine to 181 processes
  and 62.4% CPU and improved the median run to ~54.1s (~10% faster than the
  uncapped 60.1s under the same concurrency); but a SOLO run under the same
  4-worker cap cost ~9% MORE wall time (49.1s vs 44.9s uncapped). Any policy
  that bakes a cap into a shared default trades the solo and CI cases away
  to buy the concurrent case.
- CI (`.github/workflows/ci.yml`) runs `uv run pytest --junitxml=junit.xml`
  with no `-n` override of its own, so it inherits `addopts`' `-n auto`. A
  CI runner is a single-tenant machine where `auto` is the correct sizing;
  the policy must leave CI's inherited behavior untouched.
- The justfile already reads a project-branded `AEAT_PYTEST_WORKERS`
  variable (`pytest_workers := env_var_or_default("AEAT_PYTEST_WORKERS",
  "auto")`), but that only covers the `just test-unit` recipe. Agents in
  this worktree invoke pytest through many shapes — bare `uv run pytest`,
  path-scoped runs, subprocess-spawning gates — that never route through
  the justfile, so the existing variable is not a complete enforcement
  surface.

## Considered options

- **Operator/environment-level `PYTEST_XDIST_AUTO_NUM_WORKERS` (chosen).**
  The native pytest-xdist variable, set in the operator's environment (or a
  dispatch brief) on the multi-agent box only. Zero code change, covers
  every invocation shape that uses `-n auto`, and leaves CI and solo runs —
  where the variable is simply unset — byte-for-byte on their current
  behavior.
- **Blanket `-n <cap>` in `pyproject.toml` `addopts`.** Rejected: it
  penalizes exactly the environments that dominate total suite-hours. CI
  and a solo developer run pay the measured ~9% solo regression on every
  run, forever, to optimize the one machine that has a cheaper, targeted
  lever available.
- **CI-detection heuristic (cap by default, detect `CI=true` and lift).**
  Rejected: inverts the burden onto an environment-sniffing branch that
  must correctly enumerate every "not the shared box" context (CI vendors,
  a teammate's laptop, a fresh clone). A wrong guess silently slows the
  wrong environment, and the heuristic itself becomes config surface to
  maintain. The shared box is the special case; the special case should
  carry the configuration.
- **`AEAT_PYTEST_WORKERS` conftest-hook variant.** A project-branded
  variable read by a conftest hook, protecting every invocation shape
  regardless of how pytest is launched, and unifying with the justfile's
  existing variable. Deferred as P2, not rejected: it is the structural
  answer to the enforcement gap the chosen option leaves open (see
  Consequences), but it requires proof that the hook can adjust the worker
  count early enough in pytest-xdist's startup ordering to take effect.
  Gated on that hook-ordering proof-of-concept before any implementation.

## Constraints

- The cap mechanism must be native to the locked pytest-xdist version:
  `PYTEST_XDIST_AUTO_NUM_WORKERS` support is present in 3.8.0 (consulted
  before `psutil.cpu_count()`), and the `pyproject.toml` floor
  (`pytest-xdist>=3.6.0`) plus the lockfile pin keep the resolved version
  in the supporting range.
- The variable only influences `-n auto` resolution; an explicit `-n <N>`
  on the command line still wins. This is acceptable — an agent that
  explicitly asks for a count has made a deliberate choice — but it means
  the policy governs the default path, not every conceivable invocation.
- CI must remain untouched under every option: `.github/workflows/ci.yml`
  sets no `-n` override and no `PYTEST_XDIST_AUTO_NUM_WORKERS`, so it
  inherits `addopts`' `-n auto` unchanged. This was verified against the
  workflow file, not assumed.

## Implementation

No repository code changes. The policy is: on the multi-agent shared box,
the operator (or the coordinator's dispatch environment) sets
`PYTEST_XDIST_AUTO_NUM_WORKERS` to a small per-invocation cap (4 was the
measured sweet spot for three concurrent invocations on 24 cores) before
launching concurrent suite runs. `pyproject.toml` `addopts` keeps
`-n auto`; CI keeps its inherited behavior; solo runs on any machine where
the variable is unset keep full-width `auto`. The deferred P2 follow-up — a
conftest hook reading a project-branded `AEAT_PYTEST_WORKERS` and applying
it to every invocation shape — proceeds only after a proof-of-concept
demonstrates the hook fires early enough in pytest-xdist's worker-count
resolution to actually take effect; until then the justfile's existing
`AEAT_PYTEST_WORKERS` handling stays as-is, covering `just test-unit` only.

## Rationale

The measurements make the shape of the decision unambiguous: capping is a
~10% win under real multi-agent concurrency (60.1s → 54.1s median across
three concurrent invocations, CPU saturation dropping from 97.8% to 62.4%)
and a ~9% loss solo (44.9s → 49.1s). A single default cannot be right for
both, so the cap must attach to the environment that benefits, not to the
project config every environment inherits. The native env var is the
narrowest possible lever that does this: it requires no code, it is honored
by the exact pytest-xdist version the lockfile pins, it composes with every
invocation shape that reaches `-n auto`, and removing it is deleting an
environment variable rather than reverting a config commit. The
project-branded conftest variant is acknowledged as the more complete
mechanism — it is deferred on engineering risk (hook ordering), not
rejected on merit.

## Consequences

- Concurrent multi-agent suite runs on the shared box recover roughly 10%
  median wall time and stop saturating the machine (97.8% → 62.4% CPU in
  the measured three-invocation scenario), which also lowers the collateral
  latency every OTHER agent's non-pytest work pays during a suite run.
- CI and solo runs are structurally unaffected: nothing in the repository
  changed, so there is no regression surface to re-verify per environment.
- The honest trade-off: the policy is opt-in and relies on the env var
  actually being set in the shared-box environment. Nothing structurally
  forces it — a fresh agent session or a new terminal that forgets the
  variable silently reverts to full-width `-n auto` and re-creates the
  contention. Closing that gap is precisely the deferred P2 conftest-hook's
  job; until it lands, the enforcement is operator discipline plus dispatch
  briefs, and this ADR is the document that makes the discipline legible.
- A capped solo run on the shared box (variable set, but no sibling
  invocations running at that moment) pays the ~9% solo penalty. This is
  accepted: on a box whose baseline is 154 concurrent python processes,
  the truly-solo window is rare, and an operator who knows the box is
  momentarily quiet can unset the variable for that run.
