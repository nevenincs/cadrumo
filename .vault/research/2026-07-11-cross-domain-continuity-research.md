---
tags:
  - '#research'
  - '#cross-domain-continuity'
date: '2026-07-11'
modified: '2026-07-11'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# `cross-domain-continuity` research: `Article 27 and Modelo 303 casilla reconciliation`

Decision research for the two remaining legal-grounding blockers in the cross-domain continuity plan. It compares current code and bundled corpus with primary AEAT/BOE material, identifies what can safely remain advisory, and bounds the choices that require ADR approval.

## Findings

### S343 — Article 27 LGT rate posture is not a statutory assessment

Current code correctly resolves the post-2021 graduated band at the exact twelve-month boundary: the anniversary remains 13 percent and the following day enters the 15-percent-plus-interest tail. It also fails closed for known prior requirement and non-positive payable amount. Evidence: `src/aeat/domain/deadlines/_recargo.py`, `src/aeat/application/modelo/_work_plazo.py`, and `src/aeat/entrypoints/cli/_modelo_rendering.py`.

Its current `conditional=False` branch is nevertheless not an Article 27 assessment. It accepts unproven primitives, has no monetary recargo or interest calculation, can fall back to a present-day reference date, and cannot prove absence of an AEAT prior requirement. Local filing state is non-official evidence under `.codex/rules/local-filed-observations-are-non-official-evidence.md`.

The bundled Article 27 extraction is incomplete: `src/aeat/_data/corpus/normatives/html/ley-58-2003-art-27.html.extracted.md` lacks the same-facts safe harbour in 27.2, payment/executive consequences in 27.3, and period-identification condition in 27.4. It also lacks an effective-dated regime for the 2021 amendment and the historical interest inputs required for a money result.

Options:

- Keep the present output but relabel it as deadline posture and conditional rate preview. This is low risk but must remove any statutory-liability implication.
- Add provenance to the current three facts and offer a qualified rate determination. This improves evidence but remains incomplete without the omitted Article 27 and Article 26 factors.
- Implement a full statutory assessment and settlement projection. This is most useful but requires complete reviewed corpus, historical legal regimes, interest data, and provenance-bearing evidence.

Recommendation: approve a phased ADR that separates `DeadlinePosture`, `ConditionalRecargoPreview`, and a later `StatutoryRecargoAssessment`. The last must fail closed to an unassessed outcome until it has historical law, actual presentation, amount, verified no-prior-requirement, identity/period linkage, same-facts, payment/executive, and reduction evidence.

Primary sources: https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186#a27 and https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186#a26. The official publication history must be checked before any historical assessment.

### S355/S444 — Art. 20.Uno.26 is not a Modelo 303 casilla 61 route

The current Modelo 303 structure contains 59, 60, 120, and 122; it has no current casilla 61. Historical casilla 61 was removed from July 2021 and concerned non-subject/reverse-charge operations with deduction right, not Art. 20 exemptions. The current bundled registry correctly has no casilla 61 in either Modelo 303 revision.

Substantive law is also decisive: Art. 20.Uno.26 artistic services are exempt, Art. 94 does not grant their deduction right, and Art. 104 places them in the prorrata denominator rather than numerator. The current `IvaExemptionArticle.ART_20_UNO_26` prose and its special prorrata set claim the opposite and are the actual defect; no production classifier or registry binding requires this special enum route.

Options:

- Retain `ART_20_UNO_26` as an exemption with deduction right and a casilla 61 route. Reject: contrary to Arts. 94/104 and the current form.
- Retain the enum as descriptive metadata but route it without deduction. Lawful, but keeps an unused special axis without an independent consumer.
- Remove the member, its casilla-61/plena-prorrata prose, and special prorrata routing; retain generic `DOMESTIC_EXEMPT`. Recommended: it is the lawful current behavior and avoids an obsolete form mapping.

Recommendation: approve an ADR that supersedes only the Art. 20.Uno.26/casilla-61 branch of `2026-06-03-iva-exemption-article-adr`. Remove the special route after approval; do not invent casilla 61 or infer a separate casilla-83 route. A later dedicated reporting decision may address casilla 83 if needed.

Primary sources: https://sede.agenciatributaria.gob.es/Sede/todas-gestiones/impuestos-tasas/iva/modelo-303-iva-autoliquidacion_/instrucciones-2026/instrucciones-02-12-2t-4t-2026.html, https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/manual-iva-2021/capitulo-1-novedades-destacar-2021/modelo-303.html, https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740, and https://sede.agenciatributaria.gob.es/Sede/iva/que-iva-soportado-puedo-deducir/que-actividades-derecho-deduccion.html.

Code locators: `src/aeat/domain/iva/_schema.py`, `src/aeat/domain/iva/_classification.py`, `src/aeat/application/calculations/_prorrata_regularizacion.py`, and `src/aeat/application/calculations/tests/test_prorrata_regularizacion.py`.
