---
tags:
  - '#research'
  - '#m200-internal-casilla-discipline'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-06-02-modelo-200-base-determination-adr]]"
---

# `m200-internal-casilla-discipline` research: `Modelo 200 internal-only casilla discipline: exempting app-internal ceilings from AEAT diseno-coverage gates`

This research grounds task #166: three Modelo 200 calculation-registry test
reds against the published AEAT Diseno de Registros after the M200
base-determination ADR introduced a synthetic, app-internal casilla
`DP200014:bin-aplicada-maxima` that represents the LIS art. 26.1 BIN
compensation ceiling. The casilla is intentionally NOT in the AEAT
published Diseno (it computes an internal LIS art. 26.1 limit that AEAT
publishes nowhere on the form), yet it must participate in the M200
calculation graph because a BLOCKING `cap_le_when_positive` predicate
consumes it to bound the operator-elective applied BIN amount
(`DP200014:00547`). The current registry gate
`derive_calculation_completeness_casillas` refuses any casilla carrying a
`segmento` whose `(segmento, number)` pair is absent from the published
Diseno. The synthetic ceiling therefore reds three gates while serving
correct regulatory authority.

This is the call-site of a small but durable discipline gap: the registry
schema lacks a way to declare that a casilla is intentionally
*app-internal* (no fichero export, no published five-digit Diseno tag,
formula-derived from real casillas, consumed only by verification
predicates or downstream computed casillas). Authoring such a casilla
correctly today silently breaks the diseno-coverage gates; the cheap
workaround (`segmento = None`) discards the multi-segment identity the
M200 calculation graph relies on. The right fix lands the
internal-only intent in the schema, where the gate can then route around
it without per-casilla allowlists.

The reds are the symptom; the discipline gap is the cause. This
research enumerates (1) every M200 casilla that today is structurally
internal-only or is a candidate for becoming one, (2) the existing
schema and gate surfaces that an exemption could ride on, (3) the AEAT
authority for treating diseno-presence as the exhaustive form-export
contract, and (4) the legal grounding of `bin-aplicada-maxima` so the
ADR can decide between schema field, empty-export proxy, and allowlist
without losing the substantive regulatory anchor that motivates the
casilla in the first place.

## Findings

### Inventory: internal-only or candidate-internal casillas in the M200 2024 registry

The only M200 casilla today declared with a registry-internal identity
that is intentionally absent from the AEAT Diseno is
`DP200014:bin-aplicada-maxima`, authored under
`src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-bin-aplicada-maxima.toml`.
Its declared shape is the canonical archetype for the discipline this
research grounds:

- `segmento = "DP200014"` (so its identity pins to the Liquidacion III
  segment the BIN compensation lives in).
- `number = "DP200014:bin-aplicada-maxima"` (a non-five-digit,
  non-AEAT-tag composite that names the concept rather than the form
  cell).
- `input_kind = "computed"`, with `formula = "modelo-200-2024-bin-aplicada-maxima"`
  defined in
  `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records/formulas.toml`
  as `min(casilla(00670), max(1_000_000, 0.7 * base_imponible_previa))`.
- `export_refs = ()` (the casilla never feeds a fichero / BOE record).
- `legal_refs = ["ley-27-2014:art-26", "ley-27-2014:art-25"]` and
  `source_refs = ["aeat-dr-200-2025", "aeat-modelo-200-manual-2024"]`,
  both grounded in the reviewed corpus.

No other M200 casilla in the 2024-y-siguientes revision is currently
authored as internal-only. A targeted RAG sweep against the modelo-200
calculation surface (concept query "internal computation ceiling, not on
the published form", port 8766, top-20) returns one cluster: the
bin-aplicada-maxima file plus the verification predicate that consumes
it. A second candidate surface looms: any future intermediate the M200
base-determination Phase 2 derivation needs to expose (a `base imponible
previa` subtotal computed off the form, or an aggregate of correcciones)
will repeat the same shape if it is not also published in the Diseno.
The art. 26.1 ceiling is the first instance, not the last.

### Existing gate and schema surfaces that an exemption can ride on

`CasillaDefinition` (in
`src/aeat/domain/calculations/registry/_schema.py:1900-1995`) carries a
narrow set of declared fields relevant to this question:

- `segmento: str | None` (used to disambiguate the same `number` across
  M200 record segments; required for multi-segment modelos).
- `export_refs: tuple[ExportFieldId, ...] = ()` (empty by default).
- `input_kind: InputKindValue` with `formula` required when computed.
- `legal_refs` and `source_refs` (both required).

`derive_calculation_completeness_casillas` in
`src/aeat/domain/calculations/registry/_record_design.py:1475-1572` is
the gate that surfaces the three reds. Its logic in the multi-segment
path is precisely:

```
if diseno_pairs is not None and segmento is not None
    and (segmento, number) not in diseno_pairs:
    raise RegistryValidationError(
        "calculation-completeness derivation: casilla {number!r} is "
        "declared under segmento {segmento!r} but the AEAT Diseno de "
        "Registros does not carry it under that segment"
    )
```

The check is unconditional on every closure casilla. It has no
per-casilla allowlist today and no schema-level escape hatch. Three
possible exemption surfaces emerge from this shape:

- **New schema field `internal_only: bool = False` on `CasillaDefinition`.**
  The gate then reads
  `if casilla.internal_only: continue` before consulting the Diseno set.
  Most explicit; declares intent at the casilla; gates against
  incoherence (a casilla flagged `internal_only=true` whose
  `export_refs` is non-empty is a contradiction the schema validator
  can refuse).
- **Existing-field proxy: `export_refs == ()`.** A computed casilla
  with empty `export_refs` is *structurally* internal-only — it
  feeds no fichero. The gate could skip Diseno presence whenever
  `casilla.export_refs == ()` and `casilla.input_kind == COMPUTED`.
  No schema widening; rides existing data. The hazard is that several
  legitimately-Diseno-published computed casillas may also have empty
  `export_refs` because their export wiring has not been authored yet
  — the proxy then silently exempts them from the diseno gate, which
  is precisely the discipline the gate exists to enforce.
- **Per-casilla allowlist in `_record_design.py`.** A module-level
  constant `_INTERNAL_ONLY_DISENO_EXEMPTIONS: frozenset[tuple[str, str]]`
  enumerating exempt `(segmento, number)` pairs. The gate consults it
  before raising. Pragmatic; ships in one file; no schema change. But
  it is the per-fixture allowlist shape the
  `fixture-provenance-declared-in-sidecar` rule explicitly forbids
  for a structurally analogous problem: an allowlist re-introduces
  the honor-system per-casilla list the gate exists to remove, and a
  new internal-only casilla added later silently reds the gate until
  someone notices and patches the allowlist. The rule's authority is
  directly transferable here: the casilla, not the gate's test source,
  must declare its intent.

### AEAT Diseno authority: exhaustive form-export contract, NOT the calc-graph
contract

The AEAT Diseno de Registros (extracted from
`07-200-ejercicios-2024-y-siguientes-...-xlsx.xlsx` and cousins under
`src/aeat/_data/registry/aeat/sources/`) is published as the
machine-readable fichero / BOE record format for each modelo. Every
five-digit casilla number AEAT enumerates appears on the published form
and is round-tripped through fichero export and parsing. The Diseno is
authoritative on (a) which numbers exist, (b) which segmento they live
in, and (c) what data type / width they carry. It is NOT, however, the
contract for the application's *internal* calculation graph. An app
that derives an intermediate value (a base imponible previa, a
compensation ceiling, an art. 13 deducibility check) needs that value
in the calc graph but does not file it to AEAT. The diseno
authoritativeness applies to what gets *exported*, not to what gets
*computed*.

This matches the existing two-tier gate split in
`derive_diseno_coverage_casillas` (which inventories the full Diseno
casilla set as an advisory off-load-path report) and the
calculation-completeness gate (which is load-blocking on a strict
subset). The bug today is that the load-blocking gate over-extends the
Diseno authority to internal computed casillas the app authors for its
own calculation closure, where AEAT has no jurisdiction.

The `aeat-calculation-grounding` rule (every casilla observation MUST
preserve `legal_refs` and `source_refs` from registry source to
operator-facing surface) is independent of the internal-only intent: an
internal-only casilla still carries `legal_refs` and `source_refs`
because it is grounded in real regulatory authority (art. 26.1 LIS for
bin-aplicada-maxima). The grounding rule defends what the casilla
exposes; the internal-only intent defends only the Diseno-presence
contract. No conflict between the two.

### Legal grounding of bin-aplicada-maxima: the ceiling is real authority,
not a stub

LIS art. 26.1 (Ley 27/2014, BOE-A-2014-12328): "Las bases imponibles
negativas que hayan sido objeto de liquidacion o autoliquidacion podran
ser compensadas con las rentas positivas de los periodos impositivos
siguientes con el limite del 70 por ciento de la base imponible previa
a la aplicacion de la reserva de capitalizacion ... y a su compensacion.
En todo caso, se podran compensar en el periodo impositivo bases
imponibles negativas hasta el importe de 1 millon de euros."

The ceiling is `min(BIN_stock, max(1_000_000, 0.7 * base_imponible_previa))`.
This is the value the verification predicate
`modelo-200-compensacion-bin-no-excede-limite-art-26` consumes:

```
expression = 'cap_le_when_positive(["DP200014:00547", "DP200014:bin-aplicada-maxima"])'
finding_kind = "BLOCKING_RULE"
legal_refs = ["ley-27-2014:art-26"]
```

The reason AEAT does not publish a five-digit casilla for the ceiling is
that it is the *limit* a self-assessing taxpayer applies, not a value
they declare. The taxpayer declares the elected compensation amount
(casilla 00547); the limit is the mathematical bound the calculation
engine enforces. The application materialises the limit as a casilla
because the predicate evaluator operates on casilla references; without
the casilla, the predicate would have to inline the formula, which
breaks the registry-authority discipline (`aeat-registry-authority-flow`:
"validated authority -> immutable snapshots -> runtime projections"). The
casilla is the engine's representation of the limit, grounded in art.
26.1 and routed through the calc graph as a first-class derived value.

The casilla therefore is NOT a stub, NOT a placeholder, and NOT a
process-state label. It is a real computed value, with real legal
grounding, that happens to be invisible on the AEAT-published form
because AEAT publishes the limit's *formula* in the LIS rather than as
a form box. The `aeat-source-hygiene` rule (no project-management
metadata in production identifiers) is satisfied: the casilla's
identifier names the regulatory concept ("bin-aplicada-maxima"), not a
process state.

### The constraint the gate enforces, restated

The calculation-completeness manifest test
(`test_calculation_completeness_manifests_match_their_calculation_surface`)
asserts that every closure casilla pinned to a `(segmento, number)`
identity is present in the AEAT-published Diseno for that segment. Its
purpose is to catch a registry author who mis-tagged a closure casilla
with a wrong segment — they typed `DP200013` when the AEAT Diseno
carries the number under `DP200014`, and the calc would silently
read/write the wrong record on export. The gate is right to refuse
that mistake.

The gate is wrong only when the closure casilla is intentionally absent
from the Diseno because it represents an internal calculation
intermediate the form does not export. That intent has no schema home
today, so the gate cannot distinguish "wrong segment" from "internal
intermediate" and refuses both. A schema-level intent declaration would
let the gate keep its discipline against the mis-tag case while
exempting the internal case.

### Cross-cluster context

The semantic-cluster hardening campaign produced the
`fixture-provenance-declared-in-sidecar` discipline (2026-06-01): a
fixture's provenance is declared in its sidecar, not in a hardcoded
allowlist in test source. That rule's reasoning translates directly:
"a mis-stamped sidecar still reds the gate via the cross-check, so
honesty is preserved without an allowlist". An `internal_only: bool`
flag on `CasillaDefinition` is the casilla analogue: a casilla that
declares `internal_only=true` but actually carries non-empty
`export_refs` is incoherent and the schema validator refuses it. The
gate then trusts the flag because the schema has already verified the
flag's coherence with the rest of the casilla declaration. This is
the audit precedent the ADR should explicitly cite.

The `no-silent-under-declaration` rule that motivates the parent ADR
(`2026-06-02-modelo-200-base-determination-adr`) is also adjacent: the
ceiling exists because LIS art. 26.1 caps the operator's BIN
compensation, and a silent BIN over-compensation is precisely the
silent under-declaration shape the rule defends against. Removing the
ceiling to clear the gate reds (the speculative shortcut) would also
silently weaken the BIN-overcompensation defence. The
internal-only exemption must therefore preserve the casilla's role in
the calc graph, not erase it.
