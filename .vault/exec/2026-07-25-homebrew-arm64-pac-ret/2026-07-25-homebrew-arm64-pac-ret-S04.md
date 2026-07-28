---
tags:
  - '#exec'
  - '#homebrew-arm64-pac-ret'
date: '2026-07-28'
modified: '2026-07-28'
body_schema: 'body-v1'
step_id: 'S04'
related:
  - "[[2026-07-25-homebrew-arm64-pac-ret-plan]]"
---

# Re-run the Homebrew acquisition gate on all three claimed rows and record a passing homebrew-linux-arm64 evidence row, since two of three already pass and only this row blocks the claim

## Scope

- `.github/workflows/packaging-homebrew.yml`

## Description

- Break the version deadlock that made every cohort seal impossible, by executing the release cycle's first act under operator authorisation.
- Restore the Linux X64 container runner, which the gate needs for its draft-creation, x86-64, and seal jobs.
- Fix the formula defect the first acquisition attempt exposed, and clear the retained keg blocking the arm64 leg.
- Produce a green packaging smoke run so a consumable cohort exists on a commit that is on main.
- Dispatch the acquisition gate on all three claimed rows and verify each emitted record, rather than trusting the job outcomes.

## Outcome

All three claimed rows are minted and every record verifies as passing against the same cohort:

    homebrew-linux-arm64     status=passed   cohort=0.1.0   dest=linux-arm64
    homebrew-linux-x86-64    status=passed   cohort=0.1.0   dest=linux-x86_64
    homebrew-macos-arm64     status=passed   cohort=0.1.0   dest=macos-arm64

The acquisition run completed green across all five jobs including the terminal seal, so the evidence manifest binds the run identity to every asset. The row this feature exists for was independently minted and verified in the preceding run as well, so it is reproducible rather than a single fortunate pass; the macOS row likewise passed twice.

The arm64 row is the substantive result. It is the first proof that the guarded formula actually installs on the Apple-virtualization container that faults on the pointer-authentication return instruction -- the environment whose failure the decision record was written to resolve. Acquisition was a real source build through the tap, not a simulation.

Five separate blockers stood between the landed fix and this row, each of a different kind:

- **The version deadlock.** No cohort could seal at all, because the declared version was permanently unsealable: two companion projects hold it as package-index name reservations, and an index upload cannot be undone. Resolved by executing the release cycle's first act under operator authorisation -- the version was computed from the manifest floor, not chosen, and confirmed free on every destination before it was applied.
- **An unusable predecessor cohort.** The last successful smoke predated a history rewrite, so the gate's ancestry check returned no common ancestor. Correctly unfixable; a fresh cohort was the only route.
- **A dead CI runner**, whose entrypoint had been bind-mounted from a directory that no longer existed.
- **A formula that could not ship.** The guard failed the strict formula audit on the macOS leg, and had never been audited before because the existing macOS row came from a cohort predating the guard.
- **A retained keg** on the arm64 host from an earlier run whose cleanup never executed.

## Notes

Verification is on the emitted records, not the job outcomes. Each row was downloaded and its status, cohort version, and destination read directly, because a green job proves the lane ran, not that it minted a valid record.

Three of the failures along the way were self-inflicted and are recorded honestly. Rebuilding the container from the stock image silently dropped three distinct classes of dependency -- a binary the workflows assume present, a system library a lane's toolchain links against, and the package-manager tree itself -- and none announced itself as a missing dependency: they surfaced as a version-gate refusal, a lane exit code, and a path check. Worse, the fix for the third was itself wrong: installing the tree in the runner's state volume and symlinking the canonical path at it survives a rebuild and breaks the link step, because link traversals are computed against the resolved path, which through a symlink is deeper than the canonical one. That failure builds every resource successfully before dying at the last step, which makes it expensive to diagnose. The runner documentation now records all of it, including that this one dependency deliberately does not survive a rebuild.

The operator-facing runbook was found to contradict its own gates in several places while this work ran, including an instruction to bump a surface whose gate requires the opposite. Those corrections were landed separately and are recorded in the feature's audit.
