"""Closed vocabulary for why a casilla is exempt from the fichero-BOE completeness gate.

The pre-write completeness gate demands a value on disk for every casilla that is
a calculation RESULT or is schema-required, intersected with the set the official
record design files a slot for. A casilla outside that intersection is exempt —
and until this enum existed, exemption was expressed by ABSENCE: the casilla
simply carried no ``export_refs`` and no export field pointed at it. Absence
carries no reason, so the gate could not distinguish a casilla that genuinely
cannot reach a box from one that SHOULD reach a box and was never annotated. The
second case is a silent under-declaration wearing the same shape as the first.

Every other safety surface in this tree makes the reason declared data — the
dependency classifications, the deferred source kinds, the alternative-measure
declaration. This closes the same loop for export exemption: a casilla the gate
would otherwise demand, but which the record design does not carry, must say
WHY, and registry build refuses it otherwise.

The members are not interchangeable and each was forced by a real adjudication
against a bundled AEAT Diseño de Registros; do not add one without the same
evidence. In particular :attr:`ExportExemptionReason.RECORD_BLOCK_NOT_MODELLED`
records a KNOWN GAP rather than a settled absence, so it is the member to grep
for when asking what the application still does not file.

Hydration happens at the registry boundary:
:func:`~domain.calculations.registry.load_registry_tree` hands the TOML token to
strict schema validation, which resolves it to a member here.

See Also:
    :class:`~domain.calculations.registry.CasillaDefinition`
        Declares the reason on the casilla via ``export_exemption_reason``.
    :class:`~core.ExportLayoutFormat`
        The wire shape whose ``FIXED_WIDTH`` member the completeness gate binds.
"""

from __future__ import annotations

from enum import StrEnum


class ExportExemptionReason(StrEnum):
    """Declared reasons a manifest casilla files no slot on the official record.

    Members carry the exact tokens the registry TOML stores, so hydration is a
    behaviour-preserving lift: a member compares, hashes, and JSON-serialises
    identically to the string it replaces.
    """

    NOT_IN_RECORD_DESIGN = "not_in_record_design"
    """The official Diseño de Registros carries no field for this concept.

    The worked case is a carry-forward seed: Modelo 130's
    ``saldo-negativo-fin-periodo`` is the end-of-period negative balance the NEXT
    quarter consumes through its own box. The design's box ``[15]`` is the INPUT
    of prior negatives, a different concept; the end-of-period balance itself is
    never printed, so no annotation could ever route it to a slot.
    """

    INTERNAL_INTERMEDIATE = "internal_intermediate"
    """App-internal calculation support with no AEAT counterpart at all.

    Distinct from :attr:`NOT_IN_RECORD_DESIGN`, which names a real taxpayer-facing
    concept AEAT chose not to print. This names a quantity that exists only
    because the application materialised it — a regulatory ceiling a verification
    predicate bounds against, or an intermediate a downstream formula references.
    A casilla declaring ``internal_only`` already asserts this and needs no
    separate reason.
    """

    PRE_POPULATED_BY_AEAT = "pre_populated_by_aeat"
    """AEAT fills the box from third-party data the application does not hold.

    The box EXISTS on the record design and the taxpayer does file it, but its
    value originates outside this application — Modelo 100 casilla 0599 is
    pre-populated from third-party Modelo 190 withholding data. Modelling it by
    omission was indistinguishable from an oversight, which is the specific
    confusion this member removes.
    """

    FILED_VIA_BINDING_FIELD = "filed_via_binding_field"
    """The value reaches the record through a binding-addressed field.

    The record design carries the field and the export DOES write it, but the
    layout addresses the slot by ``binding`` rather than by ``casilla_id``, so a
    casilla-keyed representability scan cannot see it. Modelo 720's ejercicio
    (positions 5-8) and declaración complementaria/sustitutiva (121-122) are
    written exactly this way. This is the one member that asserts the value IS
    filed, so a casilla declaring it must be reachable through some binding.
    """

    FEEDS_ADDRESSED_CASILLA = "feeds_addressed_casilla"
    """A semantic aggregate whose figure the record files through a downstream box.

    Modelo 303's ``iva.cuota-devengada-total`` is the aggregation layer; official
    box ``27`` is the slot, and its formula reads the aggregate. Demanding the
    aggregate carry its own slot would be wrong — it has none — while the figure
    is filed all the same.

    This is the one member whose claim the registry-build gate VERIFIES rather
    than accepts: it walks the formula graph and refuses the declaration unless
    the casilla really does reach a casilla the record addresses. The exemption
    is then safe by construction, because that downstream box is itself inside
    the completeness gate's required set, so a lost figure still refuses the
    export.
    """

    RECORD_BLOCK_NOT_MODELLED = "record_block_not_modelled"
    """The design has a block for it that the application does not yet model.

    A KNOWN GAP, not a settled absence. Modelo 303's prorratas page declares
    boxes ``[500]``-``[504]``, and the application computes a prorrata percentage
    but models none of that page — it does not hold the per-CNAE inputs the block
    requires. Declaring the gap keeps it greppable instead of letting it wear the
    same silence as a concept AEAT never prints.
    """


__all__ = ["ExportExemptionReason"]
