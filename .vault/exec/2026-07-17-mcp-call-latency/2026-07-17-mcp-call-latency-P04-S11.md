---
tags:
  - '#exec'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S11'
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
     The S11 and 2026-07-17-mcp-call-latency-plan placeholders are machine-filled by
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
     The Add an in-process verb dispatch path that runs the already-importable per-verb command functions and envelope builders in one warm runtime instead of spawning a fresh aeat subprocess and ## Scope

- `src/cadrumo/entrypoints/mcp/_inprocess.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add an in-process verb dispatch path that runs the already-importable per-verb command functions and envelope builders in one warm runtime instead of spawning a fresh aeat subprocess

## Scope

- `src/cadrumo/entrypoints/mcp/_inprocess.py`

## Description

- Add `_inprocess.py`: a warm in-process CLI runtime that serves READ and MUTATE verbs without spawning a fresh `aeat` subprocess, keeping the LIVE (AEAT-sede / open-world) family on the supervised subprocess by design.
- Invoke the real Typer app through `get_command(app).main(argv_tail, standalone_mode=True)` and catch the terminating `SystemExit`, so the same command functions, the same envelope emitters, and the same per-callback error boundary run identically; only the process death is replaced by a caught exit.
- Capture stdout and stderr under a module `_CAPTURE_LOCK` so no CLI output reaches the MCP JSON-RPC pipe and two concurrent in-process calls cannot interleave their redirects of the process-global streams.
- Add `parse_cli_envelope`, the single transport-neutral parser both the subprocess and in-process paths feed a completed run through, so the two transports cannot fork the result shape.
- Add `dispatch_verb_in_process`, reconstructing the argv from the per-verb input schema via the same `cli_argv_for` the subprocess path uses.
- Add `tier_runs_in_process` declaring the transport split (LIVE stays subprocess).

## Outcome

`_inprocess.py` runs the genuine CLI pipeline in-process and returns a completed run whose captured stdout parses to a valid envelope. Seven real-behavior tests pass: the transport-split predicate, an `app contract` read-only verb emitting a `command: contract` success envelope through the runtime, schema-driven argv reconstruction, and the parser's success/error/non-zero-exit/non-JSON branches. No mocks, stubs, or monkeypatch.

## Notes

The CLI writes its envelope to the process-global `sys.stdout`, which over the stdio transport is the client pipe; this is why the capture is serialised under a lock rather than run concurrently. The byte-for-byte parity against the live subprocess transport is proven separately in the S16 parity oracle; this Step proves only that the in-process runtime produces a valid envelope of the expected shape.
