---
tags:
  - '#exec'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S18'
related:
  - "[[2026-07-17-mcp-call-latency-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace mcp-call-latency with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S18 and 2026-07-17-mcp-call-latency-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Add a durable serving-path benchmark driver that measures the research call table against isolated encrypted state and asserts the projected end-state thresholds as acceptance gates, warm calculate at or under three seconds subprocess and one point five seconds server with reads and simple writes sub-second in server mode and ## Scope

- `dev/packaging/serving_path_benchmark.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add a durable serving-path benchmark driver that measures the research call table against isolated encrypted state and asserts the projected end-state thresholds as acceptance gates, warm calculate at or under three seconds subprocess and one point five seconds server with reads and simple writes sub-second in server mode

## Scope

- `dev/packaging/serving_path_benchmark.py`

## Description

- Add `dev/packaging/serving_path_benchmark.py`, dual-use: a CLI entrypoint emitting a schema-versioned, environment-labelled JSON evidence document, and (with `--assert-gates`) a self-checking acceptance run.
- Measure the research call table in subprocess mode through the real editable-tree `aeat` executable, building the isolated encrypted environment (and its fresh passphrase) once: version, profile create, work create first-touch and warm, work calculate warm, modelo list warm.
- Measure warm server mode through the real D4 in-process runtime under a fresh env-isolated encrypted root: a read, a simple write, the first in-process calculate (one-time lazy-import cost, recorded not gated), the warm steady-state calculate, and a read driven through the full `build_server` SDK memory transport to confirm the MCP-surface framing overhead is negligible.
- Label every measurement with its environment (`editable-tree`) and record the research projections in a separate, explicitly-labelled block so no number is cross-compared unlabelled.
- Add `dev/packaging/tests/test_serving_path_benchmark.py` (integration, serial): run the benchmark once and assert the current-tree acceptance gates.

## Outcome

Gates (coordinator ruling: model A) all hold on the current tree. Measured table (editable-tree, Python 3.13.11, real serving path):

Subprocess (per-process source-import floor; only the cliff-gone gate binds):
- version 0.80s | profile create 4.43s | work create first-touch 18.75s (gate <= 25s, was 49.6s) | work create warm 7.73s | work calculate warm 8.23s | modelo list warm 6.11s

Server (warm in-process runtime, the campaign's real win):
- modelo list read 0.09s (gate <= 1s) | simple write 0.28s (gate <= 1s) | first in-process calculate 1.99s (recorded, not gated) | warm steady-state calculate 1.72s (gate <= 2.5s) | review.queue read via build_server memory transport 0.21s (gate <= 1s)

`ruff check` / `ruff format --check` / `ty check` clean on both files. The pytest gate passes: 5 passed in 52.25s. The CLI `--assert-gates` run exits 0 with empty `gate_failures`.

On the server warm-calculate bound: the research projected ~1.5s for a lighter baseline; the 16-input Modelo 200 oracle measures ~1.72s steady-state, which meets the operator's bar (sub-second reads/simple writes, low single-digit seconds at absolute worst for the heaviest calculation). The gate is 2.5s -- the honest steady-state plus slow-machine margin -- and the evidence records the projection, the measured value, and this rationale, so a regression from ~1.7s toward the gate stays visible in the recorded table even while the gate passes.

## Notes

The installed-cohort subprocess targets (warm calculate <= 3s, first-touch <= 5s) are deliberately NOT asserted here: the editable tree pays the full source-import floor per process (warm calculate 8.23s, first-touch 18.75s), 3-6x the installed-cohort projections. Those targets are S19's (re-run installed oracles) and S20's (rebuild the cohort) to prove against the built compiled wheel; the module docstring and this record state that dependency explicitly. The subprocess side here proves only that the 49.6s first-touch cliff is gone and that D1's per-storage-root verdict works (warm 7.73s < first-touch 18.75s).

The coordinator adjudicated the acceptance model before this landed: server-mode gates on the current tree, subprocess gated only on cliff-gone, server calculate at an honest 2.5s bound. No incidents; no scaffolds left in code.
