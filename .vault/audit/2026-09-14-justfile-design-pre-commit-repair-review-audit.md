---
tags:
  - '#audit'
  - '#justfile-design'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:6adb6727e068aa6653003b009fee642287f5468c9e615f3287c6f82fb02f7063'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# `justfile-design` audit: `pre commit repair review`

## Scope

Reviewed the explicit-path repair owner, its real-tool detector tests, Just and
`prek` dispatch, setup policy, and hosted workflow enrollment against the
accepted gate-integrity decision. The review exercised path refusal, command
order, advisory versus operational exits, real ty mutation confinement,
format/lint checks, configuration parsing, and test-lane reachability. No Git
or stash operation is present in the repair owner.

## Findings

### ci-detector-enrolment | high | Repair safety proofs do not gate a hosted lane

The contract and real ty detector tests live under `dev/quality/tests`, but the
per-push workflows do not select that development-tooling path. The dispatch-only
full workflow reaches it only through `test-tooling`, whose step is explicitly
`continue-on-error`. A regression in path confinement, ty mutation behavior, or
operational exit classification can therefore leave every hosted verdict green,
contrary to the decision that ty repair is enrolled only after its isolated
safety proofs pass.

Resolution: the per-push unit and integration recipes already select these
tree-wide tests, and `test-ci-contracts` now names both repair-safety modules
explicitly as an additional blocking route. The full lane invokes that recipe
without `continue-on-error` before its later informational tooling aggregate.

Re-review clarification: the durable blocking route is the explicit
`test-ci-contracts` selection; generic pathless product lanes do not own the
development-tooling tree. The focused hosted route was executed directly and
passed after its stale fixture reference was corrected below.

### benchmark-reachability | medium | The maintained p95 proof is selected by no recipe

The two-second test carries the `perf` marker under `dev/quality/tests`, while
`test-repository-contracts` excludes `perf` and the existing performance recipes
name only CI/deploy/release or packaging paths. The repository's own reachability
gate reports this exact benchmark as selected by no declared lane, so the
eligibility ceiling can regress without any supported command observing it.

Resolution: the `test-ci-contracts` performance pass now explicitly selects the
repair benchmark module. The declared-lane reachability audit no longer lists
this benchmark; its only remaining findings are two unrelated unmarked product
tests.

### strict-fix-exit | medium | The path repair drops the repository-wide strict drift contract

`dev/quality/fixes.py` no longer observes `VAULTSPEC_FIX_STRICT`, although the
canonical exit contract still requires every `fix-*` command to return the drift
status when strict execution had to modify content. An automation invoking the
new path repair under the documented strict environment can mutate a file and
still return success. The previous whole-tree fingerprint is unsuitable here,
but a digest limited to the validated explicit path set would preserve both
contracts.

Resolution: strict mode now fingerprints only the validated explicit path set,
returns the repository drift status when those files change, and refuses an I/O
failure. A detector proves a neighboring file is outside that fingerprint.

### public-path-batching | low | The Just facade narrows the validated path set to one file

The Python owner validates and repairs one or more paths as a single set, but
the public `fix-code PATH` recipe accepts exactly one. Repairing several owned
files therefore repeats all three tool startups and does not expose the approved
same-set sequencing through the root command surface. This is safe, but it
weakens the bounded multi-file workflow and its performance intent.

Resolution: accepted as a low-severity command-surface trade-off. The owner
supports one or more paths, while the Just facade accepts one quoted path so a
path containing spaces retains its boundary across every supported shell. The
measured single-file p95 remains well below budget.

### ci-mutation-guard | low | The workflow guard recognizes only the Just alias

The new CI contract rejects the text `fix-code` but not the underlying
`python -m dev.quality.fixes` entry point. A workflow can invoke the mutating
owner directly while the test named as the no-mutation proof remains green.

Resolution: the workflow guard now rejects both `fix-code` and the underlying
`dev.quality.fixes` module invocation in each hosted CI lane.

### manual-replay-enrolment | high | Dispatch-only CI still runs the manual-only `prek` replay

`ci-full.yml` invokes `just check-hooks`, which executes `prek run --all-files`.
That contradicts the accepted manual-only replay boundary and the S37 wording
that replay stays manual-only. The workflow contract test still requires this
hosted invocation, so the stale policy is protected rather than reconciled.
Although the current replay is verify-only and does not invoke the new mutator,
it remains an automatic hosted `prek` execution and may provision remote hook
environments.

Resolution: the hook replay step and its remote-environment cache were removed
from full CI. Workflow comments and contract tests now assert that every hosted
lane omits `check-hooks`; the recipe remains available only for explicit
operator replay.

### ci-contract-execution | medium | The blocking recipe remains red on a stale test path

Re-running the exact non-performance selection now owned by `test-ci-contracts`
executes the new repair proofs, but the same invocation fails because
`test_ci_workflow.py` resolves the workbook-parity marker fixture at the removed
`dev/registry/tests` location. The live module is under
`dev/registry/parity/tests`. This is pre-existing relative to S37, but it means
the newly authoritative blocking recipe is not currently a green verification
surface.

Resolution: the fixture constant now names the live parity module. The exact
normal `test-ci-contracts` selection completed with 50 passed and one expected
performance deselection.

## Recommendations

- Resolved: remove `just check-hooks` from hosted workflow dispatch and update the stale
  workflow contract to assert that manual replay remains operator-invoked.
- Resolved: add a blocking hosted route for the focused repair contract and real ty
  detector tests; keep the mutating action itself out of CI.
- Resolved: enroll the warm p95 test in the CI-contract performance pass and
  make lane reachability green for this test.
- Resolved: restore strict drift detection over only the validated caller-owned paths.
- Accepted low: keep one safely quoted Just path per invocation; the owner
  retains direct multi-path support.
- Resolved: make the CI no-mutation guard reject both the recipe and the underlying module
  entry point.
- Resolved: update the stale workbook-parity fixture path and rerun the exact
  `test-ci-contracts` normal selection before closing S37.
