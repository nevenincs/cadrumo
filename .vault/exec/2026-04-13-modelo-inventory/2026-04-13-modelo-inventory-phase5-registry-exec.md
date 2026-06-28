---
name: 2026-04-13-modelo-inventory-phase5-registry
description: Phase 5 execution record — registry assembly, invariants, and year_plan (#108)
type: exec
tags:
  - "#exec"
  - "#modelo-inventory"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-modelo-inventory-plan]]"
---

# phase 5 — registry assembly + year_plan

## delivered

- `_registry.py` imports every `_entries/modelo_*` module, collects
  their `ENTRY` objects, and assembles `MODELO_REGISTRY` via a
  `MappingProxyType` with import-time `_finalise_registry` checks.
- Invariants enforced at import: uniqueness, completeness against
  `ModeloCode`, no extra keys, `metadata.code is key`, and
  `caps_into` resolves inside the registry.
- Public helpers:
  - `get_modelo(code: ModeloCode | str)` with
    :class:`UnknownModeloError` on garbage / unknown codes.
  - `modelos_for_profile(profile)` sorted by code.
  - `year_plan(year, profile)` thin wrapper over
    :class:`DeadlineEngine` built from an `_InProcessCatalogue` whose
    `known_modelos()` returns every `ModeloCode` value wrapped in
    :class:`aeat.domain.deadlines.ModeloIdentifier`.
- `test_registry.py` covers completeness, caps_into resolution, enum
  and string lookup, both error paths, profile filtering for
  `autonomo_ed_solo`, a `_check_caps_into` synthetic dangling
  reference, and a `year_plan` smoke against a GENERAL IVA profile.

## gate outcomes

- `just lint` — fixed (moved `Mapping` to `collections.abc`).
- `just typecheck` — fixed by importing `ModeloIdentifier` from
  `aeat.domain.deadlines` and constructing it from each `ModeloCode.value`;
  the private `_InProcessCatalogue` now matches the
  `ModeloCatalogueLoader` protocol shape declared on `aeat.domain.deadlines`.
- `just test` — 749 passed, 1 skipped, 23 deselected.
- `just hooks` — ruff-format flattened two long-string error
  messages; re-run green.

## deviations

None.

## commit

`74a6362 feat(models): assemble MODELO_REGISTRY with import-time integrity invariant (#108)`
