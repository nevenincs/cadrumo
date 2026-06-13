---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-m200-cuota-formula-estado-binding-fix-exec]]"
  - "[[2026-05-27-schema-hardening-m200-estado-share-binding-repair-exec]]"
---

# cross-domain-continuity S183 Code Review

## Verdict: APPROVE+FU

No critical or high safety violations. Silent-zero defect correctly diagnosed and fixed. Two medium findings and one low finding. Safe to merge; three FU items noted.

---

## Critical Question Answers

**Q1 -- Path-A or Path-B?**

Path-B targeted defect-of-record fix. The commit does not author the full liquidacion chain. The formula chain through DP200014B:00599 and DP200014B:00611 was wired in prior slices; scope here is strictly the 00599 silent-zero multiplier defect from an unsupplied manual casilla.

**Q2 -- Full chain present post-fix?**

Yes. After this commit: 00562 (cuota integra) feeds 00599 (cuota ejercicio, now multiplied by profile binding not silent-zero casilla) feeds 00611 (cuota diferencial, subtracts pagos fraccionados relation). The cross-model relation and tipo dispatch were authored in prior slices and remain present.

**Q3 -- Cross-cut with task 210 ERD 23% and task 234 Ley 49/2002 10%?**

- Task 234 / Maria shape (sin_fines_lucrativos 10%): Addressed in a prior slice. test_non_profit_takes_the_ley_49_2002_special_regime_rate passes. No FU needed.
- Task 210 / Aitor shape (ERD INCN 23% for 2024): The 2024 flat-23% pyme bracket is present in parameters.toml. No dedicated oracle test for the exact shape: EUR 95k base, INCN EUR 850k, 23%, EUR 21850. Filed as FU-001.
- Sergio shape (EUR 95k base, INCN EUR 4.2M, 25%, EUR 23750): General 25% lane covered by existing AEAT Manual page 401 test at a different base. No dedicated oracle test at the exact nominated triple. Filed as FU-001.

**Q4 -- Anti-tautology oracle check:**

The absent-binding raises test is non-tautological. The non-zero oracle test correctly probes the binding path (not silent zero) but uses base=20000 supplied by the test itself; AEAT Manual pages 399/401 do not publish 20000 as a cuota ejercicio figure. Oracle attribution overstated; see FU-002 (low).

**Q5 -- Wizard catalogue regression (#228-class):**

No regression. tributacion_estado_porcentaje follows the incn_prior_12_months pattern: calculation-only binding, not exposed as a direct wizard question. _SETUP_OPTION_INFOS not modified.

**Q6 -- Locale parity:**

No user-facing message, CLI verb, or locale key introduced. G3 and G4 fully pass.

**Q7 -- source_refs on new binding:**

New binding declares source_refs = ["aeat-modelo-200-manual-2024"]. The consuming formula already carries both aeat-dr-200-2025 and aeat-modelo-200-manual-2024. The binding should also carry aeat-dr-200-2025. Filed as FU-003 (medium, TOML-only).

---

## Gate Results

| Gate | Result | Notes |
|------|--------|-------|
| G1 no naked env reads | PASS | No os.environ or os.getenv in any modified file. |
| G2 typed pydantic at boundaries | PASS | TaxpayerProfile is BaseModel; new field is Decimal or None. Binding follows frozen _ProfileSelector pattern. |
| G3 tr() for user messages | PASS | No user-facing message introduced. |
| G4 no locale yml hand-edits | PASS | No locale files touched. |
| G5 no shims/duplication | PASS | DP200026:00625 casilla stays manual for BOE export; formula rewritten to binding. Consistent with three existing profile_model=taxpayer bindings. |
| G6 no tautological tests | PARTIAL | Absent-binding raises test is non-tautological. Non-zero oracle test probes binding path correctly but base is self-supplied. Exact Aitor/Sergio oracle tests absent. See FU-001 and FU-002. |

---

## Findings

### FU-001 | MEDIUM | Missing dedicated oracle tests for Aitor ERD 23%/2024 and Sergio general 25% shapes

Review brief requires three profile-derived tipo shapes with external oracle values. Maria (10%) is addressed by prior tests. Sergio (EUR 95k, 25%, EUR 23750) and Aitor (EUR 95k, INCN EUR 850k, 23% for 2024, EUR 21850) have no dedicated oracle test at the nominated base/tipo/cuota triples. The 2024 flat-23% pyme rate for INCN EUR 850k has no dedicated test.

Remediation: add two tests grounded in Ley 27/2014 Art. 29 and the AEAT Manual de Sociedades 2024 parameters comments. Oracle for base=95000 at 0.23 is 21850.00 and at 0.25 is 23750.00. File period 2024-12-31 exercises the 2024 bracket.

### FU-002 | LOW | Oracle justification in non-zero regression test overstates AEAT Manual grounding

Docstring cites AEAT Manual pages 399/401 for the 20000 figure. Those pages publish cuota integra/liquidada examples; 20000 as a cuota ejercicio figure does not appear there. The test is non-tautological in proving the binding path but the attribution is misleading. Correct the docstring to describe this as a structural multiplier-path probe not a full external oracle assertion.

### FU-003 | MEDIUM | New binding source_refs omits aeat-dr-200-2025

modelo-200-2024-profile-tributacion-estado-porcentaje declares source_refs = ["aeat-modelo-200-manual-2024"]. The formula that consumes it carries both aeat-dr-200-2025 and aeat-modelo-200-manual-2024. Casilla DP200026:00625 that this binding substitutes at the formula level is described in the 2025 DR. For citation completeness add "aeat-dr-200-2025" to the binding source_refs. TOML-only fix.

---

## Safety Summary

No panics, unhandled null paths, or resource leaks. RegistryValidationError is raised on absent binding (fail-loud), not silently defaulted. Decimal or None on the new profile field is safe: None at the runtime boundary surfaces as a missing-binding error via the resolver, not an arithmetic failure. All five migrated test callsites consistently replace the manual casilla input with the new binding_values key. Migration is complete. No async, concurrency, or unsafe code concerns.

## Intent Completeness

The stated defect (silent zero on DP200014B:00599 from unsupplied manual casilla) is correctly diagnosed and fixed. Formula rewrite, profile field, new binding declaration, and test migration are all present and consistent. FU items are non-blocking for merge.
