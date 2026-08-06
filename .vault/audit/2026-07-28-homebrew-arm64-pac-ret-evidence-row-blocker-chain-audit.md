---
tags:
  - '#audit'
  - '#homebrew-arm64-pac-ret'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:782d349b1a3724397ec465fe7e5852447196d486963ca91bb2fad196ff2d31b5'
related:
  - "[[2026-07-25-homebrew-arm64-pac-ret-plan]]"
  - "[[2026-07-22-homebrew-arm64-pac-ret-adr]]"
  - "[[2026-07-27-publication-lane-consolidation-adr]]"
---

# `homebrew-arm64-pac-ret` audit: `why the Linux arm64 evidence row cannot be minted at current HEAD`

## Scope

Why the `homebrew-linux-arm64` distribution-evidence row could not be minted, established 2026-07-28 while driving the feature's plan to completion — and, by the end of the same day, how it was.

**Resolved.** The row is minted and verified passing, alongside the other two claimed rows, against a cohort at the first computed release version, with the acquisition run green across every job including the terminal seal. The blocker chain below is retained as the record of what stood in the way, not as a live obstruction; each finding carries its resolution.

The formula fix itself was never in scope here — it was landed and proven earlier under the plan's third step. What this document covers is everything that stood between that fix and its evidence.

Measurements are live reads: the forge Actions API for runner and run state, the package index for version ownership, the acquisition workflow's own gate definitions, and the emitted evidence records read directly rather than inferred from job outcomes.

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

**Superseded by execution.** These were written while the row looked unreachable without an operator release act. That act was authorised and carried out, and the row now exists. Retained so a reader can see what was believed, what was done, and what it cost.

### Closed

- **Do not mint against an existing cohort** — correct, and moot. A fresh cohort was built on a commit that is on main; the ancestry refusal never applied to it.

- **The version deadlock is broken.** The declarations were bumped to the first computed release version — derived by release-please from the manifest floor rather than chosen, and confirmed free on every destination before it was applied. Cohorts have since sealed repeatedly at that version.

- **The seal guard was not weakened**, which was the substantive risk in this area. It refused correctly throughout; the resolution was to satisfy it, not to soften it.

- **The row is minted.** All three claimed rows verify as passing against the same cohort, and the arm64 row was minted independently in two consecutive runs, so it is reproducible rather than a single fortunate pass.

### Opened by doing the work

- **The runbook contradicted the gates in several places**, each proven against the implementations and since corrected: an instruction to bump a surface whose gate requires the opposite; a stop rule gating the bump on a check only a post-bump release can satisfy; a fixed evidence-row obligation where the required set is derived from claimed channels; an arithmetic tally left stale by a platform drop; and an at-a-glance summary omitting a mandatory stage.

- **A rebuilt CI container silently loses three distinct classes of dependency** — a binary the workflows assume present, a system library a lane links against, and an entire package-manager tree — none of which announces itself as a missing dependency.

- **The obvious durability fix for the third was itself wrong.** Placing the package-manager tree in the runner's state volume and symlinking the canonical path at it survives a rebuild and breaks linking, because link traversals resolve against the real path. It fails only after building every resource, which makes it costly to diagnose. That dependency deliberately does not survive a rebuild.

- **The formula this feature exists to fix was unshippable as specified**, failing the strict formula audit on a leg that had never audited the guarded form before.

### Corrected after review

An earlier revision claimed the local readiness signal needs a check binding the cohort's version to the declared one. **Withdrawn as redundant.** The stale cohort is already refused one check earlier, by source-commit identity, which subsumes it: a version match could pass against a foreign commit, whereas a commit match cannot carry a foreign version, because the cohort's version derives from wheel metadata built at that commit.

What survives is presentation only: a surface-consistency line reading PASS while naming a superseded version is confusing in isolation, even though the report's verdict is correctly red.

### Still open

- A cosmetic residue: 174 translation-catalogue headers still name the abandoned version. No gate binds them and the next catalogue refresh regenerates them from the declared version, so they self-heal.

- Fleet capacity: the runner documentation describes two Linux X64 container runners while one is registered, so every workflow on that label serialises through it. This delayed but did not block the work.
