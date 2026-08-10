---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:68831eeada0fa3eeb28cff00267d56f7f01530b3171ee96bcefa6b8f57cd4ee5'
step_id: 'S36'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# MEASURED AND RULED. The selective local form does NOT qualify, and the reason is structural rather than a cost. Reachability across the whole dev tree is 22 test directories and 258 files, of which test-dev-tooling reaches 15 and test-dev-ci reaches 4, so only dev/docs/tests (46 files), dev/docs/apidocs/tests (1) and an empty migration directory are reached by no recipe and no workflow at all, and docs.yml invokes no pytest whatsoever. That makes the original figure of two hundred and forty-six files an overstatement by nineteen directories, because the forty-four minutes it priced was overwhelmingly the cost of re-reaching what two lanes already reach. Of the 46 remaining files, 22 reference playwright, sphinx, a docs build or a long mark.timeout, leaving 24 candidates. A bounded run over those 24 plus the apidocs directory collected 130 of 185 tests in 91.7 seconds with 16 failed and 13 errors, and 55 tests were DESELECTED by the local lane's own marker. The deselection is the ruling. Ten of the 24 candidate files are integration-marked at module level, so the local unit lane cannot select them at any price, and enrolling this directory there would leave every one of them exactly as unreached as it is today while printing green over them. The enrolment therefore cannot close the coverage gap it was proposed to close, which is a property of the markers and not of the machine. Cost only compounds it. 29 of the 130 selectable tests are currently non-passing, a never-run backlog that would red every lead's local run from the first day, and the 91.7 seconds is a floor measured while the heaviest fixture short-circuited on a HEAD-level ImportError from the CalculationRevisionId relocation rather than running its CLI-tree subprocess. Re-running once that clears would sharpen the ceiling and cannot change the direction, because the marker and backlog facts are not timing facts. The coverage half of the original question stands open and unaddressed by this row and belongs in CI, where an integration-capable lane can reach all 185. Note for whoever writes that row that this is the FIFTH remedy on this row family to be wider or blinder than the defect it targets, after a CPU bound that cannot fire on a wedge, a report hook that cannot fire on Windows, a raw descriptor write that the exit discards, and a reachability change whose cost was dominated by what it was never meant to reach

## Scope

- `justfile and .github/workflows/docs.yml and dev/docs/tests`

## Description

- Re-derived the reachability population rather than accepting the row's figure. Across the dev tree there are 22 test directories and 258 test files; one recipe reaches 15 of those directories and another reaches 4.
- Established that exactly three directories are reached by no recipe and no workflow: the docs test directory (46 files), the apidocs test directory (1 file), and an empty migration directory. The docs workflow was checked directly and invokes no pytest at all, so those files are not covered by a different gate.
- Corrected the row's own figure. Its "two hundred and forty-six files" overstated the target by nineteen directories, so the 44-minute cost it priced was overwhelmingly the cost of re-reaching what two lanes already reach.
- Narrowed the candidate set by measuring rather than by inspection. Of the 46 remaining files, 22 reference a browser driver, the docs builder, a docs build invocation or a long timeout marker, leaving 24 candidates.
- Requested a bounded run over those 24 plus the apidocs directory, asking for the collected count first as a no-op guard, wall time second, and a transitive-fixture verdict third.
- Read the module markers statically as an independent second instrument against the run's collection count.

## Outcome

Ruled in the negative: the selective local form does **not** qualify, and the reason is structural rather than a cost.

The bounded run collected 130 of 185 tests in 91.7 seconds, with 16 failures, 13 errors, and **55 tests deselected**. Ten of the 25 paths contributed nothing at all. A static read of the module markers found **exactly ten integration-marked files**, matching the ten silent paths measured dynamically — two independent instruments landing on the same population.

That is the ruling. The local unit lane cannot select those ten at any price, so enrolling the directory there would leave every one of them exactly as unreached as it is today **while the lane printed green over them**. The enrolment therefore cannot close the coverage gap it was proposed to close, and no tuning touches that, because it is a property of the markers rather than of the machine.

Cost only compounds it. Twenty-nine of the 130 selectable tests are currently non-passing — a never-run backlog that would red every lead's local run from the first day — and the 91.7 seconds is a floor measured while the heaviest fixture short-circuited on an unrelated import break instead of running its subprocess.

The coverage half of the original question stands open and is not addressed by this row. Something must run those 185 tests, and a docs workflow that invokes no docs tests is the actual defect. It belongs in CI, where an integration-capable lane can reach all of them.

A re-measurement was offered once the import break cleared and was declined, with the decline recorded in the row itself rather than only in correspondence. The two facts that decide the row — the module markers and the non-passing backlog — are not timing facts, so a sharper ceiling would move the magnitude and could not move the direction. The coverage row will still need that measurement.

## Notes

The row's action text was rewritten to carry this ruling, and that rewrite reached the repository inside a commit belonging to another lead, whose subject describes a locale row and says nothing about this measurement. A pathspec commit takes working-tree content for the named path, and this edit was sitting uncommitted in that path at the time. The content landed intact; only the attribution is wrong. It was reported immediately by the lead concerned, and it is recorded here so the archaeology on this ruling lands on a record that carries the reasoning rather than on a commit message that does not mention it.

The cost measurement everyone asked for was answering the wrong question, and a cheap number would have shipped the change. Had the wall time come back small it would have read as a green light for an enrolment that structurally could not work. The deselection count — requested only as a guard against a path set that silently selects nothing — was what decided the row.

Two instrument failures during this work, both the same class, and both caught by a plainer artefact disagreeing with a cleverer one. A pattern matching dev test directories required at least one path segment before the directory name, so it structurally could not match the shortest member of the set it was measuring and reported that directory as unreached when two lanes reach it. A later partition attempt returned a plausible-looking total of one. Both were caught against a raw listing that had been printed earlier, and the corrected run carried two controls: every parsed token must resolve to a real directory, and a specific known member must appear.

This is the fifth remedy on this row family to be wider or blinder than the defect it targets, after a CPU bound that cannot fire on a wedge, a report hook that cannot fire on the platform it measures, a raw descriptor write the process exit discards, and now a reachability change whose measured cost was dominated by what it was never meant to reach.
