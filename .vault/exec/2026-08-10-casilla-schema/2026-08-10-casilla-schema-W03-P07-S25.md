---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:7cb427ead1bca4323c831046a375aa9af02c804dd6404e4120265f337ed757d6'
step_id: 'S25'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# implement the owner-ruled progress counts: typed state plus counts against the named manifest denominator, UNDEFINED when no manifest exists, never a bare percentage

## Scope

- `src/cadrumo/application/modelo/`

## Description

- Add the core `ModeloWorkProgressState` vocabulary with complete, in-progress, blocked, and undefined states.
- Add frozen progress and denominator records to `ModeloWorkReview`, naming the calculation-completeness manifest by kind, registry revision, and source reference.
- Count only persisted, non-empty observations whose casilla ids occur in that revision manifest.
- Derive complete and blocked states from the latest persisted verification verdict while refusing a complete state whose manifest members have not all materialised.
- Prove manifest-bearing, manifest-less, partial, blocked, and verified-complete behavior through bundled registry data and real encrypted repositories.
- Gate the complete review payload against forbidden ratio tokens in field names and refuse unnamed or impossible counts at model validation.

## Outcome

S25 now exposes one facade-exported progress record on the canonical modelo work review producer. Manifest-bearing work reports materialised and target counts against an explicit revision-bound denominator. Manifest-less M189 work reports UNDEFINED with no counts or denominator. Real persisted M130 revisions exercise zero, partial, blocked, and complete outcomes without a percentage field or ratio-named field.

Focused verification passed: 7 modelo work review tests, Ruff formatting and lint over the five owned Python surfaces, BasedPyright with 0 errors, 0 warnings and 0 notes, focused collection of all 7 tests, facade import execution through `uv run --no-sync python`, and focused `git diff --check`. The payload field-name gate recursively inspects the emitted `ModeloWorkReview` JSON schema. `vaultspec-core vault check all` exited zero with this execution record clean; its standing unrelated warning inventory remained visible and untouched.

The gate-bite proof temporarily changed the no-manifest producer branch from UNDEFINED to IN_PROGRESS. The real M189 storage test failed in `ModeloWorkProgress` validation because a defined state lacked counts and a named denominator. The original UNDEFINED branch was restored, after which the focused suite passed.

A formal read-only review reported no CRITICAL or HIGH findings. Its initial MEDIUM finding about payload-gate scope was closed by recursively inspecting the complete review JSON schema, and its LOW finding about partial-count evidence was closed by persisting exactly one manifest observation. Follow-up review found no remaining findings.

## Notes

The initial inventory contained six unrelated modified paths and no S25 collision. Peer churn continued during execution; all unrelated source, tests, Vault documents, and generated surfaces were preserved. The owned facade additions were inspected against their live diffs before validation.

A combined focused-plus-import-hygiene pytest invocation exceeded the 120-second command boundary and its exact process tree then exited; no result is claimed for that broader gate. The separately executed S25 focused suite and static gates are green.

Delivery raced after verification. Commit `d6ae28688da5342650e37615d9b735ff59848b22` landed all five S25 production/test paths, but the same broad commit also absorbed unrelated S89 config-CLI, ledger, TUI, aggregation, and LLM work. Commit `5ca9be782d4f0349a52cf9b92f6d97790fc84ff5` then landed this execution record alone. This violates the campaign's one-Step/one-atomic-commit discipline and the execution record does not claim otherwise. The violation is historical and must not be concealed by rewriting or splitting published history.

Carry-forward: the S25 technical implementation and its original execution evidence are already landed. Final S25 closure is therefore limited to the plan-state change, the formal review audit, and this execution-record correction; it must not reopen or modify the source/test payload merely to manufacture atomicity after the fact. Until that closure lands, `vaultspec-core status casilla-schema` correctly leaves S25 open. No staging, commit, history rewrite, or source/test mutation was performed by this correction.
