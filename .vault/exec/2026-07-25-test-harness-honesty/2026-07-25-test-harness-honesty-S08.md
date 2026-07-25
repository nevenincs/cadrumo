---
tags:
  - '#exec'
  - '#test-harness-honesty'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S08'
related:
  - "[[2026-07-25-test-harness-honesty-plan]]"
  - "[[2026-07-25-test-harness-honesty-adr]]"
---

# Sweep the remaining survivor and conformance gates for the vacuous-pattern shape this audit found twice in one day, in the bare-literal scan and in the documentation claims gate, asserting each pattern against a known-match and a known-reject rather than trusting that a green gate is measuring anything

## Scope

- `src/cadrumo/tests/`
- `dev/`

## Description

- Screen the whole test surface mechanically for the empty-assert shape rather than reading modules one at a time, because reading is what missed the two founding cases.
- Partition the surface and sweep both halves, measuring every compiled pattern against a target and a near-miss instead of inspecting the regex.
- Prove each repair by reintroducing the defect and observing the failure name the exact site, then restoring.
- Re-run the screen at the closing commit so the delta is a measurement rather than an impression.
- Judge whether the class is closed or sampled, and say which.

## Outcome

The class was SAMPLED, not closed. The sweep found six further live instances beyond the two the audit already knew about, which triples the known count, and each of the audit's shapes reproduced at least once more.

Patterns that could never match, the founding shape, recurred twice. A process-symbol entry compiled to a transposed token, introduced by splitting the literal to keep it out of the file's own scan, so it matched a string this tree does not contain from the day it was written. Separately the destructive-command scan required a word boundary immediately after the flag letter, so it caught the bare short flag but was blind to its two bundled spellings and to the long form; measured against nine control commands the shipped pattern failed three. That second one is the most consequential find of the sweep, because the spellings it could not see are precisely the ones the worktree-safety rule names most often, so the gate was blind exactly where it mattered most.

Empty corpora recurred twice, and both were observed rather than reasoned about. One scan globbed the package for a forbidden import and reported clean; the same scan against a non-existent path reported the identical clean, with 3665 files on one side and zero on the other. The sequence ratchet folded an absent docs tree into an empty offender map and passed, measured live at 281 sequences against a confident error-free zero.

An escape outlived its reason seven times over. That ratchet only ever subtracted its enrolled set from the live violations, so an entry survived its site being fixed, moved, or deleted. All seven enrolled entries were stale, pointing at a blank line, an isinstance guard, a class statement, and in one case a line number past the end of its file. Each was a standing licence for a future suppression to drift onto that line number and be granted in silence. The set is now asserted in both directions.

A seventh instance was a correct assertion that could not discriminate: the duplication runner's failure gate checked only that the process had exited, which cannot separate a captured diagnostic from a vanished one. Closed separately.

The measured delta. An independent syntax-tree screen for the empty-assert shape ran over 227 test modules at the opening commit and again at the closing one: 38 flagged functions fell to 33. That is the honest shape of this step's result. The trend is down and every repair is proven, but a third of the original worklist is untriaged, and at least one of the remainder is a confirmed real instance rather than noise: a stub-drift gate asserts its drift lists are empty without ever proving the manager saw a module, so a moved tree or an off-by-one in its root resolution yields the same green.

One correction to this step's own first reading, recorded because the audit makes a point of not smoothing these over. A survivor module was cleared as sound on the evidence that its five patterns discriminate today and its corpus emptiness is caught by a concrete-path membership assertion in a sibling module. Both facts are true and the clearance was still wrong, because over the same 1390 files the shipped and a deliberately defective pattern both return zero hits. Nothing in the gate could tell them apart. Discriminating today is not the same property as protected from rot, and only the second one is what this campaign is buying.

Also worth recording as a general rule the sweep established: a guard living in a different module still counts. Several screen hits were false positives whose corpus substrate is guarded elsewhere by a membership assertion naming a concrete known path. Those are reported as guarded off-module rather than as findings, which is why the screen is a worklist and never a verdict.

## Notes

Semantic CODE search was degraded throughout and reported itself healthy: 188 indexed sections against roughly 4546 tracked files, an available status, and an empty degraded-reasons list, which is a regression from the roughly 1027 recorded when S01 landed. Two deliberately unrelated probes returned the same file at similarity around 0.001. Discovery for this step was therefore a mechanical syntax-tree screen over the tree plus targeted search and direct reads, and the screen is the substitute worth keeping: it does not depend on an index at all.

The screen asserts it scanned a non-zero number of modules before reporting, because a screen for this defect class that could itself return an empty result would be the defect it hunts.

Two verification traps hit during this step, both worth carrying forward. Several gate modules are integration-marked, so a bare pytest invocation against them selects nothing and exits green; the live-scan module for the duplication runner is one, which means the gate that catches this class is itself reachable only past a selection defect of the same family. Separately a grep counting zero exits non-zero, so it breaks a shell chain and makes a clean result look like a failed command, which is the same don't-believe-a-piped-exit-code lesson in miniature.

What this step did NOT examine, stated plainly so the next reader does not inherit a false sense of coverage: 33 flagged functions remain untriaged, the screen only detects one of the four shapes (an empty assertion with no non-emptiness proof) and is blind to the total-substituted-for-decomposition shape entirely, and no systematic search was run for escapes that have outlived their reasons beyond the one ratchet where seven were found. That ratchet was found by a partition sweep, not by the screen, so the seven-stale-escapes result should be read as evidence that the shape is common rather than as evidence that it has been surveyed.
