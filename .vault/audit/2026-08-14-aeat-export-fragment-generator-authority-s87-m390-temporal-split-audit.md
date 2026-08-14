---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:40aba1a75c2a3549b087977c2a78022ac70d2a66bc87e01b2b85ccc66aaca3a8'
related:
  - "[[2026-08-14-registry-temporal-coverage-adr]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---



# `aeat-export-fragment-generator-authority` audit: `S87 Modelo 390 temporal split review`

## Scope

An independent Terra review compared the S87 implementation against the accepted
temporal-coverage decision, its architecture audit, and the approved plan row.
It inspected the complete Modelo 390 replacement tree, the source-catalogue cap,
the retired publication exception, and the focused regression gate. The review
checked annual selector disjointness, nested source isolation, deadline ownership,
RDL 4/2024 scope, unsupported-year refusal, canonical identity preservation, and
the prohibition on agent-authored operator attestations.

## Findings

### s87-empty-audit-record | low | review evidence had not yet been persisted

The implementation had passed its focused gates, but the scaffolded audit still
contained only template hints. This record now persists the independent verdict
and exact evidence boundary. No critical, high, or medium implementation finding
was identified.

### s87-temporal-source-contract | low | no open implementation finding

The reviewed tree contains exactly revisions `2022`, `2023`, `2024`, and `2025`.
Each uses one exact-year selector, validity window, deadline window, workbook
identity, and nested record-design source. The 2025 catalogue source ends on
2025-12-31. RDL 4/2024 article 1 occurs only in the 2024 revision. Revisions remain
`pending_review` with absent reviewer metadata, leaving S88-S91's human gates
intact. The dedicated selector, source, legal-scope, identity, refusal, loader,
and publication-matrix lane passed 33 tests; Ruff and BasedPyright were clean.

## Recommendations

Close S87 after preserving this review record and the scoped verification
evidence. Do not reinterpret the static/loader green result as filing readiness:
the real filing-grade Modelo 390 calculation lane correctly refuses until S88-S91
complete the required human legal and revision reviews.
