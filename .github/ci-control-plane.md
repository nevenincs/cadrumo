# `.github` architecture

This folder is the repository's CI/CD control plane. Every workflow obeys four
standing invariants, each enforced by a conformance gate in the test tree:

1. **Self-hosted fleet only.** Every `runs-on` is a `[self-hosted, ...]` label
   set; GitHub-hosted images are a spend regression
   (`dev/ci/tests/test_self_hosted_fleet.py`).
2. **Zero Actions-artifact storage.** No `upload-artifact` / `download-artifact`
   anywhere; outputs live in job logs, and release evidence rides draft
   releases per the release-asset-transport ADR
   (`dev/ci/tests/test_change_class_tiers.py`, transport gates).
3. **No fork code on the fleet.** `pull_request` triggers exist only with a
   same-repo job guard; fork PRs skip every job.
4. **Evidence honesty.** Only `packaging-smoke.yml` mints promotable
   `DistributionEvidence`; `publish-release.yml` Gate 2 pins that workflow
   path, so no other lane can enter promotion.
5. **Machine-aware load.** No lane sizes itself as if it owns the machine
   (`dev/ci/tests/test_machine_aware_load.py`); see the topology below.
6. **Honest perf gates.** Performance benchmarks assert PROCESS CPU-TIME
   (load-immune on the shared machines) with wall-clock printed as advisory
   only, and run solely in the dispatch-only `ci-full.yml` lane
   (`dev/ci/tests/test_perf_gate_policy.py`).
7. **Frozen installs only.** Every `uv sync` carries `--frozen`
   (`test_no_workflow_installs_python_dependencies_unfrozen`). A bare sync
   re-resolves the dependency graph against the index on every job, which costs
   both wall-clock (measured: ~2 min per job, paid twice per push) and
   attributability — an unfrozen resolve can pick up an index change nobody
   pushed, so a red is not necessarily a property of the commit under test.
8. **Declared is not run.** A justfile recipe is a declaration; a recipe no
   workflow invokes has never executed. `dev/ci/lane_reachability.py` models
   both, and `test_every_test_ci_cannot_run_declares_why` requires every test
   CI does not run to carry a marker saying which precondition a headless
   runner lacks (`external_tool`, `aeat_live`, `os_keychain`,
   `resident_service`). "Nobody wired a lane" is not an accepted answer.

## Fleet topology and load sizing

Four runners for THIS repository, on **two physical machines** — a runner label
is NOT a machine, and jobs from other repositories co-reside on the same boxes:

| Machine | Cores | This repository's runners on it |
| --- | --- | --- |
| Windows/WSL build host (Ryzen 5900X, 12C/24T) | 24 logical | the Windows runner (Windows X64), plus two Linux X64 container runners |
| macOS build host (Apple silicon) | 6 | the macOS ARM64 runner and a Linux ARM64 runner (via colima, VM capped at 4 CPUs) |

**The workstation is NOT ours alone.** It hosts self-hosted runners for three
other repositories under four distinct mechanisms — Windows services, logon
scheduled tasks, WSL systemd units, and Docker containers. Measured 2026-08-05:
**eight runners online, ten at ceiling** once the two logon-triggered tasks
start. Only three of those belong to this repository, and one of the three (the
Windows runner) was offline at the time of measurement. Enumerating Windows
services alone finds two of them; any question of the form "what else runs on
this box" must enumerate all four mechanisms.

**The two Linux X64 container runners carry identical labels**, so a job
requesting `[self-hosted, Linux, X64]` lands on whichever is free. Provision
them as a pair and keep their tooling at parity — a capability present on one
and absent on the other is a failure that reproduces only half the time.

**Sizing rule:** the sum of co-resident workers must fit the machine's CPUs —
size every parallel knob for worst-case co-residency, never for the whole box.
Concretely: workstation lanes get explicit `-n 8`; MacBook lanes get `-n 2` (the
colima Linux ARM VM is capped at 4 of the 6 cores, leaving 2 for the macOS
lane); `pytest -n auto` is banned in any
CI invocation (it grabs every logical CPU); the packaging campaign's lane
pool and preflight pytest are sized per leg via
`CADRUMO_PACKAGING_LANE_CONCURRENCY` / `CADRUMO_TEST_WORKERS`; the Homebrew
matrix carries `max-parallel: 2` (two of its three legs live on the MacBook)
and per-leg `HOMEBREW_MAKE_JOBS`. Local development keeps `-n auto` — the
rule binds surfaces that can run CONCURRENTLY with other jobs on a shared
machine.

**`-n 8` is an unverified pin, not a derivation.** It was previously documented
as `24 / 3` — twenty-four logical CPUs divided by three co-resident runners.
That arithmetic counted only this repository's own runners and is false: seven
runners are online on that box. The value has been left at `8` deliberately,
because correcting a premise is not the same as measuring a replacement, and no
such measurement has been done. Do NOT recompute a new worker count from this
section — a smaller number derived from the true denominator would be just as
unmeasured as the old one, only more confidently wrong. Treat `-n 8` as a
working pin pending a real contention measurement, and cite that measurement,
not this paragraph, when you change it.

## Change-class tiers

Classification is **structural** (path filters and workflow topology, never
honor-system) and **fail-closed**: a push that does not match a lighter tier's
carve-out gets the heavier tier's gates. Detection is by changed paths; the
conventional-commit type on the head commit is documentation for humans, not a
gate input. Governing decision: the `ci-discipline` ADR (2026-07-21), layered
on the `ci-speed-redesign` ADR (2026-07-20).

| Tier | Change class | Detected by | What runs |
| --- | --- | --- | --- |
| T0 | vault / agent-config / loose markdown churn | `paths-ignore` carve-out, byte-identical on `ci.yml` and `packaging-quick.yml` | Nothing per-push. The dispatch-only full lane (`ci-full.yml`) is the backstop for vault drift and the slow conformance surface. |
| T1-docs | documentation surface | `docs.yml` `paths` filter (`docs/**`, `dev/docs/**`, `src/cadrumo/_data/terminology/**`) | `docs.yml` alone: the nitpicky Sphinx build, stub correspondence, CLI-reference drift, doc8, interrogate. The Python lanes carve these paths out, so a docs edit no longer starts the unit suite. |
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
  Push runs QUEUE rather than supersede
  (`cancel-in-progress: ${{ github.event_name == 'pull_request' }}`, so push
  runs finish and pull-request runs supersede). They superseded until
  2026-08-11, and at this repository's direct-push commit rate that meant each
  push cancelled the run the previous push started: the last 100 runs were 99
  cancelled, 1 in flight, 0 success, and the last green run of any age was
  2026-07-24 — eighteen days. Nothing surfaced it, because a cancelled run is
  not a red one and `main` carries no required checks. Superseding bought no
  saving to weigh against that: without `cancel-in-progress` only ONE run may be
  pending in a group and a newly queued run cancels the previously pending one,
  so both settings cap the lane at one in flight and one waiting, differing only
  in whether the in-flight run is allowed to finish. The runners are self-hosted
  and consume no Actions minutes. The real cost is latency — a completed verdict
  may name a sha several commits old — which is strictly better than no verdict.

  **A path filter is evaluated over the PUSH, not per commit.** GitHub takes the
  union of every file changed across every commit in the push, so a push that
  bundles a vault record with a source change is T1 — the carve-out only bites
  when a push is *entirely* carved-out paths. The agent fleet bundles routinely
  (a "WIP snapshot" commit sweeps everything), so T0 fires less often than the
  tier table suggests. This is a property of the trigger mechanism, not a defect
  to route around: the failure it prevents (a code change riding along with
  vault churn and skipping the suite) is far worse than the wasted run.
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
| `workflows/ci-full.yml` | Dispatch-only full conformance: integration suite, dev tooling gates, docs, CVE, hooks, vault drift, roundtrips |
| `workflows/docs.yml` | T1-docs per-push documentation verification (never delivery — see `docs-publish.yml`) |
| `workflows/docs-publish.yml` | Documentation DELIVERY, on `release: published` only; downstream of publication, never a gate |
| `workflows/packaging-quick.yml` | T1 per-push install probe (no evidence) |
| `workflows/packaging-campaign-trigger.yml` | T2 detector: auto-dispatches the full campaign |
| `workflows/packaging-smoke.yml` | Full campaign; sole source of promotable evidence |
| `workflows/packaging-scoop.yml` / `packaging-homebrew.yml` / `packaging-claude.yml` | Dispatch-only acquisition lanes consuming a tested cohort |
| `workflows/publish-release.yml` | T3: sole publication authority (Gates 1–3) |
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
