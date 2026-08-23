---
tags:
  - '#adr'
  - '#ci-discipline'
date: '2026-07-21'
modified: '2026-08-23'
body_hash: 'sha256:beb0a0253c91d4be088352f948e4e2ca5c189d4733c339db27c2b71b64343416'
related:
  - '[[2026-07-21-ci-discipline-reference]]'
  - '[[2026-07-20-ci-speed-redesign-adr]]'
  - '[[2026-07-20-release-asset-transport-adr]]'
  - '[[2026-07-04-release-readiness-gate-adr]]'
  - '[[2026-07-19-post-release-distribution-adr]]'
  - '[[2026-08-10-ci-lane-deconflation-integration-lane-live-service-dependency-adr]]'
---
# `ci-discipline` adr: `tiered push/PR discipline by change class` | (**status:** `accepted`)

## Problem Statement

Operator directive, 2026-07-21 (verbatim intent): improve branch push/pull discipline â€” differentiate when a merge lands vs a PR is opened; different disciplines for code changes vs new features vs releases; a full release requires every gate clean while chores need lighter discipline. Additionally: verify the cohesive architecture of the `.github` folder (overview, setup, event triggers, naming coherence, stale files) and fix what is found. The `2026-07-20-ci-speed-redesign-adr` already built the speed substrate (quick per-push probe, dispatch-only campaign, static+unit split, nightly lane) but left the change-class boundaries implicit, left no auto-path from a release-artifact-shaping push to fresh campaign evidence, and left three pre-redesign workflows unaudited â€” one of them (the weekly AEAT drift detector) pointing at pytest files that no longer exist after the tests-under-tests-folders refactor, a red cron nobody attributes.

## Considerations

- Development is direct-push-to-main by coordinated agents; branch protection is structurally unavailable on the current plan (the protection API returns 403) and PRs are rare (5 in the repo's `gh pr list` history, last real one 2026-07-15). Any PR semantics shipped now are future-proofing, not the primary surface.
- Self-hosted fleet only (operator cost mandate, enforced by `dev/packaging/tests/test_self_hosted_fleet.py`); fork-PR head code must never execute on the fleet (GitHub self-hosted hardening guidance).
- Evidence honesty (`2026-07-20-release-asset-transport-adr`): only `packaging-smoke.yml` mints promotable evidence; Gate 2 of `publish-release.yml` pins that workflow path and accepts `workflow_dispatch` runs with main-ancestry verification â€” so an auto-dispatched campaign is promotable through the existing trust rule, no new trust path.
- The speed-redesign ADR accepted the blind spot that flavor-lane regressions surface only at the next dispatched campaign; release-artifact-surface pushes are rare enough that closing the blind spot per-matching-push is nearly free.
- The `.vault` audit (`vault check all`) is red at HEAD (285 standing errors), so the full lane's vault-drift step must be informational until the backlog clears, or every full-lane run is red and masks real regressions.
- Operator ruling 2026-07-21 (manual cadence, no standing compute): the project is not developed continuously, so NO workflow may carry a `schedule` trigger â€” every lane is push-, PR-, or dispatch-triggered. This supersedes the nightly-schedule element of the `2026-07-20-ci-speed-redesign-adr` (that record carries a truth-update line pointing here).

## Considered options

1. Classify by conventional-commit type of the head commit: rejected as the gate input â€” honor-system (a mistyped prefix silently downgrades discipline) and unavailable to path-filtered triggers; kept as human documentation only.
2. Classify by changed paths (structural, fail-closed â€” anything not matching a lighter tier's carve-out gets the heavier tier): accepted; path filters are evaluated by GitHub before any job starts, cannot be forgotten, and default to the heavier tier.
3. A classifier job that computes a tier and gates downstream jobs on its output: rejected â€” adds a serial job to every push, and its failure modes (API flake, diff-range edge cases on force-pushes) are worse than static path filters.
4. Auto-dispatch of the full campaign as a job inside `packaging-quick.yml`: rejected â€” breaks the quick workflow's pinned three-probe read-only shape; a separate tiny workflow keeps permissions (`actions: write`) confined and the tier boundary independently pinnable.
5. Keep the retired-candidate workflows as disabled corpses: rejected per the no-legacy rule â€” `durable-maintenance-gates.yml` is deleted with its two gates re-landed in the nightly lane in the same commit (the roundtrip gate's do-not-remove-without-replacement banner is honored verbatim); the drift detector and code-health report are repaired, not retired, because their proofs (live AEAT selector parity; the monthly health dashboard) still have a consumer.

## Constraints

- `publish-release.yml`'s 12-row readiness contract, Gates 1â€“3, and the operator preflight are untouched; T3 binds to them and never weakens them.
- Load-bearing workflow filenames (`packaging-smoke.yml`, `publish-release.yml`, `ci.yml`, `ci-nightly.yml`, `packaging-quick.yml`) are pinned by Gate 2 and the conformance tests; the naming convention governs new files, and none of the pinned names are renamed.
- The self-hosted fleet gate and the transport conformance gates must stay green; the new trigger workflow runs on `[self-hosted, Linux, X64]` and mints no evidence.
- Branch protection cannot be applied by an agent (and currently not at all); the required-checks design is recorded as a proposal the operator applies when the plan allows.

## Implementation

**D1 â€” Change-class tier taxonomy, structurally detected.** T0 (vault/agent-config/markdown churn): the shared `paths-ignore` carve-out on `ci.yml` and `packaging-quick.yml`; runs nothing per-push, with the dispatch-only full lane as the backstop. T1 (ordinary code change): every push to main outside the carve-out; runs static+unit plus the per-OS quick install probe under the ten-minute wall. T2 (release-artifact-shaping change): a new `packaging-campaign-trigger.yml` whose `paths` filter (`pyproject.toml`, `uv.lock`, `packaging/**`, `dev/packaging/**`, `packaging-smoke.yml` itself) IS the detector â€” one five-minute job dispatches the full campaign via `gh workflow run packaging-smoke.yml --ref main`, producing promotable evidence under Gate 2's existing dispatch rule and closing the speed-redesign's flavor-lane blind spot. T3 (release): unchanged â€” operator dispatch of `publish-release.yml` with every gate (campaign evidence, acquisition rows, 12-row readiness, preflight, protected environment) clean. Classification is fail-closed: unmatched paths are T1 by construction, and T2 adds to (never replaces) T1's gates.

**D2 â€” Push vs PR semantics.** Push-to-main stays the primary surface (T1 always, T2 on paths-match, superseding concurrency). `pull_request` triggers are added to `ci.yml` and `packaging-quick.yml` â€” same T0 carve-out, same T1 gates â€” with a same-repo guard (`github.event.pull_request.head.repo.full_name == github.repository`) on every job so fork-PR code never reaches the fleet; a future PR flow therefore inherits the correct discipline with zero further changes. No tag/release event triggers exist anywhere: publication remains an explicit typed dispatch. Merge-time-only gates (`agent-harness-eval.yml`) stay push-scoped by design.

**D3 â€” `.github` hygiene.** `durable-maintenance-gates.yml` retired; its vault-drift gate lands in the full lane as informational (red vault backlog, flip to blocking when green at HEAD) and its ledger+storage roundtrip gate lands as blocking, same commit. `aeat-drift-detector.yml` repaired: dead pytest targets re-pointed at `src/cadrumo/adapters/outbound/aeat/sede/tests/test_groi_check_live.py`, junit artifact upload removed, no-cancel concurrency added, name aligned. `code-health-report.yml`: artifact upload removed (JSON to the log), concurrency added, name aligned. Naming convention adopted: kebab-case filenames with family prefixes for new files; the `name:` field always contains "Cadrumo". A hand-written `.github/README.md` records the tier table, trigger semantics, inventory, convention, and the branch-protection proposal.

**D4 â€” Trigger/permission coherence, zero schedules.** Cloud cache round-trips (`enable-cache: true`) removed from the repaired workflows per the speed-redesign's D5. The zero-Actions-artifact posture is promoted from per-family gates to repo-wide. Per the 2026-07-21 no-standing-compute ruling every `schedule` trigger is retired: `ci-nightly.yml` becomes the dispatch-only `ci-full.yml` (renamed for honesty â€” nothing is nightly anymore), the AEAT drift detector and the code-health report become dispatch-only, and the operator or coordinator dispatches the full lane before a release, before promoting evidence, or after a long idle stretch. A repo-wide conformance gate pins that no workflow carries a `schedule` trigger, so standing compute cannot creep back.

**D5 â€” Conformance pins.** New `dev/packaging/tests/test_change_class_tiers.py` pins: the T2 paths set, the trigger workflow's single-job dispatch-only shape and confined `actions: write`, the shared T0 carve-out, the fork guard on every `pull_request` job, the repo-wide artifact ban, the repo-wide no-schedule invariant, the naming convention, the full-lane relocation of both retired gates, and the on-disk existence of every drift-detector pytest target (the l1-anchor-drift failure class, now structurally impossible to reintroduce silently). `test_packaging_quick_workflow.py`'s trigger pin extended for `pull_request`; `test_ci_workflow.py`'s full-lane pins updated for the rename and dispatch-only triggers.

**Branch-protection proposal (operator applies; not automatable today).** When the plan allows: required checks `Cadrumo / static checks / Python 3.13` and `Cadrumo / unit suite / Python 3.13` on `main` (strict up-to-date off â€” the direct-push fleet would deadlock); quick probes informational; force-push and deletion blocked; no required human reviews (the agent fleet's coordinator/review discipline substitutes).

## Rationale

Path-filter classification wins because it is the only detector GitHub evaluates before any compute is spent, cannot be bypassed by a mislabeled commit, and fails closed. Binding T2 to an auto-dispatch of the existing campaign â€” rather than a new intermediate workflow â€” reuses the sole evidence mint and its entire verification chain, so the tier system adds discipline without adding a single new trust surface. Retire-versus-repair verdicts follow consumer existence: gates with live consumers were repaired or relocated with their protections intact; the one workflow whose function was already absorbed (weekly maintenance beats, superseded by the per-push unit lane and the nightly lane) was deleted per the no-legacy rule with its replacement in the same commit.

## Consequences

- A packaging-surface push now costs one extra queued full campaign (~20 min on idle fleet, no wall-clock coupling to the push) and in exchange release evidence is always at most one artifact-shaping change old; the readiness gate's "recent smoke evidence" row gets structurally fresher.
- Fork PRs get skipped (neutral) jobs rather than red or absent checks; a future required-checks setup must account for skipped-as-neutral on fork PRs (they would need a hosted or gated runner path, out of scope under the cost mandate).
- The weekly maintenance workflow's identity disappears from the Actions list; its gates now report inside the full lane's run.
- The vault-drift gate is visible-but-informational until the 285-error backlog clears; flipping it to blocking is a one-line change recorded in the full-lane step comment.
- With zero schedules, nothing runs unless someone pushes or dispatches: a regression in the slow surfaces (docs build, CVE audit, hook replay, live AEAT parity) is caught only at the next manual full-lane or drift-detector dispatch. That is the deliberate trade of the no-standing-compute ruling; the release path is unaffected because T3's readiness rows demand fresh evidence regardless of when it was minted.
- The drift detector runs green-or-honestly-red again; its target-existence pin turns the silent-rot class into a per-push test failure.

## D6 â€” Amendment 2026-08-05: two more T1 tiers, the "shared" carve-out was never true, and a coverage hole this ADR did not know it had

Landed as commits `2309887d93`, `c9b0529c6a`, `73992708d5`. Recorded here rather than as a
new ADR because it extends the D1 taxonomy this record owns â€” it adds tiers, corrects a
claim, and closes gaps the taxonomy's own detection mechanism should have caught â€” without
reversing any ruling. Nothing in D1â€“D5 is superseded; T0/T1/T2/T3 stand, and D5's
conformance-pin discipline is exactly what this amendment extends.

### D6.1 â€” D1's "shared" claim was false in the tree, and the gate meant to enforce it could not

D1 describes the T0 `paths-ignore` carve-out as "shared" by `ci.yml` and
`packaging-quick.yml`. That was aspirational, not measured: the carve-out was keyed on file
**suffix** (`**.md`) rather than on **role**, so `docs/**.rst` â€” 1384 files, the bulk of the
documentation surface â€” fell through the carve-out entirely and started the full Python
static+unit suite on every documentation push, while producing no documentation verdict
(`docs-check` only ran in the dispatch-only full lane). `frontend/`, a Vite/TypeScript
subproject with its own lockfile, had no carve-out and no lane at all, so a dependency bump
there ran both Python lanes and the three-OS packaging probe and failed both (measured: PR
run `30895086190`).

The gate that exists specifically to pin D1's shared-carve-out claim
(`test_change_class_tiers.py`) could not have caught either gap: it asserted
`paths-ignore >= carve_out` **per lane independently**, a predicate two disagreeing lanes
both satisfy, and it read only the `push` trigger, never `pull_request`. The claim and its
enforcement were both wrong in the direction that hides the defect. It is now an equality
check across both triggers, plus a companion (`test_every_code_lane_carve_out_path_has_a_lane_of_its_own`)
refusing a carved-out path with neither a lane nor a stated reason â€” closing the same class
of gap D1 asserted was already closed.

### D6.2 â€” Two more T1 tiers: T1-docs and T1-frontend

The fix for D6.1 is not a bigger carve-out â€” a carved-out surface with no lane of its own has
no verdict, which is the other half of the docs defect. Two new tiers join D1's table, each a
dedicated per-push lane triggered by the surface it verifies, carved out of the Python lanes
in exchange:

- **T1-docs** â€” `docs.yml`, triggered by `docs/**`, `dev/docs/**`,
  `src/cadrumo/_data/terminology/**`. Runs the nitpicky Sphinx build, stub correspondence,
  CLI-reference drift, doc8, interrogate â€” the same `docs-check` recipe `ci-full.yml` already
  ran, so the two lanes cannot drift apart.
- **T1-frontend** â€” `frontend.yml`, triggered by `frontend/**`. Runs `npm ci`, typecheck +
  build, vitest â€” the first lane of any kind for that subproject.

Both are carved out of `ci.yml` and `packaging-quick.yml`, and the carve-out set is now
pinned byte-identical across both Python lanes and both trigger types
(`test_code_lane_carve_out_is_identical_across_every_python_lane_and_trigger`).

### D6.3 â€” Interaction with `ci-speed-redesign` D4: complements, does not reverse

`2026-07-20-ci-speed-redesign-adr` D4 moved the docs build off the per-push path onto the
dispatch-only full lane, on the ten-minute-wall budget. T1-docs does not put it back: D4's
ruling is about not running the (expensive, multi-minute) docs build **on every code push**,
and T1-docs never fires on a code push â€” it fires only when the documentation surface itself
changes, which is disjoint from the code paths D4's budget was protecting. A documentation
edit previously got neither a cheap nor a correct verdict (it ran the code lane's twelve
minutes and produced no documentation signal); it now gets a lane sized to the surface it
verifies. D4's per-push wall for code changes is untouched â€” T1-docs adds no job to a `src/`
push, because `docs/**` is carved out of `ci.yml` exactly as `.vault/**` already was under T0.
The two records are read together as intended: D4 governs when the docs build runs relative
to *code* changes, D6.2 governs when it runs relative to *documentation* changes.

### D6.4 â€” Two new invariants, pinned repo-wide

- **Frozen installs only.** `ci.yml` and `ci-full.yml` were the last two workflows running a
  bare `uv sync`; every other of the eleven other sites was already `--frozen`. Measured cost
  of the bare resolve: 2m03s of a 2m25s static job and 1m56s of the unit job on run
  `30977318339`, paid independently by two co-resident jobs against one warm cache â€” and an
  unfrozen resolve can pick up an index change nobody pushed, so a red was not necessarily a
  property of the commit under test. Now `.github/ci-control-plane.md` invariant 7, pinned by
  `test_no_workflow_installs_python_dependencies_unfrozen`.
- **Declared is not run.** The prior reachability model counted a justfile recipe as covered
  the moment a workflow named it, with no check that the naming workflow ever actually
  invoked it. `.github/ci-control-plane.md` invariant 8 now distinguishes `declared_lanes`
  (every recipe on disk) from `ci_invoked_lanes` (recipes actually reached by a parsed
  workflow `run:` block, transitively), and `test_every_test_ci_cannot_run_declares_why`
  requires every test CI cannot run to carry a marker naming the precondition a headless
  runner lacks (`external_tool`, `aeat_live`, `os_keychain`, `resident_service`) â€” "nobody
  wired a lane" is no longer an accepted answer. Building the invoked-recipe scanner surfaced
  a latent bug in the same family the module already warned about for `-m` selection: it was
  harvesting `is`, `uses`, and `natively` as recipe names out of step titles and YAML
  comments; recipe discovery now reads parsed `run:` blocks only.

### D6.5 â€” What "declared is not run" found: a coverage hole this ADR did not know it had

Applying D6.4's distinction against the tree at the time found two lanes counted as covered
by the prior (declaration-based) model that no workflow had ever invoked:

- The `src/cadrumo` **integration** suite (`-m integration`) â€” every existing lane selected
  `-m unit` only; the only integration selections anywhere were path-scoped to `dev/`. ~370
  integration-marked modules under `src/cadrumo` had never once run in CI.
- `just test-dev-tooling` â€” nine `dev/` subsystem gates whose own docstring already read "the
  gates that no other lane reaches," which was equally true of CI as of any human reader who
  took that line as reassurance rather than as a literal, unactioned gap.

Both held **zero regression signal** behind a green coverage gate for as long as the prior
model counted the recipe's existence as coverage. This is the same silent-hole shape D1's
carve-out gate had (D6.1) â€” a mechanism whose predicate is satisfiable without the property
it claims to guarantee â€” recurring in a different corner of the same control plane. Both are
now enrolled in `ci-full.yml`.

### D6.6 â€” Newly-enrolled lanes are non-blocking, and this is explicitly open, not resolved

Enrolling a suite that has never run in CI surfaces its accumulated backlog on the first real
run, not a regression introduced by this change. Measured: the integration parallel pass â€”
`19 failed, 3753 passed` in 23m54s; the 58 serial-marked tests the parallel pass holds out
were not measured at all. Landing both newly-enrolled steps blocking on this same commit
would have meant either stopping releases on an untriaged backlog nobody had looked at, or
(the likelier outcome) training the fleet to read a permanently red release-verdict lane as
normal, which costs more than the signal recovers.

Both steps therefore carry `continue-on-error: true` in `ci-full.yml`, with the same
visibility-now-blocking-once-triaged contract the pre-existing vault-drift step in that file
already uses, and an explicit code comment against flipping it off before triage completes.
`ci-full.yml`'s job ceiling moved 120 â†’ 180 minutes for the same reason it existed at 120: the
lane already carried the unit suite, the dev-tree gates, real sdist/wheel builds, the docs
build, `pip-audit`, and the ledger/storage roundtrip suite, and the newly-enrolled ~24 minutes
of integration work left no headroom.

**This amendment records the gap and its interim posture; it does not close the gap.** The
58 unmeasured serial tests and the 19 measured failures are an open triage item tracked
outside this ADR, not a ruling of this record. `continue-on-error` on the two steps above
MUST flip to blocking once triage completes â€” that is a commitment this amendment makes, not
a decision it defers indefinitely.

**Amendment pending, recorded 2026-08-11 â€” the flip commitment above is contested by a proposed record and MUST NOT be read as still standing unqualified.** The triage condition it names has been met: the backlog closed on 2026-08-06, resolving to one genuine defect fixed in `963dd72f08`. The conclusion has not followed, because closing the backlog surfaced an obstacle D6.6 did not know about and could not have: the integration parallel lane transitively reaches a live external endpoint through a multi-currency fixture, established by `2026-08-06-ci-lane-deconflation-integration-lane-external-dependency-audit`. `2026-08-10-ci-lane-deconflation-integration-lane-live-service-dependency-adr` (status `proposed`) is where that question now lives and is the record that would override this commitment for the integration parallel step.

**Nothing here is amended yet, deliberately.** That record is proposed, not accepted, and its own constraints hold that the permanence question requires an operator and that the remaining measurement is blocked on an offline self-hosted Linux runner. Until it is accepted this commitment stands as written. When it is accepted, this section is amended in the same action â€” an acceptance that leaves this paragraph unchanged produces two accepted records ruling opposite ways on one flag.

**Scope, stated because the successor is narrower than this commitment.** The proposed record examines the `src/cadrumo` integration parallel step only. This commitment covers that step *and* `just test-dev-tooling`, and no record has yet examined the second. The dev-tooling half of this commitment is untouched and still binding.
## 2026-08-23 repository-boundary amendment

Decision D6.2's website-project tier is superseded by
`2026-08-23-website-repository-boundary-adr`. The website source and its dedicated CI
lane have moved to the separate `cadrumo-marketing` repository. This product repository
retains no website lane and must keep inverse guards that refuse the old source root and
workflow from returning.

The documentation tier and all other CI taxonomy, trigger, and conformance decisions in
this record remain accepted.
