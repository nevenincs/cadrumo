"""Registry-build gate: an export exemption must carry a declared reason.

The pre-write fichero-BOE completeness gate demands a value on disk for every
completeness-manifest casilla that is a calculation RESULT (declares a formula)
or is schema-required, intersected with the casillas the official record design
addresses. A casilla outside that intersection is silently exempt.

That exemption was expressed by ABSENCE. Nothing verified that a casilla the
record does not address is genuinely unrepresentable rather than merely
*un-annotated*, so a casilla that SHOULD reach a box but was never given an
export field was exempt from the very gate that exists to catch it — and read
identically to one AEAT never prints. This module closes that: where the
exemption is load-bearing, the registry must say WHY, in the closed
:class:`~core.ExportExemptionReason` vocabulary, or the build refuses.

Scope: only where absence actually suppresses the gate
------------------------------------------------------

A reason is demanded from a casilla that is ALL of:

* listed in the revision's calculation-completeness manifest;
* formula-bearing or ``required`` — the two properties that put a casilla in the
  gate's required set in the first place;
* not addressed by any fixed-width export record, on any disposition; and
* not ``internal_only``, which already asserts its own exemption.

A manifest casilla that declares no formula and is not required is excluded from
the required set by a property it DOES declare, so its absence from the record
design suppresses nothing and needs no second declaration. Demanding a reason
there would be authoring noise over a set the gate never consults. The gate
tightens exactly where the stakes rise: mark such a casilla ``required`` and it
must justify its exemption from that moment.

The scan is casilla-keyed, and that is a blind spot in the instrument
-------------------------------------------------------------------

"No record addresses it" means no record addresses it BY CASILLA ID. A
``BINDING``-kind export field names the binding, not the casilla, so a value the
export genuinely writes at a declared offset is invisible to this scan and looks
exactly like one AEAT never prints. Modelo 720's ejercicio (design positions
5-8) and declaración complementaria/sustitutiva (121-122) are both written that
way, and reading their names alone suggests the opposite conclusion.

So a refusal from this gate is a question, not a verdict: it says the exemption
is undeclared, never that the casilla is unrepresentable. Answering it means
reading the record design AND the bindings —
:attr:`~core.ExportExemptionReason.FILED_VIA_BINDING_FIELD` exists precisely
because the honest answer is sometimes "it is filed, just not through a casilla
address". The refusal message repeats this warning, because that is where an
author actually lands.

This is deliberately NOT a cross-check of casilla numbers against the bundled
Diseño de Registros. That check is not yet viable — Modelo 390 alone would emit
hundreds of false positives against the current parser — and a gate keyed on a
declared reason is the honest thing this evidence supports. It gates the presence
of a reviewed judgement, not the correctness of one.

See Also:
    :class:`~core.ExportExemptionReason`
        The closed vocabulary, one member per adjudicated exemption shape.
    :func:`~domain.calculations.registry.fixed_width_record_casilla_ids`
        The shared derivation of which casillas a record set addresses.
    :func:`~application.filing.assert_export_mirrors_manifest`
        The pre-write gate whose required set this protects.
"""

from __future__ import annotations

from ....core import ExportExemptionReason, ExportLayoutFormat
from ....core.aggregation import BindingSourceKind
from ._bindings import binding_source_casilla_ids, binding_source_modelo
from ._export import derive_export_layouts_from_bindings, fixed_width_record_casilla_ids
from ._ids import CasillaId
from ._runtime_graph import expression_casilla_refs
from ._schema import ModeloRevision


def _reaches_addressed_casilla(
    casilla_id: CasillaId,
    *,
    consumers: dict[CasillaId, set[CasillaId]],
    addressed: set[CasillaId],
) -> bool:
    """Return whether ``casilla_id`` feeds, transitively, a casilla the record addresses.

    Walks forward along consumption edges: ``consumers[x]`` holds every casilla
    that reads ``x``, whether through a formula expression or through a binding
    selector. Cycles terminate through the visited set, so a malformed graph
    cannot hang the build.

    Binding edges are not optional here. Modelo 303's ``iva.prorrata-porcentaje``
    reaches official box ``44`` only through the ``prorrata_regularizacion``
    binding — box 44 declares no formula at all — so a formula-only walk would
    refuse a true claim and push the author toward a weaker, wrong reason.
    """
    pending = [casilla_id]
    seen: set[CasillaId] = set()
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        if current in addressed:
            return True
        pending.extend(consumers.get(current, ()))
    return False


def _consumption_edges(revision: ModeloRevision, modelo_id: str) -> dict[CasillaId, set[CasillaId]]:
    """Return, per casilla, the casillas that read it WITHIN this filing.

    Two edge kinds, because a casilla can be consumed either way: a formula
    expression reading it, and a binding selector naming it as a source.

    Two edge kinds are deliberately EXCLUDED, and the exclusions carry the
    correctness of the whole check:

    - a ``previous_filing`` binding reads a PRIOR period's value, so it proves
      the figure is consumed by the NEXT filing, never that this one files it.
      Counting it would let every cross-period carry seed — which is exactly the
      population needing the ``NOT_IN_RECORD_DESIGN`` reason — masquerade as
      reaching a box on the current return.
    - a cross-modelo binding names casillas on a FOREIGN modelo, so its ids do
      not denote casillas in this revision at all.
    """
    formula_by_id = {formula.id: formula for formula in revision.formulas}
    binding_by_id = {binding.id: binding for binding in revision.bindings}
    edges: dict[CasillaId, set[CasillaId]] = {}
    for casilla in revision.casillas:
        if casilla.formula is not None and (formula := formula_by_id.get(casilla.formula)) is not None:
            for ref in expression_casilla_refs(formula.expression):
                edges.setdefault(ref, set()).add(casilla.id)
        for binding_id in (casilla.binding, *casilla.alternate_bindings):
            binding = binding_by_id.get(binding_id) if binding_id is not None else None
            if binding is None or binding.source is BindingSourceKind.PREVIOUS_FILING:
                continue
            source_modelo = binding_source_modelo(binding)
            if source_modelo is not None and source_modelo != modelo_id:
                continue
            for ref in binding_source_casilla_ids(binding):
                edges.setdefault(ref, set()).add(casilla.id)
    return edges


def validate_export_exemption_declarations(
    failures: list[str],
    *,
    prefix: str,
    modelo_id: str,
    revision: ModeloRevision,
) -> None:
    """Append a failure for every load-bearing export exemption lacking a reason.

    Resolves the revision's export layouts the way snapshot build does — through
    :func:`derive_export_layouts_from_bindings`, so binding-derived record fields
    are present — and scans every fixed-width layout. A revision declaring no
    fixed-width layout, or no completeness manifest, is a no-op: neither has a
    completeness gate to be exempt from.

    Args:
        failures: Accumulator the registry validator drains; never raises.
        prefix: Caller-supplied ``modelo N revision R`` diagnostic prefix.
        modelo_id: Modelo identifier, used to scope out cross-modelo binding
            edges whose source casilla ids name a foreign modelo.
        revision: The :class:`ModeloRevision` under validation.
    """
    manifest = revision.completeness_manifest
    if manifest is None:
        return
    layouts = tuple(
        layout
        for layout in derive_export_layouts_from_bindings(revision)
        if layout.format is ExportLayoutFormat.FIXED_WIDTH
    )
    if not layouts:
        return
    addressed: set[CasillaId] = set()
    for layout in layouts:
        addressed |= fixed_width_record_casilla_ids(layout.records)

    consumers = _consumption_edges(revision, modelo_id)

    casilla_by_id = {casilla.id: casilla for casilla in revision.casillas}
    for manifest_casilla in manifest.casillas:
        casilla = casilla_by_id.get(manifest_casilla.casilla_id)
        if casilla is None:
            # A manifest casilla the revision does not declare is a different
            # defect, already enumerated by the completeness-manifest validator.
            continue
        if casilla.id in addressed or casilla.internal_only:
            continue
        if casilla.formula is None and not casilla.required:
            continue
        if casilla.export_exemption_reason is ExportExemptionReason.FEEDS_ADDRESSED_CASILLA:
            # The one reason that asserts the figure IS filed, so the claim is
            # checked rather than taken: a casilla reaching no addressed casilla
            # would be exempt on a false premise, which is the exact failure this
            # whole gate exists to stop.
            if not _reaches_addressed_casilla(casilla.id, consumers=consumers, addressed=addressed):
                failures.append(
                    f"{prefix}: casilla {casilla.id!r} declares export_exemption_reason "
                    f"{ExportExemptionReason.FEEDS_ADDRESSED_CASILLA.value!r}, which asserts its figure "
                    f"reaches the record through a downstream box, but no formula chain leads from it to "
                    f"any casilla a fixed-width export record addresses. Either wire the chain, or declare "
                    f"the reason this casilla genuinely files no slot",
                )
            continue
        if casilla.export_exemption_reason is not None:
            continue
        failures.append(
            f"{prefix}: casilla {casilla.id!r} is in the completeness manifest and would be "
            f"required by the fichero-BOE completeness gate ("
            f"{'declares a formula' if casilla.formula is not None else 'is required'}), but no "
            f"fixed-width export record addresses it BY CASILLA ID and it declares neither "
            f"internal_only nor export_exemption_reason. Exemption from that gate must be declared, "
            f"not left to absence: annotate the casilla with the reason it files no slot, or give it "
            f"the export field it is missing. Before concluding it is not representable, check the "
            f"record design and the bindings: this scan is casilla-keyed and CANNOT see a "
            f"BINDING-kind field, so a value the export really does write at a declared offset "
            f"looks identical here to one AEAT never prints "
            f"({ExportExemptionReason.FILED_VIA_BINDING_FIELD.value!r} is the reason for that case)",
        )


__all__ = ["validate_export_exemption_declarations"]
