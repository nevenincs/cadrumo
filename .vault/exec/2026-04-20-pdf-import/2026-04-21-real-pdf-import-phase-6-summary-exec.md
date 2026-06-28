---
tags:
  - "#exec"
  - "#real-pdf-import"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-modelo-100-renta-plan]]"
  - "[[2026-04-21-real-pdf-import-phase-5-summary-exec]]"
---

# real-pdf-import execution phase 6 — wave 10 (cluster F MVP, Modelo 100 Renta)

## Delivered capability

Kent drops a Modelo 100 Renta PDF — **borrador**, **predeclaración** (Renta Web Open simulación), or **declaración** — and gets the summary block extracted + verified against the partial ruleset.

```
$ AEAT_OUTPUT_LANGUAGE=es aeat filing import --from-borrador borrador-renta-2025.pdf
Parsed Modelo 100 Renta 2025 (BORRADOR). 12 summary-block casillas extracted.
Verification status: VERIFIED (ruleset=modelo_100.summary.2025)
```

## Commit

- `9c0f1b2` — *feat(borrador,formulas): cluster F — Modelo 100 Renta summary-block MVP*

## Files landed

### New module: `src/aeat/adapters/inbound/borrador/`

- `__init__.py` + `_parser.py` — public `parse_borrador(pdf, *, artefact_kind_override, año_override)`.
- `_schema.py` — `BorradorFiling` (strict+frozen), `ArtefactKind` enum with values `BORRADOR / PREDECLARACION / DECLARACION`, plus a `warnings: tuple[str, ...]` field for unparseable values (added during audit closure for M2).
- `_errors.py` — `BorradorParseError < PdfFilingImportError`, `ArtefactNotRecognisedError`.
- `_detect.py` — regex-based detection of VISTA PREVIA banner, CSV stamp, BORRADOR header; precedence PREDECLARACION > DECLARACION > BORRADOR.
- `_extract.py` + `_parsers/` — pdfplumber backend + label-regex primitive (shared shape with `aeat.adapters.inbound.declaracion._extract`; full consolidation deferred).
- `_extractors/modelo_100_summary_v2025.py` — summary-block extractor covering 27 casillas (rendimientos netos, ganancias, base imponible, mínimos, base liquidable, cuotas íntegras, deducciones, cuota líquida, retenciones, resultado).

### New ruleset: `src/aeat/domain/formulas/_rulesets/modelo_100_summary_2025.py`

12 casillas × 4 formulas:

- `0595 = 0550 + 0551 + 0560 + 0561` — cuota íntegra total.
- `0630 = 0620 + 0622` — total deducciones.
- `0698 = clamp_pos(0595 - 0630)` — cuota líquida.
- `0720 = 0698 - 0699 - 0700` — cuota resultante.

Legal citations: Ley 35/2006 (IRPF) + RD 439/2007 (RIRPF).

### Synthetic generator: `tests/fixtures/pdf_corpus/l3_synthetic/_generators/modelo_100_generator.py`

Renders 27 summary casillas + the artefact-specific marker (BORRADOR header / VISTA PREVIA banner + diagonal watermark / CSV footer) so `detect_artefact_kind` classifies each kind distinguishably.

### CLI extension: `src/aeat/entrypoints/cli/filing/__init__.py`

- New `--from-borrador <PATH>` flag, mutually exclusive with `--from-justificante` / `--from-declaracion`.
- Auto-detects artefact kind; chains `Engine.audit_against` with the summary ruleset; prints Kent-readable verdict.

### Tests: `src/aeat/adapters/inbound/borrador/test_modelo_100_summary.py`

8 tests:

- `TestArtefactKindDetection` (3 tests) — each of the three artefact kinds detected.
- `TestSummaryBlockExtraction` — round-trip of every summary casilla; ruleset's 12 casillas all present.
- `TestDetectionDisambiguation` (2 tests) — CSV precedence + VISTA PREVIA precedence (added during audit closure M3).
- `TestSparseExtraction` — sparse predeclaración yields strictly smaller value tuple (added during audit closure M4).
- `TestOverrides` — forcing DECLARACION without a CSV raises cleanly.

## Kent UX roleplay

- **Kent with a Renta Web Open simulation**: drops `renta-web-open-vista-previa.pdf` → detection returns `PREDECLARACION`, extractor finds every summary casilla, ruleset verifies. "Yes, AEAT's tool computed the same cuota resultante as my tool."
- **Kent with his AEAT-filed 2024 declaración**: drops `declaracion-renta-2024.pdf` → detection returns `DECLARACION`, CSV surfaces in output, every casilla extracted + verified.
- **Kent with a pre-filing borrador**: drops the Portal Renta borrador → detection returns `BORRADOR`, casillas extracted, verification runs against whatever AEAT computed — any discrepancy with Kent's expected return lands as a cause-typed divergence.

## Quality gates

- `uv run ruff check src tests` + `uv run ty check src tests` — clean.
- `uv run pytest -m unit` — 1980 passed, 0 xfails, 1 skipped.
- End-to-end CLI smoke for Renta (Spanish default) — VERIFIED verdict chain confirmed.

## Follow-up (sub-EPIC #305-F-full)

- Full-anexo extraction (Anexos A, B, C, D, H, Ñ).
- Régimen-conditional sections (autónomo estimación directa vs. módulos; single vs. married with dependents).
- Pre-2020 XFA PDF support (Renta forms before the Renta Web era).
- Tarifa progresiva evaluation (cuota íntegra from base liquidable, currently a literal in MVP).
- Deducciones autonómicas per comunidad autónoma (17 Spanish regions × their own tables).
- Reintegración de deducciones practicadas indebidamente (casilla 0609).

None are blocking for the Kent MVP; every extension lands additively on this module family.
