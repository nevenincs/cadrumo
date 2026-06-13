---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: "2026-05-27"
modified: '2026-05-27'
related:
  - "[[2026-05-27-cross-domain-continuity-fu-177-exec]]"
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-lourdes-cli-testimonial-audit]]"
---

# `cross-domain-continuity` Code Review

## Status: APPROVE+FU

No CRITICAL or blocking HIGH issues. One HIGH follow-up (motor TOML wiring absent)
and one MEDIUM (Q7 wizard scope). Safe to merge as a domain-model axis step.

## Critical Question Answers

### Q1 — custodia_compartida placement

CORRECT. Per-descendant on DescendantInfo. Integrates with #221 DescendantInfo
structure. No parallel list added. G5 passes.

### Q2 — Motor wiring 0513/0514/0515/0516

NOT YET WIRED. custodia_compartida_prorrata_factor exists on RentaFamilyProfile
and is unit-tested. No M100 registry formula TOML applies the 0.5 multiplier.
HIGH follow-up required before operator exposure.

### Q3 — Override refusal

NOT ADDRESSED. Consistent with step scope. Motor/engine layer not yet wired.
Follow-up required.

### Q4 — Locale parity es/en/ca/hu

PASS. All four locales carry profile.descendiente.custodia_compartida_prorrata_applied.
es/en/ca have full translated strings; hu uses passthrough (established pattern).
G4 passes.

### Q5 — Oracle values

PARTIAL. Single-child oracle (1 child custodia => 1200 eur, two progenitors sum
to 2400 eur) is correct and tested. Two-descendant escalado scenario (2400+2700
total, each halved to 1200+1350=2550 per progenitor) is NOT tested. Low gap given
motor is not yet wired.

### Q6 — Anti-tautology

PASS. test_antitautology_without_custodia_full_minimo asserts factor=1 and
minimo=2400 without the flag. Roundtrip anti-tautology removes the persisted key
and verifies reload as False. G6 passes.

### Q7 — Wizard catalogue _SETUP_OPTION_INFOS

NO REGRESSION. This commit does NOT add a WizardQuestion to _catalogue.py.
CUSTODIA=true|false is a sub-token of the existing --descendiente flag string,
parsed by parse_descendiente_flag. No new _SETUP_OPTION_INFOS lookup is created.
The S176 P0 crash vector (KeyError at module import at _commands.py:434) is not
reproduced. The es.yml descendiente flag help text documents the CUSTODIA= token.

Standing gate: any future dedicated wizard question for custodia MUST be added to
both _catalogue.py AND _SETUP_OPTION_INFOS simultaneously (S176 audit gate).

## Safety Domain

SAFETY-001 | LOW | Inline imports in family.py method bodies
custodia_compartida_prorrata_factor imports Decimal inline; custodia_compartida_advisory
imports tr inline. Both are pure and crash-safe, but inconsistent with module-level
import style. Move to module level.

No panics, no unhandled exceptions, no resource leaks identified.

## Intent Domain

INTENT-001 | HIGH | Motor TOML wiring absent
custodia_compartida_prorrata_factor has no registry binding selector and no formula
TOML applies the prorrata to casillas 0513/0514/0515/0516. Feature is domain-model-only
until this lands. Must close before operator exposure.

INTENT-002 | MEDIUM | Override-refusal not implemented
No guard refuses --casilla 0513=<full_value> when custodia_compartida descendant is
present. Acceptable deferral for axis step; required before operator exposure.

INTENT-003 | LOW | Escalado + prorrata 2-child oracle not tested
Add in motor binding follow-up step.

## Standing Gate Sweep

- G1 no naked env reads: PASS
- G2 typed pydantic at boundaries: PASS
- G3 tr() for user messages: PASS
- G4 locale via scaffold+audit: PASS
- G5 no shims/duplication: PASS
- G6 no tautological tests: PASS

## Follow-Up Items Required Before Operator Exposure

1. HIGH: Motor binding — add custodia_compartida binding selector to M100 formula
   TOML for casillas 0513/0514/0515/0516.
2. HIGH: Override refusal — guard in CLI/application layer refusing --casilla 0513=X
   override exceeding prorrata ceiling when any descendant has custodia_compartida=True.
3. LOW: 2-child escalado oracle test.
4. LOW: Move inline imports to module level in family.py.
