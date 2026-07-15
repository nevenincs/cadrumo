---
tags:
  - '#research'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
related:
  - "[[2026-07-10-cross-domain-continuity-reference]]"
  - "[[2026-06-03-iva-exemption-article-adr]]"
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# `cross-domain-continuity` research: `Modelo 303 Article 20 exemption routing correction`

## Findings

Article 20.Uno.26 is an exempt domestic professional-service category, not an exemption carrying a right to deduct. The bundled corpus locators are `ley-37-1992-art-20.html:10,168`, `ley-37-1992-art-94.html:1,3`, and `ley-37-1992-art-104.html:7,11-12`; the current primary source is https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740.

Article 94 grants a deduction right for taxable non-exempt domestic operations and named exempt operations in Articles 20 bis and 21 through 25. It does not include Article 20.Uno.26. Article 104 therefore requires its amount in the general-prorrata denominator but excludes it from the numerator. AEAT’s current guidance agrees: https://sede.agenciatributaria.gob.es/Sede/iva/que-iva-soportado-puedo-deducir/que-actividades-derecho-deduccion.html.

Casilla 61 is not a lawful route. AEAT removed it from Modelo 303 effective 1 July 2021: https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/manual-iva-2021/capitulo-1-novedades-destacar-2021/modelo-303.html. Its former meaning was operations not subject to IVA or subject to reverse charge that generated a deduction right, not Article 20 domestic exemptions. Current 2025 Modelo 303 instructions treat Article 20 operations as exempt without deduction: https://sede.agenciatributaria.gob.es/Sede/todas-gestiones/impuestos-tasas/iva/modelo-303-iva-autoliquidacion_/instrucciones-2025.html.

The live code diverges from those sources only through `IvaExemptionArticle.ART_20_UNO_26` and the prorrata special case that sends it to `con_derecho`. No production classifier stamps that member and no committed Modelo 303 binding consumes it. The valid approaches are:

1. Preserve the current full-deduction/casilla-61 route. Reject: it contradicts Articles 94 and 104 and can overstate recoverable IVA.
2. Retain the member but route it as exempt without deduction. Legally correct but leaves an unused special surface without a present consumer.
3. Remove the member and its special route. Recommended: pre-release no-legacy policy permits deletion, while the existing `DOMESTIC_EXEMPT` path supplies the complete current legal treatment.

The recommended decision is to remove `ART_20_UNO_26`, its documentation, and its special prorrata behavior; retain the generic `DOMESTIC_EXEMPT` classification; and prohibit any casilla-61 compatibility or inferred casilla-83 authoring. The 2026-06-03 IVA exemption-article ADR must be superseded rather than retroactively rewritten.
