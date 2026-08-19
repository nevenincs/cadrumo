---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:5b5cee0ad60b04683ec30571a97b8b5d1594c93fe4f20512b3975dae4a444ba4'
step_id: 'S95'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# DONE. All 204 casillas the 2025 Modelo 200 design declares and the registry omitted are authored, and all 1624 of their locale leaves are applied. 117 acontecimientos de excepcional interes publico as sibling transfers from the shipped 2025_barcelona_mobile_world_capital_mw trio, 28 named LIS deduction families from an explicit per-family role table led by ley-27-2014:art-36, and 58 structural AIE/UTE, RIC and participaciones rows. Registry casillas 3250 to 3453, missing design tokens 204 to 0, modelo 200 locale drift to 0, and the validating authority back to its baseline 8 failures with zero non-grade refusals. Two genuine block totals declare intentional_singleton cardinality with a reason after the registry's own gate refused 48 slot-disambiguated roles as likely typos. No translation in en, ca or hu is identical to its Spanish source, so the honesty ratchet is satisfied without an allowlist entry

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/`

## Description

The 2025 Modelo 200 record design declares 204 casillas the registry did not
carry. They were authored in three tranches, each grounded differently and none
by text similarity.

**117 acontecimientos de excepcional interes publico** across 39 events, as
sibling transfers from the SHIPPED trio `2025_barcelona_mobile_world_capital_mw`
(03523/03524/03525): same section head, same three column roles, same legal_refs
bundle, same data_type and input_kind. An earlier reading held these blocked on
acquiring 38 establishing dispositions; that was wrong, because the grounding
rule governs compiled regulatory VALUES and these are `manual` `money` slots
with no formula and no stored percentage.

**28 named LIS deduction families** from an EXPLICIT per-family role table. I+D,
innovacion tecnologica and Africa Occidental reuse roles the registry already
carries. Productor and financiador of producciones cinematograficas and of
espectaculos en vivo, creacion de empleo con discapacidad, inversion en
beneficios and sociedades forestales are newly named; their binding provision
`ley-27-2014:art-36` is bundled and catalogued, and its text covers the productor
AND "los contribuyentes que participen en la financiacion" AND espectaculos en
vivo in one provision.

**58 structural rows** -- AIE/UTE datos economicos and participes, RIC
inversiones anticipadas, participaciones directas, INCN.

All 1,624 locale leaves followed through `dev.locales set-batch`: Spanish is
AEAT's printed label, the other three translate the column and concept phrases
while carrying programme proper nouns verbatim.

## Outcome

- registry casillas 3250 -> 3453; design tokens naming no casilla 204 -> 0
- modelo 200 locale drift -> 0 across all four catalogues
- validating authority back to its BASELINE 8 failures, zero non-grade refusals
- `test_export_split_part_rendering.py` + `test_render_profile.py`: 140 passed
- no `en`/`ca`/`hu` value equals its Spanish source, so the honesty ratchet needs
  no allowlist entry

## Notes

**A gate caught a wrong shape mid-flight and was right.** AEAT prints the SAME
label for distinct sub-rows of the AIE/UTE block -- 00999 and 01138 are both
"6.- Deduc. evitar doble imposicion: Base de la deduccion" -- and the
interna/internacional distinction is in the form's visual grouping, absent from
the field text and from the bundled 868-page manual's extractable lines. A first
attempt disambiguated by printed slot; the registry's cardinality gate refused
all 48 such roles as "appears on exactly one casilla; likely typo or missing
role". Same-concept rows now SHARE a role, matching the shipped
`is_deduccion_idi_evento_especial`, and the two genuine block totals declare
`semantic_role_cardinality = "intentional_singleton"` with a reason.

**This does not clear Modelo 200 from the authority.** The revision still
declares no export layout, and its `extraction_profiles` and
`projection_endpoints` families are still unpopulated. The casillas were the
prerequisite, not the closure.
