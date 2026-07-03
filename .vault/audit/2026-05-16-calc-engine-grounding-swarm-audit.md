---
tags:
  - '#audit'
  - '#calc-engine-grounding-swarm'
date: '2026-05-16'
modified: '2026-06-29'
related: []
---

# `calc-engine-grounding-swarm` audit: `Calculation engine grounding`

## Scope

This audit traces legal grounding provenance (`legal_refs`, `source_refs`, `formula_id`, `operand_refs`, `operand_values`) across five domain boundaries in the calculation runtime chain:

1. **Engine internals** — `RegistryCalculationEntry` and `RegistryCalculationResult` in `_formula_runtime.py`
2. **Typed envelope** — `CasillaObservation` and `RegistryFilingObservation` in `_bindings.py`
3. **Domain model persistence** — `CalculationRevision.observations` in `_calculation_revision.py`
4. **Application action** — `calculate_modelo_revision` in `application/modelo/_actions.py`
5. **CLI output surfaces** — `work calculate`, `work revisions`, and the `formulas` introspection command in `entrypoints/cli/_modelo.py`

Reference patterns consulted: `test_cross_boundary_roundtrip.py`, `test_secure_storage_roundtrip.py`, `test_selector_shape.py`.

---

## Current State — 2026-06-29

The original 2026-05-16 gaps are closed on the current implementation path:

- `RegistryCalculationResult.observations` is now the canonical all-casilla observation surface. It covers manual, bound, and formula-computed casillas; `values` and `entries` are derived views with documented asymmetry.
- CLI JSON payloads for `modelo.work.calculate`, `modelo.work.revisions`, and `modelo.work.revision` carry the typed `observations` tuple with legal/source refs and operand traces.
- `aeat app modelo work observations` now provides the dedicated read-only operator surface for persisted revision observations.
- `modelo.calculation.created` bucket events carry `has_provenance`, allowing event readers to detect whether the stored revision has typed observations.

## Findings

### F1 — CLOSED: engine observations cover input and bound casillas

**Pathway**: engine → `CalculationRevision.observations`

**Original lossy site (2026-05-16)**: `src/aeat/application/modelo/_actions.py`, lines 846–857 and 845.

**Original gap (2026-05-16)**: `CalculationRevision.observations` was built exclusively from `engine_result.entries`, which the runtime only populated for formula-computed casillas. Input casillas (`input_kind == "manual"` or `"bound"`) were initialised into `engine_result.values` via `_initial_values` but never appended to `entries`.

**Current closure (2026-06-29)**: `src/aeat/domain/calculations/registry/_formula_runtime.py` materialises `RegistryCalculationResult.observations` as the all-casilla canonical observation surface. `src/aeat/application/modelo/_calculation_helpers.py` builds typed observations for non-formula values from registry casilla legal/source refs, so bound and manual casillas carry provenance with `formula_id=None`. Regression coverage lives in `src/aeat/application/modelo/tests/test_typed_observation_provenance.py` and `src/aeat/entrypoints/cli/tests/test_modelo_source_mesh_calculate.py`.

---

### F2 — CLOSED: revision JSON payloads include typed observations

**Pathway**: revision → CLI JSON (`work calculate`, `work revisions`, `work status`)

**Original lossy site (2026-05-16)**: `src/aeat/entrypoints/cli/_modelo.py`, lines 938–953 (`_calculation_revision_payload`).

**Original gap (2026-05-16)**: The CLI emitted `casilla_values` as a flat `{str: str}` mapping but did not include `observations`, making computed-casilla provenance invisible to JSON consumers of `work calculate` or `work revisions`.

**Current closure (2026-06-29)**: `src/aeat/entrypoints/cli/_modelo_rendering.py::calculation_revision_payload` serialises every `rev.observations` row into `ObservationPayload`. `WorkCalculateResult`, `WorkRevisionsResult`, and `WorkRevisionResult` all carry the same typed observation contract. Regression coverage lives in `src/aeat/entrypoints/cli/tests/test_modelo_payloads.py` and `src/aeat/entrypoints/cli/tests/test_modelo_source_mesh_calculate.py`.

---

### F3 — CLOSED: flat casilla values are paired with joinable observation rows

**Pathway**: revision → CLI JSON

**Original lossy site (2026-05-16)**: `src/aeat/entrypoints/cli/_modelo.py`, line 943.

```
"casilla_values": {k: str(v) for k, v in rev.casilla_values.items()},
```

**Original gap (2026-05-16)**: `rev.casilla_values` was emitted without a companion surface linking each casilla value to its `formula_id` or regulatory citations.

**Current closure (2026-06-29)**: `casilla_values` remains as the convenience flat map, and each revision payload now includes the joinable `observations` tuple keyed by `casilla_id`. The observation rows carry `value`, `formula_id`, `legal_refs`, `source_refs`, `operand_refs`, `operand_casilla_refs`, and `operand_values`.

---

### F4 — CLOSED: dedicated `work observations` read path exists

**Pathway**: persistence → CLI operator surface

**Original lossy site (2026-05-16)**: `src/aeat/entrypoints/cli/_modelo.py` had no `work_app.command("observations")`.

**Original gap (2026-05-16)**: `CalculationRevision.observations` was persisted end-to-end, but there was no CLI command that read a persisted revision and printed its typed observations. Operators had to inspect encrypted storage manually to audit the legal/source refs of a filed casilla.

**Current closure (2026-06-29)**: `src/aeat/entrypoints/cli/_modelo_work_revision_cli.py` registers `aeat app modelo work observations`. The command accepts a direct `calculation_revision_id` positional or resolves the target through `--modelo`, `--year`, `--period`, `--registry-revision`, `--work-unit-id`, `--select`, and `--bucket-id`, then emits `WorkObservationsResult` in JSON and a tab-separated text table from `calculation_observation_lines`. Generated CLI docs include `docs/cli/app.rst` and `docs/cli/schemas.rst`; regression coverage lives in `src/aeat/entrypoints/cli/tests/test_modelo_source_mesh_calculate.py`.

---

### F5 — CLOSED: bucket events carry a provenance availability signal

**Pathway**: engine→revision persistence → bucket event log

**Original lossy site (2026-05-16)**: `src/aeat/application/modelo/_actions.py`, lines 907–918 (`_emit_bucket_event` call inside `calculate_modelo_revision`).

**Original gap (2026-05-16)**: The `modelo.calculation.created` event carried metadata counts but no signal that full grounding was available on the joined calculation revision.

The `revision_id` is present as `object_id`, so grounding is recoverable by joining against the revision catalogue. The gap was that this join requirement was undocumented and the event carried no provenance-availability signal.

**Current closure (2026-06-29)**: `src/aeat/application/modelo/_revision_persistence.py` emits `has_provenance` as `"true"` when the persisted revision carries observations and `"false"` otherwise. The event remains lightweight while allowing audit tools to detect a calculation revision with missing typed observations before loading the full catalogue.

---

### F6 — CLOSED: `entries` vs. `values` asymmetry is documented

**Pathway**: engine internal contract → application action consumer

**Original lossy site (2026-05-16)**: `src/aeat/domain/calculations/registry/_formula_runtime.py`, lines 86–145, specifically the distinction between `values` (all casillas) and `entries` (formula-computed casillas only).

**Original gap (2026-05-16)**: `RegistryCalculationResult` declared both `values` and `entries`, but the docstrings did not state that `values` covers all casillas while `entries` covers formula targets only.

**Current closure (2026-06-29)**: `src/aeat/domain/calculations/registry/_formula_runtime.py` documents `RegistryCalculationResult.observations` as canonical, `values` as the full value view derived from observations, and `entries` as the formula-computed compatibility view. This prevents future consumers from treating `entries` as the all-casilla source of truth.

---

## Closure Record

- **P1 (F1)**: Closed. All-casilla `CasillaObservation` coverage is implemented and tested.

- **P2 (F2, F3)**: Closed. CLI JSON payloads include the typed `observations` tuple alongside `casilla_values`.

- **P3 (F4)**: Closed on 2026-06-29. `aeat app modelo work observations` reads persisted revision observations through the supported CLI surface.

- **P4 (F5)**: Closed. Bucket events carry `has_provenance`.

- **P5 (F6)**: Closed. Runtime result docs state the canonical observation surface and derived-view asymmetry.

Current verification on 2026-06-29: focused CLI/source-mesh tests and CLI-reference drift passed after adding the dedicated observations command.
