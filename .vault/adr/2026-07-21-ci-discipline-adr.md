---
tags:
  - '#adr'
  - '#ci-discipline'
date: '2026-07-21'
modified: '2026-07-21'
related:
  - '[[2026-07-20-ci-speed-redesign-adr]]'
  - '[[2026-07-20-release-asset-transport-adr]]'
  - '[[2026-07-04-release-readiness-gate-adr]]'
  - '[[2026-07-19-post-release-distribution-adr]]'
---

# `ci-discipline` adr: `tiered push/PR discipline by change class` | (**status:** `accepted`)

## Problem Statement

Operator directive, 2026-07-21 (verbatim intent): improve branch push/pull discipline — differentiate when a merge lands vs a PR is opened; different disciplines for code changes vs new features vs releases; a full release requires every gate clean while chores need lighter discipline. Additionally: verify the cohesive architecture of the `.github` folder (overview, setup, event triggers, naming coherence, stale files) and fix what is found. The `2026-07-20-ci-speed-redesign-adr` already built the speed substrate (quick per-push probe, dispatch-only campaign, static+unit split, nightly lane) but left the change-class boundaries implicit, left no auto-path from a release-artifact-shaping push to fresh campaign evidence, and left three pre-redesign workflows unaudited — one of them (the weekly AEAT drift detector) pointing at pytest files that no longer exist after the tests-under-tests-folders refactor, a red cron nobody attributes.

## Considerations

- Development is direct-push-to-main by coordinated agents; branch protection is structurally unavailable on the current plan (the protection API returns 403) and PRs are rare (5 in the repo's `gh pr list` history, last real one 2026-07-15). Any PR semantics shipped now are future-proofing, not the primary surface.
- Self-hosted fleet only (operator cost mandate, enforced by `dev/packaging/tests/test_self_hosted_fleet.py`); fork-PR head code must never execute on the fleet (GitHub self-hosted hardening guidance).
- Evidence honesty (`2026-07-20-release-asset-transport-adr`): only `packaging-smoke.yml` mints promotable evidence; Gate 2 of `publish-release.yml` pins that workflow path and accepts `workflow_dispatch` runs with main-ancestry verification — so an auto-dispatched campaign is promotable through the existing trust rule, no new trust path.
- The speed-redesign ADR accepted the blind spot that flavor-lane regressions surface only at the next dispatched campaign; release-artifact-surface pushes are rare enough that closing the blind spot per-matching-push is nearly free.
- The `.vault` audit (`vault check all`) is red at HEAD (285 standing errors), so the full lane's vault-drift step must be informational until the backlog clears, or every full-lane run is red and masks real regressions.
- Operator ruling 2026-07-21 (manual cadence, no standing compute): the project is not developed continuously, so NO workflow may carry a `schedule` trigger — every lane is push-, PR-, or dispatch-triggered. This supersedes the nightly-schedule element of the `2026-07-20-ci-speed-redesign-adr` (that record carries a truth-update line pointing here).

## Considered options

1. Classify by conventional-commit type of the head commit: rejected as the gate input — honor-system (a mistyped prefix silently downgrades discipline) and unavailable to path-filtered triggers; kept as human documentation only.
2. Classify by changed paths (structural, fail-closed — anything not matching a lighter tier's carve-out gets the heavier tier): accepted; path filters are evaluated by GitHub before any job starts, cannot be forgotten, and default to the heavier tier.
3. A classifier job that computes a tier and gates downstream jobs on its output: rejected — adds a serial job to every push, and its failure modes (API flake, diff-range edge cases on force-pushes) are worse than static path filters.
4. Auto-dispatch of the full campaign as a job inside `packaging-quick.yml`: rejected — breaks the quick workflow's pinned three-probe read-only shape; a separate tiny workflow keeps permissions (`actions: write`) confined and the tier boundary independently pinnable.
5. Keep the retired-candidate workflows as disabled corpses: rejected per the no-legacy rule — `durable-maintenance-gates.yml` is deleted with its two gates re-landed in the nightly lane in the same commit (the roundtrip gate's do-not-remove-without-replacement banner is honored verbatim); the drift detector and code-health report are repaired, not retired, because their proofs (live AEAT selector parity; the monthly health dashboard) still have a consumer.

## Constraints

- `publish-release.yml`'s 12-row readiness contract, Gates 1–3, and the operator preflight are untouched; T3 binds to them and never weakens them.
- Load-bearing workflow filenames (`packaging-smoke.yml`, `publish-release.yml`, `ci.yml`, `ci-nightly.yml`, `packaging-quick.yml`) are pinned by Gate 2 and the conformance tests; the naming convention governs new files, and none of the pinned names are renamed.
- The self-hosted fleet gate and the transport conformance gates must stay green; the new trigger workflow runs on `[self-hosted, Linux, X64]` and mints no evidence.
- Branch protection cannot be applied by an agent (and currently not at all); the required-checks design is recorded as a proposal the operator applies when the plan allows.

## Implementation

**D1 — Change-class tier taxonomy, structurally detected.** T0 (vault/agent-config/markdown churn): the shared `paths-ignore` carve-out on `ci.yml` and `packaging-quick.yml`; runs nothing per-push, with the dispatch-only full lane as the backstop. T1 (ordinary code change): every push to main outside the carve-out; runs static+unit plus the per-OS quick install probe under the ten-minute wall. T2 (release-artifact-shaping change): a new `packaging-campaign-trigger.yml` whose `paths` filter (`pyproject.toml`, `uv.lock`, `packaging/**`, `dev/packaging/**`, `packaging-smoke.yml` itself) IS the detector — one five-minute job dispatches the full campaign via `gh workflow run packaging-smoke.yml --ref main`, producing promotable evidence under Gate 2's existing dispatch rule and closing the speed-redesign's flavor-lane blind spot. T3 (release): unchanged — operator dispatch of `publish-release.yml` with every gate (campaign evidence, acquisition rows, 12-row readiness, preflight, protected environment) clean. Classification is fail-closed: unmatched paths are T1 by construction, and T2 adds to (never replaces) T1's gates.

**D2 — Push vs PR semantics.** Push-to-main stays the primary surface (T1 always, T2 on paths-match, superseding concurrency). `pull_request` triggers are added to `ci.yml` and `packaging-quick.yml` — same T0 carve-out, same T1 gates — with a same-repo guard (`github.event.pull_request.head.repo.full_name == github.repository`) on every job so fork-PR code never reaches the fleet; a future PR flow therefore inherits the correct discipline with zero further changes. No tag/release event triggers exist anywhere: publication remains an explicit typed dispatch. Merge-time-only gates (`agent-harness-eval.yml`) stay push-scoped by design.

**D3 — `.github` hygiene.** `durable-maintenance-gates.yml` retired; its vault-drift gate lands in the full lane as informational (red vault backlog, flip to blocking when green at HEAD) and its ledger+storage roundtrip gate lands as blocking, same commit. `aeat-drift-detector.yml` repaired: dead pytest targets re-pointed at `src/cadrumo/adapters/outbound/aeat/sede/tests/test_groi_check_live.py`, junit artifact upload removed, no-cancel concurrency added, name aligned. `code-health-report.yml`: artifact upload removed (JSON to the log), concurrency added, name aligned. Naming convention adopted: kebab-case filenames with family prefixes for new files; the `name:` field always contains "Cadrumo". A hand-written `.github/README.md` records the tier table, trigger semantics, inventory, convention, and the branch-protection proposal.

**D4 — Trigger/permission coherence, zero schedules.** Cloud cache round-trips (`enable-cache: true`) removed from the repaired workflows per the speed-redesign's D5. The zero-Actions-artifact posture is promoted from per-family gates to repo-wide. Per the 2026-07-21 no-standing-compute ruling every `schedule` trigger is retired: `ci-nightly.yml` becomes the dispatch-only `ci-full.yml` (renamed for honesty — nothing is nightly anymore), the AEAT drift detector and the code-health report become dispatch-only, and the operator or coordinator dispatches the full lane before a release, before promoting evidence, or after a long idle stretch. A repo-wide conformance gate pins that no workflow carries a `schedule` trigger, so standing compute cannot creep back.

**D5 — Conformance pins.** New `dev/packaging/tests/test_change_class_tiers.py` pins: the T2 paths set, the trigger workflow's single-job dispatch-only shape and confined `actions: write`, the shared T0 carve-out, the fork guard on every `pull_request` job, the repo-wide artifact ban, the repo-wide no-schedule invariant, the naming convention, the full-lane relocation of both retired gates, and the on-disk existence of every drift-detector pytest target (the l1-anchor-drift failure class, now structurally impossible to reintroduce silently). `test_packaging_quick_workflow.py`'s trigger pin extended for `pull_request`; `test_ci_workflow.py`'s full-lane pins updated for the rename and dispatch-only triggers.

**Branch-protection proposal (operator applies; not automatable today).** When the plan allows: required checks `Cadrumo / static checks / Python 3.13` and `Cadrumo / unit suite / Python 3.13` on `main` (strict up-to-date off — the direct-push fleet would deadlock); quick probes informational; force-push and deletion blocked; no required human reviews (the agent fleet's coordinator/review discipline substitutes).

## Rationale

Path-filter classification wins because it is the only detector GitHub evaluates before any compute is spent, cannot be bypassed by a mislabeled commit, and fails closed. Binding T2 to an auto-dispatch of the existing campaign — rather than a new intermediate workflow — reuses the sole evidence mint and its entire verification chain, so the tier system adds discipline without adding a single new trust surface. Retire-versus-repair verdicts follow consumer existence: gates with live consumers were repaired or relocated with their protections intact; the one workflow whose function was already absorbed (weekly maintenance beats, superseded by the per-push unit lane and the nightly lane) was deleted per the no-legacy rule with its replacement in the same commit.

## Consequences

- A packaging-surface push now costs one extra queued full campaign (~20 min on idle fleet, no wall-clock coupling to the push) and in exchange release evidence is always at most one artifact-shaping change old; the readiness gate's "recent smoke evidence" row gets structurally fresher.
- Fork PRs get skipped (neutral) jobs rather than red or absent checks; a future required-checks setup must account for skipped-as-neutral on fork PRs (they would need a hosted or gated runner path, out of scope under the cost mandate).
- The weekly maintenance workflow's identity disappears from the Actions list; its gates now report inside the full lane's run.
- The vault-drift gate is visible-but-informational until the 285-error backlog clears; flipping it to blocking is a one-line change recorded in the full-lane step comment.
- With zero schedules, nothing runs unless someone pushes or dispatches: a regression in the slow surfaces (docs build, CVE audit, hook replay, live AEAT parity) is caught only at the next manual full-lane or drift-detector dispatch. That is the deliberate trade of the no-standing-compute ruling; the release path is unaffected because T3's readiness rows demand fresh evidence regardless of when it was minted.
- The drift detector runs green-or-honestly-red again; its target-existence pin turns the silent-rot class into a per-push test failure.
