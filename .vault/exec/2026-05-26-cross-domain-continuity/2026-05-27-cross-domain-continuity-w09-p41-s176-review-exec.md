---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-W09-P41-S208]]"
  - "[[2026-05-27-cross-domain-continuity-P50-S176]]"
---

# cross-domain-continuity Code Review

## Commit

dc4f07386 S176: Art. 82 LIRPF situacion_familiar axis

## Status: REVISION REQUIRED

---

## Critical Question Answers

**Q1 Profile schema typing.**
SituacionFamiliar is a StrEnum with five members (CASADO, PAREJA_HECHO_REGISTRADA, PAREJA_HECHO_NO_REGISTRADA, SOLTERO, SEPARADO_DIVORCIADO). The SetupAnswers field is typed SituacionFamiliar|str="" with a mode=before field_validator. Blank passthrough is allowed. Not a bare str at the boundary. pareja_hecho_registrada / pareja_hecho_no_registrada are distinct members. PASS.

**Q2 Model_validator conjunta cross-validation.**
_check_joint_taxation_situacion_familiar refuses taxation_type="2" with ERROR for PAREJA_HECHO_NO_REGISTRADA. SOLTERO and SEPARADO_DIVORCIADO requesting conjunta both return OK with no warning. The inline comment states a WARNING path will be issued for the monoparental case but no WARNING branch is implemented. PARTIAL PASS for the registered-couple path; see HIGH finding VERIFIER-001.

**Q3 Custodia compartida exclusivity.**
unidad_familiar_descendientes_exclusivos field is added to SetupAnswers with a validator. No verifier check cross-validates against the descendant axis. Field exists but is inert. Acknowledged in docstring. DEFERRED.

**Q4 Wizard catalogue registration.**
situacion-familiar question is added to _TAXPAYER_SECTION. Profile key renta_taxpayer.situacion_familiar is auto-derived by _keys.py from the catalogue. CLI accesses this via the catalogue-driven wizard flow. No dedicated typer Option is required by the architectural pattern. PASS.

**Q5 Locale parity.**
es, en, ca carry substantive translated strings for all new keys. hu carries scaffold passthrough delegate references for the situacion-familiar choice labels, help, and prompt keys. The i18n runtime does not follow delegates: rendered==translation_key triggers _humanise_key fallback, producing broken text ("Casado label", etc.). _intentional_identical.json ceiling was NOT updated. The honesty test is silently bypassed because passthrough values are key-path strings not equal to en values. HIGH violation see LOCALE-001.

**Q6 Anti-tautology.**
test_antitautology_different_situacion_yields_different_severity asserts CASADO+conjunta vs PAREJA_HECHO_NO_REGISTRADA+conjunta produce different severities. Genuine discriminating test. PASS.

**Q7 Art. 81 2150 monoparental casilla wiring.**
The registry notes the 2150 euro monoparental reduccion flows through "a separate casilla" (confirmed in test_reduccion_art_84_conjunta.py docstring and irpf.toml). That casilla is not wired. The test_0461_conjunta_tipo_2_monoparental_yields_0_2024 test accepts 0=zero on 0461 but asserts nothing about the 2150 landing elsewhere. The monoparental conjunta path is now reachable via SOLTERO+taxation_type=2 without a guard, while the reduccion has no output. HIGH follow-up see ART81-001.

---

## Findings

### LOCALE-001 | HIGH | hu.yml situacion-familiar keys are scaffold passthrough resulting in broken runtime operator text

hu.yml values for wizard.setup.taxpayer.situacion-familiar.* (prompt, help, all choice labels and descriptions) are dotted key-path strings, not Hungarian translations. The i18n runtime in _render.py:_lookup_translation does not follow delegates; when rendered==translation_key it falls back to _humanise_key, producing output like "Casado label" and "Pareja hecho registrada label" visible to hu-locale operators. The _intentional_identical.json ceiling is not breached because passthrough values differ textually from en values, so the existing honesty gate does not catch this.

Remediation: translate all situacion-familiar choice labels, descriptions, help, prompt, and both verifier message keys into Hungarian via python -m aeat.locales scaffold followed by manual Hungarian authoring per the #161 LOCALE-001 FU pattern.

### VERIFIER-001 | HIGH | SOLTERO and SEPARADO_DIVORCIADO requesting conjunta receive OK with no verification of descendiente presence

_JOINT_INELIGIBLE contains only PAREJA_HECHO_NO_REGISTRADA. SOLTERO+taxation_type=2 and SEPARADO_DIVORCIADO+taxation_type=2 both return WizardCheckSeverity.OK. The inline comment acknowledges a WARNING should be emitted for the monoparental path but no WARNING branch exists. A childless soltero can configure conjunta without any wizard-layer warning or block. Art. 82.1.2 LIRPF requires hijos a cargo for the monoparental unidad familiar.

Remediation: add a WARNING branch for SOLTERO|SEPARADO_DIVORCIADO when family_minor_children_in_unit is False or blank. Provide locale keys for the WARNING message in all four locales.

### ART81-001 | HIGH | Art. 81 2150 euro monoparental reduccion has no wired casilla output path

The commit permits SOLTERO/SEPARADO_DIVORCIADO to reach taxation_type=2. The registry (irpf.toml, test_reduccion_art_84_conjunta.py docstring) documents the 2150 euro reduccion for tipo-2 monoparental as destined for a separate casilla. No formula, binding, or casilla for this path exists. The tipo-2 path is silently zeroed while monoparental conjunta is now reachable.

Remediation: wire the Art. 81 monoparental casilla in a numbered follow-up step, or add an explicit DEFERRED comment and create a follow-up task. Leaving the amount silently dropped while advertising monoparental conjunta support is a legal-correctness gap.

### DOMAIN-001 | MEDIUM | conjunta_eligible() returns True for SOLTERO and SEPARADO_DIVORCIADO unconditionally

SituacionFamiliar.SOLTERO.conjunta_eligible() returns True. The helper has no context for the hijos-a-cargo requirement. Callers that rely on conjunta_eligible() to gate routing will misclassify a childless soltero. The docstring notes the condition but the method does not enforce or communicate it to callers.

Remediation: document clearly in the method signature that conjunta_eligible() is a necessary-but-not-sufficient test, and that callers must additionally verify family_minor_children_in_unit for SOLTERO and SEPARADO_DIVORCIADO. Or expose a two-argument variant.

### G4-001 | MEDIUM | hu.yml situacion-familiar section shows direct editing with scaffold passthrough not completed

The hu.yml situacion-familiar section contains raw scaffold delegate strings, consistent with a scaffold pass that was not followed by Hungarian authoring. Per the aeat-quality-gates rule and #161 LOCALE-001 FU, locale yml structure edits must go through scaffold + audit, not direct yml hand-edits.

---

## Gates Summary

| Gate | Result |
|------|--------|
| G1 no naked env reads | PASS |
| G2 typed pydantic at boundaries | PASS |
| G3 tr() for all user messages | FAIL for hu locale at runtime |
| G4 locale keys via scaffold+audit | PARTIAL |
| G5 no shims/duplication | PASS |
| G6 no tautological tests | PASS |
