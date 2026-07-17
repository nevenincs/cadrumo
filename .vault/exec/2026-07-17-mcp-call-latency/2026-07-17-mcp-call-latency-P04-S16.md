---
tags:
  - '#exec'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S16'
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
     The S16 and 2026-07-17-mcp-call-latency-plan placeholders are machine-filled by
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
     The Prove CLI-versus-MCP envelope parity with a real-behavior oracle asserting byte-identical envelopes across the subprocess and in-process transports so D4 does not fork result shapes and ## Scope

- `src/cadrumo/entrypoints/mcp/tests/test_inprocess_envelope_parity.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove CLI-versus-MCP envelope parity with a real-behavior oracle asserting byte-identical envelopes across the subprocess and in-process transports so D4 does not fork result shapes

## Scope

- `src/cadrumo/entrypoints/mcp/tests/test_inprocess_envelope_parity.py`

## Description

- Add `test_inprocess_envelope_parity.py`: a real-behavior oracle running the same verb with the same arguments through both real transports - a genuine `aeat` subprocess (`_run_subprocess_tool`) and the warm in-process runtime (`_run_inprocess_tool`) - and asserting the emitted envelopes are byte-for-byte identical after canonical JSON serialisation.
- Cover the stdout success document with a read verb needing no active profile (`contract`).
- Cover the stderr error document with a verb that refuses with no active profile (`review.queue`), so parity holds on the error boundary path too.

## Outcome

Both transports emit byte-identical envelopes. The success envelope (`contract`) and the refusal envelope (`review.queue`, rendered by the CLI error boundary to stderr) match exactly across the subprocess and warm in-process transports - D4 does not fork the result shape. Two tests pass against the real registry and filesystem, no mocks.

## Notes

The Cadrumo envelope carries no per-run fields (the error document's `trace_id` is null, not a per-call token), so the whole envelope is compared rather than an excluded subset; the test documents that a future per-run field would be excluded by name with a stated reason rather than the comparison being loosened. `overview.status` was rejected as the refusal probe because it renders a success landing card without a profile; `review.queue` refuses cleanly.
