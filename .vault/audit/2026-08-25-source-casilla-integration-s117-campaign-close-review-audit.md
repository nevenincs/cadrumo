---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:31a52bdb1f9e05d4349aaa90b5c3ba23cf7199d6756fd0ebdfa39891c6268509'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# `source-casilla-integration` audit: `S117 campaign close review`

## Scope

Formal review of the dedicated S117 campaign-close test against the accepted census authority, live discovery, expiry governance, and independent connected-proof composition. The review tests whether the gate proves the three plan predicates without duplicating a registry authority or manufacturing support.

## Findings

### ambient-expiry-clock | high | Fixed historical date would conceal future expired deferrals

The first implementation pinned the gate to 2026-08-25. That proved only the execution-day snapshot and would remain green after all dated deferrals expired on 2026-12-31. The implementation now uses the canonical current-date boundary, so an expired deferral makes the permanent close gate fail.

### hard-coded-census-counts | medium | Exact counts duplicated stronger identity equality

The first implementation treated 478 capabilities and 15 rows as pass criteria. Those counts were removed. The final gate compares the complete assigned identity set with live discovery and requires assignment cardinality equality, which proves the intended property without turning historical totals into authority.

### canonical-composition | pass | Final gate composes existing authorities without redeclaration

The final test delegates parsing, law-selected destination validation, locator correspondence, governance, discovery assignment, and live connected proof to the existing canonical functions. It adds no source taxonomy, census loader, proof authority, or registry declaration.

### final-re-review | pass | All three S117 predicates are durable and non-vacuous

Re-review found no critical, high, or medium issue. Expiry follows the current date; assigned and discovered identities are exactly equal and unique; connected census IDs must exactly equal the independently authored fixture IDs, and any future connected claim is validated through the canonical live proof authority. Existing mutation tests independently demonstrate refusal of disappearance, expiry, and proof-free promotion.

### verification | pass | Focused, full-suite, style, and Vaultspec gates pass

The focused campaign-close test passed once, the complete source-connectivity suite passed all 64 tests, Ruff passed over the new test and canonical check/proof modules, and the feature-scoped Vaultspec gate passed after annotations and the generated feature index were refreshed.

## Recommendations

- Close S117 only after its focused test, the full source-connectivity suite, Ruff, and feature-scoped Vaultspec gates pass on the final tree.
- Do not extend the 2026-12-31 deferrals mechanically; allow the permanent gate to refuse until each expired item is re-adjudicated.
