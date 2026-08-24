---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:cac05e258483c92b0c5e4ae50235bbf29422c891a5635e419cacbcfbd652eba4'
step_id: 'S76'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# Correct the aggregate filing-capability worklist assertion and report so terminal no-authority refusals such as Modelo 136 are never described as requiring an authorable layout, retain named owners for authorable gaps, and pass the terminal-versus-owner distinction to S29.

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py`
- `.vault/reference/`

## Description

- Run Vaultspec-RAG semantic discovery and exact-symbol confirmation across the filing-capability worklist, the export-exemption validator, and the governing closure artifacts.
- Confirm that the worklist classifier is the one canonical reporting surface; retain the validator as its distinct registry refusal mechanism rather than redeclaring either responsibility.
- Replace unstructured blocker prose with a fail-closed disposition report that distinguishes terminal no-authority refusals from owner-routed authorable gaps.
- Anchor Modelo 136's terminal disposition to its reviewed visual-form versus machine-contract source condition; give every authorable row its applicable temporal, source/casilla, and export owner route.
- Update the Modelo 136 evidence reference with the aggregate classification and its self-invalidating reconsideration condition.
- Add a real-source mutation proving a machine-readable Modelo 136 authority removes the terminal label and produces a named-owner gap instead.

## Outcome

The capability worklist still refuses every revision that cannot emit, but it no longer claims that every such row can be cleared by authoring a fixed-width layout. `136/2026` reports `TERMINAL NO-AUTHORITY`: the current reviewed source set has a visual approved form and no registered record-design, XSD, or dictionary contract. The terminal label is a present-evidence disposition, not a permanent exclusion; a qualifying source removes it and routes the row to the canonical export owner.

Every other non-emitting row reports `AUTHORABLE GAP` and one or more existing owner routes: temporal coverage, source-casilla integration, or export-fragment authority. Modelo 721 is expressly not inherited into Modelo 136's terminal category because its separately reviewed structured XML/SOAP authority is an authorable extension.

Focused owner/disposition regressions passed: 2 tests. The expected capability-worklist refusal remained red with the same 14 non-emitting revisions, now with terminal-versus-owner diagnostics. Ruff passed for the changed module.

## Notes

No registry definition, corpus source, filing writer, or runtime validator changed. The Vaultspec-RAG redeclaration audit found no substitutable duplicate of the classifier: `validate_export_exemption_declarations` enforces snapshot/build refusal and has no ownership-report responsibility.

A feature-index regeneration also saw concurrent S73, S75, S81, and S82 artifacts. Its mixed index delta remains outside this Step's scoped commit; the index owner can regenerate it after concurrent records settle.
