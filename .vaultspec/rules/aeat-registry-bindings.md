# AEAT registry binding contract

## One validator, run at registry build

Every binding `source` family MUST expose a single
`validate(binding) -> list[str]` validator — accumulating, never raising —
registered in the one dispatch table keyed by `BindingSourceKind`, and run by the
registry-build section validator for ALL families. Op and fact invariants MUST be
enforced at **build** time, never resolve-time-only; resolve-time helpers may
remain as backstops. Preserve the underlying pydantic field error in the
diagnostic — never flatten it to a generic "malformed selector".

Validation was once scattered across three incompatible conventions, with
invariants run at build for some sources and only at resolve time for others, so
a malformed binding shipped clean through snapshot build and failed only when a
taxpayer's calculation ran.

## Aggregation is a typed model with a closed op enum

A binding's aggregation MUST be the typed `BindingAggregation` model carrying a
closed `BindingAggregationOp` enum declared in `core`, never a free-form
`Mapping`. No call site may re-parse `aggregation.get("op")` or pick its own
default: `binding_aggregation_op(binding)` returns the typed op and applies the
one declared per-family default in one place. A new op is added to the enum, so
the typed field validates it at build.

The op was once re-derived at roughly ten sites with divergent silent defaults,
so the effective default was source-dependent and unauditable. The relation and
formula-expression `op` axes are separate concepts, out of scope.

## Source kinds are one canonical core taxonomy

The `source` closed set MUST be the single canonical `BindingSourceKind` StrEnum
in `core`; `DataBindingDefinition.source` is typed as it, and every per-family
collection MUST be **derived** from it, never hand-listed. A new kind is added
with its value byte-identical to its stored token, and a registry-versus-enum
parity gate keeps them in lock-step. A hand-listed ledger collection once carried
only half the ledger kinds, so the ledger preflight misclassified the rest.

**Before deleting a retired member**, reconcile every validation, schema, fixture
and test consumer into one coherent accept-or-reject state and prove the owning
collection gate is green — a member can look retired at the CLI layer while still
powering a contradictory registry-validation surface.

## Values carry provenance at casilla parity

Every persisted and operator-facing binding value MUST carry its `legal_refs`,
`source_refs` and a typed `BindingSourceKind` source, at parity with casilla
provenance. The filing builder populates them from the binding definition it
already holds; a hardcoded free-text source string is forbidden. The CLI bindings
list and preview payloads MUST expose the same grounding as typed models, never
an untyped dict bag.

There was a provenance asymmetry at exactly the operator boundary: casilla values
carried full grounding to draft and export while binding values were flattened to
a hardcoded source string, so an operator inspecting a bound value could not see
its legal basis.

## Relation-targeted slots declare relation_prefill

A binding that exists only as a relation's `target_binding` materialisation slot
MUST declare `source = "relation_prefill"`, never `source = "previous_filing"`. A
`previous_filing` binding MUST satisfy the direct-selector predicate, and registry
validation refuses a binding that is both relation-targeted AND
previous-filing-resolvable — the M303 IVA-wallet compensación slot being the sole
documented carve-out.

Slots were once mislabelled `previous_filing` for a value only relation
resolution could produce, so one fold-in looked like two mechanisms and the
enrolled resolver skipped the non-direct slot by design, leaving it dormant.

## How

- **Good:** a new family is added to the dispatch table with a
  `validate(binding) -> list[str]` entry, routing the selector through
  `selector_as_dict` and surfacing the field message verbatim.
- **Good:** `frozenset(k for k in BindingSourceKind if ...)` — complete by
  construction.
- **Good:** `ModeloBindingValue` carries `legal_refs`, `source_refs` and
  `source: BindingSourceKind`, read from the binding definition.
- **Good:** a same-modelo direct carry keeps `source = "previous_filing"` and
  passes the direct-selector predicate.
- **Bad:** a per-family validator that raises, or a private validated selector
  invoked only inside the resolver.
- **Bad:** `str((binding.aggregation or {}).get("op", "sum"))` inline, or
  widening `aggregation` back to a bare mapping.
- **Bad:** a hand-listed string set for a family, a mixed enum/string Literal on
  `source`, or renaming a stored token to "align" it.
- **Bad:** constructing a `ModeloBindingValue` with a literal free-text source,
  or a bindings payload that omits grounding while the casilla payload carries it.
- **Bad:** a relation `target_binding` slot declaring `previous_filing` with a
  non-direct selector.

Gates: `test_binding_build_validation.py`, `test_binding_aggregation.py`,
`test_binding_source_kind_taxonomy.py`,
`test_binding_value_provenance_roundtrip.py`,
`domain/calculations/registry/_validate_relation_sources.py`. Source: ADRs
`2026-06-14-bindings-interface-hardening-adr` (A, B, D),
`2026-06-10-calculation-aggregation-taxonomy-adr`.
