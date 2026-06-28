---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-W09-P41-S208]]"
  - "[[2026-05-26-cross-domain-continuity-P19-S210]]"
---

# cross-domain-continuity Code Review

## Commit d9c002a51 -- #210 M200 tipo IS ERD 23 percent derivation from INCN

**Status: PASS**

Scope: formulas.toml, parameters.toml, bindings.toml, constructs.part-001.toml, is.toml, five HTML stubs, one test file.

---

### Standing Gates


- **G1 (no naked env reads):** No Python production code modified. Gate vacuously passes.
- **G2 (typed pydantic at boundaries):** Registry TOML schema-validated by the loader. No boundary layer code changed. Gate passes.
- **G3 (tr() for user messages):** No user-facing strings added. Gate passes.
- **G4 (locale via scaffold + audit):** No locale files touched. Gate passes.
- **G5 (no shims/duplication):** Two new parameters (is.modelo-200.tipo-gravamen-erd scalar + is.modelo-200.cuota-integra-bracket-erd bracket) are additive. No shim, re-export, or duplicate introduced. Gate passes.
- **G6 (no tautological tests):** Oracle values grounded in Ley 31/2022 Art. 39 (Aitor SAL 850k -> 23; SA 1.5M -> 25; new-entity 200k -> 15; cooperativa 500k -> 20; ERD parameter = 23). Anti-tautology: INCN exactly 1.000.000 (not qualifying) -> tipo 25, confirming strict less-than. Gate passes.

---


### Critical Question Answers


**CQ1 -- Profile field consultation correctness**


new_entity_first_two_profit_periods = True -> 15%: Correct. Outermost if_then_else on modelo-200-2024-profile-new-entity-flag routes all eight legal-form keys to is.modelo-200.tipo-gravamen-new-entity-first-2-years (value 15). Priority is correct.


legal_entity_form = sin_fines_lucrativos (Maria case): Correct. In both the ERD lane and the general lane the dispatch table routes sin_fines_lucrativos to is.modelo-200.tipo-gravamen-non-profit-special-regime (value 10). Maria pays 10% regardless of INCN.


legal_entity_form = sal (Aitor case): Correct. With INCN = 850k below 1M and new-entity-flag = 0 the ERD lane routes sal to is.modelo-200.tipo-gravamen-erd (value 23). Oracle test confirms.


incn_prior_12_months < 1_000_000 -> 23%: Correct. less_than predicate with literal = 1000000. Boundary test at exactly 1M returns 25%, confirming strict inequality.


Default -> 25%: Correct. General lane routes sl/sa/sal/sll/scm/other to is.modelo-200.tipo-gravamen-general.


**CQ2 -- Casilla DP200014:00558 computation status**


DP200014:00558 was already the target of formula modelo-200-tipo-gravamen-por-forma-juridica in the prior revision; no manual-to-computed flip was needed. The diff replaces the single lookup_parameter_by_entity_type expression with the three-lane nested if_then_else. The casilla remains fully computed. Correct.


**CQ3 -- legal_refs completeness**


The tipo formula carries [ley-27-2014:art-29, ley-27-2014:art-30, ley-31-2022:art-39]. Covers the general rate, related provisions, and the ERD modification.


The task brief requests ley-27-2014:art-29-1, ley-27-2014:art-29-2, and ley-49-2002:art-10. None are present. The registry uses article-level IDs (art-29) not paragraph-level (art-29-1, art-29-2) as a pre-existing convention -- this commit is consistent. ley-49-2002:art-10 is not registered in is.toml and is absent from tipo-gravamen-non-profit-special-regime legal_refs. Pre-existing provenance gap, not introduced here.

**CQ4 -- Cross-cut with #183 and #234**


#183 (cuota-integra Path-B Estado-share binding fix): The cuota-integra formula INCN < 1M lane previously dispatched all forms to is.modelo-200.tipo-gravamen-pyme; it now routes general-rate forms to is.modelo-200.cuota-integra-bracket-erd and cooperativas/sin_fines_lucrativos to their own brackets. The tributacion-estado-porcentaje binding and Estado-share logic are untouched. No conflict.


#234 (Maria Ley 49/2002 10% formula): sin_fines_lucrativos dispatch to 10% is preserved in all three lanes. No duplication.


**CQ5 -- Wizard catalogue parity (#228/#239 family)**


No wizard, profile-wizard, or CLI entrypoint files modified. Commit is purely registry + test. No regression vector.


**CQ6 -- Locale keys**


No locale files modified. No new user-facing strings. Gate passes.


**CQ7 -- Oracle test coverage**


Sergio shape (INCN 4.2M -> 25): Covered by test_tipo_gravamen_dispatch_routes_general_25_when_incn_at_or_above_1m (SA, INCN 1.5M -> 25) and the pre-existing form-dispatch test (INCN 10M -> 25). Any value above 1M exercises the same general lane.


Aitor shape (SAL, INCN 850k -> 23): Directly exercised by test_tipo_gravamen_dispatch_routes_erd_23_when_incn_below_1m.


Maria shape (sin_fines_lucrativos -> 10): Covered by pre-existing test_tipo_gravamen_dispatch_routes_00558_by_legal_entity_form (INCN 10M, above ERD threshold). No new test asserts sin_fines_lucrativos + INCN < 1M -> 10 (not 23). Minor gap -- see TIPO-001.


New-entity shape (new-entity = True -> 15): Directly exercised by test_new_entity_flag_overrides_erd_threshold (SL, INCN 200k, flag = 1 -> 15).


**CQ8 -- Anti-tautology**


test_tipo_gravamen_dispatch_routes_general_25_when_incn_at_or_above_1m uses INCN = 1.000.000 (boundary, not qualifying) -> tipo 25. Combined with the ERD test at INCN 850k -> tipo 23, the same entity form (SA / SAL) at two INCN values straddling 1M produces different rates. Anti-tautology gate passes.

---


### Findings


**TIPO-001 | LOW | Missing sin_fines_lucrativos oracle in ERD lane**


No test asserts sin_fines_lucrativos + INCN < 1M -> 10% (not 23%). The dispatch table routes correctly by construction; the pre-existing INCN 10M test covers the general-lane non-profit path. A dedicated ERD-lane test for this form would complete the four-persona oracle matrix (Sergio / Aitor / Maria / new-entity). Correctness is assured by table inspection; this is oracle documentation debt.


**TIPO-002 | LOW | ley-49-2002:art-10 absent from non-profit parameter legal_refs**


is.modelo-200.tipo-gravamen-non-profit-special-regime cites only ley-27-2014:art-29. The task brief names ley-49-2002:art-10 as the authority for the Maria 10% rate. Pre-existing gap not introduced by this commit. A follow-up should register ley-49-2002:art-10 in is.toml and add it to the non-profit parameter legal_refs.


**TIPO-003 | LOW | Paragraph-level art refs (art-29-1, art-29-2) not used**


The registry convention uses article-level IDs throughout. The task brief requests paragraph-level precision. Pre-existing convention gap, out of scope for this commit.


**TIPO-004 | LOW | bindings.toml required_text corrected from reserva especial to base imponible**


Two source citations on existing SAL-related bindings had required_text corrected from reserva especial to base imponible. Legitimate fix (SAL binding concerns base imponible). No logic change.


---


### Verdict


**PASS** -- No CRITICAL or HIGH issues. The three-lane tipo formula is correctly structured. The ERD 23% rate is properly scoped to INCN < 1M for general-rate forms only. Special regimes (cooperative 20%, non-profit 10%) are preserved across all three lanes. The new-entity override takes unconditional priority. The anti-tautology boundary test is present and effective. Four LOW findings are all pre-existing gaps or minor oracle coverage notes; none block merge.


Follow-up recommended (non-blocking): add explicit sin_fines_lucrativos + INCN < 1M -> 10% oracle test; register ley-49-2002:art-10 in is.toml and on the non-profit parameter.