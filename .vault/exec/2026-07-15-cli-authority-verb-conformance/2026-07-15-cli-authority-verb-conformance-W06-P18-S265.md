---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S265'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run scoped and unscoped registry query suites across historical as-of boundaries and projection parity

## Scope

- `src/cadrumo/domain/calculations/registry/tests/`
- `src/cadrumo/application/modelo/tests/`

## Description

- Run the registry query suite and the whole modelo application suite under an explicit execution-marker selection covering both lanes.
- Confirm a non-zero collected count before reading the result line.
- Run the whole registry test directory as a second pass, since the scope line names the directory while the implementing Step named only the query suite inside it, and a named directory should not be left unrun.
- Collect the serial and OS-keychain remainders.

## Outcome

Verdict: SATISFIED.

First command: `uv run --no-sync pytest -q -rs -p no:cacheprovider -n auto --dist=loadfile --tb=short -m "(unit or integration) and not serial and not os_keychain and not external_tool and not perf" src/cadrumo/domain/calculations/registry/tests/test_queries.py src/cadrumo/application/modelo/tests`.

Collected 1223, passed 1223, failed 0, skipped 0. Exit line: `1223 passed in 489.37s (0:08:09)`, exit code 0. HEAD at run time was `f6449026877811c46e9311270b6d95c2f50c8849`. The serial and OS-keychain selections both collected nothing.

Second command, the whole registry test directory: same selection over `src/cadrumo/domain/calculations/registry/tests`. Collected 3030, passed 3026, failed 4. Exit line: `4 failed, 3026 passed, 2 warnings in 166.60s (0:02:46)`, exit code 1, at HEAD `f6b057f229bfaa187f82071316105d1facfbd67e`. The serial selection collected nothing.

None of those four is a query-surface failure and none survives triage. Three are the cross-domain snapshot registration cases for the renta-free import path; re-run sequentially they pass, `3 passed, 3027 deselected in 24.99s`, which is the loader-cache race that registry suites show under workers rather than a regression. The fourth is the bundled-root disk-cache case, which spawns real pytest subprocesses and failed them on a validation error for the external-constants model; both the external-constants module and its data file are uncommitted in the shared worktree, and the model imports cleanly on a later read, so that failure is another agent's mid-edit state passing through a subprocess rather than a defect in the cache behaviour.

The as-of claim is the load-bearing one and it is proven in the strong direction: the implementing Step's requirement was that every accepted as-of argument either participates in revision validity selection or is rejected explicitly, rather than being silently ignored, and the query suite exercises both the historical boundaries and the invalid-window refusal. Scoped and unscoped resolution are asserted for parity while the deliberate distinction between the bindings report and the casilla-detail report is preserved rather than collapsed.

## Notes

The semantic code index was degraded for the whole of this wave, reporting itself healthy while carrying roughly a fifth of the tree. No conclusion in this record rests on a semantic search result.

Registry-suite failures under parallel workers are usually a loader-cache race rather than a regression. That guidance held: the three cross-domain registration failures in the second pass reproduced only under workers and passed cleanly with none, so no regression was recorded against them.

## Re-measurement at HEAD `1437055950`

Verdict: SATISFIED.

Combined command over both scope directories: `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/ src/cadrumo/application/modelo/tests/ -n auto --dist=loadfile -m "not os_keychain" -q --tb=no --no-header`.

Collected 4399, passed 4399, failed 0, skipped 0. Exit line: `4399 passed, 2 warnings in 530.99s`, exit code 0. HEAD at run time was `1437055950f5b8f4082d323578294fc32ad1d9fe`. The four worker-artefact failures from the prior second pass (three cross-domain registration races, one external-constants model validation against uncommitted peer work) are absent: the cross-domain registration cases are stable with workers at this HEAD and the external-constants file is now committed.

## Post-freeze re-measurement at HEAD `9c4b780e1aed5c41938e16eaed2eccdcbddd3cfd`

Verdict: SATISFIED. Count unchanged at 4399; four changed registry files did not add or remove tests.

Command: `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/ src/cadrumo/application/modelo/tests/ -n auto --dist=loadfile -m "not os_keychain" -q --tb=no --no-header`.

Collected 4399, passed 4399, failed 0, skipped 0. Exit line: `4399 passed, 2 warnings in 789.89s`, exit code 0. The four previously-uncommitted files now committed (`_classification_coherence.py`, `_export.py`, `tests/test_export.py`, `__init__.py`) introduced no regressions and the test count is identical to the prior reading at `1437055950`. The as-of invariant is unaffected.
