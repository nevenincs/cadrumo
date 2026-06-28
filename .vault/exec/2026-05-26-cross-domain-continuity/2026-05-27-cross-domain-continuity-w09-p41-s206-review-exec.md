---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: "2026-05-27"
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity Code Review -- commit bd6a05f51 (#206 DT 12a LIRPF)

## Status: REVISION REQUIRED

---

## MATH-001 | HIGH | Oracle docstring claims 6983.64 but math yields 6981.82

The class-level docstring of TestDt12ReduccionPlanPensiones in
test_modelo.py:1219 states: "Carla oracle: 9600 / 33000 * 60000 * 40% = 6983.636... rounded to 6983.64"

Independent verification: (9600 / 33000) * 60000 * 0.40 = 6981.8181... rounded HALF_UP = 6981.82.

The assertion at line 1240 is correct (asserts 6981.82). Only the docstring is wrong.
However it directly contradicts the task brief value (6983.64) and will mislead auditors.
Must be corrected.

Affected: src/aeat/entrypoints/cli/test_modelo.py lines 1215, 1219.

---

## KIND-002 | HIGH | Advisory finding uses kind=BLOCKING_RULE with severity=WARNING

_dt12_reduccion_advisory_finding at _actions.py:2711 emits
kind=ModeloVerificationFindingKind.BLOCKING_RULE, severity=ModeloVerificationFindingSeverity.WARNING.

The enum documents BLOCKING_RULE as a hard refusal. VerificationReport._enforce_invariants
tests for BLOCKED status by severity, so WARNING correctly avoids blocking VERIFICADO_COMPLETO.
However kind=BLOCKING_RULE contradicts its own documentation for an advisory finding and will
mislead downstream consumers that filter by kind.

Remediation: add ModeloVerificationFindingKind.ADVISORY (preferred) or repurpose
UNRESOLVED_BINDING as proxy.

Affected: src/aeat/application/modelo/_actions.py:2711.

---

## G4-004 | HIGH | Six new tr() keys absent from all four locale files

Keys introduced in src/aeat/entrypoints/cli/_modelo.py:
  - cli.app.modelo.work.rescate_plan_pensiones_casilla_not_found
  - cli.app.modelo.work.rescate_plan_pensiones_capital_help
  - cli.app.modelo.work.rescate_plan_pensiones_aportaciones_pre_2007_help
  - cli.app.modelo.work.rescate_plan_pensiones_aportaciones_totales_help
  - cli.app.modelo.work.rescate_plan_pensiones_incomplete
  - cli.app.modelo.work.rescate_plan_pensiones_not_decimal

Zero entries in es.yml, en.yml, ca.yml, hu.yml (confirmed by grep). tr() falls back
to default= so no crash, but the scaffold+audit cycle was bypassed and translation
parity cannot be verified. G4 violation for all four locales.

Affected: src/aeat/locales/es.yml, en.yml, ca.yml, hu.yml.

---

## G3-003 | MEDIUM | Advisory next_action not routed through tr()

next_action at _actions.py:2720-2725 is a raw English string (CLI flag names).
Pre-existing internal finding messages use the same raw-string pattern, so this is
consistent with the codebase idiom. Flagged MEDIUM: the next_action surfaces to the
operator-facing CLI output and should use a locale key.

---

## G6-005 | LOW | Anti-tautology oracle derived from same formula

test_anti_tautology_different_ratio_different_reduccion at test_modelo.py:1625 derives
3490.91 from 4800/33000*60000*0.40 -- the same formula under test. No external
authority is available for a pure math helper, so ratio-sensitivity is the best
achievable proof. Flagged LOW only.

---

## Critical Question Answers

Q1 CLI flags: confirmed -- all three flags present on work calculate. PASS.

Q2 Formula: pre_2007 / totales * gross * 0.40 HALF_UP money-2; injects into
irpf_rendimiento_trabajo_reduccion by semantic_role lookup (casilla 0011 in 2024/2025).
PASS.

Q3 Advisory: DT_12A_REDUCCION_POSSIBLE WARNING fires when ingreso_integro > 20000 AND
reduccion == 0. Present. Kind classification wrong (KIND-002).

Q4 legal_refs: legal_refs=("ley-35-2006:dt-12",) confirmed on the advisory finding.
PASS.

Q5 Wizard parity: no SETUP_OPTION_INFOS pattern exists in this codebase. No wizard
catalogue entry added for rescate flags (correct -- they are work-calculate-only).
No regression. PASS.

Q6 Locale parity: FAIL -- all six keys absent from all four locales (see G4-004).

Q7 Oracle test: assertion correct (6981.82); docstring wrong (claims 6983.64). PASS
assertion, FAIL documentation (see MATH-001).

Q8 Anti-tautology: ratio-change-produces-proportional-change. PASS with LOW caveat.

Q9 2024 + 2025: both revisions carry irpf_rendimiento_trabajo_reduccion and
irpf_rendimiento_trabajo_importe_integro_dinerario semantic roles. Advisory and
injection resolve correctly for both years. PASS.

---

## Verdict Summary

| # | Severity | Finding |
|---|----------|---------|
| MATH-001 | HIGH | Test docstring oracle value wrong (6983.64 vs 6981.82) |
| KIND-002 | HIGH | Advisory finding kind=BLOCKING_RULE is architecturally incorrect |
| G4-004 | HIGH | Six tr() locale keys missing from all four locale files |
| G3-003 | MEDIUM | Advisory next_action bypasses tr() |
| G6-005 | LOW | Anti-tautology uses formula-derived expected value |

REVISION REQUIRED. Three HIGH findings must be resolved:
1. Correct the class docstring oracle value in test_modelo.py.
2. Change kind on the advisory finding away from BLOCKING_RULE.
3. Run python -m aeat.locales scaffold for the six new keys and supply es/en/ca/hu translations.
