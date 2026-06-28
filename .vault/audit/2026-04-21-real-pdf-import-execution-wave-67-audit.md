---
tags:
  - "#audit"
  - "#real-pdf-import"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-integration-tests-ci-plan]]"
  - "[[2026-04-21-casilla-schema-completeness-plan]]"
  - "[[2026-04-21-real-pdf-import-phase-3-summary-exec]]"
  - "[[2026-04-21-real-pdf-import-phase-4-summary-exec]]"
---

# real-pdf-import execution waves 6 / 7 — code review audit

## Scope

- **Wave 6** (`ee6931b`) — cluster H: Kent workflow integration tests + fixture-tier marker gate + weekly L1 drift workflow.
- **Wave 7** (`01ba60b`) — cluster B phase 2: Modelo 130 schema completion (casillas 08-19) + builder _compute handlers + xfail removal + submitter catalogue widening.

## Findings + resolutions

### HIGH — H1: Missing phase-N-summary for each wave (**fixed**)

Plan mandated one summary per wave. Present: phase-1 (#271 justificante), phase-2 (waves 2/3/4/5 combined). Missing: phase-3 (wave 6 / cluster H) and phase-4 (wave 7 / cluster B phase 2).

**Resolution**: new `2026-04-21-real-pdf-import-phase-3-summary.md` + `2026-04-21-real-pdf-import-phase-4-summary.md` under `.vault/exec/2026-04-20-pdf-import/`.

### MEDIUM — M1: Missing hand-calculated assertions for apartado-II/III/IV/V casillas (**fixed**)

Only casillas 03/04/07 had hand-calculated assertions; the 6 new computed casillas (09/11/12/14/17/19) shipped with schema + builder but no test proving the formulas compute the right values.

**Resolution**: `test_apartado_ii_to_v_casillas_match_hand_calculations` in `src/aeat/application/filing/test_filing.py` — deterministic input set (01=12500, 02=3500, 05=400, 06=0, 08=5000, 10=30, 13=0, 15=100, 16=0, 18=0); asserts every computed casilla value + formula trace.

### MEDIUM — M2: Coverage matrices stale vs. shipped state (**fixed**)

`docs/coverage/modelos.md` Modelo 130 `declaración import` column still showed `🚧 #305/D` after cluster D phase 1 + E shipped. `docs/coverage/kent-capabilities.md` cluster D + E rows still ❌.

**Resolution**: Modelo 130 row advanced to `✅ (19 casillas)` on schema + `✅ (2025 MVP)` on declaración import column. Kent capability `Import past filing from full declaración PDF` → `✅ Documented / ✅ CLI / ✅ Tested (L3 synthetic) / partial Observable`. `See import verdict` → `✅` across all four columns.

### MEDIUM — M3: correctness + fixture-tier + drift workflow (**passed**)

Reviewer confirmed the six new `_compute` handlers match the ruleset formulas verbatim. `_apply_fixture_tier_gates` runs harmlessly when no env vars are set. `.github/workflows/l1-anchor-drift.yml` has correct permissions + matches the script's CLI.

### LOW — L1: Brittle `"7 of 7 casillas extracted"` assertion (**fixed**)

The integration test hard-coded the extractor's current 7-casilla output count. When cluster D phase 2 widens the extractor to 19, three assertions would break silently.

**Resolution**: replaced with `re.search(r"\d+ of \d+ casillas extracted", result.output)` + equality between the two captured counts.

## Test + lint results post-fix

- `uv run pytest -m unit` — 1967 passed (1966 + new `test_apartado_ii_to_v_...`), 0 xfails, 1 skipped.
- `uv run ruff check src tests` + `uv run ty check src tests` — clean.
- End-to-end Kent smoke: Spanish "verificado" verdict stable; synthetic PDF → COMPLETE → VERIFIED round-trip unaffected.

## Decision

Waves 6 + 7 **ready to merge** with this same commit's fixes. No critical safety items; every HIGH / MEDIUM finding resolved.

## Closing observations

EPIC #305 has delivered 7 execution waves covering all 8 vaultspec-documented clusters except D phase 2 (Modelo 303 extractors) and F (Renta). The current state represents a fully-functional Kent UX improvement: drop a Modelo 130 declaración PDF → calc-verified draft with trilingual verdict. Every subsequent wave is additive; no regressions to the `#271` shipping contract.
