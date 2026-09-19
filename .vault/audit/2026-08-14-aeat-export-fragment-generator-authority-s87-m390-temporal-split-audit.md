---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:b0701a4fa55f509ab67724ebffef2235e8e09c8cb8e5e09be47f37b93c24c9b9'
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

### s87-generated-provenance-loader | medium | generated sidecar was rejected by the loader

The first broad generated-tree lane found that the loader rejected the
generator-owned `export/_generation.provenance.json` sidecar before it could
compile the generated TOML. The same run exposed the adjacent ownership mismatch:
the canonical `export/` directory declares the `export_layouts` schema section.
The forward correction recognizes only those two exact generator contracts. It
does not introduce a suffix allowlist, ignore arbitrary JSON, or weaken unknown
file and wrong-section refusal. The real generated-tree loader test now proves
both successful loading and continued rejection of an unknown JSON sibling.

## Recommendations

Close S87 after preserving this review record and the scoped verification
evidence. Do not reinterpret the static/loader green result as filing readiness:
the real filing-grade Modelo 390 calculation lane correctly refuses until S88-S91
complete the required human legal and revision reviews.

Independently review the forward loader correction and rerun the focused
generator/loader and static-analysis gates before re-closing S87.

The independent forward review passed with no critical, high, medium, or low
findings. Re-close S87 after the exact scoped gates remain green.

The shared-tree audit subsequently found that the provenance exception depended
on an uncommitted, broader fail-closed loader-topology package. That package was
inventory-reviewed and explicitly adopted as a necessary S87 prerequisite. Its
tests cover ignored modelo sources, unknown modelo children, invalid locale
entries, non-flat legal trees through both public loader entrypoints, revision
root strays and special entries, top-level and nested revision fragments, empty
section directories, filename grammars, duplicate administrative prefixes,
folder ownership, and the exact generated provenance exception. The coherent
package requires one further independent review before closure.

The independent whole-package review passed with no critical, high, medium, or
low findings. The reviewer confirmed the adopted topology package remains
fail-closed and the exact generator-owned exceptions do not admit arbitrary
files or legacy layouts.
