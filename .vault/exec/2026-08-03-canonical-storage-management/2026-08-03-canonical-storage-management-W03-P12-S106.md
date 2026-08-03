---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:da76ae8c79dbad3c7ce9fd5cb935ea0225486d84710df7aaf1a56a72feb6bbec'
step_id: 'S106'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Close the gap in the reclaim containment proof, which quantifies over declared taxonomy members so it can only detect a declared protected member nested under an accepted one, and cannot see undeclared nesting beneath an accepted category at all, safe today only because every known undeclared nesting sits under an unbounded_by_design parent rather than by any assertion the proof makes

## Scope

- `src/cadrumo/application/storage_management/tests/`

## Description

- Pinned `5c951abc88` and read the proof, the reclaim verb, and the taxonomy out of `git show` rather than the working tree, which carried another agent's uncommitted retained-path change to the service.
- Separated the containment claim into its two directions and established which is provable from the declaration and which is not.
- Measured what reclaim actually reaches: materialised the declared tree under a temporary root, planted sentinels in every declared directory, at the storage root, outside the root entirely, and in undeclared nesting beneath every accepted member, ran the real verb over the whole accepted set, and recorded every casualty.
- Probed the one real escape vector with live symlinks at both depths that different mechanisms defend.
- Measured the grouping axis against the reclaimable set, which surfaced a hole the Step did not ask about.
- Added four assertions and a positive control, rewrote the module docstring to state the quantification and the residual, and left the by-design whole-subtree delete pinned.

## Outcome

**What the proof quantified over, and the split that resolves it.** The proof iterated `STORAGE_TAXONOMY`, so it could only ever see declared members. That conflated two properties with very different provability, and stating them separately is most of the work.

*Outward — can reclaim reach outside the directory it was handed?* Provable in full generality, because it quantifies over the filesystem rather than the declaration: plant, run, observe. No enumeration is involved, so an undeclared location cannot hide from it. It was previously only inferred from a path comparison over declared members. Now asserted behaviourally.

*Inward — is everything inside a reclaimable directory safe to delete?* Not provable from the declaration, because the declaration is the incomplete thing. The strongest available statement is the existing one over declared members. The residual is now named in the docstring instead of left to inference: an undeclared location holding something that must survive, sitting beneath a member declared `RETENTION`, `ROTATION`, or `TTL`. It is closed by enrolling the location, not by testing harder.

**Measured, not reasoned.** Across the whole accepted set — eight members at the pinned commit — reclaim deleted 15 of 46 planted sentinels and **zero escaped**: every casualty lay beneath a directory reclaim had been handed. Live symlinks pointing out of a reclaimable directory were created at both depths and the target survived both: an immediate child is caught by the verb's own `is_symlink` branch, and one nested deeper is reached by `shutil.rmtree`, which unlinks rather than follows. So the escape direction is sound — it was simply unasserted, and a regression would not have reddened anything.

**A hole the Step did not ask about, found by measuring the grouping axis.** The existing assertion refuses `StorageGrouping.STATE` and nothing else. `EXPORTS` was admitted — the drafts, justificantes, filing history, filed declarations, invoices and attachments a taxpayer defends a return with. All fifteen `EXPORTS` members are `UNBOUNDED_BY_DESIGN` today, so nothing is reclaimable now, but that is a property of the current declaration: one lifecycle edit made in entirely good faith ("filing history grows forever, prune it") moves a member into the accepted set with the denylist still green. Evaluating both predicates over every grouping shows `exports` is precisely the one value the old assertion admits and the new one refuses. Restated as an allowlist: reclaim may reach logs and caches, and any other family joining the accepted set must be a deliberate decision.

**Assertions added.** Outward containment measured over the filesystem; a positive control that withholds one genuinely accepted directory so the comparison is shown able to fail; the symlink escape vector; the grouping allowlist; and the deliberate whole-subtree delete pinned, so narrowing reclaim to declared children reds a test and forces the decision to be re-taken rather than drifted into.

**Verification.** 91 tests pass across the owning package, `ruff check` and `ruff format --check` clean, and the tree-wide gates that can see the change — docstring core-struct links, docstring well-formedness, codebase size budgets, storage provenance — pass at 54 tests. The first attempt at those gates reported "NOTHING RAN" against three filenames that do not exist; that is not a pass, and the run was repeated against the real files.

## Notes

**The Step's stated premise is the superseded one, and the correction changes what to watch for.** The Step text says the gap is "safe today only because every known undeclared nesting sits under an `unbounded_by_design` parent". The honesty review had already corrected exactly that claim: 11 of the 34 nested-ungoverned sites *do* sit under a reclaimable parent — `runs` with seven sites, plus `llm-cache`, `llm-usage`, `llm-run-telemetry` and `logs`. Safety does not come from those sites avoiding reclaimable parents; it comes from deletion being the *intended* behaviour for all eleven, because they are regenerable traces, caches and telemetry. Same conclusion, different reason, and the reason is what tells a future reader where to look: not "watch for new nesting under reclaimable parents", which is already routine and fine, but "watch for a writer of *non-regenerable* data choosing a path under a `RETENTION` or `ROTATION` parent". The docstring states it that way.

**No production mutation was available for the escape proof.** The service carried another agent's uncommitted work, so opening a mutation window in it would have risked a peer committing the defect. The positive control mutates the *permitted set* instead — withholding a genuinely accepted directory and requiring the real deletion beneath it to read as an escape — which is the same technique the sibling nesting control already uses.

**The exec scaffolder reproduced the placeholder defect in this record.** `vaultspec-core vault add exec` substituted the Step heading and the scope list into the explanatory comment that was meant to describe those placeholders, destroying the instruction. The mangled comment block was removed from this file rather than left as noise; the defect itself is upstream in the template and is recorded in the corpus review, where it was found across nine records here and in unrelated campaigns.

**A safety guard is built into the test rather than assumed.** Every helper that hands a path to a deleting verb first asserts the path resolves inside the test's own temporary root, so a settings override that silently failed to take effect fails the test instead of reaching the real storage tree.
