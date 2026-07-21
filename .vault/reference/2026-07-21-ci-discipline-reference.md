---
tags:
  - '#reference'
  - '#ci-discipline'
date: '2026-07-21'
modified: '2026-07-21'
related:
  - "[[2026-07-21-ci-discipline-adr]]"
  - '[[2026-07-20-ci-speed-redesign-adr]]'
  - '[[2026-07-20-release-asset-transport-adr]]'
---

# `ci-discipline` reference: `CI surface grounding for the tiered push/PR discipline`

This reference records the evidence base the ci-discipline ADR decided against:
the state of the `.github` control plane before the campaign, the two operator
rulings of 2026-07-21, and the commits that landed the decision. Every claim
below was read directly from the workflows, the conformance tests, or the named
commits; nothing is reconstructed from memory.

## Summary

### Operator rulings (2026-07-21)

Two verbatim-intent directives drove the campaign:

1. **Tiered push/PR discipline.** Differentiate when a merge lands versus when a
   PR is opened; different disciplines for code changes, new features, and
   releases — a full release requires every gate clean, chores need lighter
   discipline. Additionally: verify the cohesive architecture of the `.github`
   folder (overview, setup, event triggers, naming coherence, stale files) and
   fix what is found.
2. **Manual cadence, no standing compute.** The project is not developed
   continuously, so no workflow may carry a `schedule` trigger; every lane is
   push-, PR-, or dispatch-triggered. This supersedes the nightly-schedule
   element of the ci-speed-redesign decision (that record carries a truth-update
   line).

A standing prior mandate frames both: self-hosted fleet only (GitHub-hosted
runner images are a spend regression), enforced by
`dev/packaging/tests/test_self_hosted_fleet.py`.

### Prior decision substrate

The campaign built on two accepted records rather than a green field:

- The ci-speed-redesign decision (2026-07-20) had already split the per-push
  lane into parallel static+unit jobs, added the per-OS quick install probe
  (`packaging-quick.yml`), made the packaging campaign dispatch-only
  (`packaging-smoke.yml`), and parked slow surfaces in a nightly lane
  (`ci-nightly.yml`). It left the change-class boundaries implicit and accepted
  a blind spot: flavor-lane regressions surface only at the next dispatched
  campaign.
- The release-asset-transport decision fixed evidence honesty: only
  `packaging-smoke.yml` mints promotable `DistributionEvidence`, and Gate 2 of
  `publish-release.yml` pins that workflow path, accepting `workflow_dispatch`
  runs with main-ancestry verification. This existing trust rule is what makes
  an auto-dispatched campaign promotable with no new trust path.

### Pre-campaign stale surfaces (what the `.github` audit found)

- `aeat-drift-detector.yml` (weekly cron) pointed at pytest files deleted by the
  tests-under-tests-folders refactor (`test_groi_oracle_live.py`,
  `test_groi_dependency_chain_live.py`) — every scheduled run since had been a
  collection error, a red cron nobody attributed. The live target is
  `src/cadrumo/adapters/outbound/aeat/sede/tests/test_groi_check_live.py`.
- `durable-maintenance-gates.yml` (weekly) duplicated function already absorbed
  by the per-push unit lane and the nightly lane, but carried an S336
  do-not-remove-without-replacement banner on its ledger+storage roundtrip
  gate.
- `code-health-report.yml` (monthly) uploaded an Actions artifact, against the
  zero-artifact posture, and round-tripped the uv cache through the cloud on a
  self-hosted runner.
- Development is direct-push-to-main by coordinated agents; the branch
  protection API returns 403 on the current plan, and the repo's PR history is
  ~5 PRs (last real one 2026-07-15). PR semantics are future-proofing.
- `vault check all` carried a 285-error standing backlog at decision time, so a
  blocking vault-drift gate would have made every full-lane run red.

### Landed commits

- `6914725a22` — repaired the drift detector (live pytest target, no junit
  artifact, no cloud cache, no-cancel concurrency), retired
  `durable-maintenance-gates.yml` with both gates re-landed in the nightly lane
  in the same commit (roundtrip suite blocking, vault-drift informational),
  stripped the code-health artifact upload.
- `2e9ac933d1` — retired every `schedule` trigger: `ci-nightly.yml` renamed to
  the dispatch-only `ci-full.yml`, drift detector and code-health report made
  dispatch-only, speed-redesign ADR stamped with the truth-update line.
- `ecb1dbbbb9` — the T0–T3 tier topology: shared `paths-ignore` carve-out (T0),
  static+unit plus quick probe per push (T1), new
  `packaging-campaign-trigger.yml` whose `paths` filter auto-dispatches the full
  campaign on release-artifact-shaping changes (T2), release dispatch untouched
  (T3); same-repo-guarded `pull_request` triggers on `ci.yml` and
  `packaging-quick.yml`; `.github/README.md` documenting the control plane; and
  the `dev/packaging/tests/test_change_class_tiers.py` conformance gates.
- Merged to main via `9235e8cabc`.

### Post-campaign surface

Fourteen workflows: `aeat-drift-detector.yml`, `agent-harness-eval.yml`,
`ci-full.yml`, `ci.yml`, `code-health-report.yml`, `evidence-gc.yml`,
`packaging-campaign-trigger.yml`, `packaging-claude.yml`,
`packaging-homebrew.yml`, `packaging-quick.yml`, `packaging-scoop.yml`,
`packaging-smoke.yml`, `publish-release.yml`, `pypi-upload.yml`. Zero
`schedule` triggers repo-wide, pinned by conformance test. `.github/README.md`
is the hand-written control-plane overview: standing invariants (self-hosted
only, zero Actions artifacts, no fork code on the fleet, evidence honesty,
machine-aware load), fleet topology, tier table, and the branch-protection
proposal held for operator application.

### Conformance pins

`dev/packaging/tests/test_change_class_tiers.py` (T2 paths set, trigger-workflow
shape and confined `actions: write`, T0 carve-out, fork guard on every
`pull_request` job, repo-wide artifact ban, repo-wide no-schedule invariant,
naming convention, relocated maintenance gates, drift-detector target
existence), `test_packaging_quick_workflow.py` (trigger pin extended for
`pull_request`), `test_ci_workflow.py` (full-lane pins swept to `ci-full.yml`
and dispatch-only triggers), `test_self_hosted_fleet.py` (runner labels).
