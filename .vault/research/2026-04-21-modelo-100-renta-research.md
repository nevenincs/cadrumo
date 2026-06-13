---
tags:
  - "#research"
  - "#modelo-100-renta"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-real-pdf-import-umbrella-research]]"
  - "[[2026-04-21-declaracion-extractor-adr]]"
  - "[[2026-04-21-real-pdf-fixture-corpus-adr]]"
---

# modelo-100-renta research

## Problem

Modelo 100 (IRPF annual) — Renta — is the most complex AEAT filing. Kent's yearly Renta has several orthogonal dimensions that make extraction structurally unlike the quarterly modelos (130, 303, …):

1. **Multi-page scale** — a typical Renta PDF is 10–30 pages (vs. 1–2 for 130).
2. **Multi-anexo structure** — the filing is a base form plus a subset of Anexos A–N triggered by life events (rent, capital gains, foreign income, autónomo activity, charitable giving).
3. **Conditional sections** — even within one anexo, sections appear or disappear based on régimen (estimación directa vs. módulos), civil status, ingreso types.
4. **Pre-filing artefact plurality** — Kent's input is ambiguous: he might drop the *borrador* (pre-filing draft AEAT computes), the *declaración* (final filed copy), or the *predeclaración* (simulation). Each has a different structure.
5. **Scale of casillas** — hundreds, split across anexos.
6. **Historical XFA risk** — pre-2020 Renta PDFs embedded XFA overlays; pdfplumber cannot parse XFA.

Cluster F either ships as its own EPIC or as a scoped MVP. This research argues for a scoped MVP: the **summary block** (ingresos totales / deducciones totales / resultado de la declaración — cuota líquida, retenciones, cuota diferencial) — the ~30 casillas every Renta prints at the top of the final filing. That's enough for Kent's "did AEAT compute the same result I'm sending them?" verification need; full anexo coverage is a follow-up.

## AEAT Renta artefact types (per cluster A's taxonomy)

| Artefact | Carries casillas? | Stage | Source |
| --- | --- | --- | --- |
| Borrador | Yes (pre-populated) | Pre-filing | Downloaded from Portal Renta or "Renta Web Open" public simulator |
| Predeclaración / simulación | Yes | Pre-filing | From "Renta Web Open" (no cert needed) |
| Declaración | Yes (final) | Post-filing | Kent's own copy after submission |
| Justificante de presentación | No (totales only) | Post-filing | Already handled by cluster `#271` |

Renta Web Open (cluster C §1 research, confirmed accessible) is a free-to-access anonymous simulator that can generate **filled PDFs** for any synthetic input. It is our single best L1 anchor source for Renta.

## MVP scope proposal

**In scope for cluster F**:

- Parse the Renta **summary block** — ~30 casillas covering:
    - Ingresos por rendimientos del trabajo (casillas 001–040 range).
    - Ingresos por rendimientos de capital (mobiliario + inmobiliario).
    - Ingresos por actividades económicas (autónomo).
    - Deducciones totales (mínimo personal + familiar, aportaciones, donaciones).
    - Base liquidable + cuota líquida.
    - Retenciones + pagos a cuenta.
    - Cuota diferencial (resultado final).
- Produce a `DeclaracionFiling`-shaped record with ~30 ExtractedCasilla entries.
- No anexo traversal.
- No conditional-section detection.

**Out of scope for cluster F (later phases or sub-EPIC)**:

- Anexo A (rendimientos del trabajo per pagador).
- Anexo B (rendimientos del capital inmobiliario per finca).
- Anexo D (actividades económicas estimación directa).
- Anexo H (deducciones por inversión).
- Anexo Ñ (vivienda).
- Anexo J (rendimientos actividades agrícolas).
- Full ruleset for Modelo 100 formulas (huge; a separate formula-engine project).

## Calc-verification feasibility (MVP)

The Renta summary block's outputs are derivable from its inputs via the same `Engine.audit_against` primitive, IF a partial ruleset for Modelo 100 lands. Scope proposal:

- Summary-block-only ruleset covering ~5 top-level derivations:
    - `rendimiento_neto_actividades = ingresos_actividades - gastos_actividades`
    - `base_imponible_general = sum(rendimientos_netos_generales) + imputaciones_rentas`
    - `cuota_integra = apply_tarifa(base_liquidable)` — tarifa progresiva from BOE (scale table).
    - `cuota_liquida = cuota_integra - deducciones`
    - `cuota_diferencial = cuota_liquida - retenciones_total - pagos_cuenta`

Each is a one-line formula; the tarifa table is a small constant table. This is tractable cluster F work.

## Structural implementation

New module: `src/aeat/adapters/inbound/borrador/` (following cluster A's taxonomy naming — the BORRADOR / declaración / predeclaración all feed Modelo 100 import).

Registry extends cluster D's pattern with a `ModeloClass` axis: "summary-block-only" vs. "full-anexo" (future). MVP registers one extractor: `_extractors/modelo_100_summary_v2024.py`.

## Fixture sourcing for Renta

- **L1 anchors**: Renta Web Open outputs a watermarked PDF. Generate ~10 per año covering a range of life shapes (single no-dependents vs. married with kids; employee vs. autónomo; renter vs. owner).
- **L2 scrubbed private**: Kent's own Renta borrador / declaración from past years. Scrubbing policy extends cluster C's scrubber with Renta-specific guard patterns (IBAN, address, name).
- **L3 synthetic**: a `modelo_100_generator.py` mirroring the Renta summary-block layout. Fidelity-validated against the L1 Renta Web Open anchors.

## Open questions (for ADR)

1. **Cluster F as its own EPIC?** Recommendation: **within EPIC #305** for the summary-block MVP; open a follow-up EPIC for full-anexo coverage later.
2. **Ruleset ownership**: does Modelo 100's ruleset live in `src/aeat/domain/formulas/_rulesets/` like the others, or in a dedicated `src/aeat/domain/formulas/_rulesets/renta/` subfolder given the eventual size? Recommendation: same folder for MVP; split later.
3. **XFA fallback**: any Renta PDF < 2020 probably has XFA. Recommendation: **MVP targets 2020+**; older Rentas need their own plan.
4. **Kent's first Renta might be the borrador, not the declaración**. CLI should accept both under `--from-borrador` and `--from-declaracion` flags — dispatch to the same summary-block extractor internally.
5. **Watermarked Renta-Web-Open PDFs** have a "VISTA PREVIA" watermark across every page. Does this interfere with extraction? Answer: **no, text layer is unaffected by watermark rendering** — confirmed via spot-inspection.
