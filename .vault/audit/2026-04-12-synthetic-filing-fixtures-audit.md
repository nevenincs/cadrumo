---
name: Synthetic filing fixtures code review
description: Post-implementation code review for issue #14 (vaultspec-code-review)
tags:
  - "#audit"
  - "#synthetic-filing-fixtures"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-synthetic-filing-fixtures-plan]]"
  - "[[2026-04-12-synthetic-filing-fixtures-adr]]"
  - "[[2026-04-12-synthetic-filing-fixtures-phase1-summary-exec]]"
---

# audit — synthetic-filing-fixtures

Reviewer: vaultspec-code-reviewer (in-head)
Status: **APPROVED**

## Scope

- `src/aeat/errors.py` — added `FilingFixtureError`.
- `src/aeat/domain/testing/__init__.py` — public API + contributor doc.
- `src/aeat/domain/testing/_schema.py` — pydantic v2 schema.
- `src/aeat/domain/testing/_loader.py` — filesystem loader.
- `src/aeat/domain/testing/test_testing.py` — 21 colocated unit tests.
- `tests/fixtures/filing_history/modelo_130/*.json` — 8 files.
- `tests/fixtures/filing_history/modelo_303/*.json` — 6 files.
- `tests/fixtures/filing_history/modelo_390/*.json` — 3 files.

## Synthetic-only invariant

- Every fixture file opens with `"synthetic": true` and
  `"_comment"` carrying a warning string beginning with
  `SYNTHETIC FIXTURE`. Verified manually on a spot sample and
  automatically by `test_every_file_has_comment_marker`.
- `FilingRecord.synthetic` is typed as `Literal[True]`;
  `test_refuses_non_synthetic_flag` proves `false` raises.
- `FilingRecord.comment` is typed as `str` with `min_length=1`
  and aliased to `_comment`; `test_refuses_missing_comment_marker`
  and `test_refuses_empty_comment_marker` both raise
  `ValidationError`.
- `FilingRecord.source` is typed as `Literal["synthetic"]`;
  `test_refuses_non_synthetic_source` covers the negative path.
- `extra="forbid"` on every model; `test_extra_fields_forbidden`
  covers that an unknown top-level key is rejected.

## Pydantic v2 mandate

- `FilingRecord`, `FixtureCasilla` — `ConfigDict(strict=True,
  frozen=True, extra="forbid", populate_by_name=True)`.
- `FilingRecordPeriodKind`, `FilingRecordScenario` — closed
  `enum.StrEnum`.
- `FilingDraftStatus` is reused from `aeat.application.filing` (no parallel
  enum).
- `FilingRecord.totals` typed as `dict[str, Decimal]`; values
  round-trip through pydantic v2 JSON mode as Decimals.
  `test_totals_are_decimals` proves it on the whole corpus.
- No bare `dict[str, Any]` anywhere in public signatures.
- Loader parses via `model_validate_json` — JSON mode coerces
  Decimal/datetime from strings while keeping strict Python-mode
  invariants on non-string fields.

## Public API discipline

- Callers import only from `aeat.domain.testing`. `_loader.py` and
  `_schema.py` are underscored and private.
- `aeat.domain.testing.__init__` exports 9 symbols (schema types,
  loader, error, root constant, helper).
- `test_malformed_json_raises_filing_fixture_error` imports
  `_load_one` from `aeat.domain.testing._loader` solely to exercise a
  branch that cannot be reached through the public API with
  in-corpus files; this mirrors the private-helper test pattern
  used elsewhere in `aeat.application.filing`.

## Errors / logging

- `FilingFixtureError` inherits from `aeat.core.errors.AeatError`.
- Every loader failure (directory missing, I/O error, malformed
  JSON, validation error) is re-raised as `FilingFixtureError`
  with the offending path in the message and the original
  exception chained via `raise … from exc`.
- Loader uses `aeat.core.logging.get_logger(__name__)` for a DEBUG
  line per loaded record. No bare `print`, no bare `logging`.

## Src-layout + test colocation

- Loader lives at `src/aeat/domain/testing/`. This satisfies the
  CLAUDE.md hard rule that all Python modules live under
  `src/aeat/`.
- Fixture files live under `tests/fixtures/filing_history/`
  (not shipped in the wheel) — satisfies the "only test helper
  code in the source tree" constraint from issue #14.
- Unit tests are colocated at `src/aeat/domain/testing/test_testing.py`
  per the Rust-style convention.

## Testing discipline

- All 21 tests marked `@pytest.mark.unit`. No `@pytest.mark.live`
  usage (correct — this issue has no live surface).
- Zero mocks, patches, fakes, stubs, shadows. The fixtures are
  the test data.
- `just test` passes (403 passed, 1 skipped, 15 deselected).
- Every negative path asserted via `pytest.raises(ValidationError)`
  or `pytest.raises(FilingFixtureError)` — no silent skips.

## Lint / typecheck / hooks

- `just lint` — clean (ruff).
- `just typecheck` — clean (ty, not mypy).
- `just test` — clean.
- `just hooks` — clean (prek, not pre-commit).
- No `# type: ignore`, `# noqa`, or `--no-verify` anywhere in
  the diff.

## Findings

None.

## Decision

APPROVED for commit and PR.
