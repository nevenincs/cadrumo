---
tags:
  - "#exec"
  - "#real-pdf-import"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-casilla-schema-completeness-plan]]"
  - "[[2026-04-21-real-pdf-import-phase-3-summary-exec]]"
---

# real-pdf-import execution phase 4 — wave 7 (cluster B phase 2)

## Delivered capability

The Modelo 130 runtime schema now enumerates **all 19 casillas** the formula engine references. The silent correctness bug cluster-B research documented — drafts built today were missing 12 of 19 casillas — is closed. The cross-validation xfail flipped to pass and was removed; every computed casilla now has a matching schema entry and a matching builder handler. Kent's draft for Modelo 130 now carries the full Apartado I–V structure.

## Commit

- `01ba60b` — *feat(filing): cluster B phase 2 — Modelo 130 schema completion (EPIC #305 wave 7)*

## Files landed

- `src/aeat/application/filing/_builders/_modelo_130_schema.py` — 12 new `StaticCasillaSchema` entries (08-19) across Apartado II (agrícola), III (suma parcial + minoración), IV (deducciones + arrastre), V (ingreso previo + resultado final). Each carries the AEAT Manual práctico description.
- `src/aeat/application/filing/_builders/modelo_130.py` — 6 new `_compute` branches for computed casillas 09, 11, 12, 14, 17, 19. New `_PAGO_AGRARIA_RATE = 0.02` mirrors the ruleset's `agraria.trimestral_rate` parameter.
- `src/aeat/application/filing/test_schema_completeness.py` — xfail markers for Modelo 130 2024 + 2025 removed; all 4 parametrised cases now pass.
- `src/aeat/adapters/outbound/aeat/export/_submitters/test_modelo130.py` — `_Catalogue` fixture widened from 7 to 19 casillas so submission smoke tests reflect the real form.

## Kent UX roleplay

- `aeat filing build --modelo 130 --period 2025Q1 --inputs <json>` now expects inputs for 01, 02, 05, 06, 08, 10, 13, 15, 16, 18 (ten literals). Computed outputs emerge at 03, 04, 07, 09, 11, 12, 14, 17, 19.
- `aeat filing show <draft>` renders every apartado's casilla row in declaration order; the draft JSON carries 19 values vs. the previous 7.
- `aeat filing validate <draft>` runs the full ruleset; missing literals on apartado II/III/IV/V surface as per-casilla findings rather than silently falling through.
- For the agrícola path specifically: supplying casilla 08 (volumen ingresos agraria) triggers casilla 09 = 2% × 08 computation, and casillas 10 / 11 close the agrícola loop exactly as the ruleset derives them.

## Quality gates

- `uv run pytest -m unit` — 1966 passed, **0 xfails**, 1 skipped. Cluster B phase 2 is complete — the xfail debt from phase 1 is fully discharged.
- `uv run ruff check src tests` + `uv run ty check src tests` — clean.
- New hand-calculated apartado-II/III/IV/V assertions in `src/aeat/application/filing/test_filing.py::TestModelo130Builder::test_apartado_ii_to_v_casillas_match_hand_calculations`: six computed casillas with deterministic inputs (01=12500, 02=3500, 05=400, 08=5000, 10=30, 13=0, 15=100) verify every new handler.

## Follow-up

- Modelo 303 schema (Apartado IV+) — cluster B phase 3; ~88 casillas.
- Modelo 390 schema — cluster B phase 4; blocked on ruleset #221.
- Modelo 130 declaración extractor (cluster D phase 1) still targets 7 casillas; cluster D phase 2 widens the label-regex map to the full 19.

## Reconciled audit findings

Wave 6/7 code review landed two HIGH / three MEDIUM / one LOW items; every required fix was applied in this same commit chain:

- Hand-calculated assertions for new casillas — ✅ `test_apartado_ii_to_v_casillas_match_hand_calculations`.
- Phase-3 + phase-4 exec summaries — ✅ present (this file and its phase-3 sibling).
- Coverage-matrix refresh — ✅ Modelo 130 schema column shows `✅ (19 casillas)`; Kent capability row `Import past filing from full declaración PDF` + `See import verdict` advanced to `✅`.
- Regex softening of the `N of N casillas extracted` Kent integration assertion — ✅ `re.search` replaces the fixed string.
