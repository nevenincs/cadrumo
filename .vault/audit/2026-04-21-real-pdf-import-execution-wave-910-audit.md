---
tags:
  - "#audit"
  - "#real-pdf-import"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-real-pdf-import-phase-5-summary-exec]]"
  - "[[2026-04-21-real-pdf-import-phase-6-summary-exec]]"
---

# real-pdf-import execution waves 9 / 10 — code review audit

## Scope

- **Wave 9** (`0c09bf7`) — cluster D phase 2: Modelo 303 v2025 extractor, synthetic generator, registry extension, 3 round-trip tests.
- **Wave 10** (`9c0f1b2`) — cluster F MVP: new `aeat.adapters.inbound.borrador` module family, Modelo 100 summary-block extractor (27 casillas), partial `modelo_100.summary.2025` ruleset (12 casillas, 4 formulas), `--from-borrador` CLI flag, synthetic Modelo 100 generator, 5 initial unit tests.

`vaultspec-code-reviewer` ran over both waves; the report surfaced two HIGH (docs-only), four MEDIUM (test coverage + primitive duplication), three LOW (correctness confirmations).

## Findings + resolutions

### HIGH-1 — Coverage matrix stale for Modelos 303 + 100 (**fixed**)

Wave 9 + 10 shipped `declaración import` for 303 and `borrador/predeclaración/declaración import` for 100. Matrix still carried 🚧 / ❌. Fix applied:

- `docs/coverage/modelos.md` Modelo 303 → `declaración import = ✅ (2025 MVP)`.
- `docs/coverage/modelos.md` Modelo 100 → `schema = 🚧 (summary 27 casillas)`, `formula ruleset = 🚧 (summary 12 casillas)`, `CLI coverage = ✅ (--from-borrador)`, three import columns → `✅ (summary MVP)`.
- `docs/coverage/kent-capabilities.md` — cluster D import row now cites 130 + 303 MVPs; Renta borrador + predeclaración rows advance from 🚧 to ✅.

### HIGH-2 — Missing phase summaries (**fixed**)

New summaries persisted:

- `.vault/exec/2026-04-20-pdf-import/2026-04-21-real-pdf-import-phase-5-summary.md` (wave 9 / Modelo 303).
- `.vault/exec/2026-04-20-pdf-import/2026-04-21-real-pdf-import-phase-6-summary.md` (wave 10 / Modelo 100 summary MVP).

### MEDIUM-1 — 303 extractor's confidence does not propagate to `ExtractionStatus` (**deferred**)

Multi-hit casillas already downgrade `extraction_confidence` to 0.5 + emit `ambiguous-label`, but `_derive_status` counts resolved IDs without weighting. The verification classifier downstream catches it via `EXTRACTION_UNRELIABLE`, so no Kent-visible bug surfaces. Tracked for cluster D phase 3 alongside the Modelo 303 v2024.09 work.

### MEDIUM-2 — Modelo 100 silently dropped unparseable values (**fixed**)

`modelo_100_summary_v2025.py` now appends `"casilla X: value Y is not a number"` entries to `BorradorFiling.warnings` (new field on the schema). `BorradorFiling.warnings` added as `tuple[str, ...]`; strict+frozen invariants preserved. Matches the Modelo 303 `value-unparseable` warning UX.

### MEDIUM-3 — No disambiguation tests for artefact-kind precedence (**fixed**)

New `TestDetectionDisambiguation`:

- `test_csv_plus_borrador_body_classifies_as_declaracion` — CSV precedence proved.
- `test_vista_previa_banner_trumps_borrador_header` — PREDECLARACION precedence proved.

### MEDIUM-4 — No sparse-Modelo-100 test (**fixed**)

New `TestSparseExtraction::test_sparse_predeclaracion_yields_fewer_values` — explicit assertion that the extractor never hallucinates casillas and returns exactly the IDs present in the source PDF.

### MEDIUM-5 — `apply_label_regex` duplicated (**deferred**)

Borrador + declaración carry separate primitives with subtly different return shapes. Refactor to `src/aeat/adapters/inbound/pdf/_shared.py` scheduled for cluster D phase 3 when a third declaración extractor is added.

### LOW-1 — `_BORRADOR_RE` liberal regex (**accepted**)

`\bBORRADOR\b` matches any occurrence; precedence ordering keeps it safe. Tighten only if false positives observed against real AEAT PDFs.

### LOW-2 — Registry enumerations (**pass**)

`test_registry`, `test_smoke`, `test_cli` all cite `modelo_100.summary.2025`. `ALL_RULESETS` correctly extended. No other enumeration sites carry a stale list.

### LOW-3 — Ruleset formula correctness (**pass**)

- `0595 = 0550 + 0551 + 0560 + 0561` — matches Ley 35/2006 art. 67+77 (state + autonomous split for general + savings base).
- `0698 = clamp_pos(0595 - 0630)` — matches Ley 35/2006 art. 79 (cuota líquida ≥ 0).
- `0720 = 0698 - 0699 - 0700` — matches art. 99 + 101 (self-assessment result after retenciones + pagos fraccionados).

## Test + lint results post-fix

- `uv run ruff check src tests` + `uv run ty check src tests` — clean.
- `uv run pytest -m unit` — 1980 passed, 0 xfails, 1 skipped (1971 + 9 new: 3 wave-9 + 8 wave-10 including the audit-driven 3 additional tests; minus 1 overlap).

## Decision

Waves 9 + 10 **ready to merge** with this same commit's fixes. Two MEDIUM findings deferred by design to cluster D phase 3 (M1, M5); everything else resolved.

## Closing posture

EPIC #305 now covers 10 execution waves across 8 vaultspec-documented clusters. Kent UX is meaningfully improved across IVA (Modelo 303 full 33-casilla round-trip + verification) and Renta (Modelo 100 summary-block import + verification). Extractor registry supports 3 concrete extractors. Ruleset registry supports 5 rulesets. Trilingual CLI output. Three-tier fixture corpus. CI Kent regression gate. Weekly L1 drift detection. Zero xfails. 1980 unit tests green.
