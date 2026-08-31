---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:2671ab07e11dca7e3ebf4738e0958e7e5d3db5ceaae3b720ecae3f5b5a3a523b'
step_id: 'S71'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Diagnose the seven red Modelo 390 tests in application/calculations/tests. They share a modelo but NOT a cause, and the split matters because one half is a test-fixture problem and the other half is a live engine question. FIRST CAUSE, four tests, SETTLED: modelo 390 once carried a forward-open '2010-y-siguientes' revision covering every year. Commit f9f3f77704 replaced it with year-pinned epochs 2021..2025, so filing year 2026 lost coverage and every test pinned to 2026 now raises NoRevisionForPeriodError. Modelo 303 by contrast IS forward-open ('2026-y-siguientes'), which is what hid the asymmetry. Authoring a 390 exercise-2026 revision is NOT available: the governing orden is EHA/3111/2009 and the per-year epochs exist because the form CONTENT changes annually by amending orden, which for exercise 2026 publishes around November 2026 and is filed January 2027 -- today is 2026-08-28, so it does not exist and inventing it is forbidden. The tests therefore move to a covered pair rather than the registry moving to them: the property under test is multi-year continuity and cross-renta isolation, which is year-agnostic, and 2025/2026 was only ever an arbitrary pick made while the registry was forward-open. Retargeted the reconciliation module to (2024, 2025) with its clock moved 2027-01-20 -> 2026-01-20, after confirming the reconciliation casilla exists in 390 revisions 2022..2025 and that iva.cuota-devengada-total and iva.cuota-deducible-total exist in BOTH halves of the split 303 2024 epoch, so the four quarters resolve cleanly across the mid-year revision boundary. Renamed the year-suffixed locals to earlier/later so a future retarget cannot leave misleading labels behind. STANDING GAP worth its own trigger: 303 computes 2026 quarters but 390 cannot produce the 2026 annual summary, so a real 2026 filer meets an honest refusal until the exercise-2026 orden is published and authored. SECOND CAUSE, a different failure entirely, NOT a year problem and NOT yet resolved: test_verify_modelo_revision_refuses_m390_when_prior_filings_are_not_clean already uses the covered year 2025 and fails inside calculate_modelo_revision at _require_m303_regimen_simplificado_annual_summary_handoff, which is a strict biconditional -- a revision that DECLARES an m303_regimen_simplificado_annual_summary binding must receive a handoff, and one that does not must not. All four 390 epochs declare that family, and so did the deleted 2010-y-siguientes, so the declaration is not new; the guard is, landing 2026-08-14 in e2797f1aad. The resolver keys applicability on the REVISION alone: m303_regimen_simplificado_annual_summary_requirement returns non-None whenever the bindings exist, and _source_work_unit then RAISES unless exactly one filed same-bucket 303 4T work unit exists. Boxes 74-83 are regimen simplificado boxes that every 390 form carries, so the requirement fires for every 390 filer including the GENERAL-regime taxpayer this test declares. THE OPEN QUESTION, which is a tax-semantics question and must be grounded rather than assumed: whether a 390 calculation may legitimately hard-require a filed 303 4T source unconditionally. It is defensible that an annual IVA summary presupposes the year's quarterly filings, and equally defensible that a general-regime filer with no simplificado activity should not be routed through a simplificado handoff -- and 2026-07-01-modelo-303-regimen-simplificado-adr already establishes a narrower applicability vocabulary in which not-claimed is neutral and must reject Orden and module rows, which this requirement never consults. Do not resolve by relaxing the guard: it exists to keep the handoff on one mesh-owned arrival path

## Scope

- `src/cadrumo/application/calculations/tests/test_modelo_390_303_reconciliation_continuity.py`
- `src/cadrumo/application/modelo/_calculation_actions.py`

## Changes

- `M` `src/cadrumo/application/calculations/tests/test_modelo_390_303_reconciliation_continuity.py`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S71.md`

## Notes

- Immutable historical provenance: `f9f3f77704` replaced the open `2010-y-siguientes` Modelo 390 revision with bounded 2022–2025 epochs; test coverage at that point still selected 2025/2026 and therefore requested uncovered 390/2026. `71cb4416c5` retargeted the reconciliation fixture to 2024/2025, moved its clock to 2026-01-20, and renamed the year-suffixed locals to `earlier`/`later`.
- This Step records the fixture diagnosis and retarget only. The then-independent covered-2025 GENERAL-regime handoff failure belongs to S72's question and was later resolved under S73 by `94187f454c55ddd1df6265d7f66601c0df4fdfe2`, which makes the handoff antecedent declaration AND taxpayer applicability.
- No historical pytest receipt was recovered from immutable commits or Vault records. No fresh pytest receipt is claimed: active shared suites were running. When the tree and test processes are quiescent, the serial candidate is `uv run --no-sync pytest -n0 -q src/cadrumo/application/calculations/tests/test_modelo_390_303_reconciliation_continuity.py src/cadrumo/application/calculations/tests/test_cross_period_clean_state_provenance.py`.
