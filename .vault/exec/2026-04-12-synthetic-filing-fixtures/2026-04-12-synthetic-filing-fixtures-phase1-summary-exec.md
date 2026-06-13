---
name: Synthetic filing fixtures phase1 summary
description: Execution summary for issue #14 — synthetic filing history loader + corpus
tags:
  - "#exec"
  - "#synthetic-filing-fixtures"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-synthetic-filing-fixtures-plan]]"
  - "[[2026-04-12-synthetic-filing-fixtures-adr]]"
  - "[[2026-04-12-synthetic-filing-fixtures-research]]"
---

# exec summary — synthetic-filing-fixtures phase1

Branch: `feature/14-synthetic-filing-fixtures`
Worktree: `Y:/code/aeat-worktrees/feature-14-synthetic-filing-fixtures`

## Bootstrap

The worktree carried a pre-merge snapshot from the prior stalled
Gemini session (11 #4 commits already merged to main via different
hashes). A `git rebase origin/main` surfaced rename/delete
conflicts that had no resolution path because the branch had zero
#14 work. Action: `git reset --hard origin/main`, then
`uv sync` (vaultspec-core was already installed).

## Work delivered

1. **Errors** — added
   `aeat.core.errors.FilingFixtureError(AeatError)`.
2. **Schema** — `src/aeat/domain/testing/_schema.py` defines
   `FilingRecord`, `FixtureCasilla`,
   `FilingRecordPeriodKind`, `FilingRecordScenario`, and the
   `compute_record_id` helper. All models are strict + frozen
   + `extra="forbid"`. `FilingDraftStatus` is reused from
   `aeat.application.filing`.
3. **Loader** — `src/aeat/domain/testing/_loader.py` resolves
   `SYNTHETIC_FIXTURES_ROOT` by walking parents of `__file__`
   until `tests/fixtures/filing_history/` appears, then
   implements `load_filing_history(modelo, period)` via
   `FilingRecord.model_validate_json` (pydantic v2 JSON mode
   handles Decimal + datetime coercion without loosening the
   strict Python-mode invariants).
4. **Public API** — `src/aeat/domain/testing/__init__.py` re-exports
   the whole public surface and carries the contributor doc
   (how to add a new fixture, invariants, example usage).
5. **Fixture corpus** — 17 hand-curated JSON files under
   `tests/fixtures/filing_history/modelo_{130,303,390}/`:
   - 130: 2024Q1 clean + complementaria, 2024Q2 with-errors,
     2024Q3 amended, 2024Q4 cancelled, 2025Q1 clean, 2025Q2
     clean, 2025Q3 rounding.
   - 303: 2024Q1 clean, 2024Q2 clean, 2024Q3 complementaria,
     2024Q4 clean, 2025Q1 with-errors, 2025Q2 amended.
   - 390: 2023 clean, 2024 clean, 2024 complementaria.
   Every file starts with `"synthetic": true` followed by the
   `_comment` warning string.
6. **Unit tests** — `src/aeat/domain/testing/test_testing.py` with 21
   `@pytest.mark.unit` tests covering corpus load, modelo
   coverage, scenario coverage, synthetic invariant,
   filename-level comment marker, modelo/period filters,
   period-kind parser, status enum identity, record_id
   uniqueness, Decimal totals, negative paths for missing /
   empty / non-synthetic markers, `extra="forbid"`, stable
   content-addressed hash, and a malformed-JSON loader smoke
   test. No mocks, no patches.

## Results

- `just lint` → clean (ruff).
- `just typecheck` → clean (ty).
- `just test` → 403 passed, 1 skipped, 15 deselected (the 21
  new tests are all inside the 403).
- `just hooks` → clean (prek).

## Notes for followups

- #6 modelo enum is not yet on main — `FilingRecord.modelo`
  remains a loose `str`. When the enum lands, tighten the
  field and re-run the suite; fixture files keep their
  current string values.
- #23 casilla DB is not yet on main — `FixtureCasilla.casilla_id`
  likewise remains a loose string. Future strict-mode upgrade
  is additive.
- The corpus was authored once via a transient helper script
  that produced content-addressed `record_id` values; the
  script has been deleted to honour the "no generation
  tooling" scope boundary. The JSON files are the source of
  truth.
