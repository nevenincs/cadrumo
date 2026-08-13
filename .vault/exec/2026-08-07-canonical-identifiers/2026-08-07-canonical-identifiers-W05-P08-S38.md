---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:3c555429367c697f5a3d0ecd2bc054dadb640cab8ccc9f0907f01db51b7a603f'
step_id: 'S38'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# declare `RegistrySnapshotId` as a new `IdentifierNamespace.APP_REGISTRY_SNAPSHOT_ID` member and alias for the composite `modelo:revision_id:filing_year:period` string, explicitly distinct from `core.identity.SnapshotId`

## Scope

- `src/cadrumo/core/identity/_namespace.py`

## Description

- Semantic-searched and grepped for every `registry_snapshot_id` site before
  declaring anything, per the mandatory discovery sequence. Confirmed the
  composite exists and is genuinely untyped: `adapters.outbound.aeat.sede
  ._schema.FiledDeclaracionObservation.registry_snapshot_id` is a bare
  `str | None = Field(default=None, min_length=1, max_length=128)`, and
  `domain.calculations.registry._snapshot_coordinate.registry_snapshot_id` /
  `registry_snapshot_id_for` both return bare `str` — the three sites the
  row names. Confirmed the format from the function body and from real
  call-site literals in tests: `f"{modelo}:{revision_id}:{filing_year}:
  {period}"`, e.g. `"130:2019-y-siguientes:2025:1T"`.
- Confirmed the ADR's stated distinction from `core.identity.SnapshotId`
  holds: `SnapshotId` is a SHA-256 content-address (`_Hex64Str`), while this
  value is derived from four coordinates and carries no digest — the ADR's
  citation of `SnapshotId`'s own docstring disclaiming non-hex minters is
  accurate at HEAD.
- Declared `IdentifierNamespace.APP_REGISTRY_SNAPSHOT_ID` and the
  `RegistrySnapshotId` alias in `core/identity/_namespace.py`, alongside the
  other bespoke-shaped (non-hex-64) aliases in that module rather than in
  `core/identity/__init__.py`'s hex-64 block, since this concept is not
  hex-64-shaped (matching the ADR's own reasoning for why neither
  `Hex64Str` nor `Hex16Str` fits). Re-exported through
  `core/identity/__init__.py`'s import block and `__all__`, mirroring the
  existing `AeatCsv` / `AeatExpedienteId` pattern.
- Carried the bound (`min_length=1, max_length=128`) unchanged from the one
  production field this alias will eventually replace, and asserted no
  colon-structure pattern — the `revision_id` segment is a human-authored
  registry slug of variable shape (`RevisionId`, adjudicated in
  `W05.P07.S35`/`S36`), so inventing a regex from today's observed values
  would be invention rather than evidence, matching this module's own
  precedent for `AeatClaveLiquidacion`.
- Declaration only, per the row's own scope (`_namespace.py`); the three
  sites themselves are `W05.P08.S40`'s row, not this one's.

## Outcome

COMPLETE. `RegistrySnapshotId` is declared and exported, matching the ADR's
Wave `W05.P08` description exactly — the composite-string premise held up
under re-verification, unlike its sibling row `W05.P08.S39`/`S40`'s
`registry_revision_id` half (see that Step's record). `ruff check`, `ruff
format --check`, `basedpyright` all clean on both touched files.

## Notes

No incidents. Nothing consumes the new alias yet — that is `W05.P08.S40`'s
row.

**Resolved a discrepancy the team lead's independent re-derivation
flagged.** A separate, model-field-only census instrument reported
`registry_snapshot_id` at ONE site, already constrained, calling this
row's "3 sites" stale. Confirmed rather than assumed: the three sites
this row and `W05.P08.S40` actually worked are
`registry_snapshot_id()` and `registry_snapshot_id_for()` in
`_snapshot_coordinate.py` — plain function return-type annotations, never
pydantic model fields — plus ONE genuine model field,
`FiledDeclaracionObservation.registry_snapshot_id` in `_schema.py`. That
field already carried `Field(default=None, min_length=1, max_length=128)`
at HEAD before this row touched anything (confirmed by the file content
read before editing, earlier in this same record's own working session).
The re-derivation's narrower "model-field sites" definition never counted
the two function signatures at all — not because they were retyped away,
but because they were never in that instrument's population to begin
with. Both counts are correct under their own definitions; the ADR's
original "3 sites" mixed two different populations (function signatures
plus model fields) under one number, and the row's own retype covered
every one of the three regardless of which population it belongs to. No
correction needed to the work done; recorded here so a future reader does
not re-open this as a defect.
