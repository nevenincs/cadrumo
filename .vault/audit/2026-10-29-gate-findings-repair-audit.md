---
tags:
  - '#audit'
  - '#gate-findings-repair'
date: '2026-10-29'
modified: '2026-10-29'
body_schema: 'body-v2'
body_hash: 'sha256:b8502c0be84c96065f7913c63816d2b8be9fbc9ccab067aa11ab821272d68e42'
related:
  - "[[2026-10-29-gate-findings-repair-plan]]"
---

# `gate-findings-repair` audit: requested gates and integrated repairs

## Scope

Review the eleven operator-requested commands and repairs under the gate-findings-repair plan. S02 is committed as e679d68a54; S01 as 722bcd9b4a. S04 is committed as 16011e731f and S05 as 44100effda. The final authored-repair review passed; aggregate outcomes and residual debt are recorded below. The independent Sol 6.1 high reviewer inspected the canonical import relocation, documentation inclusion policy, spelling segmentation and punctuation, numeric section identities, Python snapshot ownership, and concurrent build environments. It reused focused test, Ruff and type evidence rather than duplicating expensive gates.

External concurrent source, ADR, dictionary and exact Google/Drive spelling changes remain outside this patch. S01 staging excluded those vocabulary entries and their dependent provider-name control. No scan result is represented as proof of current law, a published package or a submitted tax return.

## Findings

### cleanup-survivor | medium | Failed snapshot removal must remain visible

Independent review found that replacement calls in `dev/packaging/python_cohort.py` ignored a false return from `remove_tree`. A locked Windows snapshot could therefore survive a successful cohort return without a diagnostic. The executor is adding one canonical cleanup policy with exact surviving-path errors on normal completion and an exception note preserving an existing primary failure. Injected cleanup-failure tests and review of liveness-aware release cleanup are required before S04 closes. Initial review verdict: PENDING, with no high or critical code defects found.

### locale-inventory | medium | Strict locale audit retains substantial content and language-context debt

The final exact locale run exited 1 with 10,109 unique affected spelling cells, including 3,441 overlapping runtime review records. There were zero missing translations, placeholder failures, extraction failures or dictionary-tool failures among 49,516 required cells. Surfaces: runtime 3,441; generated casillas 2,683; PO translations 1,469; generated legal 1,279; generated CLI 620; authored docs 371; TOML 246. Regeneration changed audited coverage, so total-count differences are not a pure repair delta.

Representative remaining sources include abbreviated or unaccented generated labels in `docs/_generated/casillas/200.rst`, mixed English and Spanish legal notes in `docs/_generated/legal/boc-j-2009-90008.rst`, runtime command/technical terms such as auth/config/snapshot, Hungarian foreign tax nouns, British-dictionary rejection of amortization, the unmarked exact official name Certificado de Situación Censal, and Declaracion without an accent in `src/cadrumo/_data/terminology/concepts/autoliquidacion.toml`. These findings require owner review; broad vocabulary acceptance or language guessing would hide defects.

### moving-tree-verification | low | Concurrent writers invalidated otherwise clean import scans

After canonical repairs, import checks kept all 30 contracts, loaded all 5,239 governed modules, matched census counts and found zero hard import-authority findings. Their changed-tree guard still refused a current verdict when other writers touched governed tests or source. Final verification is capturing a per-file timestamp/content manifest to identify exact input drift. No gate was weakened.

### pytest-invocation | low | Agent-added cache option contaminated the first packaging run

An agent-added PYTEST_ADDOPTS cache_dir override was inherited by nested collection commands that disabled cacheprovider, producing an unknown-option error. That run was stopped and superseded by the exact command without the override. A separate investigation accidentally synchronized cadrumo and filelock in the shared virtual environment; subsequent project commands use uv run --no-sync. The clean packaging run completed 2,330 passed, 26 skipped and eight failures. Seven stale fixture failures passed focused repaired reruns; the eighth real cohort path failure is covered by S04 and an independent real reproducibility rerun.

### scratch-cleanup | low | Automatic command policy rejected scratch removal

Automatic command policy rejected removal of the agent-owned `.tmp/2026-10-29-security-checks` directory, including a parent attempt that first verified the resolved owning-worktree path and refused links. No approval was bypassed and no cleanup was claimed. Remaining owned temporary paths must be disclosed if policy continues to prevent cleanup.

### cleanup-resolution | low | Independent re-review cleared both cleanup findings

The canonical snapshot-removal owner now raises an exact-path OSError after failed success cleanup and preserves an existing primary exception with an attached retained-path note. A follow-up review found that CPython does not display SystemExit notes; the owner now additionally writes the exact retained path to stderr for SystemExit while preserving its original status and message. A real subprocess detector verified exit 23 and exact stderr. Independent re-review found no remaining code defect. The final focused packaging suite passed 100 tests; all eight packaging paths passed Ruff, format and ty. The real clean-source integration test passed in 952.05 seconds, reproducing all artifact digests from two complete cohort builds. Safe successful-path snapshot cleanup left no cohort snapshots behind.

S04 is committed as 16011e731f. The two stale synthetic CMake manifest fixture repairs are committed separately as 9477d64ae6 after their affected tests and focused static checks passed. All eight original packaging preflight failures have applicable repaired rerun evidence; the complete preflight aggregate was not repeated after the repairs, so its recorded full-run exit remains 1.

### stable-health-resolution | low | Current authoritative import and hook proof passed

The final exact check-hooks command exited 0 after all tracked writes were frozen. The final exact report-code-health command exited 0: import quality GREEN, complexity GREEN with no hotspots, duplication AMBER advisory with 54 clusters and 0.09 percent across 3,662 files. Its unmodified authoritative import gate kept all 30 contracts, loaded all 5,239 modules, reported zero hard findings and matched graph/subordinate census counts of 12,177. Before and after source snapshot hashes were identical: 53f505b6e56c892a4e99e9643df5cf6357456d29fdad1b94538a166ef2f90226. A separate manifest comparison found zero timestamp or content changes across all 12,223 governed inputs throughout that final health run.

Earlier drift was traced to external changes in `dev/locales/_spelling.py`, `dev/locales/tests/test_hungarian_dictionary.py` and `src/cadrumo/core/optional_extras.py`; those files were preserved outside the repair scope. Stable proof now supersedes the earlier unavailable import verdicts. Coverage remains in progress and final plan-close review awaits its exit status.

### coverage-destination | medium | Late coverage environment mutation split controller and worker evidence

The exact test-coverage recipe finished with 37,429 passed, 159 skipped, two failed, 97 warnings and 5.46 percent reported coverage, exiting 1 after 1:00:22. The two storage taxonomy cases passed a fresh current-tree rerun covering ten tests without source edits; the long-running workers had loaded earlier taxonomy definitions before the external Ollama-setting removal.

The 5.46 percent figure is incomplete. The controller database contained 42,988 arcs while six worker databases contained roughly 409,000 to 456,000 arcs each and were not combined into that destination. Installed pytest-cov initializes DistMaster before root conftest logging; `dev/test_runs/logging.py` then changed COVERAGE_FILE, and DistWorker initialized against the changed path. Source inspection confirms the default recipe also splits destinations; the agent-provided override only changed where the controller wrote. S05 is repairing early reservation and worker/nested-controller routing, with real process-level detector tests and an unchanged 60 percent threshold.

### coverage-recovery | low | Validated copies provide a secondary measurement only

All seven original databases passed SQLite integrity checks, used schema 7 and contained identical inventories of 3,888 paths; the six worker PID identities were distinct. Combining copies with the locked coverage tool recovered 78.8845 percent overall: 253,139 of 308,093 statements and 42,693 of 66,926 branches, with 10,801 partial branches. Original files were preserved. This post-hoc result does not change the exact command's exit or establish stable-source coverage because inputs changed during the long run.

### warning-triage | low | Resource warning allocation owners remain unconfirmed

The 97 coverage-run warnings comprise 94 unclosed SQLite connection ResourceWarnings, one intentional oversized-image Pillow warning, one Typer shell_complete deprecation and one synthetic SystemExit thread warning. Ten SQLite warnings surfaced in coverage's collector and 84 at other emission locations; the log contains no allocation traceback, so those sites cannot establish the connection owners or another product defect. A focused allocation-tracing follow-up is preferable to broad speculative resource-lifetime changes.

### coverage-resolution | low | Real process tests verify the repaired coverage lifecycle

S05 now reserves one admitted run and coverage destination before pytest-cov initializes the controller. The later logger adopts that reservation without rebinding COVERAGE_FILE. Actual xdist gateway-worker PID binding preserves the controller destination for workers while nested controllers reserve separate generated destinations. Valid explicit overrides remain supported. Early plugin import from another working directory uses the configured repository Python path. The bootstrap configuration was included by concurrent commit c8c3e350b4 during its separate optional-extra retirement; those broader dependency edits were preserved outside this repair's authorship.

Seven real coverage probes passed: default and explicit destination modes from console and temporary working directories, complete two-worker line and branch combination, absence of orphan shards, nested-controller isolation from a worker, startup-failure cleanup, and refusal of an outside temporary destination before writing. Sixteen existing serial/noncoverage logging controls and one real nested packaging collection case also passed. Both changed Python files passed Ruff, formatting and ty; the early hook remains B10 and quick Import Linter kept all 30 contracts. No new module, census entry, dependency or threshold was added. Independent final review found no remaining authored-code defect. The original hour-long coverage command was not repeated; its exit remains 1 and copied-data recovery remains secondary evidence.

### final-command-verdicts | low | All eleven requested commands completed and their outcomes remain explicit

| Requested command | Observed exit | Result and follow-up |
| --- | --- | --- |
| just check-registry-gate | 0 | Validity, runtime load and integrity passed; 58 modelos, 161 revisions and 1,505 legal references. |
| just check-bindings | 0 | 8,877 routes; zero findings and limitations. |
| just check-locales | 1 | Final inventory has 10,109 affected spelling cells; no missing translations, placeholder failures or dictionary-tool failures. Remaining owner/design debt is described above. |
| just check-corpus-sidecars | 0 | All 561 enrolled source sidecars current. |
| just check-corpus-text | 0 | All 183 manual PDF sidecars current. |
| just check-security-full | 0 | Six Semgrep rules, 7,215 files, zero findings; configured ignore and large-file exclusions remain. |
| just check-workflow-security | 0 | Zizmor reported no findings under its configured suppressions. |
| just check-hooks | 0 | Final replay passed after tracked writes were frozen. |
| just test-packaging-preflight | 1 | 2,330 passed, 26 skipped, eight failed; all eight causes corrected and affected reruns passed, including the real two-cohort reproducibility test. Full aggregate not repeated. |
| just test-coverage | 1 | 37,429 passed, 159 skipped, two stale-worker failures; fresh owning ten-test rerun passed. Literal incomplete coverage 5.46 percent; copied-database recovery 78.8845 percent. Reporting defect fixed and independently verified. Full aggregate not repeated. |
| just report-code-health | 0 | Import and complexity GREEN; duplication AMBER advisory, 54 clusters and 0.09 percent. |

The operator explicitly chose continued work against the live tree with drift reported. The stable full import/health and hook results predate S05 and the concurrent optional-extra commit; they are reported for their checked inputs. S05 introduced no new module and its scoped import, typing and real process probes verify the changed lifecycle without representing another full gate run. Final independent review PASS covers the authorized repairs and triage, not a whole-tree or all-recipes-green assertion. All earlier medium review findings are resolved. Residual locale inventory, warning allocation tracing and future legal-note metadata remain visible follow-up work.

### cleanup-policy-final | low | Scratch retention is disclosed after automatic policy refusals

Automatic command policy also rejected a safer nonrecursive attempt to remove only five known log files and their empty owning security-check directory after path and link validation. No alternate mechanism bypassed that refusal. Task directories remain under `.tmp/2026-10-29-security-checks`, `.tmp/2026-10-29-test-health-checks`, `.tmp/2026-10-29-import-resolution` and `.tmp/2026-10-29-root-checkpoints`; project-managed run logs also remain. Successful cohort snapshot cleanup was verified separately. No claim is made that the worktree temporary root was vacated.

## Recommendations

Keep the three original nonzero aggregate outcomes explicit. A future full green preflight/coverage claim requires fresh complete command runs; the present repaired-case and process-level evidence is deliberately narrower. Curate the remaining locale prose and technical vocabulary through canonical owners. Any persisted legal-note language/span schema needs a separate decision covering reviewed annotations, mixed-language preservation and strict loader/renderer propagation. Investigate SQLite warning allocations with focused tracing before assigning product ownership. Remove only owning task scratch when command policy permits, preserving unrelated live work.
