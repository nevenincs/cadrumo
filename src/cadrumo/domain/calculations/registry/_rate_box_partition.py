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
--------------------------------------------------------------------------

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
    :mod:`domain.calculations.registry._ledger_bindings`
        Owns the ``applied_rates`` selector axis and the deliberate
        no-match-on-unknown-rate rule this module measures the consequence of.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal

from pydantic import Field

from ....core.aggregation import BindingSourceKind
from ._ids import BindingId, CasillaId
from ._ledger_bindings import _iva_ledger_selector
from ._schema import DataBindingDefinition, ModeloRevision
from ._schema_base import RegistryModel

__all__ = [
    "RateBoxPartition",
    "RateBoxShortfall",
    "derive_rate_box_partitions",
    "rate_box_coverage_shortfalls",
]

_APPLIED_RATES_AXIS = "applied_rates"


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


def _rate_kind_names(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str):
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
    return _iva_ledger_selector(binding).model_dump()


def _casillas_by_binding(revision: ModeloRevision) -> dict[BindingId, list[CasillaId]]:
    """Map every binding id to the casillas it may populate, primary or alternate.

    Alternate bindings are included because a casilla reached only through one is
    still that binding's money; omitting it would understate the box layer and
    manufacture a shortfall. The caller de-duplicates, so a casilla naming the
    same binding twice contributes once.
    """
    mapping: dict[BindingId, list[CasillaId]] = {}
    for casilla in revision.casillas:
        binding_ids = (
            *((casilla.binding,) if casilla.binding is not None else ()),
            *casilla.alternate_bindings,
        )
        for binding_id in binding_ids:
            mapping.setdefault(binding_id, []).append(casilla.id)
    return mapping


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

    Args:
        revision: The :class:`ModeloRevision` whose bindings and casillas are read.

    Returns:
        Partitions in canonical total-casilla order; empty when the revision
        declares no rate-specific ledger-IVA binding at all.
    """
    casillas_by_binding = _casillas_by_binding(revision)
    exports = {casilla.id: bool(casilla.export_refs) for casilla in revision.casillas}

    grouped: dict[tuple[tuple[str, str], ...], list[tuple[DataBindingDefinition, Mapping[str, object]]]] = {}
    for binding in revision.bindings:
        if binding.source is not BindingSourceKind.LEDGER_IVA_AGGREGATION:
            continue
        axes = _iva_selector_axes(binding)
        grouped.setdefault(_partition_key(axes), []).append((binding, axes))

    partitions: list[RateBoxPartition] = []
    for members in grouped.values():
        blind = [member for member in members if not member[1].get(_APPLIED_RATES_AXIS)]
        rated = [member for member in members if member[1].get(_APPLIED_RATES_AXIS)]
        if len(blind) != 1 or not rated:
            continue
        blind_binding, blind_axes = blind[0]
        total_casillas = _distinct(casillas_by_binding.get(blind_binding.id, ()))
        box_casillas = _distinct(
            casilla_id for binding, _ in rated for casilla_id in casillas_by_binding.get(binding.id, ())
        )
        if len(total_casillas) != 1 or not box_casillas:
            continue
        total_casilla_id = total_casillas[0]
        if exports.get(total_casilla_id, False) or total_casilla_id in box_casillas:
            continue
        if not any(exports.get(casilla_id, False) for casilla_id in box_casillas):
            continue
        rate_kinds = _rate_kind_names(blind_axes.get("rate_kinds"))
        if not rate_kinds:
            continue
        partitions.append(
            RateBoxPartition(
                total_casilla_id=total_casilla_id,
                box_casilla_ids=tuple(sorted(box_casillas)),
                rate_kinds=rate_kinds,
                fact=str(blind_axes.get("fact", "iva_amount_sum")),
            ),
        )
    return tuple(sorted(partitions, key=lambda partition: partition.total_casilla_id))


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
