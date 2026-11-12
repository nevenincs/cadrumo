"""Caller override precedence for source resolution."""

from enum import StrEnum
from typing import NamedTuple

from ...core.aggregation import BindingSourceKind
from ...domain.modelos.source_disagreement import SourceDisagreementRole


class CallerOverrideDisposition(StrEnum):
    """Whether the calculate path permits a caller override of a source's value.

    The override disposition axis of the caller-override precedence ladder.

    Members:
        LOCK: Deterministic bucket-owned resolvers (ledger aggregations,
            invoice families, inventory projection, and other complete source
            authorities). A caller override is REJECTED so the persisted
            revision faithfully reflects the sources it aggregates.
        CARRY: Carry-style sources (previous_filing, relation_prefill, the
            IVA-compensation annual partition, and prorrata regularizacion).
            A caller override of an
            automatically-carried prior value is legitimate and must reach the
            engine, so these are EXCLUDED from the post-merge caller-override
            guard.
    """

    LOCK = "lock"
    CARRY = "carry"


class CallerOverridePrecedenceTier(NamedTuple):
    """One ordered tier of the calculate-path caller-override precedence ladder.

    Carries the tier name, the source kinds it owns, and the override disposition
    the guard applies to them. The ordered ladder is the single declaration the
    caller-override guard sets are derived from — :data:`CALLER_OVERRIDE_PRECEDENCE_LADDER`
    replaces the hand-listed lock / carry frozensets, and a conformance test binds
    the policy's derived sets to it so the two cannot silently diverge.
    """

    name: str
    source_kinds: frozenset[BindingSourceKind]
    disposition: CallerOverrideDisposition


#: The calculate-path caller-override precedence ladder as ordered tier data,
#: lowest-precedence tier first. The
#: guard's lock and carry source sets are the unions of the LOCK- and
#: CARRY-disposition tiers (see :func:`precedence_ladder_sources`). This encodes
#: the override DISPOSITION axis only. The overlay ORDER (profile < mesh backend
#: < borrador < caller, later tier wins) is :data:`PRECEDENCE_OVERLAY_ORDER`,
#: which
#: :func:`~cadrumo.application.aggregation.source_resolution_operations.merge_source_resolutions_by_precedence`
#: enforces and screens: a caller tier reaches the overlay only for the CARRY
#: sources this ladder lets through, and a higher tier replacing a different
#: lower-tier value there is reported rather than applied in silence.
CALLER_OVERRIDE_PRECEDENCE_LADDER: tuple[CallerOverridePrecedenceTier, ...] = (
    CallerOverridePrecedenceTier(
        name="deterministic_lock",
        source_kinds=frozenset(
            {
                BindingSourceKind.LEDGER_IVA_AGGREGATION,
                BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
                BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
                BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION,
                BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION,
                BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION,
                BindingSourceKind.LEDGER_OSS_AGGREGATION,
                BindingSourceKind.COLLECTIBLE_INVOICE,
                BindingSourceKind.PAYABLE_INVOICE,
                BindingSourceKind.M347_THIRD_PARTY_OPERATION,
                BindingSourceKind.M349_INTRACOMMUNITY_OPERATION,
                BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY,
                BindingSourceKind.INVENTORY,
                BindingSourceKind.RETENCION_SOPORTADA,
                BindingSourceKind.CAPITAL_MOBILIARIO_POSITION,
            },
        ),
        disposition=CallerOverrideDisposition.LOCK,
    ),
    CallerOverridePrecedenceTier(
        name="carry_forward",
        source_kinds=frozenset(
            {
                BindingSourceKind.PREVIOUS_FILING,
                BindingSourceKind.RELATION_PREFILL,
                BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION,
                BindingSourceKind.PRORRATA_REGULARIZACION,
            },
        ),
        disposition=CallerOverrideDisposition.CARRY,
    ),
    CallerOverridePrecedenceTier(
        name="box_shared_with_the_filer",
        source_kinds=frozenset({BindingSourceKind.ACTIVITY_ASSET_DISPOSAL}),
        disposition=CallerOverrideDisposition.CARRY,
    ),
)


PRECEDENCE_OVERLAY_ORDER: tuple[SourceDisagreementRole, ...] = (
    SourceDisagreementRole.PROFILE,
    SourceDisagreementRole.BACKEND,
    SourceDisagreementRole.BORRADOR,
    SourceDisagreementRole.CALLER,
)
"""The order the precedence overlay lays its tiers in, lowest first; the later tier's value is the one used."""


def precedence_ladder_sources(disposition: CallerOverrideDisposition) -> frozenset[BindingSourceKind]:
    """Union of the source kinds carried by every ladder tier of ``disposition``.

    The single derivation the caller-override policy sets read, so a source kind's
    lock-vs-carry disposition is declared once in
    :data:`CALLER_OVERRIDE_PRECEDENCE_LADDER` rather than hand-listed per set.

    Returns:
        The :class:`BindingSourceKind` members carried by every ladder tier
        whose disposition matches *disposition*.
    """
    return frozenset(
        kind
        for tier in CALLER_OVERRIDE_PRECEDENCE_LADDER
        if tier.disposition is disposition
        for kind in tier.source_kinds
    )
