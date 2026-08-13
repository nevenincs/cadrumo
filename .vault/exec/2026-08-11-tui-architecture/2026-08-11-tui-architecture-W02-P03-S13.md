---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:9bdbc7a1d0e37ea7103f8d3271fcb872ea6edf8c75dd15d910a62278a9429ebf'
step_id: 'S13'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S13 and 2026-08-11-tui-architecture-plan placeholders are machine-filled by
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
     The Define executor context, cancellation scope, deadline access, event emission, secure operand lookup, and cleanup ownership and ## Scope

- `src/cadrumo/application/operations/_executor.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Define executor context, cancellation scope, deadline access, event emission, secure operand lookup, and cleanup ownership

## Scope

- `src/cadrumo/application/operations/_executor.py`

## Description

- Define the application-owned executor and invocation-context protocols.
- Separate cooperative cancellation, deadline access, typed event facts, secure operand lookup, and cleanup ownership into narrow supervisor-provided ports.
- Reuse `AsyncCloseable`, `ContentDigest`, and the existing operation identity, request, event-code, diagnostic-reference, severity, effect, and result-reference authorities.
- Keep event identity, revision, sequence, timestamp, persistence, lifecycle mutation, and terminal settlement outside executor control.

## Outcome

The new executor boundary gives application-owned executors only the capabilities accepted by D3 and D5. Event methods accept typed facts instead of complete `OperationEvent` records, so executors cannot manufacture supervisor-owned ordering or envelope revision. Confidential operands resolve only from canonical content digests into an explicitly requested Pydantic model type. Resources transfer through the canonical asynchronous-closeable contract and remain supervisor-owned until settlement.

Focused verification passed:

- `uv run ruff check src/cadrumo/application/operations/_executor.py` - passed.
- `uv run basedpyright src/cadrumo/application/operations/_executor.py` - passed with 0 errors, 0 warnings, and 0 notes.
- `uv run pytest -q src/cadrumo/application/operations/tests/test_contract_invariants.py src/cadrumo/application/operations/tests/test_facade.py` - 72 passed in 4.20 seconds.

## Notes

Live code and vault semantic searches converged on `OperationCapabilities` and D3/D5 as the operation-specific authorities and on `core.async_cleanup.AsyncCloseable` as the canonical cleanup shape. Whole-file reads covered the operation models, capabilities, events, interactions, public facade, and asynchronous cleanup implementation. Targeted source search found no existing generic executor context, cancellation scope, operation event-emission port, or digest-addressed operand lookup to reuse. The new module therefore owns these missing application ports without duplicating observability capture, persistence, frontend, adapter, or cleanup execution.

The existing S16 row owns behavioral refusal proofs for invalid phase emission and unowned resources; this contract-only step does not mirror those future supervisor and registry rules in tests. Unrelated shared-worktree changes, including concurrent formatting edits in existing operation tests, were preserved and excluded.
