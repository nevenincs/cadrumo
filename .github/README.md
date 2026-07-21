# `.github` architecture

This folder is the repository's CI/CD control plane. Every workflow obeys four
standing invariants, each enforced by a conformance gate in the test tree:

1. **Self-hosted fleet only.** Every `runs-on` is a `[self-hosted, ...]` label
   set; GitHub-hosted images are a spend regression
   (`dev/packaging/tests/test_self_hosted_fleet.py`).
2. **Zero Actions-artifact storage.** No `upload-artifact` / `download-artifact`
   anywhere; outputs live in job logs, and release evidence rides draft
   releases per the release-asset-transport ADR
   (`dev/packaging/tests/test_change_class_tiers.py`, transport gates).
3. **No fork code on the fleet.** `pull_request` triggers exist only with a
   same-repo job guard; fork PRs skip every job.
4. **Evidence honesty.** Only `packaging-smoke.yml` mints promotable
   `DistributionEvidence`; `publish-release.yml` Gate 2 pins that workflow
   path, so no other lane can enter promotion.
5. **Machine-aware load.** No lane sizes itself as if it owns the machine
   (`dev/packaging/tests/test_machine_aware_load.py`); see the topology below.

## Fleet topology and load sizing

Six runners, but only **two physical machines** — a runner label is NOT a
machine, and up to three jobs can co-reside on one box:

| Machine | Cores | Runners on it |
| --- | --- | --- |
| gw-workstation (Ryzen 5900X, 12C/24T) | 24 logical | `gw-workstation-win` (Windows X64), `gw-workstation-wsl` + `gw-workstation-wsl-2` (Linux X64 containers) |
| MacBook (Apple silicon) | 6 | `macbook-neo` (macOS ARM64), `macbook-neo-intel` (macOS X64 via Rosetta), `gw-macbook-linux-arm` (Linux ARM64 via colima, VM capped at 4 CPUs) |

**Sizing rule:** the sum of co-resident workers must fit the machine's CPUs —
size every parallel knob for worst-case co-residency (3 jobs/machine), never
for the whole box. Concretely: workstation lanes get explicit `-n 8`
(24 / 3); MacBook lanes get `-n 2` (6 / 3); `pytest -n auto` is banned in any
CI invocation (it grabs every logical CPU); the packaging campaign's lane
pool and preflight pytest are sized per leg via
`CADRUMO_PACKAGING_LANE_CONCURRENCY` / `CADRUMO_TEST_WORKERS`; the Homebrew
matrix carries `max-parallel: 2` (three of its four legs live on the MacBook)
and per-leg `HOMEBREW_MAKE_JOBS`. Local development keeps `-n auto` — the
rule binds surfaces that can run CONCURRENTLY with other jobs on a shared
machine.

## Change-class tiers

Classification is **structural** (path filters and workflow topology, never
honor-system) and **fail-closed**: a push that does not match a lighter tier's
carve-out gets the heavier tier's gates. Detection is by changed paths; the
conventional-commit type on the head commit is documentation for humans, not a
gate input. Governing decision: the `ci-discipline` ADR (2026-07-21), layered
on the `ci-speed-redesign` ADR (2026-07-20).

| Tier | Change class | Detected by | What runs |
| --- | --- | --- | --- |
| T0 | vault / agent-config / markdown churn | `paths-ignore` carve-outs shared by `ci.yml` and `packaging-quick.yml` | Nothing per-push. The dispatch-only full lane (`ci-full.yml`) is the backstop for docs, vault drift, and the slow conformance surface. |
| T1 | ordinary code change | any push to `main` outside the T0 carve-out | `ci.yml` (static checks ∥ full unit suite) + `packaging-quick.yml` (one cohort build + one core install probe per OS, proof-cache memoized). Ten-minute wall. |
| T2 | release-artifact-shaping change | `packaging-campaign-trigger.yml` paths filter (`pyproject.toml`, `uv.lock`, `packaging/**`, `dev/packaging/**`, `packaging-smoke.yml`) | Everything in T1, **plus** an auto-dispatched full packaging campaign (`packaging-smoke.yml`), whose run is promotable evidence. |
| T3 | RELEASE | operator dispatch of `publish-release.yml` | Every gate: full-campaign evidence + acquisition-lane rows + the 12-row readiness aggregation + operator preflight + the protected `release` environment. Nothing here is weakened by the tier system — T3 binds to the existing Gate 1/2/3 topology. |

Manual verification lanes (dispatch-only; operator ruling 2026-07-21: no
schedules, no standing compute): `ci-full.yml` (full conformance: docs build,
CVE audit, hook replay, full unit suite, vault drift, ledger/storage
roundtrips - run before releases or whenever a full verdict is wanted),
`aeat-drift-detector.yml` (live AEAT selector parity - run before relying on
the GROI oracle), `code-health-report.yml` (informational dashboard).

## Event-trigger semantics

- **push to `main`** — the primary discipline surface (development is
  direct-push by coordinated agents). Runs T1 always, T2 when the paths match.
  Push runs auto-supersede (`cancel-in-progress: true`).
- **pull_request** — future-proofing for a PR flow: same T1 gates, same-repo
  only. Currently exercised rarely.
- **workflow_dispatch** — release-candidate campaigns (`packaging-smoke.yml`),
  acquisition lanes, publication (`publish-release.yml`), evidence GC, and
  ad-hoc re-runs. Release-critical dispatch runs never cancel in progress
  (`cancel-in-progress: false`, queueing).
- **schedule** — deliberately none anywhere (operator ruling 2026-07-21:
  cadence is manual; a schedule trigger is standing compute the no-schedule
  conformance gate refuses).
- **tag / release events** — deliberately none: publication is an explicit
  operator dispatch with typed inputs, never a tag side effect.

## File inventory

| File | Role |
| --- | --- |
| `workflows/ci.yml` | T1 per-push: static checks ∥ unit suite |
| `workflows/ci-full.yml` | Dispatch-only full conformance + vault drift + roundtrip gates |
| `workflows/packaging-quick.yml` | T1 per-push install probe (no evidence) |
| `workflows/packaging-campaign-trigger.yml` | T2 detector: auto-dispatches the full campaign |
| `workflows/packaging-smoke.yml` | Full campaign; sole source of promotable evidence |
| `workflows/packaging-scoop.yml` / `packaging-homebrew.yml` / `packaging-claude.yml` | Dispatch-only acquisition lanes consuming a tested cohort |
| `workflows/publish-release.yml` | T3: sole publication authority (Gates 1–3) |
| `workflows/evidence-gc.yml` | Dispatch-only bounded GC of evidence drafts |
| `workflows/agent-harness-eval.yml` | Merge-time gate on the operator agent harness |
| `workflows/aeat-drift-detector.yml` | Weekly live AEAT (tax agency) selector parity |
| `workflows/code-health-report.yml` | Monthly informational health dashboard |
| `ISSUE_TEMPLATE/` | audit / operator-capability / regression issue forms |

## Naming convention

Workflow **filenames** are kebab-case, prefixed by family where one exists
(`ci-*`, `packaging-*`, `publish-*`); the **`name:` field** always contains
"Cadrumo". Load-bearing filenames (`packaging-smoke.yml`,
`publish-release.yml`, `ci.yml`, `ci-full.yml`, `packaging-quick.yml`) are
pinned by conformance tests and by publish-release Gate 2 — renaming one
requires sweeping every pin in the same commit. "AEAT" appears only as the
name of the Spanish tax agency, never as the former product name.

## Branch protection (proposal, operator applies)

Branch protection is unavailable on the current plan (API returns 403). When
the repo gains it (Pro or public), the proposed settings for `main` are:

- Required status checks: `Cadrumo / static checks / Python 3.13`,
  `Cadrumo / unit suite / Python 3.13`; strict (branch up to date) off — the
  direct-push fleet would deadlock on it.
- The three quick probes as non-required informational checks (their
  proof-cache warm path can lag a queued runner).
- Block force pushes and deletions on `main` (the worktree-safety rule already
  forbids them socially; protection makes it structural).
- No required reviews: the agent fleet lands reviewed work via its own
  coordinator/review discipline; a human-review requirement would stall it.
