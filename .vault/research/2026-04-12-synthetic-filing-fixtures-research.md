---
name: Synthetic filing fixtures research
description: Research for issue #14 — synthetic past filing history backlog for offline tests
tags:
  - "#research"
  - "#synthetic-filing-fixtures"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-synthetic-filing-fixtures-adr]]"
  - "[[2026-04-12-synthetic-filing-fixtures-plan]]"
  - "[[2026-04-12-filing-draft-engine-adr]]"
  - "[[2026-04-12-base-module-structure-adr]]"
---

# research — synthetic-filing-fixtures

## problem

Upstream features (#9 schema extraction, #10 storage, #11 sync/self-
heal, #13 google fixtures) need *some* historical filing record to
test against. Real tax history is sensitive and live. We need a
hand-curated corpus of synthetic filing records that tests, dev
runs, and demos can work against with zero network and zero
secrets.

## goals

- A typed record describing one past filing.
- 3+ modelos (130, 303, 390), rolling 2–3 year window, spread of
  edge cases (clean / complementaria / errors / amended / cancelled
  / rounding).
- Version-controlled, diff-friendly, human-inspectable.
- Every file visibly synthetic — header comment *and* a top-level
  `synthetic: true` field the loader refuses to skip.
- A typed loader under `src/aeat/domain/testing/` that the rest of the
  source tree can import without reaching into `tests/`.

## non-goals

- Generation tooling (no Faker, no randomisers). Hand-curated only.
- Wiring into #11 sync or #10 storage pipelines.
- Any real client data, ever — synthetic-only invariant is non-
  negotiable.
- Modelos beyond 130/303/390 for this first cut.

## landscape — what already exists on main

- `aeat.application.filing` is merged. It ships:
  - `FilingDraftStatus` (`StrEnum`): `DRAFT`, `VALIDATED`,
    `READY_TO_SUBMIT`, `SUBMITTED`, `ACKNOWLEDGED`, `REJECTED`,
    `AMENDED`, `CANCELLED`.
  - `FilingDraft`, `FilingValue`, `FilingValueKind`,
    `FilingValidationFinding` — all frozen, strict pydantic v2.
  - `compute_draft_id` — content-addressed 16-char SHA-256 prefix.
- `aeat.core.errors.AeatError` is the project error base.
- `aeat.core.logging.get_logger(__name__)` is the logging entry point.
- #12 base module structure is merged — each subpackage exposes
  its API from `__init__.py`, with colocated `_test_*.py` or
  `test_*.py` files per the CLAUDE.md Rust-style convention.
- #6 modelo catalogue is **not** yet on main; modelo IDs are
  currently loose strings (`"130"`, `"303"`, etc.). We pin to
  strings for now and mark the ADR decision so the future enum
  can swap in.
- #23 casilla DB is not yet on main. Casilla IDs are loose
  strings — fixtures carry them as free-form two-digit IDs, which
  the real schema will tighten later.

## filing history record — what does one record need?

Reading issue #14 and the `FilingDraft` schema, a synthetic
*historical* record must carry:

| field | type | notes |
|---|---|---|
| `record_id` | `str` | stable, content-addressed hash prefix |
| `synthetic` | `Literal[True]` | the invariant — refuses `False` |
| `modelo` | `str` | loose string for now (`"130"`, `"303"`, `"390"`) |
| `period` | `str` | `"2024"`, `"2024Q1"`, `"2024-03"` forms |
| `period_kind` | `StrEnum` | `ANNUAL`, `QUARTERLY`, `MONTHLY` |
| `profile_tax_id` | `str` | synthetic tax ID |
| `status` | `FilingDraftStatus` | imported from `aeat.application.filing` |
| `casillas` | `tuple[FixtureCasilla, ...]` | typed casilla values |
| `totals` | `dict[str, Decimal]` | named computed totals |
| `created_at` | `datetime` | UTC |
| `submitted_at` | `datetime \| None` | UTC |
| `acknowledged_at` | `datetime \| None` | UTC |
| `source` | `Literal["synthetic"]` | literal constant |
| `scenario` | `StrEnum` | `CLEAN`, `COMPLEMENTARIA`, `WITH_ERRORS`, `AMENDED`, `CANCELLED`, `ROUNDING` |
| `complementaria_of` | `str \| None` | another record_id |
| `notes` | `str` | free-form comment for humans |

`FixtureCasilla` is its own strict pydantic v2 model with
`casilla_id: str`, `value: Decimal | int | str | bool | None`, and
a free-form `label: str`. It mirrors the shape of the production
`FilingValue` but without the `kind`/`source`/`formula_trace`
metadata that's irrelevant for historical snapshots.

## serialisation choice — JSON vs YAML vs TOML

| option | pros | cons |
|---|---|---|
| JSON | stdlib, diff-friendly line-per-field when indented, pydantic round-trips natively, no 3rd-party dep | no comments, so the `synthetic: true` header lives as a field, not a comment |
| YAML | comments allowed, richer literal form for Decimal/date | extra dependency, YAML pitfalls (bool/string coercion), messier diffs |
| TOML | stdlib 3.11+, human-friendly | poor for deeply nested data (`casillas` are lists of maps) |

**Decision**: JSON, indented 2 spaces, one record per file. To
preserve a human-readable "this is synthetic" marker without
relying on comments:

1. Every file's **first** JSON key is `"synthetic": true`. The
   loader asserts this as a strict pydantic field (`Literal[True]`).
2. Every file's **second** key is `"_comment"` carrying the exact
   string `"SYNTHETIC FIXTURE — do not confuse with real client
   data. See src/aeat/domain/testing/__init__.py."`. The loader validates
   the field exists and is non-empty.

Both checks fire at model-validation time, not at lint time, so
there is no path to load a fixture that drops either marker.

## loader shape

`src/aeat/domain/testing/` is a new subpackage. It exposes:

- `FilingRecord` — strict, frozen pydantic v2 `BaseModel`.
- `FilingRecordScenario` / `FilingRecordPeriodKind` — `StrEnum`.
- `FixtureCasilla` — strict, frozen pydantic v2 `BaseModel`.
- `SYNTHETIC_FIXTURES_ROOT: Path` — resolves relative to the
  worktree's repository root via `importlib.resources` traversal
  (the fixtures live in `tests/fixtures/filing_history/`, so we
  walk up from `__file__` to the repo root deterministically).
- `load_filing_history(modelo=None, period=None)` iterator.
- `FilingFixtureError(AeatError)` for every loader failure.

The iterator glob is deterministic (sorted) so test ordering is
stable.

## directory layout

```
tests/fixtures/filing_history/
├── modelo_130/
│   ├── 2024q1-clean.json
│   ├── 2024q1-complementaria.json
│   ├── 2024q2-with-errors.json
│   ├── 2024q3-amended.json
│   ├── 2024q4-cancelled.json
│   ├── 2025q1-clean.json
│   ├── 2025q2-clean.json
│   └── 2025q3-rounding.json
├── modelo_303/
│   ├── 2024q1-clean.json
│   ├── 2024q2-clean.json
│   ├── 2024q3-complementaria.json
│   ├── 2024q4-clean.json
│   ├── 2025q1-with-errors.json
│   └── 2025q2-amended.json
└── modelo_390/
    ├── 2023-clean.json
    ├── 2024-clean.json
    └── 2024-complementaria.json
```

That's 17 records covering all required modelos, a 2–3 year
window, and every required edge case.

## testing strategy

Unit tests only (`@pytest.mark.unit`), colocated at
`src/aeat/domain/testing/test_testing.py` (Rust-style). No mocks, no
patches — the fixtures *are* the test inputs.

- `test_load_all_records_parse_cleanly` — iterator returns every
  file parsed through `FilingRecord`.
- `test_expected_modelo_set` — the set of modelos loaded matches
  `{"130", "303", "390"}`.
- `test_every_record_is_synthetic` — `record.synthetic is True`
  and `record.source == "synthetic"` for every record.
- `test_every_file_has_comment_marker` — header comment field
  non-empty.
- `test_filter_by_modelo_and_period` — iterator respects both
  filters.
- `test_period_kind_matches_period_string` — ensures parser
  agreement (annual → `"YYYY"`, quarterly → `"YYYYQn"`, monthly →
  `"YYYY-MM"`).
- `test_status_enum_is_aeat_filing_enum` — asserts the `status`
  field is a `FilingDraftStatus` instance, guarding the import
  contract.
- `test_refuses_non_synthetic_flag` — constructs a dict with
  `synthetic: false`, expects pydantic validation to raise.
- `test_refuses_missing_comment_marker` — same pattern.
- `test_record_ids_are_unique` — across the whole corpus.

## contributor doc

Goes in the subpackage `__init__.py` docstring — "how to add a
new synthetic record". Covers:

1. Pick the correct modelo folder.
2. Filename convention: `<period>-<scenario>.json`.
3. Mandatory fields, in order: `synthetic` first, `_comment`
   second.
4. Status must be a valid `FilingDraftStatus` name.
5. Run `just test -k test_load_all_records_parse_cleanly` to
   verify.

## open questions / followups

- When #6 ships the modelo enum and #23 ships the casilla DB,
  the loader will grow a strict-mode that cross-checks every
  casilla ID against the DB. That is explicitly out of scope
  here; the fixture format is designed so a strict-mode upgrade
  is additive.
- When #11 sync / self-heal lands, it will consume
  `load_filing_history()` directly; no fixture format churn
  expected.
