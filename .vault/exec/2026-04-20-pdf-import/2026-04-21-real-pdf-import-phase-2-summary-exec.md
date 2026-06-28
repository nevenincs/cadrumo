---
tags:
  - "#exec"
  - "#real-pdf-import"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-real-pdf-fixture-corpus-plan]]"
  - "[[2026-04-21-declaracion-extractor-plan]]"
  - "[[2026-04-21-calc-verification-plan]]"
  - "[[2026-04-21-real-pdf-import-execution-wave-234-audit]]"
---

# real-pdf-import execution phase 2 — waves 2 / 3 / 4 summary

## Delivered capability

Kent drops a Modelo 130 v2025 declaración PDF on the CLI and gets a single-word verdict re-derived from the project's formula engine:

```
$ AEAT_OUTPUT_LANGUAGE=es aeat filing import --from-declaracion ~/path/to/declaracion-130-2025Q1.pdf
Parsed Modelo 130 2025Q1 declaración (template 2025.01). 7 of 7 casillas extracted.
Extraction status: COMPLETE
Verification status: VERIFIED
  Modelo 130 2025Q1: verificado. Cobertura 37%. 0 discrepancias no bloqueantes (redondeo / reglas no modeladas).
```

Kent does not observe phases A or G directly (scaffolding), nor phase B-1 (schema provenance); he first observes a Kent-level change at phase 2 — the full extract → verify loop against a Modelo 130 PDF.

## Commits landed (in order)

1. `fbde5d2` — wave 2 cluster C scaffolding (PII scrub library, synthetic generator primitives, L1 manifest fetcher, pytest markers).
2. `398ef82` — wave 3 cluster D phase 1 (aeat.adapters.inbound.declaracion module + Modelo 130 v2025 extractor + synthetic Modelo 130 L3 generator + CLI `--from-declaracion`).
3. `1723119` — wave 4 cluster E (aeat.application.verification module + discrepancy classifier + CLI verification chaining).
4. This commit (audit-driven hardening) — fixes H1, H2, M1, M2, M4, M5 from the formal code review (`.vault/audit/2026-04-21-real-pdf-import-execution-wave-234-audit.md`).

## Files touched this phase

- `src/aeat/adapters/inbound/pdf/_scrub.py` — full Spanish-PII regex set (NIF / NIE / IBAN / phone / email / CP / prefixed name / amounts / CSV / presentation ID).
- `src/aeat/adapters/inbound/pdf/test_scrub.py` — 20 scrub tests (up from 13).
- `src/aeat/adapters/inbound/declaracion/` — new module family; 7 extractor tests + 7 integration round-trip tests.
- `src/aeat/application/verification/` — new module; 6 tests.
- `src/aeat/entrypoints/cli/filing/__init__.py` — `--from-declaracion` + verification chaining + trilingual output.
- `tests/fixtures/pdf_corpus/` — three-layer corpus directory skeleton + synthetic generator primitives.
- `scripts/fetch_l1_anchors.py` — L1 manifest + hash-verified fetch + drift detection.
- `pyproject.toml` — `fixture_tier_l1/l2/l3` markers registered.

## Quality gates

- `uv run ruff check src tests` — clean.
- `uv run ty check src tests` — clean.
- `uv run pytest -m unit` — 1970+ passed, 2 intentional xfails (cluster-B schema gap), 1 skipped.
- End-to-end CLI smoke: Modelo 130 synthetic PDF → COMPLETE extraction → VERIFIED verdict, with Spanish default output.

## Kent UX roleplay (post-hardening)

**Path A — happy**: Kent drops a well-formed Modelo 130 PDF. CLI prints parse + extraction + verification in five lines; single-word verdict `VERIFIED`. Spanish narrative by default.

**Path B — partial extraction**: Kent drops a scan-heavy or layout-drifted PDF. CLI prints the parse line + a `[warnings] N:` block listing each missing casilla + `Extraction status: PARTIAL`. Verification runs against whatever was extracted and returns `NEEDS_REVIEW` (because `casilla-not-found` now downgrades the verdict). Kent sees the per-casilla reason and knows exactly which cells to fill manually.

**Path C — ambiguous regex**: Kent drops a PDF where one casilla's label phrase matches the template twice (e.g. a summary + a detail block). The extractor emits `ambiguous-label` with `extraction_confidence=0.5`; the verification classifier classifies that casilla's discrepancy as `EXTRACTION_UNRELIABLE` and the final verdict is `NEEDS_REVIEW`. Kent sees a cause-typed rationale pointing him at the exact casilla.

**Path D — structural integrity**: Kent's PDF has legitimately mis-extracted `01`, `02`, or `03`. The `_structural_integrity_check_01_minus_02` helper sees `01 - 02 ≠ 03` beyond the 0.02 € tolerance, downgrades 03's confidence, and surfaces the inconsistency as an `ambiguous-label` warning — which the classifier then flips to `EXTRACTION_UNRELIABLE`. Kent sees a specific "ruptura de integridad (01 - 02 ≠ 03)" message.

**Path E — unverifiable**: Kent drops a Modelo 390 PDF. There's no ruleset registered for 390 (`#221`). Verification returns `UNVERIFIABLE` with a Spanish narrative: *"Modelo 390 2025: no hay ruleset registrado; no se puede verificar."* Draft still lands; Kent knows why the verdict is held.

## Known gaps / follow-ups

- **Cluster B phase 2**: Modelo 130 schema has 7 casillas vs. ruleset's 9; 6 of 19 real-form casillas still missing. Needs corpus completion before coverage > 37%.
- **Cluster D phase 2+**: Modelo 303 post-HAC/819/2024 + Modelo 303 2025 extractors. H2 hardening prepared the registry; bodies still to land.
- **Cluster F**: Renta (Modelo 100) summary-block extractor.
- **Cluster H**: CI integration — `fixture_tier_*` collection hook + extraction-quality artifact + weekly drift workflow.
- **Real L1 anchors**: manifest is empty. Requires a one-shot fetch pass (BOE `BOE-A-2024-16129.pdf`, Manual IVA 2024 Cap_9_303 offprint) — not blocking, but CI drift-detection is a noop until entries exist.
- **L2 sourcing**: blocked on the user's one-shot `aeat drive find` + `just scrub-from-drive` run. Scrub library is ready when fixtures arrive.

## Next execution wave

- **Wave 5** — cluster H execution (CI wiring + Kent workflow integration tests).
- **Wave 6** — cluster B phase 2 (Modelo 130 schema completion + formula engine consistency).
- **Wave 7** — cluster D phase 2 (Modelo 303 v2024.09 + v2025 extractors).
- **Wave 8** — cluster F MVP (Renta summary block + borrador artefact detection).
