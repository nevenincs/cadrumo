---
tags:
  - '#research'
  - '#schema-hardening'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-schema-hardening-continuity-conformance-plan]]'
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]'
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-research]]'
  - '[[2026-05-28-schema-hardening-m100-continuity-inventory-research]]'
---



# `schema-hardening` research: `continuity-conformance`

Audited the landed continuity implementation against the accepted generic
casilla continuity ADR before any further corpus data rollout.

## Method

Read the schema, loader, registry-scope validator, cross-revision validator,
directory-loader tests, cross-revision tests, and the committed M100 continuity
slice. The audit focused on whether the implementation is generic and whether
it satisfies ADR decisions D1 through D5.

Commands run:

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_validate_cross_revision.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`

The pytest run passed with existing M347 singleton semantic-role warnings.

## Findings

### D1 generic continuity identity surface

Status: implemented.

`src/aeat/domain/calculations/registry/_schema.py` defines
`ContinuidadId`, and `CasillaDefinition` carries optional `continuidad_id`.
The field is Spanish-stem, generic, and not keyed to a modelo id.

No generic validator currently enforces continuity-id uniqueness or existence
against evolution declarations. This is not required by D1 alone, but it
becomes relevant under D2 and D3.

### D2 explicit evolution records

Status: partially implemented.

`CasillaContinuidadEvolutionDefinition` exists with the ADR evolution kinds:
`unchanged`, `label_evolved`, `legal_refs_evolved`,
`label_and_legal_refs_evolved`, `repurposed`, and `retired`. The record carries
`legal_refs` and `source_refs`, and validates that `from_revision` and
`to_revision` differ.

The loader includes `casilla_continuidad_evolutions` in generic revision append
arrays, and `test_loader_directory_mode.py` proves continuity fragments load
from directory-mode TOML without a modelo-specific branch.

Gap: there is no validator that an evolution references existing revisions or
an actually declared continuity surface. A misspelled `continuidad_id` in an
evolution can currently load if no drift path depends on it.

### D3 opt-in enforcement

Status: partially implemented with one material conformance conflict.

`ModeloRevision.continuidad_validation` implements the opt-in flag, and
`validate_registry_scope` calls `_validate_strict_cross_revision_casilla_continuity`.
The current strict validator is generic and does not branch on M100.

Implemented behavior:

- Non-overlapping drift remains advisory unless either side of the revision
  pair is strict.
- Strict validation rejects uncovered drift for declared continuity surfaces.
- `label_evolved`, `legal_refs_evolved`, and
  `label_and_legal_refs_evolved` cover only their matching fields.
- `repurposed` covers all drift fields for a matching continuity pair.
- `unchanged` covers no drift, so any changed field still fails.

Conformance conflict: the ADR says that after opt-in, repeated casilla-id drift
must either share a continuity id with an allowed evolution declaration or be
explicitly marked as repurposed. The current implementation explicitly skips
unannotated drift even when a revision is strict via
`_has_declared_continuity_surface`. That made scoped M100 rollout possible, but
it means `continuidad_validation = "strict"` currently means strict for
declared surfaces only, not strict for every repeated id in the opted-in
revision pair.

This is a real decision point. The next implementation step must either:

- change the validator to match ADR D3 and then adjust corpus opt-in so M100 is
  not globally strict until all repeated-id drift is declared; or
- write an ADR amendment that renames or narrows the current flag semantics to
  surface-scoped strictness.

Gap: `retired` is schema-only today. The validator iterates divergences between
repeated ids, so it never observes a missing later casilla and cannot enforce
retirement declarations or accidental omission checks.

### D4 template expansion downstream

Status: implemented by absence.

No template compiler or inheritance model was introduced in the continuity
implementation. Runtime consumers still receive complete `ModeloRevision`
objects from the loader.

### D5 overlap validation preserved

Status: implemented.

`_validate_cross_revision_casilla_consistency` still hard-fails drift for
overlapping revisions independently of continuity opt-in. Tests cover
overlapping selector drift and non-overlapping advisory inventory.

## Genericity Check

No continuity implementation path found in `src/aeat/domain/calculations/registry`
uses a modelo-id branch for M100 semantics. The only M100-specific continuity
state found is data under `src/aeat/_data/registry/aeat/modelos/100`.

The only M100 mention in the validator is explanatory prose noting that annual
non-overlapping forms can legally evolve.

## Current M100 Data Slice

M100 revisions `2022`, `2023`, `2024`, and `2025` carry
`continuidad_validation = "strict"`. Casilla `0582` in those revisions carries
`continuidad_id = "irpf.intereses-demora-regularizacion.estatal"`, and
revisions `2023`, `2024`, and `2025` declare `unchanged` evolution records for
adjacent revision pairs.

Committed tests prove this surface loads and that mutating the 2025 `0582`
label produces strict continuity failures against source revisions `2022`,
`2023`, and `2024`.

Because current strict mode is surface-scoped, large unannotated M100 drift
continues to load advisory-only. That is consistent with the current code, but
not fully consistent with the literal D3 wording.

## Required Next Step

Do not add more M100 continuity data before resolving the D3 semantics.

The next implementation step should be a generic validator conformance fix or
an ADR amendment. The safer code path is to make strict enforcement match D3
and replace M100 revision-level strictness with a more accurately named
surface-scoped flag only if the architecture owner explicitly approves that
semantic change.
