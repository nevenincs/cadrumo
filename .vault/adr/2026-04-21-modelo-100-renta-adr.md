---
tags:
  - "#adr"
  - "#modelo-100-renta"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-modelo-100-renta-research]]"
  - "[[2026-04-21-declaracion-extractor-adr]]"
  - "[[2026-04-21-real-pdf-fixture-corpus-adr]]"
---

# `modelo-100-renta` adr: `summary-block-mvp-via-aeat-borrador-module-plus-partial-ruleset` | (**status:** `accepted`)

## Problem Statement

Full Modelo 100 extraction is structurally unlike the quarterly modelos cluster D handles: multi-page, multi-anexo, conditional sections, hundreds of casillas, historical XFA risk, multiple artefact types (borrador / predeclaración / declaración). Shipping everything in one cluster is unrealistic. This ADR scopes a **summary-block MVP** that validates the approach end-to-end on ~30 casillas across every life shape Kent is likely to encounter, and defers anexo-level coverage to follow-up sub-EPICs. The summary block alone is enough for Kent's "did AEAT compute the same result I'm sending them?" use case.

## Considerations

- AEAT's Renta Web Open simulator is publicly accessible (no cert) and generates filled PDFs for arbitrary synthetic inputs. This is a unique asset: it gives us unlimited L1 anchors for Renta.
- The Renta summary block occupies the last 1–2 pages of every declaración and is structurally stable across años (label text drifts, but casilla IDs are consistent since 2020).
- Full anexo coverage is years of work; summary-block is days-to-weeks.
- The `aeat.adapters.inbound.borrador` module name (cluster-A taxonomy) covers all three Renta artefact types — borrador, predeclaración, declaración — because they share a summary-block layout for cluster-F purposes.
- Modelo 100's ruleset can land as a minimal summary-block-only implementation: ~5 top-level derivations, a small tarifa progresiva table. Deferred: reglas específicas per anexo.
- Pre-2020 Renta PDFs risk XFA; MVP targets 2020+ only.
- Project mandate: Pydantic strict+frozen; no bare dicts; Spanish authoritative.

## Constraints

- **Summary-block only for MVP.** Anexo-level extraction is out.
- **Renta 2020+ only**; older años deferred.
- **`aeat.adapters.inbound.borrador` module name** per cluster-A taxonomy.
- **Partial ruleset**: ~5 derivations for the summary block; register under `src/aeat/domain/formulas/_rulesets/modelo_100_summary_2025.py`.
- **Cluster F remains within EPIC #305**; full-anexo follow-up becomes sub-EPIC #305-F-full.
- **No XFA work in MVP**; document the limitation.
- **Zero cert / live-submit coupling**.
- **Fidelity-validated** against ≥ 5 Renta-Web-Open anchors per año.

## Implementation

### 1. `aeat.adapters.inbound.borrador` module

```
src/aeat/adapters/inbound/borrador/
    __init__.py       # parse_borrador(pdf, ...) -> BorradorFiling
    _schema.py        # BorradorFiling (extends DeclaracionFiling shape with
                      #   artefact_kind: Literal["borrador","predeclaracion","declaracion"])
    _errors.py        # BorradorParseError < PdfFilingImportError
    _extract.py       # Renta-specific primitives (multi-page traversal, summary-block finder)
    _extractor.py     # BorradorExtractor ABC
    _detect.py        # detect_artefact_kind(pdf) — watermark / header heuristics
    _extractors/
        __init__.py
        modelo_100_summary_v2025.py  # MVP extractor
    _parsers/
        _pdfplumber_backend.py
    test_extractor.py
```

### 2. Summary-block layout map

Hard-coded casilla IDs for the MVP: `{"001", "002", ..., "030"}` representing:

- 001–020: rendimientos netos (trabajo / capital / actividades).
- 021–025: deducciones.
- 026: base liquidable.
- 027: cuota íntegra.
- 028: cuota líquida.
- 029: retenciones totales.
- 030: cuota diferencial.

Label-anchored regex primary; bbox fallback uses last-2-page scope (summary always appears near the end).

### 3. Partial Modelo 100 ruleset

`src/aeat/domain/formulas/_rulesets/modelo_100_summary_2025.py`:

```python
@ruleset("100", año=2025, scope="summary")
class Modelo100SummaryRuleset2025:
    def derive_rendimiento_neto_actividades(self, inputs):
        return inputs["ingresos_actividades"] - inputs["gastos_actividades"]

    def derive_base_imponible_general(self, inputs):
        ...

    def derive_cuota_integra(self, base_liquidable: Decimal) -> Decimal:
        # Tarifa progresiva 2025: [(bracket_upper, rate), ...]
        return apply_tarifa(base_liquidable, _TARIFA_2025)

    def derive_cuota_liquida(self, cuota_integra, deducciones_total):
        return cuota_integra - deducciones_total

    def derive_cuota_diferencial(self, cuota_liquida, retenciones_total, pagos_cuenta):
        return cuota_liquida - retenciones_total - pagos_cuenta
```

Scope annotation (`scope="summary"`) is new metadata enabling cluster E to report `coverage=summary-block-only`.

### 4. Artefact-kind detection

`detect_artefact_kind(pdf_path) -> Literal["borrador", "predeclaracion", "declaracion"]`:

- Borrador: AEAT stamps "BORRADOR" prominently; watermark absent.
- Predeclaración: "VISTA PREVIA" watermark on every page.
- Declaración: neither; has a CSV stamp at the foot.

If none of the three markers match → `BorradorParseError("unrecognised Modelo 100 artefact")`.

### 5. CLI wiring

Extend `aeat filing import` with `--from-borrador PATH` (supporting all three artefact kinds via auto-detection):

```
aeat filing import --from-borrador ~/Downloads/borrador-renta-2024.pdf
    → detect_artefact_kind(pdf) = "borrador"
    → parse_borrador(pdf) → BorradorFiling(artefact_kind="borrador", values=..., ...)
    → build_draft(modelo=100, period=2024A, ...)
    → verify_declaracion(draft, filing, modelo_100_summary_ruleset_2025)
    → persist triplet; render verdict
```

### 6. Fixture corpus

- L3 synthetic generator: `tests/fixtures/pdf_corpus/l3_synthetic/_generators/modelo_100_summary_generator.py` renders a ~3-page PDF mimicking AEAT's summary block.
- L1 anchors: manually-generated Renta-Web-Open outputs covering ~5 life shapes per año (employee single / employee married with kids / autónomo / retiree / mixed).
- L2 anchors: Kent's own scrubbed Renta PDFs via the cluster-C scrub pipeline.

### 7. Tests

- `test_parse_borrador_summary_l3` — parametrised over 200 synthetic life-shape permutations. Assert every of the ~30 casillas extracted matches ground truth.
- `test_parse_borrador_artefact_kind_detection` — feed watermarked / unwatermarked / CSV-stamped synthetic PDFs; assert correct detection.
- `test_verify_modelo_100_summary_ruleset` — build a full synthetic Renta draft, verify via cluster-E pipeline, assert `status=verified`.
- `test_parse_borrador_unsupported_año_2019` — pre-2020 PDF → `BorradorParseError` naming the year constraint.

### 8. Explicit out-of-scope (becomes sub-EPIC #305-F-full)

- Anexo A / B / C / D / H / J / Ñ traversal.
- XFA parsing for pre-2020 Renta.
- Régimen-conditional section detection beyond summary.
- Integration with `aeat modelos` catalogue for autónomo-specific actividad codes.
- Renta rectificativa flow.
- Tarifa tables for años before 2020.

## Consequences

- Kent gets a working "verify my Renta summary matches AEAT's computation" workflow without waiting for full-anexo coverage.
- `aeat.adapters.inbound.borrador` module lands with artefact auto-detection; all three Renta artefact types share one extractor family.
- The synthetic generator pattern proves itself on a complex modelo — confirming cluster C's strategy scales.
- Full-anexo coverage becomes a well-scoped follow-up (sub-EPIC #305-F-full).
- `aeat.domain.formulas` gains its first Renta ruleset entry; future anexo rulesets plug into the same registry.
