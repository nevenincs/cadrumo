---
name: Synthetic filing fixtures ADR
description: Architecture decision for issue #14 — synthetic filing history corpus + loader
tags:
  - "#adr"
  - "#synthetic-filing-fixtures"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-synthetic-filing-fixtures-research]]"
  - "[[2026-04-12-synthetic-filing-fixtures-plan]]"
  - "[[2026-04-12-filing-draft-engine-adr]]"
---

# adr — synthetic-filing-fixtures

Status: **Accepted**
Branch: `feature/14-synthetic-filing-fixtures`

## Context

See `[[2026-04-12-synthetic-filing-fixtures-research]]` for the full
landscape. Summary: upstream features need a hand-curated,
synthetic, version-controlled corpus of past filings so tests
and demos run offline. Real filing history is sensitive and live.

## Decision

Introduce a new `aeat.domain.testing` subpackage under `src/aeat/` that
owns the typed public API for loading synthetic filing fixtures.
Persist the fixtures as JSON files under
`tests/fixtures/filing_history/<modelo>/<period>-<scenario>.json`.

### Pydantic v2 schema

Every boundary-crossing record is a strict, frozen pydantic v2
`BaseModel` with
`ConfigDict(strict=True, frozen=True, extra="forbid")`:

- `FilingRecord` — one past filing. Carries `record_id`,
  `synthetic: Literal[True]`, `_comment: str` (non-empty),
  `modelo`, `period`, `period_kind`, `profile_tax_id`, `status`
  (reusing `aeat.application.filing.FilingDraftStatus`), `casillas`,
  `totals: dict[str, Decimal]`, `created_at`, `submitted_at`,
  `acknowledged_at`, `source: Literal["synthetic"]`, `scenario`,
  `complementaria_of`, `notes`.
- `FixtureCasilla` — one casilla on a record. Carries
  `casilla_id: str`, `label: str`, `value` (Decimal | int | str
  | bool | None).
- `FilingRecordPeriodKind` — `StrEnum` with `ANNUAL`,
  `QUARTERLY`, `MONTHLY`.
- `FilingRecordScenario` — `StrEnum` with `CLEAN`,
  `COMPLEMENTARIA`, `WITH_ERRORS`, `AMENDED`, `CANCELLED`,
  `ROUNDING`.

`FilingDraftStatus` is reused from `aeat.application.filing` (merged on main
via #39) — no new status enum.

### Serialisation format — JSON

Rejected YAML (comments but extra dep and coercion foot-guns),
rejected TOML (awful for nested lists of maps). JSON is stdlib,
diff-friendly, pydantic round-trips natively.

The synthetic-only invariant does **not** rely on comments:
every file's first key is `synthetic: true` and the second key
is `_comment` carrying a fixed warning string. Both are
validated as model fields — `synthetic` as `Literal[True]` and
`_comment` as a non-empty `str`. There is no code path that
parses a fixture without both fields present.

### Loader shape

`src/aeat/domain/testing/__init__.py` exposes the public API:

- `FilingRecord`, `FixtureCasilla`, `FilingRecordPeriodKind`,
  `FilingRecordScenario` — re-exported.
- `SYNTHETIC_FIXTURES_ROOT: Path` — resolved once at import time
  by walking parents from `__file__` until the sibling
  `tests/fixtures/filing_history/` directory is found.
- `load_filing_history(modelo: str | None = None,
  period: str | None = None) -> Iterator[FilingRecord]` — yields
  records in deterministic sorted order. Raises
  `FilingFixtureError` (a new `AeatError` subclass) on any I/O,
  JSON, or validation failure, wrapping the underlying cause.
- `FilingFixtureError(AeatError)` — the subpackage's only error
  type.

Callers outside the subpackage import only from `aeat.domain.testing`.
Private helpers live in `_loader.py`.

### Location of the fixtures — `tests/` not `src/`

The fixture files are *test data*, not shipped code. They live
under `tests/fixtures/filing_history/` so they are excluded from
the wheel while still being version-controlled next to the code
that consumes them. The loader itself lives under `src/aeat/`
because the CLAUDE.md hard rule mandates that all Python modules
live under `src/aeat/`, and the loader is importable by any
code in the project — including the future #11 sync pipeline.

### Scope — modelos and edge cases

17 hand-curated records across three modelos:

- **Modelo 130** (quarterly IRPF): 8 records covering 2024Q1…
  2025Q3, every required edge case.
- **Modelo 303** (quarterly IVA): 6 records covering 2024Q1…
  2025Q2, with clean / complementaria / with-errors / amended.
- **Modelo 390** (annual IVA summary): 3 records for 2023 and
  2024 plus a complementaria.

All values are invented (not anonymised real data). Tax IDs are
synthetic (`"00000000T"` and variants). Amounts are chosen to
exercise rounding and the complementaria scenario.

## Consequences

### Positive

- Tests for #9/#10/#11 can load realistic-shaped historical
  records without network, secrets, or live systems.
- The synthetic-only invariant is enforced by pydantic
  validation, not by convention — no code path can bypass it.
- The loader is the *only* "test helper" code in `src/aeat/`,
  satisfying both the src-layout rule and the issue's explicit
  "everything else stays under `tests/`" constraint.
- Additive upgrade path: when #6 and #23 land, the loader can
  grow a strict mode without touching fixture files.

### Negative

- 17 files is enough for the first cut but will grow as
  downstream issues demand more scenarios — the hand-curated
  corpus is not a generation pipeline.
- `FilingRecord` is *not* a `FilingDraft`. The two schemas
  diverge deliberately: drafts carry kind/provenance/findings
  that historical records don't. Callers must not conflate
  them. The ADR flags this so future refactors don't
  accidentally unify the types prematurely.

### Neutral

- JSON loses comments; the `_comment` field compensates.
- Rounding-case amounts are chosen, not derived — a human
  reading the file sees a "this was chosen to exercise rounding
  at casilla 03" note in the `notes` field.
