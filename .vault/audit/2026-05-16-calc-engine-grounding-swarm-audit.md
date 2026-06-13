---
tags:
  - '#audit'
  - '#calc-engine-grounding-swarm'
date: '2026-05-16'
modified: '2026-05-16'
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

## Findings

### F1 — engine→observations: input and bound casillas receive no `CasillaObservation` entry

**Pathway**: engine → `CalculationRevision.observations`

**Lossy site**: `src/aeat/application/modelo/_actions.py`, lines 846–857 and 845.

**Data lost**: `CalculationRevision.observations` is built exclusively from `engine_result.entries`, which the runtime only populates for formula-computed casillas (the loop at `_formula_runtime.py:94` iterates `formula_evaluation_order`). Input casillas (`input_kind == "manual"` or `"bound"`) are initialised into `engine_result.values` via `_initial_values` but never appended to `entries`. Consequently, every manual and bound casilla present in `casilla_values` has no corresponding `CasillaObservation`. For those casillas, `legal_refs`, `source_refs`, `formula_id`, `operand_refs`, and `operand_values` are entirely absent from the typed envelope — even though the registry schema carries `legal_refs` and `source_refs` on the `CasillaDefinition` itself.

**Remediation**: After building `typed_observations` from `engine_result.entries`, iterate over `resolved_inputs` and emit a `CasillaObservation` for each input casilla with `formula_id=None`, empty operand fields, and — by loading the casilla's `legal_refs`/`source_refs` from `snapshot.revision.casillas` — the regulatory citations the registry declares for that casilla. The runtime already has `casillas_by_id` built; the application action should build the same lookup from `snapshot.revision.casillas` and use it to populate input observations.

---

### F2 — revision→CLI JSON: `observations` tuple silently absent from `_calculation_revision_payload`

**Pathway**: revision → CLI JSON (`work calculate`, `work revisions`, `work status`)

**Lossy site**: `src/aeat/entrypoints/cli/_modelo.py`, lines 938–953 (`_calculation_revision_payload`).

**Data lost**: The function emits `casilla_values` as a flat `{str: str}` mapping (line 943) but does not include the `observations` tuple. All computed-casilla provenance that survived the domain boundary (`formula_id`, `legal_refs`, `source_refs`, `operand_refs`, `operand_values`) is therefore invisible to any JSON consumer of `work calculate` or `work revisions`. Because the CLI is the primary operator-facing surface, operators and downstream integrators have no programmatic access to the regulatory grounding carried in the typed envelope.

**Remediation**: Extend `_calculation_revision_payload` to include an `"observations"` list — one entry per `CasillaObservation` in `rev.observations`, serialised with all fields (`casilla_id`, `value`, `formula_id`, `legal_refs`, `source_refs`, `operand_refs`, `operand_values`). Add a matching `_calculation_revision_lines` row only when `--explain` is passed (mirroring the `formulas` command pattern at lines 580–590) to avoid flooding the default text output.

---

### F3 — revision→CLI JSON: `casilla_values` Decimals stringified without provenance key

**Pathway**: revision → CLI JSON

**Lossy site**: `src/aeat/entrypoints/cli/_modelo.py`, line 943.

```
"casilla_values": {k: str(v) for k, v in rev.casilla_values.items()},
```

**Data lost**: `rev.casilla_values` is a plain `Mapping[str, Decimal]`; the `str()` coercion discards the `Decimal` precision but, more critically, there is no key in the emitted object that links each casilla value to its `formula_id` or regulatory citations. A consumer reading only the JSON envelope cannot determine whether a casilla value was manually supplied or computed, nor which BOE article authorises the formula. The `observations` tuple that carries this linkage is present on the domain object but not projected into the JSON (see F2). The two gaps compound: the mapping is emitted without any cross-reference pointer, so even a consumer that knew observations exist has no join key in the flat `casilla_values` dict to recover them.

**Remediation**: Replace the flat `casilla_values` projection with the structured `observations` list proposed in F2. Retain `casilla_values` as a convenience alias pointing at the same data, but emit it alongside `observations` so existing consumers can continue reading the flat view while new consumers use the typed envelope.

---

### F4 — no `observations` CLI subcommand: typed envelope has no dedicated read path

**Pathway**: persistence → CLI operator surface

**Lossy site**: `src/aeat/entrypoints/cli/_modelo.py` — no `work_app.command("observations")` exists (confirmed by reviewing all `@work_app.command(...)` decorators).

**Data lost**: `CalculationRevision.observations` is persisted end-to-end (the model carries it, the repository serialises it via `model_dump_json()` through the encrypted envelope, the roundtrip test at `test_cross_boundary_roundtrip.py:446–488` confirms JSON fidelity). However, there is no CLI command that reads a persisted revision and prints its typed observations. An operator who wants to audit the `legal_refs` and `source_refs` of a filed casilla must deserialise the encrypted storage manually; the CLI provides no path. The `formulas` command surfaces static registry grounding (pre-calculation) but not the per-casilla runtime trace.

**Remediation**: Add `work observations <work_unit_id> [--revision <revision_id>]` as a new `work_app` command. It loads the specified (or `current`) revision, iterates `rev.observations`, and emits a JSON list plus a tab-separated text table of `casilla_id`, `formula_id`, `legal_refs`, `source_refs`, `operand_refs`, `value`. The `--explain` flag pattern from the `formulas` command (lines 566–599) is the natural template.

---

### F5 — bucket event payload: provenance counts only, no `formula_id` or `legal_refs` linkage

**Pathway**: engine→revision persistence → bucket event log

**Lossy site**: `src/aeat/application/modelo/_actions.py`, lines 907–918 (`_emit_bucket_event` call inside `calculate_modelo_revision`).

**Data lost**: The `payload` dict emitted in the `modelo.calculation.created` event carries metadata counts (`formula_count`, `casilla_count`, `input_casilla_count`) but no reference to any `formula_id`, `legal_refs`, or `source_refs`. The bucket event is the durable audit-trail record for the calculation. If the encrypted calculation-revision catalogue is ever rotated, migrated, or queried by an audit tool that only reads the event log, it cannot determine which regulatory articles authorised the calculation for that bucket event. This is a lightweight event by design, but the total absence of any grounding pointer (even a single canonical `revision_id` cross-reference from which grounding could be recovered) means the event log cannot stand alone as an audit trail.

The `revision_id` is present as `object_id` (line 906), so grounding is recoverable by joining against the revision catalogue. The gap is that this join requirement is undocumented and the event carries no `grounding_available: true` signal.

**Remediation**: Add a `"has_provenance"` boolean string field (`"true"` / `"false"`) to the bucket event payload indicating whether the persisted revision carries a non-empty `observations` tuple. This allows audit tools to detect regressions (a calculation with no typed observations) without loading the full catalogue. The `revision_id` already present as `object_id` serves as the join key for full provenance recovery.

---

### F6 — `RegistryCalculationResult.entries` vs. `values`: coverage asymmetry not documented

**Pathway**: engine internal contract → application action consumer

**Lossy site**: `src/aeat/domain/calculations/registry/_formula_runtime.py`, lines 86–145, specifically the distinction between `values` (all casillas) and `entries` (formula-computed casillas only).

**Data lost**: `RegistryCalculationResult` declares both `values: Mapping[str, Decimal]` (covers all casillas) and `entries: tuple[RegistryCalculationEntry, ...]` (covers formula targets only). The application action at `_actions.py:845–857` correctly reads from both: `casilla_values = dict(engine_result.values)` and `typed_observations` from `engine_result.entries`. However, the `RegistryCalculationResult` docstring and `RegistryCalculationEntry` docstring do not state this asymmetry. A future action author building on `RegistryCalculationResult` may assume `len(entries) == len(values)` and attempt to use `entries` as the sole source of truth for all casillas — reproducing the provenance gap described in F1. The contract is implicit, not enforced.

**Remediation**: Add a sentence to the `RegistryCalculationResult` docstring clarifying that `entries` covers only formula-computed casillas, while `values` covers all casillas (inputs + computed). Add a corresponding note to the `RegistryCalculationEntry` docstring. No code change is required, but the documentation gap leaves the boundary fragile for future implementors.

---

## Recommendations

In priority order:

- **P1 (F1)**: Populate `CasillaObservation` entries for input and bound casillas in `calculate_modelo_revision`. This is the highest-impact fix: without it, the typed envelope only covers part of the casilla space and the legal-grounding claim for manually-supplied casillas is unverifiable from the stored revision alone.

- **P2 (F2, F3)**: Extend `_calculation_revision_payload` to include the `observations` list in the CLI JSON output. The data already exists in the domain object; the serialisation gap is the only barrier to operator access.

- **P3 (F4)**: Add `work observations` as a dedicated CLI subcommand so operators can inspect typed formula provenance without deserialising encrypted storage directly.

- **P4 (F5)**: Add a `"has_provenance"` signal to the `modelo.calculation.created` bucket event payload to make the audit log self-describing.

- **P5 (F6)**: Document the `entries` vs. `values` asymmetry in `RegistryCalculationResult` to prevent future implementors from reproducing the F1 gap.

No production code was modified during this audit. No new tests were added. All boundary checks were performed by static code inspection against the five source files listed in Scope and the three reference test files.
