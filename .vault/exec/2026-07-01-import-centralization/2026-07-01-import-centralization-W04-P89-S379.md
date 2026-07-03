---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S379'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Wire dev/import_hygiene_scan.py into the pytest/CI surface as the authoritative import-hygiene gate

## Scope

- `src/aeat/tests/test_import_hygiene_gate.py`

## Description

- Authored `src/aeat/tests/test_import_hygiene_gate.py` (`pytest.mark.unit`,
  `pytest.mark.hex_core`) importing the real scanner (`dev.import_hygiene_scan`)
  and running it against the live `src/aeat` tree on every test run — no
  fixtures, no mocks, real AST walk.
- Six checks, backed by `dev/import_hygiene_baseline.json`:
  - `test_baseline_file_is_well_formed` — the baseline exists and declares all
    three families.
  - `test_production_family1_violations_do_not_exceed_baseline_count` — the
    ratchet: current non-test violation count must not exceed the baseline
    count.
  - `test_production_family1_violations_are_exactly_the_named_baseline_set` —
    stricter than a bare counter: every current violation must be a NAMED
    baseline entry, so a new unnamed violation cannot hide behind an unrelated
    fix in the same pass (net-count-unchanged smuggling).
  - `test_family2_shim_modules_are_exactly_the_documented_bridges` — equality,
    not a ceiling: a new undocumented shim fails, and a documented bridge that
    stops being a shim also fails (forces deliberate baseline maintenance).
  - `test_family3_retired_umbrella_symbols_have_not_reappeared` — the 7
    symbols retired from the app-layer umbrella facades in Wave W03.P88 must
    stay out of their retired owning facade's `__all__`. Checked directly
    against each retired symbol's own former owning package (not the noisy
    multi-sourced Case-B signal, which still flags these names purely because
    a test file reaches the sole domain-layer private submodule directly —
    that is Wave W05 test debt, not an umbrella-retirement regression).
  - `test_family3_genuine_duplicate_symbols_are_exactly_the_pinned_set` — every
    Case-A (declared in more than one facade's `__all__`) `confidence="high"`
    symbol must be in the named tolerated set (currently only
    `DEFAULT_IVA_GENERAL_RATE_PCT`); Case-B hits (facade + private dual
    consumption, overwhelmingly test-only) are explicitly out of scope for
    this pin, since they shrink via Wave W05, not via a Family-3 fix.
- Proved the gate is not tautological: temporarily shrank the baseline's
  `sites` list to 2 entries and re-ran the suite — both the count-ratchet and
  the set-equality tests failed loudly with the expected precise
  `path:lineno imports [...] from ...` diagnostics; restored the full baseline
  and re-ran green.
- Confirmed `PKG_ROOT` is exported from `dev/import_hygiene_scan.py`
  (module-level constant, no change needed) and that
  `from dev.import_hygiene_scan import ...` from `src/aeat/tests/` is an
  established pattern (mirrors
  `src/aeat/_data/corpus/tests/test_extraction_sidecar_freshness.py` importing
  `from dev.docs.preprocess import ...`).

## Outcome

`uv run --no-sync pytest src/aeat/tests/test_import_hygiene_gate.py -m unit`
passes 6/6. `ruff check` / `ruff format --check` pass on the new module.
`pytest --collect-only -q src/aeat` collects 12167 tests with zero collection
errors.

## Notes

None.
