---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:f17419c6a9df72852f7532c2365f10092458688ae3bfe934979c0d49822f7964'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `tui-architecture` audit: `s13 review`

## Scope

Independent review of `W02.P03.S13`, limited to the executor/context protocols, their canonical dependencies, public operation facade, execution record, and governing architecture evidence.

## Findings

### rag-grounding | critical | Fresh mandatory semantic grounding is unavailable

The required live vault search returned `quiesce_admission_closed`. The execution record states that earlier semantic searches succeeded, but this independent review cannot verify current canonical authority or overlap through the mandatory discovery channel. Under the repository's fail-closed RAG rule, S13 cannot be approved until the service is healthy and the binding sources and overlap search are re-read live.

### protocol-proof | high | No test imports or exercises the new executor contracts

The focused pytest command runs only the pre-existing contract-invariant and facade suites; neither imports `_executor.py`. Ruff and basedpyright establish syntax and static typing, but there is no evidence for runtime-checkable protocol behavior, method/property shape, generic request/result typing at the runtime boundary, or the absence of unintended public capabilities. The step therefore has zero mutation-sensitive behavioral proof of its authored surface.

### facade-boundary | high | Application executors cannot consume the new contracts through the sole public facade

The seven executor/context protocols are absent from `application.operations.__init__`. Future application-owned executors would have to import the private `_executor` module, conflicting with the accepted sole-public-facade boundary and the established S11 rule against private operation imports. The execution record's facade test remains green precisely because its exact export expectation was not updated and never sees S13.

### authority-shape | low | The protocol surface itself preserves supervisor directionality

The executor receives read-only identity/deadline views and narrow cancellation acknowledgement, typed fact emission, digest-addressed operand resolution, and canonical `AsyncCloseable` ownership transfer. It has no event identity, revision, sequence, timestamp, persistence, lifecycle mutation, terminal receipt, or settlement method. No frontend or adapter type is imported.

## Recommendations

- Re-run live code and vault RAG after service recovery and record the exact governing and overlap results.
- Add real production-import tests for the public executor contracts and runtime protocol behavior without mocks, fakes, patches, or mirrored contract logic.
- Export the approved S13 contracts from the sole `application.operations` facade and update its exact export/boundary tests.
- Record and run focused pytest, Ruff, and basedpyright gates that include every S13-authored and amended file.

## Final re-review

### rag-grounding-closure | low | Live combined semantic discovery closes the CRITICAL finding

The service is healthy and live combined discovery returns the executor module, sole facade, direct tests, governing ADR, and plan as the ownership cluster. Together with the recorded targeted overlap adjudication, this closes the RAG blocker.

### protocol-proof-closure | low | Direct public imports exercise all seven runtime protocols

The new focused suite imports every protocol from the public facade, accepts a complete structural implementation, invokes cancellation, operand lookup, cleanup transfer, and every event-emission method, and rejects independently incomplete surfaces. The execution record reports 74 tests passing with clean Ruff and basedpyright. The original missing-proof HIGH is closed.

### facade-boundary-closure | low | All seven contracts are exported and exact facade topology is updated

The facade imports and lists all seven executor contracts, while the exact import-boundary assertion now includes only `_executor` in addition to the previously approved owners. The original facade HIGH is closed.

### public-parameter-names | high | Underscore renames leak implementation-warning names into the public protocol

The current production diff renames `phase_code`, keyword-only `unit_code`, and `operand_type` to `_phase_code`, `_unit_code`, and `_operand_type`. These are public protocol parameter names, not private implementation locals. In particular, the intended `progress(..., unit_code=...)` call now fails against the declared contract, while the direct test mirrors `_unit_code` and omits that argument, so the 74-test gate cannot detect the regression. Restore semantic public names and use a lint-safe protocol declaration without weakening or mirroring the callable contract; add keyword invocation coverage for all named parameters.

Final verdict: FAIL. One HIGH finding remains; no CRITICAL or MEDIUM findings remain.

## Callable-name re-review

### public-parameter-names-closure | low | Semantic names and keyword proof close the final HIGH

The public protocols again declare `phase_code`, keyword-only `unit_code`, and `operand_type`. The direct suite invokes `unit_code` by keyword and pins the production signatures, preventing recurrence of the underscore-name regression. The execution record reports the exact focused suite at 75 passing with the same Ruff and basedpyright commands clean.

Final verdict: PASS. No CRITICAL, HIGH, or MEDIUM findings remain.
