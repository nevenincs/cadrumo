---
tags:
  - "#exec"
  - "#real-pdf-import"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-declaracion-extractor-plan]]"
  - "[[2026-04-21-real-pdf-import-phase-4-summary-exec]]"
---

# real-pdf-import execution phase 5 — wave 9 (cluster D phase 2, Modelo 303)

## Delivered capability

`aeat filing import --from-declaracion <pdf>` now handles Modelo 303 IVA declaraciones alongside Modelo 130. Kent drops the quarterly IVA PDF and every one of 33 schema casillas round-trips to the extractor + chains through the formula engine.

```
$ aeat filing import --from-declaracion iva303-2025Q1.pdf
Parsed Modelo 303 2025Q1 declaración (template 2025.01). 33 of 33 casillas extracted.
Extraction status: COMPLETE
Verification status: NEEDS_REVIEW (ruleset=modelo_303.2025)
  — per-casilla discrepancy classifications surface Spanish-first rationales.
```

## Commit

- `0c09bf7` — *feat(declaracion): cluster D phase 2 — Modelo 303 v2025 extractor*

## Files landed

- `src/aeat/adapters/inbound/declaracion/_extractors/modelo_303_v2025.py` — line-anchored regex for all 33 casillas covering Apartado 1 (01-09), Apartado 2 (28-43), Resultado (44, 45, 64-71). Multi-match confidence downgrade + `ambiguous-label` warning mirror the Modelo 130 primitive stack.
- `src/aeat/adapters/inbound/declaracion/_extractors/__init__.py` — registry extended with `(303, 2025, "2025.01")`.
- `tests/fixtures/pdf_corpus/l3_synthetic/_generators/modelo_303_generator.py` — `Modelo303GenParams` + `generate()` renders 33 casillas in declaration order. Shares `_generator_shared` primitives with Modelo 130.
- `src/aeat/adapters/inbound/declaracion/test_modelo_303_v2025.py` — 3 unit tests: 33-casilla COMPLETE round-trip, template auto-detection, sparse 23-of-33 PARTIAL extraction + 10 casilla-not-found warnings.

## Kent UX roleplay

- **Happy path**: 33 of 33 casillas extracted; calc verification chains against `modelo_303.2025` ruleset (12 formulas). Internally-consistent IVA values → VERIFIED. Mis-totalled cuota líquida → per-casilla `CORRECTNESS_DIVERGENCE` rationale.
- **Partial**: 23 of 33 casillas → `PARTIAL` status + 10 `casilla-not-found` warnings in Kent's output language.
- **Ambiguous label**: when the synthetic's regex double-matches (not currently observable because generator produces one line per casilla), confidence drops to 0.5 and downstream verification classifies as EXTRACTION_UNRELIABLE.

## Quality gates

- `uv run ruff check` + `uv run ty check` — clean.
- `uv run pytest -m unit` — 1971 passed, 0 xfails, 1 skipped (1967 + 4 new).

## Follow-up

- Wave 10 (cluster F MVP) lands Modelo 100 Renta summary-block import — closes the IVA + Renta pair the user requested.
- Modelo 303 v2024.09 (post-HAC/819/2024 renumbering) tracked for cluster D phase 3; the template-revision registry is ready.
