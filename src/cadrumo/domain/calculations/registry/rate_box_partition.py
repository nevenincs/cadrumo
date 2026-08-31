"""Rate-box partitions: the two-layer shape a rate-keyed official box requires.

A casilla cannot both feed a computed total and be exported to a rate-specific
AEAT box. The two roles want opposite bindings: rate-BLIND to keep every row in
the total, rate-SPECIFIC to keep the box truthful. The registry expresses the
split as two layers over one selector shape -- a rate-blind binding whose
casilla carries no ``export_refs`` (the total layer) and its rate-specific
siblings whose casillas do (the box layer).

This module derives those layers from the revision alone, so no consumer has to
name a modelo's casillas to find them. A ledger-IVA binding's selector is a set
of axes plus an optional ``applied_rates`` narrowing; two bindings that agree on
every other axis and disagree only there are the same quantity read twice, once
whole and once per rate. That agreement is the partition key.

Why the layers can disagree, and why the difference is not an error to hide
---------------------------------------------------------------------------

An observation whose ``applied_rate`` is unknown matches the blind binding and
no rate-specific one, deliberately: admitting it would place an unmeasured line
in a box asserting a rate the operator never stated. So the box layer sums to
LESS than the total layer by exactly the amount whose rate was never recorded,
and that difference is a fact about the taxpayer's ledger rather than a defect
in the calculation.

:func:`rate_box_coverage_shortfalls` is the single arithmetic both gates read:
the calculate path raises it as a non-blocking advisory (the operator needs the
number in order to repair the ledger) and the export path refuses on it (a
return whose rate boxes do not account for its declared total is what a human
files, with nothing behind it). Two copies of this subtraction is how the two
gates would come to disagree about the same return, so there is one.

See Also:
    :mod:`domain.calculations.registry.ledger_iva_bindings`
        Owns the ``applied_rates`` selector axis and the deliberate
        no-match-on-unknown-rate rule this module measures the consequence of.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from typing import TypeGuard

from pydantic import Field

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId
from ....core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from .binding_targets import casillas_by_binding
from .ids import BindingId
from .ledger_iva_bindings import iva_ledger_selector
from .schema import DataBindingDefinition, ModeloRevision
from .schema_base import RegistryModel

__all__ = [
    "RateBoxPartition",
    "RateBoxShortfall",
    "RateBoxUnscreenedGroup",
    "derive_rate_box_partitions",
    "rate_box_coverage_shortfalls",
    "rate_box_unscreened_groups",
]

_APPLIED_RATES_AXIS = "applied_rates"

#: Why a rate-split selector group formed no partition and was therefore never
#: screened. Named rather than inlined so a caller can branch on severity: the
#: first is the total absence of the blind layer and loses rate-unrecorded rows
#: outright, while the rest are shapes the partition arithmetic cannot read.
_NO_RATE_BLIND_SIBLING = "no_rate_blind_sibling"
_MULTIPLE_RATE_BLIND_SIBLINGS = "multiple_rate_blind_siblings"
_NO_SINGLE_TOTAL_CASILLA = "no_single_total_casilla"
_TOTAL_CASILLA_EXPORTS = "total_casilla_exports"
_NO_BOX_CASILLA_EXPORTS = "no_box_casilla_exports"
_NO_RATE_KINDS = "no_rate_kinds"


class RateBoxPartition(RegistryModel):
    """One rate-blind total casilla and the rate-specific casillas breaking it down."""

    total_casilla_id: CasillaId
    """The rate-blind layer: catches every row, including rows with no recorded rate."""
    box_casilla_ids: tuple[CasillaId, ...] = Field(min_length=1)
    """The rate-specific layer, in canonical id order. Each admits exactly the rates
    its binding declares, so their sum omits every row whose rate is unknown."""
    rate_kinds: tuple[str, ...] = Field(min_length=1)
    """The semantic tier(s) both layers share, named so an advisory can say WHICH
    tier holds the unaccounted money rather than only how much."""
    fact: str = Field(min_length=1)
    """The quantity being partitioned (``iva_amount_sum`` / ``base_amount_sum`` /
    ``recargo_amount_sum``). Two layers over different facts are different
    partitions and never share one."""


class RateBoxUnscreenedGroup(RegistryModel):
    """A rate-split selector group that formed no partition, and why.

    Its existence is the answer to a question the shortfall list cannot answer:
    whether "no shortfalls" means everything was checked and was clean, or that
    nothing was eligible to be checked.
    """

    selector_identity: tuple[str, ...] = Field(min_length=1)
    """The partition key as ``axis=value`` pairs, excluding the rate axis."""
    rated_binding_ids: tuple[BindingId, ...] = Field(min_length=1)
    """The rate-pinned bindings whose rows this group would have screened."""
    reason: str = Field(min_length=1)
    """Why no partition formed. ``no_rate_blind_sibling`` is the severe one."""


class RateBoxShortfall(RegistryModel):
    """A partition whose rate boxes account for less than its rate-blind total."""

    partition: RateBoxPartition
    total: Decimal
    boxes_total: Decimal
    shortfall: Decimal
    """``total - boxes_total``, strictly positive. The amount sitting in the return
    that no official rate box accounts for."""


def _partition_key(axes: Mapping[str, object]) -> tuple[tuple[str, str], ...]:
    """Return the selector identity the two layers of one partition must share.

    Every axis except ``applied_rates``, rendered as a sorted, stringified pair
    sequence. Rendering rather than comparing models is deliberate: the key
    exists only to group, and an axis value that happens to be unhashable must
    not decide whether a partition is found. The axes come from the parsed
    selector model rather than the authored mapping, so a default an author left
    implicit and a sibling stated explicitly still key alike -- otherwise the two
    layers of one partition would land in different groups and the gate would go
    quiet on exactly the return it exists for.
    """
    return tuple(sorted((key, repr(value)) for key, value in axes.items() if key != _APPLIED_RATES_AXIS))


def _distinct(casilla_ids: Iterable[CasillaId]) -> list[CasillaId]:
    return list(dict.fromkeys(casilla_ids))


def _is_object_sequence(value: object) -> TypeGuard[Sequence[object]]:
    """Narrow an unparameterized runtime sequence to untrusted object entries, excluding ``str``."""
    return isinstance(value, Sequence) and not isinstance(value, str)


def _rate_kind_names(value: object) -> tuple[str, ...]:
    if not _is_object_sequence(value):
        return ()
    return tuple(str(getattr(kind, "value", kind)) for kind in value)


def _iva_selector_axes(binding: DataBindingDefinition) -> Mapping[str, object]:
    """Return one ledger-IVA binding's selector axes, defaults resolved.

    Parsed through the family's own selector model rather than read off the
    authored mapping, so every axis is present with its declared default. The
    partition key below compares axis-for-axis, and an author who states a
    default explicitly on one layer and leaves it implicit on the other would
    otherwise split one partition into two groups, silencing the gate for
    exactly the return it exists to catch.
    """
    return STR_KEYED_MAPPING_ADAPTER.validate_python(iva_ledger_selector(binding).model_dump())


def _partition_for_rate_box_group(
    *,
    members: Sequence[tuple[DataBindingDefinition, Mapping[str, object]]],
    casillas_by_binding: Mapping[BindingId, Sequence[CasillaId]],
    exports: Mapping[CasillaId, bool],
) -> RateBoxPartition | None:
    """Build one formed partition, or preserve the group for unscreened reporting.

    The formation decision is deliberately delegated to
    :func:`_unscreened_reason`: a group that has a reason must remain absent from
    this result so :func:`rate_box_unscreened_groups` can report it instead.
    """
    blind = [member for member in members if not member[1].get(_APPLIED_RATES_AXIS)]
    rated = [member for member in members if member[1].get(_APPLIED_RATES_AXIS)]
    if not rated:
        return None
    if (
        _unscreened_reason(
            rated=rated,
            blind=blind,
            casillas_by_binding=casillas_by_binding,
            exports=exports,
        )
        is not None
    ):
        return None
    blind_binding, blind_axes = blind[0]
    total_casilla_id = _distinct(casillas_by_binding.get(blind_binding.id, ()))[0]
    box_casillas = _distinct(
        casilla_id for binding, _ in rated for casilla_id in casillas_by_binding.get(binding.id, ())
    )
    return RateBoxPartition(
        total_casilla_id=total_casilla_id,
        box_casilla_ids=tuple(sorted(box_casillas)),
        rate_kinds=_rate_kind_names(blind_axes.get("rate_kinds")),
        fact=str(blind_axes.get("fact", "iva_amount_sum")),
    )


def derive_rate_box_partitions(revision: ModeloRevision) -> tuple[RateBoxPartition, ...]:
    """Return every two-layer rate partition the revision declares.

    A partition is recognised when the revision's ledger-IVA bindings contain,
    for one selector identity, exactly one rate-blind binding (``applied_rates``
    unset) and at least one rate-specific sibling, each resolving to a declared
    casilla, where the blind casilla carries NO ``export_refs`` and at least one
    box casilla does.

    Each condition removes a way this derivation could otherwise ground a refusal
    on a filing that is not wrong:

    * **The blind casilla must not export.** A casilla that both totals and
      exports is the un-split shape the two-layer design repairs; it writes its
      own rate assertion to the record, so reading its siblings as the box layer
      would measure a coverage gap the artefact does not have.
    * **At least one box casilla must export.** Rate-specific casillas reaching no
      official record assert no rate, so a difference between them and the total
      is internal bookkeeping, not something a filed artefact gets wrong.
    * **Exactly one blind binding.** Two rate-blind siblings mean the selector
      identity is not the partition axis it is being read as, and the arithmetic
      downstream would silently pick one of them.

    Rate-specific siblings carrying no ``export_refs`` still count toward the box
    sum. They are not boxes, but they are money accounted for, and dropping them
    would overstate the shortfall.

    .. warning::
        **Do not make a gate over rate-asserting casillas consume this function.**
        The convergence looks obviously correct from outside — this is the
        canonical owner of the rate-box concept — and it silently narrows the
        gate's population. What comes back here is only casillas belonging to a
        FORMED partition, so a rate-pinned casilla whose group formed none is
        absent by construction. That group is exactly where the severe defect
        lives: every binding pins a rate, no blind sibling remains, and a row
        whose rate was never recorded reaches no casilla at all. A gate rebuilt
        on this output would stop seeing precisely the case it exists for.

        :func:`rate_box_unscreened_groups` returns that residue and is the
        correct thing to consume when the question is "what was never checked".

    Args:
        revision: The :class:`ModeloRevision` whose bindings and casillas are read.

    Returns:
        Partitions in canonical total-casilla order; empty when the revision
        declares no rate-specific ledger-IVA binding at all.
    """
    populated_casillas = casillas_by_binding(revision)
    exports = {casilla.id: bool(casilla.export_refs) for casilla in revision.casillas}

    grouped = _ledger_iva_bindings_by_partition_key(revision)

    partitions: list[RateBoxPartition] = []
    for members in grouped.values():
        partition = _partition_for_rate_box_group(
            members=members,
            casillas_by_binding=populated_casillas,
            exports=exports,
        )
        if partition is not None:
            partitions.append(partition)
    return tuple(sorted(partitions, key=lambda partition: partition.total_casilla_id))


def _ledger_iva_bindings_by_partition_key(
    revision: ModeloRevision,
) -> dict[tuple[tuple[str, str], ...], list[tuple[DataBindingDefinition, Mapping[str, object]]]]:
    """Group the revision's ledger-IVA bindings by their non-rate selector identity.

    The rate axis is excluded from the key, which is what makes a rate-pinned
    binding and its rate-blind sibling land in the same group.
    """
    grouped: dict[tuple[tuple[str, str], ...], list[tuple[DataBindingDefinition, Mapping[str, object]]]] = {}
    for binding in revision.bindings:
        if binding.source is not BindingSourceKind.LEDGER_IVA_AGGREGATION:
            continue
        axes = _iva_selector_axes(binding)
        grouped.setdefault(_partition_key(axes), []).append((binding, axes))
    return grouped


def _unscreened_reason(
    *,
    rated: list[tuple[DataBindingDefinition, Mapping[str, object]]],
    blind: list[tuple[DataBindingDefinition, Mapping[str, object]]],
    casillas_by_binding: Mapping[BindingId, Sequence[CasillaId]],
    exports: Mapping[CasillaId, bool],
) -> str | None:
    """Return why this rate-split group forms no partition, or ``None`` if it does.

    The order is load-bearing: the absent-blind-sibling case is checked first
    because it is the severe one -- every binding pins a rate, so a row whose
    rate the ledger never recorded matches none of them and reaches no casilla
    at all.
    """
    if not blind:
        return _NO_RATE_BLIND_SIBLING
    if len(blind) > 1:
        return _MULTIPLE_RATE_BLIND_SIBLINGS
    total_casillas = _distinct(casillas_by_binding.get(blind[0][0].id, ()))
    box_casillas = _distinct(
        casilla_id for binding, _ in rated for casilla_id in casillas_by_binding.get(binding.id, ())
    )
    return _unscreened_layout_reason(
        total_casillas=total_casillas,
        box_casillas=box_casillas,
        exports=exports,
        blind_axes=blind[0][1],
    )


def _unscreened_layout_reason(
    *,
    total_casillas: Sequence[CasillaId],
    box_casillas: Sequence[CasillaId],
    exports: Mapping[CasillaId, bool],
    blind_axes: Mapping[str, object],
) -> str | None:
    if len(total_casillas) != 1 or not box_casillas:
        return _NO_SINGLE_TOTAL_CASILLA
    if exports.get(total_casillas[0], False) or total_casillas[0] in box_casillas:
        return _TOTAL_CASILLA_EXPORTS
    if not any(exports.get(casilla_id, False) for casilla_id in box_casillas):
        return _NO_BOX_CASILLA_EXPORTS
    if not _rate_kind_names(blind_axes.get("rate_kinds")):
        return _NO_RATE_KINDS
    return None


def rate_box_unscreened_groups(revision: ModeloRevision) -> tuple[RateBoxUnscreenedGroup, ...]:
    """Return rate-split selector groups that :func:`derive_rate_box_partitions` drops.

    A partition forms only when several conditions hold at once, and every one of
    them is a way a group can vanish from the screened population. So an empty
    shortfall list has two readings that are indistinguishable from the outside:
    every partition was checked and was clean, or **nothing was eligible to be
    checked at all**. This function separates them.

    The population returned is deliberately narrow: groups that declare at least
    one RATE-PINNED binding and still form no partition. A group with no
    rate-pinned binding is not a rate split, forms no partition correctly, and is
    NOT residue -- reporting it would bury the real cases under every ordinary
    rate-blind binding in the registry.

    That leaves three states a caller can now distinguish, where before there
    were two names for three things:

    * **screened** -- the group formed a partition and its arithmetic was read;
    * **unscreened** -- returned here, with the reason it was dropped;
    * **ineligible** -- no rate-pinned binding, correctly absent from both.

    The severe case is ``NO_RATE_BLIND_SIBLING``: every binding for the selector
    identity pins a rate, so a row whose rate the ledger never recorded matches
    none of them and reaches no casilla at all. That is the total absence of the
    blind layer, which is worse than the partial coverage
    :func:`rate_box_coverage_shortfalls` measures, and it is invisible to it.

    Args:
        revision: The :class:`ModeloRevision` whose bindings and casillas are read.

    Returns:
        One entry per dropped rate-split group, in canonical reason-then-binding
        order; empty when every rate-split group the revision declares formed a
        partition.
    """
    populated_casillas = casillas_by_binding(revision)
    exports = {casilla.id: bool(casilla.export_refs) for casilla in revision.casillas}
    grouped = _ledger_iva_bindings_by_partition_key(revision)

    unscreened = [
        group
        for key, members in grouped.items()
        if (group := _unscreened_group_for_members(key, members, populated_casillas, exports)) is not None
    ]
    return tuple(sorted(unscreened, key=lambda group: (group.reason, group.rated_binding_ids)))


def _unscreened_group_for_members(
    key: tuple[tuple[str, str], ...],
    members: Sequence[tuple[DataBindingDefinition, Mapping[str, object]]],
    casillas_by_binding: Mapping[BindingId, Sequence[CasillaId]],
    exports: Mapping[CasillaId, bool],
) -> RateBoxUnscreenedGroup | None:
    rated = [member for member in members if member[1].get(_APPLIED_RATES_AXIS)]
    if not rated:
        return None
    blind = [member for member in members if not member[1].get(_APPLIED_RATES_AXIS)]
    reason = _unscreened_reason(
        rated=rated,
        blind=blind,
        casillas_by_binding=casillas_by_binding,
        exports=exports,
    )
    if reason is None:
        return None
    return RateBoxUnscreenedGroup(
        selector_identity=tuple(f"{axis}={value}" for axis, value in key),
        rated_binding_ids=tuple(sorted(binding.id for binding, _ in rated)),
        reason=reason,
    )


def rate_box_coverage_shortfalls(
    partitions: Sequence[RateBoxPartition],
    values: Mapping[CasillaId, Decimal],
) -> tuple[RateBoxShortfall, ...]:
    """Return the partitions whose rate boxes account for less than their total.

    An absent casilla reads as zero, the same reading the export renderer gives
    it: a casilla the calculation did not populate contributes nothing to the
    record either.

    Only a strictly positive difference is returned. An equal box sum is the
    healthy state, and a box sum EXCEEDING the total is a different defect
    (rate boxes whose declared rates overlap, so one row lands in two) that this
    function deliberately does not claim to detect -- reporting it here as a
    coverage shortfall would name the wrong condition and point the operator at
    a ledger repair that would not fix it.
    """
    shortfalls: list[RateBoxShortfall] = []
    for partition in partitions:
        total = values.get(partition.total_casilla_id, Decimal("0"))
        boxes_total = sum(
            (values.get(casilla_id, Decimal("0")) for casilla_id in partition.box_casilla_ids),
            Decimal("0"),
        )
        if total - boxes_total <= 0:
            continue
        shortfalls.append(
            RateBoxShortfall(
                partition=partition,
                total=total,
                boxes_total=boxes_total,
                shortfall=total - boxes_total,
            ),
        )
    return tuple(shortfalls)
