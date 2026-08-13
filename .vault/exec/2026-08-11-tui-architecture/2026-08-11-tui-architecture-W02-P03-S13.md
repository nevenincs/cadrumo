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
- Export all seven executor protocols through the sole public operation-platform facade.
- Exercise the public runtime-checkable protocols directly with complete structural implementations and independently incomplete surfaces.
- Preserve the semantic public callable names `phase_code`, `unit_code`, and `operand_type`, including keyword invocation and signature proof.

## Outcome

The new executor boundary gives application-owned executors only the capabilities accepted by D3 and D5. Event methods accept typed facts instead of complete `OperationEvent` records, so executors cannot manufacture supervisor-owned ordering or envelope revision. Confidential operands resolve only from canonical content digests into an explicitly requested Pydantic model type. Resources transfer through the canonical asynchronous-closeable contract and remain supervisor-owned until settlement.

Focused verification passed:

- `uv run ruff check src/cadrumo/application/operations/_executor.py` - passed.
- `uv run basedpyright src/cadrumo/application/operations/_executor.py` - passed with 0 errors, 0 warnings, and 0 notes.
- `uv run pytest -q src/cadrumo/application/operations/tests/test_contract_invariants.py src/cadrumo/application/operations/tests/test_facade.py` - 72 passed in 4.20 seconds.
- `uv run ruff check src/cadrumo/application/operations/_executor.py src/cadrumo/application/operations/__init__.py src/cadrumo/application/operations/tests/test_executor.py src/cadrumo/application/operations/tests/test_facade.py` - passed after review remediation.
- `uv run basedpyright src/cadrumo/application/operations/_executor.py src/cadrumo/application/operations/__init__.py src/cadrumo/application/operations/tests/test_executor.py` - passed with 0 errors, 0 warnings, and 0 notes.
- `uv run pytest -q -n 0 src/cadrumo/application/operations/tests/test_executor.py src/cadrumo/application/operations/tests/test_facade.py src/cadrumo/application/operations/tests/test_contract_invariants.py` - 74 passed in 1.19 seconds.
- Final callable-name remediation reran the same Ruff and basedpyright commands successfully, then the same focused pytest command passed 75 tests in 1.42 seconds.
- `uvx vaultspec-core vault check all` completed successfully during closeout with 1,349 pre-existing repository warnings and no failing check.

## Notes

Live code and vault semantic searches converged on `OperationCapabilities` and D3/D5 as the operation-specific authorities and on `core.async_cleanup.AsyncCloseable` as the canonical cleanup shape. Whole-file reads covered the operation models, capabilities, events, interactions, public facade, and asynchronous cleanup implementation. Targeted source search found no existing generic executor context, cancellation scope, operation event-emission port, or digest-addressed operand lookup to reuse. The new module therefore owns these missing application ports without duplicating observability capture, persistence, frontend, adapter, or cleanup execution.

Independent review initially found unreproduced RAG evidence, missing public-facade exposure, and missing direct protocol tests. After RAG admission recovered, live code search returned `_executor.py`, `_capabilities.py`, `core.async_cleanup`, and the operation facade as the top ownership cluster; live vault search returned the governing TUI architecture ADR, plan, and research. Whole-file reads and targeted search additionally covered core operation axes and existing application and adapter cleanup consumers. The incomplete-index caveat was handled by exact `rg` across cancellation, deadline, cleanup, secure-reference, executor, and event-emission terms. No competing executor-context authority or semantic duplicate was found.

One initial xdist-focused run ended in an unrelated worker internal error before tests ran. The explicit serial command then exposed the repository's required test marker, which was added. Final review adjudicated the previously preserved underscore-prefixed protocol parameters as a public callable regression. The exact three semantic names were restored and are now pinned by direct keyword use and signature inspection; the final serial focused run passed all 75 tests.

The existing S16 row owns behavioral refusal proofs for invalid phase emission and unowned resources; this contract-only step does not mirror those future supervisor and registry rules in tests. Unrelated shared-worktree changes, including concurrent formatting edits in existing operation tests, were preserved and excluded.
