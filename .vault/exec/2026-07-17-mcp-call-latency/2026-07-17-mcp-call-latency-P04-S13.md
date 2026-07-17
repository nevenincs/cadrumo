---
tags:
  - '#exec'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S13'
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
     The S13 and 2026-07-17-mcp-call-latency-plan placeholders are machine-filled by
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
     The Replace the unbounded anyio thread-pool spawn with an explicit concurrency cap or request queue bounding concurrent in-process calls and ## Scope

- `src/cadrumo/entrypoints/mcp/_call_runtime.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Replace the unbounded anyio thread-pool spawn with an explicit concurrency cap or request queue bounding concurrent in-process calls

## Scope

- `src/cadrumo/entrypoints/mcp/_call_runtime.py`

## Description

- Add `serving_capacity_limiter` to `_call_runtime.py`: a lazily-built, cached process-wide anyio capacity limiter sized from settings, bounding how many MCP calls are dispatched off the event loop at once and replacing the anyio default (40 threads).
- Add the `cadrumo_mcp_serving_concurrency` setting (default 4, ge 1) to central config so the cap is an operator-tunable field, not an inline literal.
- Pass the shared limiter to every `run_sync` in the server's off-loop wrapper and the bulk-resource resolver, so the explicit cap governs both the supervised subprocess spawn (robustness research F3) and the warm in-process worker pool.

## Outcome

Concurrent off-loop dispatch is bounded. A real-behavior test fires three times the cap of concurrent `run_sync` tasks through the shared limiter and observes the live-count peak equal exactly the cap - proving the bound both holds (never exceeded) and binds (actually reached), not the anyio default of 40. The limiter is a settings-sized singleton reused across calls. The settings-conformance and loop-responsiveness suites stay green.

## Notes

The cap is the outer bound shared by both transports; the warm in-process path additionally serialises on its stdout capture lock, so in-process calls run effectively one at a time regardless of the cap, while up to `cap` supervised subprocesses may run concurrently. Default 4 suits the single-operator desktop client and is raisable for a multi-client host.

Review remediation (MEDIUM-1): the single-file capture serialisation is now backed by a bounded wait plus wedge detection, so a slow or hung in-process call no longer blocks the transport indefinitely - it degrades warm-eligible calls to the subprocess transport with a warning Notice until the capture frees. Two new settings govern it: `cadrumo_mcp_warm_capture_wait_seconds` (the bounded acquire) and `cadrumo_mcp_wedge_threshold_seconds` (the wedge declaration). The S13 `serving_capacity_limiter` also hoisted its `core.config` import to module level as part of the lazy-import gate remediation.
