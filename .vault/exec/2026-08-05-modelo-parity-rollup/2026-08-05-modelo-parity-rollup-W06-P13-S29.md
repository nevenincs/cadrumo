---
tags:
  - '#exec'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:481d1ad1c4a00730ab981f6de5cfe489c1942e349334dba967e6032c70ec6fe9'
step_id: 'S29'
related:
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
---
# Draft the SOL-bounded S16 rental source-contract research and a proposed ADR without changing fincas models, persistence, source readiness, or M100 0150 wiring

## Scope

- `.vault/research/2026-08-05-modelo-parity-rollup-s16-source-contract-research.md`
- `src/cadrumo/domain/fincas`
- `src/cadrumo/application/aggregation`
- `.vault/adr`

## Description

- Ran VaultSpec-RAG before discovery. Code RAG matched the explicit `fincas_source_readiness`, aggregate, model, and secure-source boundaries with current index `77,847`; vault RAG matched the accepted parity ADR, S16 addendum, and third SOL adjudication.
- Recorded the current persisted-record gap and the candidate source-contract questions in the S16 research addendum.
- Applied SOL's bounded decision: S16 production remains deferred. Only focused source-contract ADR/research and independent-oracle acquisition are authorized. The production-file set is empty.

## Outcome

Research and the ADR decision are complete. The user explicitly approved the ADR, and VaultSpec Core amended the existing accepted parity ADR in place with the SOL-bounded S16 rental source-contract boundary. S16 production remains deferred: the current `0150` producer stays manual, fincas source readiness stays false, and no registry, formula, binding, relation, profile, persistence, application, or `0150` wiring changed.

## Verification

- Source locators are recorded in the research body: `_models.py:225-311`, `_aggregates.py:267-311`, `_source_readiness.py:34-52`, and the official 2025 worked example at `source.pdf.extracted.md:12833`.
- No fincas model, SQL row, aggregate, resolver, source-readiness flag, formula, binding, relation, profile, or casilla file was changed.

## Notes

- RAG request references: code `25bb634a60a14a27883c63cb1303e3cf`, code `c81c6a7b49e94822928fc66875abc03f`, vault `4599bd9f55c84bfbbaea8331bde789e6`.
- This execution record closes S29 research and ADR authoring only. It does not certify M100 `0150` or authorize production implementation. The concurrent registry/application-wide IRP invocation-shape remediation remains outside this tranche.
