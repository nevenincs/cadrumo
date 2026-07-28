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

**Superseded the same day.** The recommendations below were written while the row was believed unreachable without an operator release act. The operator authorised that act, it was carried out, and the chain is broken. What follows records both the original guidance and what actually happened, because a reader arriving later would otherwise conclude the row is still blocked.

### Closed

- **Do not mint against an existing cohort** — still correct, and now moot. A fresh cohort exists, built on a commit that is on main, so the ancestry refusal no longer applies to it.

- **The version deadlock is broken.** The declarations were bumped to the first computed release version, which release-please derived from the manifest floor rather than anyone choosing it, and which the identity guard confirmed free on every destination before it was applied. A cohort has since sealed twice at that version — the refusal that killed every run since the reset is gone, and reproducibly so. Seven surfaces moved; the bundle manifest deliberately did not, because its tracked value is a sentinel the version gate requires to stay put.

- **The seal guard was not weakened**, which was the substantive risk in this whole area. It refused correctly throughout; the resolution was to satisfy it, not to soften it.

### Opened by doing the work

- **The runbook contradicted the gates in three places**, each proven against the implementations and since corrected: it instructed bumping a surface whose gate requires the opposite, it gated the bump on a check only a post-bump release can satisfy, and it asserted a fixed evidence-row obligation where the required set is derived from the channels a release claims. A separate arithmetic error — claiming eight CI-minted rows including four homebrew, where the descriptor declares three — was residue from the platform drop and would have stranded an operator hunting a row no lane can mint.

- **A rebuilt CI container silently loses three classes of dependency**: a binary the workflows assume present, a system package a lane's toolchain links against, and an entire package-manager tree. None announced itself as a missing dependency; each surfaced as an unrelated-looking failure — a version-gate refusal, a lane exit code, and a first-step path check. All three are now documented with verification commands.

- **The formula this feature exists to fix was unshippable as specified.** The guarded form failed the strict formula audit on the macOS leg, and it had never been audited before because the existing macOS evidence row was minted from a cohort predating the guard. Fixed in the generator, with the pin rewritten to anchor on the whole guard-opening line — the bare condition also appears inside the corrected form, so the obvious assertion would have passed while pinning nothing.

### Corrected after review

An earlier revision of this section claimed the local readiness signal needs hardening, on the grounds that no check binds the cohort's version to the declared one. **That recommendation is withdrawn as redundant.** The stale cohort IS refused, by a stronger rule one check earlier: `distribution-evidence-complete` compares the cohort's source COMMIT against the checked-out commit and blocks on mismatch. Commit identity subsumes version identity here — a version match could still pass against a foreign commit, whereas a commit match cannot carry a foreign version, because the cohort's version is derived from the wheel metadata built at that commit. Adding the version assertion would buy nothing, and adding a burned-version check to the local report would duplicate the guard that already runs at both CI gates.

What survives is only a presentation point: the surface-consistency line reads PASS while naming a superseded version, which is confusing in isolation even though the report's overall verdict is correctly red for the right reason.

### Still open

- The evidence row itself is not yet minted. What blocks it now is only the remaining run, not a structural refusal.

- A cosmetic residue: 174 translation-catalogue headers still name the abandoned version. No gate binds them, and the next catalogue refresh regenerates them from the declared version, so they self-heal; they are not a release blocker.
