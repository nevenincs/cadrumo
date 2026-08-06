---
tags:
  - '#audit'
  - '#release-pipeline-full-automation'
date: '2026-08-03'
modified: '2026-08-03'
body_hash: 'sha256:42494e70117aa18a2de1188095af8adc0487c42927eaab812bd217bad4158207'
related: []
---

# Handover: release-orchestrator rehearsal, 2026-08-03

## Goal

Publish cadrumo through one workflow_dispatch of `.github/workflows/release-orchestrator.yml`
with no manual approval click and no soak wait: it bumps the version (release-please, no
hand-picked numbers), builds the packaging cohort, runs any claimed acquisition lanes, seals a
candidate, and immediately dispatches `publish-release.yml`, which validates (Gate 1/2) and
actually publishes (Gate 3) to PyPI + GitHub Release + any claimed channels.

**Not done yet.** No real (`dry_run=false`) dispatch has ever completed. Every dispatch today was
`dry_run=true` (a rehearsal — proves the chain wires together, pushes no real bump, publishes
nothing). Several rehearsals hit real bugs, each fixed and pushed; the last one hit a structural
issue that isn't fixed (see below), and all in-flight runs were then cancelled per operator
instruction because the repo is under heavy concurrent development right now and a moving `main`
defeats rehearsal in a way described below. `/goal clear` was run to stop the standing Stop-hook
mandate; there is currently no active goal driving further dispatches.

## Fixes landed this session (all pushed to `main`, tests green)

In commit order, each independently green on `dev/release/tests/test_release_orchestrator_workflow.py`:

1. `59d55d44e2` — give the bump commit a real git identity (bump job had no configured
   `user.name`/`user.email`, so `git commit` failed).
2. `07bc932d23` — **move the resting version floor off the burned `0.2.1` to `0.2.2`.**
   `pyproject.toml`/`.release-please-manifest.json`/`src/cadrumo/__init__.py`/both
   `packaging/cadrumo_data_*` companions now read `0.2.2`, not `0.2.1`. Root cause:
   `dev/release/version_identity.py`'s seal-time identity guard (`--scope seal`) deliberately
   refuses *any* burned version even as a mere "not yet bumped" resting state — see its own
   docstring at `version_identity.py:278` ("so is a burned one [refused, even at seal time]").
   Setting the resting floor to the burned `0.2.1` meant the guard fired on every un-bumped push,
   not just orchestrator dry-runs. `0.2.2` is never burned/shipped and sits above every existing
   `CHANGELOG.md` section (0.1.0/0.1.1/0.2.0/0.2.1), so release-please still computes past the
   burned range with no changelog collision. The burned ledger itself lives at
   `dev/release/burned_versions.py` (append-only; `0.2.0`/`0.2.1` are the two seeded entries from
   the deleted partial source-forge releases — do not touch that file to "fix" this class of bug,
   the floor/resting-version choice is the lever, not the ledger).
3. `3e1b3c98dc` — widen `run_resolution.py`'s `--resolve-seconds` from its 600s default to 1800s
   at both dispatch call sites in the orchestrator (campaign stage, each acquisition lane). This
   is "how long to wait for a dispatched run to even become visible in the Actions API", separate
   from `--conclude-seconds` (7200s, "how long to wait for it to finish") which was untouched.
4. `395c265742` — **a rehearsal now dispatches `packaging-quick.yml`, not the full
   `packaging-smoke.yml`.** The full multi-OS smoke campaign has historically taken 1-6 hours;
   paying that cost on every dry-run rehearsal (whose only job is proving bump → campaign →
   acquire → seal wiring) made every rehearsal the fleet's single longest-running job. The seal
   step correspondingly *skips* dispatching `publish-release.yml` when `dry_run=true`: Gate 2
   there pins the exact `.github/workflows/packaging-smoke.yml` path as its only acceptable
   source, which the quick lane structurally cannot satisfy — dispatching anyway would produce a
   permanent, expected-looking failure on every single rehearsal with zero diagnostic value. See
   the two new tests `test_a_rehearsal_uses_the_quick_campaign_not_the_full_smoke` and
   `test_a_rehearsal_never_dispatches_the_publication_authority` in
   `dev/release/tests/test_release_orchestrator_workflow.py`.

All four are pushed; `origin/main` has them. 38/38 tests pass in
`dev/release/tests/test_release_orchestrator_workflow.py`.

## Known unresolved structural risk — NOT fixed

The last rehearsal (run `30800920802`, then `30805630451`) failed with `RunNotYetVisibleError`
even after the widened 1800s budget, and the root cause is not a contention/timing bug:

`gh workflow run <path>` (used by `run_resolution.py`'s `dispatch_and_resolve`) dispatches against
a **branch ref** (`main`), not a pinned commit — the GitHub Actions `workflow_dispatch` API has no
way to pin a dispatch to a specific historical SHA. `resolve_dispatched_run` then searches for
"the run of this workflow, at this exact `head_sha`, created after my dispatch instant." On this
repo's `main`, which many concurrent agents push to continuously, the branch can advance between
when the calling job captured its `head_sha` (via `git rev-parse HEAD` or the bump job's output)
and when GitHub actually processes the dispatch. When that happens, the resulting run's
`head_sha` is a *different*, newer commit than the one being searched for — confirmed directly:
a `packaging-quick.yml` run (`30803466342`) landed within 2 seconds of the expected timestamp
window but at commit `d05e564cb...`, not the expected `395c265742...`. No run will ever match the
stale expected SHA in that case, so the poll exhausts its full budget and fails — retrying with a
fresh dispatch has a chance of landing in a quieter moment, but nothing in the code guarantees it,
and on a sufficiently busy `main` it could recur indefinitely.

This was **not fixed** — it needs a real design decision, not a quick patch. Options worth
considering next time this is picked up, roughly in order of how much they change the design:
- Accept the race but make the failure mode cheaper: on `RunNotYetVisibleError`, retry the
  dispatch itself (not just the poll) a bounded number of times, capturing a fresh `head_sha`
  each time.
- Widen `resolve_dispatched_run`'s matching to "the newest run of this workflow created after my
  dispatch instant, regardless of exact `head_sha`, PROVIDED its `head_sha` is `main`-ancestor-or-
  equal to what I expected" — trades a little precision for tolerance of small `main` drift,
  while still refusing an obviously-unrelated older/foreign run.
- Serialize release dispatches behind something that guarantees `main` is quiescent for the
  dispatch window (a short-lived lock branch, a merge-queue pause, or simply picking a deliberately
  quiet moment — which is what the operator chose today).

## Why everything was cancelled today

Per direct operator instruction ("stop all run, stop everything and cancel. we won't be able to
do jack shit. we're actively developming the application"): the repo is under heavy, continuous
concurrent development from many other agents/campaigns right now. Both problems above (runner
contention delaying job start, and the dispatch-by-ref race above) get *worse*, not better, while
`main` is this active — there is no point rehearsing against a target that won't hold still. All
queued/in-progress/pending runs across the repo were cancelled (`gh run cancel`) rather than left
to finish. The standing "publish cadrumo" goal was cleared via `/goal clear` so it stops re-firing
the Stop hook.

## Recommended next steps

1. Wait for (or negotiate) a quieter window on `main` — fewer concurrent commits landing — before
   the next rehearsal attempt.
2. Re-dispatch `release-orchestrator.yml` with `dry_run=true` first. If it now completes cleanly
   (bump → campaign [packaging-quick] → acquire → seal, all green, ending in "not dispatching
   publish-release.yml" rather than a failure), the chain is proven.
3. Only then dispatch with `dry_run=false` for a real release. Expect the campaign stage to take
   the full 1-6h this time (real `packaging-smoke.yml`), and expect `publish-release.yml` to
   actually fire at the end — that's the point.
4. If `RunNotYetVisibleError` recurs even on a quieter `main`, treat it as confirmation the
   structural fix above is now worth doing rather than working around by hand each time.
5. Cancelling stuck runs: `gh run cancel <id>` sometimes leaves a run in `in_progress`/`queued`
   for a while even after the request is accepted — if a job is polling on an *underlying*
   dispatched run (e.g. campaign polling packaging-smoke), cancel that underlying run too
   (`gh run list --workflow <name> ...` to find it by `headSha`/`createdAt`), which lets the
   polling loop see a terminal state and exit promptly instead of waiting out its own budget.
