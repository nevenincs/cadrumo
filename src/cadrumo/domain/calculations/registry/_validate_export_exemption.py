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
-------------------------------------------------------------------------------

"No record addresses it" means no record addresses it BY CASILLA ID. A
``BINDING``-kind export field names the binding, not the casilla, so a value the
export genuinely writes at a declared offset is invisible to this scan and looks
exactly like one AEAT never prints. Modelo 720 is the worked case: its raw export
records deliberately carry zero inline fields, while registry bindings declare
``ejercicio`` at positions 5-8 and declaración complementaria/sustitutiva at
121-122. :func:`derive_export_layouts_from_bindings` materialises those selectors
as ``BINDING`` fields before this validator scans the layout. The positions belong
to the binding-derived layout, not to fields authored inline on the raw records.

A value can reach a casilla through THREE channels, and this gate sees two:

1. a formula expression naming it;
2. a binding selector naming it — the registry-declared route, which the
   ``feeds_addressed_casilla`` check walks; and
3. **application-code injection**, via ``bound_inputs_by_casilla_id`` on a
   :class:`CalculationSourceResolution`, which never consults ``casilla.binding``
   at all.

Channel three is invisible here and cannot be made visible: it lives in the
application layer, which a domain validator must not import. Modelo 303's box 44
is the worked case — it is ``input_kind = manual`` with ``binding = None``, no
casilla names its binding, and the prorrata resolver delivers its value anyway by
returning ``{"44": ...}`` keyed on the casilla id. **"No casilla names the
binding" does not imply "the value does not arrive."**

So a refusal from this gate is a question, not a verdict: it says the exemption
is undeclared, never that the casilla is unrepresentable and never that its value
fails to arrive. Answering it means reading the record design, the bindings, AND
the resolver mesh. :attr:`~core.ExportExemptionReason.FILED_VIA_BINDING_FIELD`
exists precisely because the honest answer is sometimes "it is filed, just not
through a casilla address". The refusal message repeats this warning, because
that is where an author actually lands.

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
    :func:`~application.filing._export_parity.assert_export_mirrors_manifest`
        The pre-write gate whose required set this protects.
"""

from __future__ import annotations

from collections.abc import Mapping

from ....core.aggregation import BindingSourceKind
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.casilla_id import CasillaId
from ....core.export_exemption_reason import ExportExemptionReason
from ....core.export_layout_format import ExportLayoutFormat
from .bindings import binding_source_casilla_ids, binding_source_modelo
from .export import derive_export_layouts_from_bindings, fixed_width_record_casilla_ids
from .runtime_graph import expression_casilla_refs
from .schema import (
    DataBindingDefinition,
    FormulaDefinition,
    ModeloDefinition,
    ModeloRevision,
)
from .schema_base import RegistrySourceKind
from .schema_references import SourceReference
from .schema_surfaces import CasillaDefinition


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


def _formula_consumption_sources(
    casilla: CasillaDefinition,
    *,
    formulas: dict[str, FormulaDefinition],
) -> tuple[CasillaId, ...]:
    if casilla.formula is None:
        return ()
    formula = formulas.get(casilla.formula)
    return () if formula is None else tuple(expression_casilla_refs(formula.expression))


def _binding_consumption_sources(
    casilla: CasillaDefinition,
    *,
    bindings: dict[str, DataBindingDefinition],
    modelo_id: str,
) -> tuple[CasillaId, ...]:
    sources: list[CasillaId] = []
    for binding_id in (casilla.binding, *casilla.alternate_bindings):
        binding = bindings.get(binding_id) if binding_id is not None else None
        if binding is None or binding.source is BindingSourceKind.PREVIOUS_FILING:
            continue
        source_modelo = binding_source_modelo(binding)
        if source_modelo is not None and source_modelo != modelo_id:
            continue
        sources.extend(binding_source_casilla_ids(binding))
    return tuple(sources)


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
        sources = _formula_consumption_sources(casilla, formulas=formula_by_id)
        sources += _binding_consumption_sources(casilla, bindings=binding_by_id, modelo_id=modelo_id)
        for source in sources:
            edges.setdefault(source, set()).add(casilla.id)
    return edges


def _fixed_width_addressed_casillas(revision: ModeloRevision) -> set[CasillaId] | None:
    layouts = tuple(
        layout
        for layout in derive_export_layouts_from_bindings(revision)
        if layout.format is ExportLayoutFormat.FIXED_WIDTH
    )
    if not layouts:
        return None
    addressed: set[CasillaId] = set()
    for layout in layouts:
        addressed |= fixed_width_record_casilla_ids(layout.records)
    return addressed


def _manifest_casilla_exemption_failure(
    *,
    casilla: CasillaDefinition | None,
    addressed: set[CasillaId],
    consumers: dict[CasillaId, set[CasillaId]],
    prefix: str,
) -> str | None:
    if casilla is None or casilla.id in addressed or casilla.internal_only:
        return None
    if casilla.formula is None and not casilla.required:
        return None
    if casilla.export_exemption_reason is ExportExemptionReason.FEEDS_ADDRESSED_CASILLA:
        if _reaches_addressed_casilla(casilla.id, consumers=consumers, addressed=addressed):
            return None
        return (
            f"{prefix}: casilla {casilla.id!r} declares export_exemption_reason "
            f"{ExportExemptionReason.FEEDS_ADDRESSED_CASILLA.value!r}, which asserts its figure "
            f"reaches the record through a downstream box, but no formula or binding chain leads "
            f"from it to any casilla a fixed-width export record addresses. Either wire the chain, "
            f"or declare the reason this casilla genuinely files no slot. Note this walk sees the "
            f"REGISTRY graph only: a value delivered by application code through "
            f"bound_inputs_by_casilla_id is invisible here, so confirm no resolver already carries "
            f"it before rewiring"
        )
    if casilla.export_exemption_reason is not None:
        return None
    return (
        f"{prefix}: casilla {casilla.id!r} is in the completeness manifest and would be "
        f"required by the fichero-BOE completeness gate ("
        f"{'declares a formula' if casilla.formula is not None else 'is required'}), but no "
        f"fixed-width export record addresses it BY CASILLA ID and it declares neither "
        f"internal_only nor export_exemption_reason. Exemption from that gate must be declared, "
        f"not left to absence: annotate the casilla with the reason it files no slot, or give it "
        f"the export field it is missing. Before concluding it is not representable, check the "
        f"record design, the bindings AND the resolver mesh: this scan is casilla-keyed and sees "
        f"neither a BINDING-kind export field (so a value the export really does write at a "
        f"declared offset looks identical here to one AEAT never prints -- "
        f"{ExportExemptionReason.FILED_VIA_BINDING_FIELD.value!r} is the reason for that case) nor "
        f"a value injected by application code through bound_inputs_by_casilla_id, which never "
        f"consults casilla.binding. 'No casilla names the binding' does not imply 'the value does "
        f"not arrive'"
    )


def modelo_publishes_a_record_design(
    modelo: ModeloDefinition,
    source_refs: Mapping[str, SourceReference],
) -> bool:
    """Return whether AEAT publishes a machine-readable record design for this MODELO.

    Read across the modelo and every one of its revisions, deliberately, not per
    revision. A design bundled for one epoch proves AEAT publishes one for the
    form; a revision of the same modelo that cites none is an ACQUISITION gap --
    the epoch's design exists and has not been fetched -- and that must stay a
    refusal. Modelo 185 is the worked case: its 2026 design is bundled, its
    ``2003-2025`` revision cites none, and scoping this per revision quietly
    excused exactly the acquisition gap the refusal exists to surface.

    A ``form_spec`` does not count and the distinction carries the decision:
    Modelo 721 cites its approving BOE orden's anexo at ``layout_authority``
    tier, which is a printable form, not a positional design a fixed-width
    writer could be authored from.
    """
    refs = set(modelo.source_refs)
    for revision in modelo.revisions.values():
        refs |= set(revision.source_refs)
    return any(
        (source := source_refs.get(ref)) is not None and source.kind is RegistrySourceKind.RECORD_DESIGN for ref in refs
    )


def validate_export_exemption_declarations(
    *,
    prefix: str,
    modelo_id: str,
    revision: ModeloRevision,
    publishes_record_design: bool,
) -> list[str]:
    """Refuse a revision that cannot emit, and every export exemption lacking a reason.

    Resolves the revision's export layouts the way snapshot build does — through
    :func:`derive_export_layouts_from_bindings`, so binding-derived record fields
    are present — and scans every fixed-width layout.

    A revision declaring no fixed-width layout is refused HERE, at registry build.
    That is deliberate and it is the whole point: the registry must fail until the
    filing capability exists. The mechanism this replaces returned early on exactly
    that condition, which made the completeness gate a no-op for the revisions
    furthest from being filable — the larger the gap, the quieter it was. There is
    no allowance, no allowlist and no per-modelo exemption; a modelo the
    application cannot file is a capability still to build, never a settled state.

    Failures accumulate rather than raising, so one load reports every revision
    that cannot emit instead of the first. That enumeration is the capability
    worklist, and it shrinks only when a layout is authored.

    Args:
        prefix: Caller-supplied ``modelo N revision R`` diagnostic prefix.
        modelo_id: Modelo identifier, used to scope out cross-modelo binding
            edges whose source casilla ids name a foreign modelo.
        revision: The :class:`ModeloRevision` under validation.
        publishes_record_design: Whether AEAT publishes a record design for this
            modelo, from :func:`modelo_publishes_a_record_design`.
    """
    claims_filing_grade = revision.effective_authority_grade is RegistryAuthorityGrade.FILING
    failures: list[str] = []
    # Refused on emitting NOTHING, not on lacking a fixed-width layout specifically.
    # Modelo 100 files through an XML dictionary and declares no fichero BOE at all;
    # refusing it for the missing fixed-width layout would report a modelo that CAN
    # emit as incapable, and would put a second, larger number into circulation
    # beside the capability worklist's. One question, one count.
    if not derive_export_layouts_from_bindings(revision):
        # Scoped twice, on two independent claims the revision itself makes.
        #
        # FIRST, on the declared authority grade. The filing rung is the one that
        # asserts "can additionally back a filing draft and its export"; the
        # applicability rung asserts scheduling reach and nothing more. Refusing an
        # applicability-grade revision for lacking an export layout refuses a claim
        # it never made. Modelo 182 is the worked case: its revision carries a
        # reviewed comment recording that the donativos declaration is filed by the
        # entity RECEIVING the donation, so this application's taxpayer is the
        # subject of the declaration and not its filer -- authoring a layout there
        # would assert a filing capability the registry deliberately disclaims.
        #
        # This cannot become a mute button, and the reason is not that grade is
        # hard to change. It is that the RUNTIME check is not scoped by grade:
        # `_check_snapshot_filing_capability` refuses a filing-grade snapshot from
        # any revision with no export layout, so the capability can never be
        # exercised whatever a revision declares here. Demotion is also a real
        # capability loss rather than a free pass -- an applicability-grade
        # revision serves no filing surface at all -- and promotion is an
        # attestation no program may make.
        #
        # SECOND, on whether a record design EXISTS to author from.
        # The refusal's own instruction is "author the layout from its official
        # record design", and for a modelo AEAT publishes no design for that is
        # not a task, it is an impossibility -- the refusal would stand forever
        # and mean nothing. This is NOT a per-modelo exemption: the condition is
        # a property of the source catalogue, and a revision cannot dodge it by
        # dropping its citation, because every bundled design must stay
        # registered (``test_every_bundled_record_design_is_registered``). Over
        # the bundled registry it separates exactly two modelos, 136 and 721,
        # from the other forty-six.
        if publishes_record_design and claims_filing_grade:
            failures.append(
                f"{prefix}: declares no export layout, so this application cannot file it. A missing "
                "layout is not an exemption and there is no declaration that excuses it: it is the "
                "filing capability being absent. Author the revision's export layout from its official "
                "record design.",
            )
        return failures
    # Checked BEFORE the manifest, deliberately. A revision carrying neither a
    # layout nor a completeness manifest is the least capable state there is, and
    # ordering the manifest test first would let it return clean.
    manifest = revision.completeness_manifest
    if manifest is None:
        return failures
    addressed = _fixed_width_addressed_casillas(revision)
    if addressed is None:
        # An XML-dictionary revision emits, but has no fichero-BOE completeness
        # gate for a casilla to be exempt FROM, so the per-casilla scan below
        # does not apply to it.
        return failures
    consumers = _consumption_edges(revision, modelo_id)

    casilla_by_id = {casilla.id: casilla for casilla in revision.casillas}
    for manifest_casilla in manifest.casillas:
        failure = _manifest_casilla_exemption_failure(
            casilla=casilla_by_id.get(manifest_casilla.casilla_id),
            addressed=addressed,
            consumers=consumers,
            prefix=prefix,
        )
        if failure is not None:
            failures.append(failure)
    return failures


__all__ = ["modelo_publishes_a_record_design", "validate_export_exemption_declarations"]
