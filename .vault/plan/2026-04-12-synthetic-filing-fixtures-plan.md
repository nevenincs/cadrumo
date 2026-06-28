---
name: Synthetic filing fixtures plan
description: Implementation plan for issue #14 — synthetic filing history corpus + loader
tags:
  - "#plan"
  - "#synthetic-filing-fixtures"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-synthetic-filing-fixtures-research]]"
  - "[[2026-04-12-synthetic-filing-fixtures-adr]]"
---

# plan — synthetic-filing-fixtures

Status: **Approved (self-review, see Plan Review section below)**
Branch: `feature/14-synthetic-filing-fixtures`

## Goal

Land the `aeat.domain.testing` subpackage: a typed pydantic v2
`FilingRecord`, a deterministic `load_filing_history` iterator,
17 hand-curated synthetic fixture files, colocated unit tests,
and a contributor docstring — all gated by the synthetic-only
invariant.

## Steps

1. **Errors** — add `FilingFixtureError(AeatError)` to
   `src/aeat/errors.py`, following the existing
   `FixtureProvisioningError` docstring style.

2. **Subpackage layout**
   - `src/aeat/domain/testing/__init__.py` — public API, contributor
     docstring, `__all__`.
   - `src/aeat/domain/testing/_schema.py` — `FilingRecord`,
     `FixtureCasilla`, `FilingRecordPeriodKind`,
     `FilingRecordScenario`. Strict, frozen, `extra="forbid"`.
   - `src/aeat/domain/testing/_loader.py` — `SYNTHETIC_FIXTURES_ROOT`
     resolver, `load_filing_history` iterator, JSON + pydantic
     parsing wrapped in `FilingFixtureError`.
   - `src/aeat/domain/testing/test_testing.py` — colocated unit tests.

3. **Schema details**
   - `FilingRecord.synthetic: Literal[True]` — pydantic will
     reject anything else.
   - `FilingRecord._comment: str = Field(..., min_length=1,
     alias="_comment")`. Configure the model to accept the
     alias on load (pydantic v2 `populate_by_name=True`).
   - `FilingRecord.source: Literal["synthetic"]`.
   - `FilingRecord.status: FilingDraftStatus` — imported from
     `aeat.application.filing`.
   - `FilingRecord.casillas: tuple[FixtureCasilla, ...]`.
   - `FilingRecord.totals: dict[str, Decimal]` — frozen dict
     semantics come from `frozen=True` on the model.
   - `FilingRecord.created_at`, `submitted_at`,
     `acknowledged_at` — `datetime`, UTC.
   - `compute_record_id(...)` — stable 16-char hash prefix
     mirroring `aeat.application.filing.compute_draft_id`, persisted to
     the fixture file so `record_id` is both human-readable
     and content-addressed.
   - Field order in JSON matches declaration order so diffs
     stay stable: `synthetic` first, `_comment` second.

4. **Loader details**
   - `SYNTHETIC_FIXTURES_ROOT` resolves by walking parents
     from `Path(__file__)` until a sibling
     `tests/fixtures/filing_history/` directory is found.
     Raises `FilingFixtureError` if not found.
   - `load_filing_history(modelo, period)` globs
     `SYNTHETIC_FIXTURES_ROOT / f"modelo_{modelo}"` (or every
     modelo dir) sorted by filename, opens each `.json`,
     parses it with `FilingRecord.model_validate_json`.
     Optional `period` filter matches exactly against
     `record.period`.
   - All parse/IO errors re-raised as `FilingFixtureError`
     carrying the offending path.

5. **Fixture corpus** — 17 files, see ADR for the exact list.
   Every file:
   - Starts with `"synthetic": true`.
   - Includes the `_comment` warning string.
   - Carries a plausible `record_id` computed at authoring time
     (the `_test_record_ids_are_unique` test verifies uniqueness;
     a separate optional script can recompute them on change).

6. **Unit tests** — one `test_testing.py` colocated next to
   the loader. Every test is marked `@pytest.mark.unit`. No
   mocks, no patches. Tests from the research doc:
   `test_load_all_records_parse_cleanly`,
   `test_expected_modelo_set`,
   `test_every_record_is_synthetic`,
   `test_every_file_has_comment_marker`,
   `test_filter_by_modelo_and_period`,
   `test_period_kind_matches_period_string`,
   `test_status_enum_is_filing_enum`,
   `test_refuses_non_synthetic_flag`,
   `test_refuses_missing_comment_marker`,
   `test_record_ids_are_unique`.

7. **Contributor doc** — inside `aeat.domain.testing.__init__`
   module-level docstring. Covers filename convention, the
   invariant, how to run the smoke tests.

8. **Dev loop** — `just lint && just typecheck && just test`
   plus `just hooks`. Fix root causes, no skips.

9. **Exec records + commits** — one exec step per logical
   commit. Vault artefacts committed alongside the code.

10. **Code review** — vaultspec-code-review skill covers
    every file, the invariant, pydantic strictness, public API
    discipline, lint/type/test/hooks green.

11. **PR** — opened after the code review phase, targeting
    `main`, title references `Closes #14`, body links the vault
    artefacts.

## Plan Review

**Reviewer**: self (vaultspec-code-reviewer persona in-head).
**Outcome**: APPROVED.

Checks performed:

- Scope matches issue #14 acceptance criteria.
- No overlap with sibling branches (see handover prompt).
- Synthetic-only invariant is enforced by pydantic, not
  convention — no code path can load a fixture missing either
  marker.
- Pydantic v2 mandate satisfied: every boundary-crossing type
  is strict + frozen + `extra="forbid"`.
- Loader under `src/aeat/domain/testing/` satisfies the src-layout
  mandate; fixtures under `tests/fixtures/…` satisfy the "only
  test helper code in the source tree" constraint.
- Errors inherit from `AeatError`. Logging via
  `get_logger(__name__)`.
- Tests marked `@pytest.mark.unit`, no mocks/patches/fakes.
- Contributor doc lives in the subpackage docstring, no new
  top-level README.

No blockers. Proceed to execution.
