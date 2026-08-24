---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:4534e99914bc625ccfa741c7dd9fe0b5b2205415ea18dabdafc5a633569d772b'
step_id: 'S38'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Prove dry-run parity, committed-unit accounting, child provenance references, unsupported cancellation and deadline claims, and cleanup before settlement

## Scope

- `src/cadrumo/application/live/tests/test_filed_history_operation.py`

## Description

- Consolidate the filed-history executor and facade proofs into the plan-owned canonical test module.
- Delete the two fragmented predecessor test modules without a shim, forwarding import, or duplicate copy.
- Exercise the registered definition through the production supervisor, filesystem journal, filesystem lease repository, encrypted secure-reference repository, and encrypted sync-run repository.
- Assert dry-run discovery-unit parity and effect `NONE`, committed-unit `UPDATED` and `PARTIAL` accounting, and a resolvable domain-owned sync-run reference.
- Assert cancellation is refused, execution and cleanup deadlines remain absent, and the cleanup phase precedes the operation settlement phase.
- Retain public-facade origin, privacy, uniqueness, resolution, and lazy-import proofs in the same canonical home.

## Outcome

The filed-history operation now has one test owner at `src/cadrumo/application/live/tests/test_filed_history_operation.py`. The prior executor and facade modules were removed rather than bridged. The canonical suite proves the operation declaration and durable runtime agree that cancellation is unsupported and no deadline exists, preview and normal execution walk the same fixture-backed production discovery unit while preview records no unknown effect, and cleanup is durably ordered before settlement.

The completed-run child reference is produced by the canonical sync-run writer, resolves through the real encrypted repository to the exact stored record, and is the same reference returned by the filed-history result boundary. Committed reference accounting settles `UPDATED`, while the same committed result plus a scoped stage failure settles `PARTIAL`; refusal-only and dry-run results settle `NONE`.

Focused Ruff and the twelve-test integration module pass. The execution record was scaffolded through `vaultspec-core`; the coordinator-owned plan checkbox was intentionally not mutated.

## Notes

The first focused run exposed that an inspected snapshot retains only its latest committed event batch. The proof was corrected to replay the authoritative durable event stream before asserting whole-operation parity. No production behavior, mock, monkeypatch, skip, xfail, compatibility bridge, or alternate test home was added.
