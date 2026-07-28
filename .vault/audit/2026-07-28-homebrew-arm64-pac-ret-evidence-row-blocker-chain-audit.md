---
tags:
  - '#audit'
  - '#homebrew-arm64-pac-ret'
date: '2026-07-28'
modified: '2026-07-28'
related:
  - "[[2026-07-25-homebrew-arm64-pac-ret-plan]]"
  - "[[2026-07-22-homebrew-arm64-pac-ret-adr]]"
  - "[[2026-07-27-publication-lane-consolidation-adr]]"
---

# `homebrew-arm64-pac-ret` audit: `why the Linux arm64 evidence row cannot be minted at current HEAD`

## Scope

Why the `homebrew-linux-arm64` distribution-evidence row cannot be minted at current HEAD, established 2026-07-28 while driving the feature's plan to completion. The formula fix itself is not in scope -- it is landed, proven, and closed under the plan's third step. What is in scope is everything standing between that fix and a passing evidence row.

Measurements are live reads taken the same day: the forge Actions API for runner and run state, the package index for version ownership, and the acquisition workflow's own gate definitions.

## Findings

### last-good-cohort-unreachable | high | the newest consumable cohort is permanently unusable, and not because it is stale

The acquisition gate consumes a cohort from a successful packaging smoke run. The most recent successful smoke run finished 2026-07-27 and its evidence draft still holds both required cohort archives, so it looks consumable. It is not.

That run was dispatched rather than pushed, and for a dispatched run the gate demands the run's commit be verified against main history through the compare API. Main's history has since been rewritten: the compare call does not merely report divergence, it returns 404 with "no common ancestor". The gate refuses, correctly -- the commit is genuinely not on main.

The content is fine; the commit carries the complete guarded fix, confirmed by reading the generator at that revision. Only its ancestry is disqualifying, and ancestry cannot be repaired. No older successful run helps either: every smoke run predating the rewrite shares the same defect, and every run after it has failed.

### smoke-refusal-is-by-design | high | the blocking refusal is the pipeline working, not a regression to fix

Every smoke run since the rewrite fails at cohort seal with a refusal that the declared version `0.0.0` is already carried by two of the three published projects. This reads like a broken gate and is the opposite.

The accepted publication-lane decision reset every version declaration to `0.0.0` deliberately, and the two companion projects' `0.0.0` uploads are name reservations whose entire job is to hold the names -- to be yanked only after the first complete release lands. The seal guard checks all three projects, so it sees those reservations and refuses. Both halves are behaving as designed; they simply interlock into a state where no cohort can be sealed until the version advances.

Treating this as a bug and loosening the guard would be the harmful move: the guard exists because an index upload is irreversible, and it is the check that a skipped bump is caught while a re-run is still the only cost.

### row-blocked-on-a-release-cycle | high | the remaining step is gated on an operator release act, not on packaging work

Advancing the version is not an incidental unblock. The runbook makes the bump the first act of a release cycle, spanning eight release surfaces in one commit, from a clean main, behind a readiness gate that must report no open blocker. The version is computed by release-please from the manifest floor, never hand-picked; with the floor at `0.0.0` and minor-bump-before-major configured, the first computed version is `0.1.0`.

So the plan's remaining step is gated exactly as its first step was -- on an operator act -- and the gate is a release decision rather than a packaging one. No plan currently open owns executing that bump.

### runner-entrypoint-on-ephemeral-path | medium | a CI runner was dead because its entrypoint lived in a temp directory

The Linux X64 container runner had exited 127 and stayed down despite an always-restart policy. Its entrypoint was bind-mounted from an ephemeral agent-session scratch directory; when that directory was cleaned up the daemon recreated the bind source as an empty DIRECTORY, so the entrypoint could not be executed.

This runner is not incidental to this feature: the acquisition workflow needs it for the evidence-draft creation job, the x86-64 leg, and the terminal seal job, so all three claimed rows depend on it, not just the x86-64 one. Restored the same day by installing the entrypoint inside the runner's own state volume, where it shares the runner's lifetime; the runner is online and idle again, with the broken container retained renamed for rollback. The failure class is the fragility of the mount source, so the fix is durable only while the entrypoint stays out of ephemeral paths.

### rag-code-index-unusable | medium | the discovery gate's instrument is broken while reporting success

The semantic code index reports a succeeded job with no degraded reasons while holding content for 1 of the 4597 files it names. Two unrelated probes each returned chunks from a single unrelated file, one set at negative relevance.

The service does report the shortfall honestly in its own search response, which is what makes the state detectable at all; the job status alone would not have revealed it. Re-running the index resolves almost nothing -- a rebuild reported adding 106 chunks and coverage stayed at one file -- so the index believes it is current while holding no content, and an ordinary reindex does not converge it.

## Recommendations

- Do not attempt to mint the Linux arm64 row against any existing cohort. The one consumable candidate fails an ancestry check that cannot be repaired, and the failure is a correct refusal rather than an obstacle to route around.

- Treat the remaining plan step as operator-gated and leave it open until a release cycle begins. It becomes actionable the moment the Stage 0 bump lands: bump, run the smoke to produce a cohort on a commit that is on main, then dispatch the acquisition gate for all three rows.

- Do not loosen the seal-time version guard to unblock the smoke lane. The refusal is the guard doing its job; the resolution is the bump, and weakening the check would remove the protection that makes a skipped bump cheap to discover.

- Keep container entrypoints out of ephemeral directories. The restored runner holds its entrypoint in its own state volume; the provisioning knowledge behind that is still undocumented, and documenting it in the runner operations directory is the outstanding follow-up.

- Repair the semantic code index before any further code work that the discovery mandate governs. An ordinary reindex does not converge it, so it needs a clean rebuild rather than another incremental pass, and until then an absent search result is not evidence of absence.
