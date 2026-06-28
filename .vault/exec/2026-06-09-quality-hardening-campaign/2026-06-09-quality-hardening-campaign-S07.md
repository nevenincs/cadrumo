---
step_id: S07
tags:
  - '#exec'
  - '#quality-hardening-campaign'
date: '2026-06-10'
modified: '2026-06-10'
related:
  - '[[2026-06-09-quality-hardening-campaign-audit]]'
---

# `quality-hardening-campaign` S07: QHC-004 duplication consolidation, slice 3

## Outcome

Three clone families consolidated.  Live `just audit-duplication` run before and
after confirms the clone count dropped from **44 to 41** (0.41% → 0.38%).  One
additional clone in the same sede module cluster remains (a parametric operation
loop with differing string literals per driver — not a clean extract without
obscuring driver intent; recorded as constraint-shape mismatch below).

## Live inventory before slice

44 clones, 0.41% duplicated lines (down from 47 in slice 2).

Non-WIP, non-modelo-work families available for this slice:

- Sede `_LocateHelper` Protocol (both `_groi_check.py` and `_nif_iva_check.py`).
- `contribuyente/family.py` shared validators (`RentaDescendantProfile` /
  `RentaAscendantProfile`).
- Ledger `_models.py` `_validate_source_jurisdiction` (4 copies).

## Family A — Sede `_LocateHelper` Protocol (commit `276503703`)

`_LocateHelper` was defined identically in both `_groi_check.py` and
`_nif_iva_check.py`.  The canonical home is `_adapter_utils.py`, which already
hosts all other shared helpers for these two drivers.  Moved the Protocol there;
both drivers now import from `_adapter_utils`.  Unused `Protocol`, `Coroutine`,
`Any`, and `Locator` imports cleaned up by ruff.  228 sede tests pass.

**Files changed:** `_adapter_utils.py`, `_groi_check.py`, `_nif_iva_check.py`

## Family B — `contribuyente/family.py` shared validators (commit `ad655ecdc`)

`RentaDescendantProfile` and `RentaAscendantProfile` each declared identical
`_optional_text_not_blank` (`@field_validator("tax_id", "display_name",
"disability_grade")`) and `_parse_date` (`@field_validator("birth_date",
"death_date", mode="before")`) validators.  Extracted `_RentaPersonProfileBase`
(private Pydantic `BaseModel`) carrying the shared fields (`tax_id`,
`display_name`, `birth_date`, `disability_grade`, `death_date`) and both
validators.  `RentaDescendantProfile` inherits directly with no additional
fields; `RentaAscendantProfile` adds `cohabiting_descendant_count: int | None =
Field(default=None, ge=0, le=10)`.

Substitutability pre-filter passed: `_RentaPersonProfileBase`'s field
constraints are a strict subset of both subclasses; the `cohabiting_descendant_count`
field on `RentaAscendantProfile` is additive and not constrained by the base.

Note: the contribuyente test suite could not be collected due to a pre-existing
circular import in peer WIP (`src/aeat/core/resources/_repos/user_profile.py`
has an uncommitted direct runtime import of `ProfileSchemaDefinition` that
creates a circular import through the logging / config chain). The family module
change was verified via direct ruff pass and structural inspection; the broader
ledger/aggregation tests that exercise `source_jurisdiction` (which imports the
same chain) ran clean under Family C.

**Files changed:** `src/aeat/domain/contribuyente/family.py`

## Family C — Ledger `_validate_source_jurisdiction` (commit `17a4bed0a`)

`_validate_source_jurisdiction` was duplicated four times in
`src/aeat/application/ledger/_models.py`:

- `ManualLedgerTransactionCommand` — full 7-line body.
- `ManualLedgerTransactionPatch` — delegated to `ManualLedgerTransactionCommand`
  with a redundant `if value is None: return None` guard above the delegation.
- `LedgerTransactionPayload` — full 7-line body.
- `LedgerTransactionReviewPayload` — full 7-line body.

Extracted `_validate_iso_3166_jurisdiction(value: str | None) -> str | None`
as a module-level function carrying the single canonical implementation.  All
four `@field_validator` methods now delegate to it.  The `ManualLedgerTransactionPatch`
delegation was simplified (the redundant `None` guard is already inside the
module-level function).  229 ledger tests pass; ruff clean.

**Files changed:** `src/aeat/application/ledger/_models.py`

## Constraint-shape mismatch — sede operation-loop pattern (NOT PROMOTED)

The second clone cluster involving `_groi_check.py[202:9-212:50]` and
`_nif_iva_check.py[231:9-241:53]` is the `for nif in sorted(...): operations.append(...)` +
`operations.append(RemoteOperation(kind="browser_action", action="discard-session"))`
loop.  The two copies differ in the string literals for the `action` prefix
(``"open-groi-form"`` vs ``"open-nif-iva-form"``; ``"check-nif-…"`` prefix is
identical but the surrounding `RemoteOperation` for the GET URL differs).
Extracting this into a shared helper would require a parameter for the
form-open action string and the URL; the current shape is readable in-context
and the parametric extract would obscure the per-driver semantics.
Recorded as constraint-shape mismatch; no merge.

## Verification gate

- Family A: `uv run --no-sync ruff check` clean; 228 sede tests passed.
- Family B: `uv run --no-sync ruff check` clean; structural inspection confirmed
  no constraint changes; contribuyente test collection blocked by unrelated peer WIP
  (circular import in `user_profile.py` working tree).
- Family C: `uv run --no-sync ruff check` clean; 229 ledger tests passed.
- Post-slice `just audit-duplication`: **41 clones, 0.38%** (was 44 / 0.41%).

## Commits

- `276503703` refactor(qhc-004): consolidate sede _LocateHelper Protocol clone family
- `ad655ecdc` refactor(qhc-004): consolidate contribuyente family profile validators clone family
- `17a4bed0a` refactor(qhc-004): consolidate ledger source_jurisdiction validator clone family
