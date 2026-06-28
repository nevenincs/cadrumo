---
tags:
  - '#audit'
  - '#registry-applicability-boundary'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---

# `registry-applicability-boundary` audit: `applicability extraction boundary audit`

## Scope

Audited `src/aeat/domain/calculations/registry/_applicability.py` as a
large registry production module that owns modelo applicability, taxpayer
tax-route derivation, and Modelo 202 modality derivation.

## Findings

### High

- `_applicability.py` is 1,455 working-tree lines and combines enum
  definitions, profile fact predicates, applicability DTOs, rule
  evaluation, legal-ref constants, the seed rule table, public rule-table
  accessors, taxpayer-model completeness logic, tax-route derivation, and
  Modelo 202 modality derivation.
- The current working tree contains formatting-only peer WIP throughout
  the module. This slice must not edit production code.
- `src/aeat/domain/calculations/registry/applicability.py` is already the
  focused public facade. Extraction must preserve that facade and the
  registry-root public re-exports.
- `test_applicability_canonical.py` pins `_MODELO_APPLICABILITY_RULES` as
  a single canonical assignment in `_applicability.py` and requires the
  facade's `derive_modelo_applicability` to be identity-equal to the
  domain implementation. Splitting the seed table or duplicating it in a
  helper module would violate current architecture.

### Medium

- Tax-route derivation is a small cohesive family:
  `TaxRoute`, `_TAX_ROUTE_FOR_ENTITY_TYPE`,
  `taxpayer_model_is_declared`, and `derive_tax_route`.
- Modelo 202 modality is a cohesive family with its own constants,
  `Modelo202Modality`, `Modelo202ModalityVerdict`, and
  `derive_modelo_202_modality`. It can move behind compatibility
  re-exports without changing the seed applicability table.
- The applicability DTOs and `ModeloApplicabilityRule.evaluate` are
  tightly coupled to legal-ref constants, profile gates, and the seed rule
  table. They should remain together until rule-table ownership is
  intentionally revisited.
- The seed rule table is data-heavy and central. Moving it is possible
  only if the canonical-definition test is revised in the same commit and
  the new module becomes the one true definition. That is an architectural
  change, not a mechanical cleanup.

### Low

- `_payer_fact_holds`, `_incomplete_applicability`, and
  `_undetermined_applicability` are helper functions, but they are
  load-bearing for rule evaluation and should not be extracted before the
  surrounding DTO/rule family is stable.

## Recommendations

1. Keep `registry/applicability.py` as the focused public facade.
2. Keep `_applicability.py` as the canonical rule-table owner unless a
   future ADR changes rule authoring and the canonical-definition test.
3. First safe extraction candidate: move tax-route derivation to a
   private helper module, preserving `_applicability.py` re-exports and
   public facade identity where applicable.
4. Second safe extraction candidate: move Modelo 202 modality derivation
   to a private helper module, preserving public imports from both
   `aeat.domain.calculations.registry` and
   `aeat.domain.calculations.registry.applicability`.
5. Leave `ModeloApplicabilityRule`, the seed rule table, legal-ref
   constants, incomplete verdict helpers, and
   `derive_modelo_applicability` in `_applicability.py` for now.
6. Do not introduce modelo-specific applicability modules or ad hoc rule
   registries. Applicability remains a generic registry-owned subsystem.
7. Each extraction commit should run `test_applicability_canonical.py`,
   `test_modelo_applicability.py`, application overview applicability
   tests, CLI Modelo 202 modality tests if modality moves, and public API
   boundary tests.

## Codification candidates

- **Source:** finding High-4.
  **Rule slug:** `registry-applicability-canonical-rule-table`.
  **Rule:** Applicability refactors must preserve exactly one canonical
  seed rule-table definition and the focused public facade unless an ADR
  changes rule authoring ownership.
