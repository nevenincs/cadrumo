---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-W09-P41-S208]]"
  - "[[2026-05-26-cross-domain-continuity-W09-P41-S252]]"
---

# cross-domain-continuity Code Review

Commit 5a63bb9da -- #215 Conjunta vs individual comparison surface (Marcos B1)

**Status: REVISION REQUIRED**

---

## Critical Question Answers

**Q1:** aeat app modelo work compare-taxation sub-verb. Correct verb-per-operation pattern.

**Q2:** Engine runs twice with identical inputs; injects declaration_type=2 (conjunta) and declaration_type=1 (individual). Delta = individual_resultado minus conjunta_resultado. The declaration_type binding is excluded from ProfileSourceResolver via caller_binding_ids.

**Q3:** TaxationComparisonResult is frozen pydantic v2, extra=forbid. WorkCompareTaxationResult registered under modelo.work.compare_taxation. Compliant.

**Q4:** HIGH gap see TCOMP-001. Equal-income dual-earner individual-wins test documented in test module docstring but not implemented.

**Q5:** Not applicable. Ephemeral over existing work unit; no wizard surface touched.

**Q6:** Four locale keys in es/en/ca/hu. Parity complete. TCOMP-003 for reason interpolation.

**Q7:** Marriage bindings flow through ProfileSourceResolver at runtime. Casilla 0461 evaluated when declaration_type=2 injected; formula 0179-renta-2025-reduccion-art-84-conjunta.toml applies EUR 3400 for matrimonio. Both dependencies consumed via registry mechanism without reimplementation.

---

## Findings

### TCOMP-001 | HIGH | Missing equal-income dual-earner test (anti-tautology gap)

The test module docstring declares scenario 2 as equal-income couple both spouses EUR 45000 individual winning. No such test exists. test_moderate_income_conjunta_recommended_via_art84_reduccion tests a SINGLE earner at 45k and asserts CONJUNTA. Correct for that profile but does not satisfy the sensitivity requirement.

A regression where CONJUNTA is always recommended would pass the current suite.

Fix: add test_equal_income_couple_individual_recommended asserting recommendation == TaxationRecommendation.INDIVIDUAL and delta_resultado < -1.

### TCOMP-002 | HIGH | Dual-earner individual comparison architecturally incomplete

compare_taxation_modes runs both paths with identical casilla inputs. The individual path uses the same casilla 0003 as the conjunta path. For a dual-earner couple the individual comparison requires two separate engine runs (one per spouse income) summed. For a sole-earner couple (spouse B = EUR 0) this is correct. For a dual-earner couple the individual run underestimates total individual tax.

The CLI help text does not communicate this constraint. An operator with EUR 45k + EUR 45k receives a comparison where the individual run taxes only EUR 45k, making individual appear cheaper by construction.

Fix options: (a) constrain to sole-earner profiles and raise TaxationComparisonError for dual-earner profiles; (b) accept --spouse-income and run a third engine pass; (c) document the single-primary-earner assumption in CLI help and surface a warning when stored profile carries renta_spouse income. Minimum: guard against silent misleading output.

### TCOMP-003 | MEDIUM | recommendation_reason hardcoded English in domain layer

TaxationComparisonResult.recommendation_reason is a raw English f-string. The CLI wraps via tr(cli.app.modelo.work.compare_taxation_recommendation_line, reason=...) but the reason slot always contains English. Spanish-locale operators see English in the reason clause.

Fix: move reason construction to CLI layer with per-case tr() keys per TaxationRecommendation value, or store a structured detail model with Decimal fields.

### TCOMP-004 | MEDIUM | Engine errors not caught at CLI layer

work_compare_taxation catches only WorkUnitNotFoundError and TaxationComparisonError. calculate_registry_snapshot can raise RegistryValidationError (missing binding, unknown key, constraint violation) which escapes uncaught. work calculate (line 3081) catches RegistryValidationError and routes via _missing_binding_guidance. Parity required.

Fix: add except RegistryValidationError handler in work_compare_taxation mirroring work calculate.

### TCOMP-005 | LOW | Dead TYPE_CHECKING block

_taxation_comparison.py line 34: if TYPE_CHECKING: pass. TYPE_CHECKING imported but no type guarded under it. Dead scaffolding code.

Fix: remove import and block.

---

## Standing Gate Results

- G1 no naked env reads: PASS
- G2 typed pydantic at boundaries: PASS
- G3 tr() for user messages: PARTIAL PASS -- CLI errors use tr(); recommendation_reason does not (TCOMP-003)
- G4 no locale yml structure hand-edits: PASS
- G5 no shims/re-exports/duplication: PASS
- G6 no tautological tests: PASS on tests present; omission is TCOMP-001

---

## Summary

Core architecture is sound: pure function, frozen typed result, work-unit entry point, locale parity across all four languages, Art.84 reduccion dependency consumed via existing registry mechanism. Operator surface gate does not require updating.

Two HIGH findings block merge. TCOMP-001 requires the equal-income anti-tautology test documented in the test module header but not implemented. TCOMP-002 requires either a scope constraint guarding dual-earner profiles or a mechanism to model both spouse incomes in the individual path. Both must be resolved before merge.