"""Shared group-by, name-cache, and casilla-fold helpers for per-modelo aggregators.

Used by: :mod:`_retenciones`, :mod:`_counterpart` to bucket observations and cache canonical names;
:mod:`_renta_income_ledger`, :mod:`_renta_gasto_ledger`, :mod:`_impatriado_income_ledger`, and
:mod:`_irnr_income_ledger` to fold their observations into a :class:`CasillaAggregation`.

The name-cache consumers implement the same shape of aggregation: bucket
observations by a composite key, then roll up each bucket. They additionally
need to resolve a stable human-readable name per (source_kind, identity_nif)
pair across multiple observations.

The ledger-projection consumers share a second shape: fold a sequence of
single-casilla observations into per-casilla totals plus the
:class:`CasillaProvenance` rows tracing them, differing only in the modelo they
target and the amount each observation contributes.

This module extracts both shared mechanisms. The per-domain aggregators retain
their domain-specific rollup composition (e.g. counterpart adds country +
readiness fields) — only the group-and-name-cache and casilla-fold steps are
shared. A projection that groups on more than the casilla axis (the Modelo 100
first-slice expense path, which buckets by casilla AND spending category and
emits a populated ``category_id``) keeps its own fold: that is a different
grouping shape, not this one under another name.
"""

from __future__ import annotations

from collections.abc import Callable, Container, Iterable, Mapping, Sequence
from decimal import Decimal
from typing import Protocol

from ...core import Period
from ...domain.calculations.registry import CasillaId
from ._errors import AggregationUnsupportedModeloError, t
from ._models import CasillaAggregation, CasillaProvenance


def group_and_collect_names[T, GroupKey: tuple[object, ...], IdentityKey: tuple[object, ...]](
    observations: Iterable[T],
    *,
    group_key_fn: Callable[[T], GroupKey],
    identity_key_fn: Callable[[T], IdentityKey],
    name_fn: Callable[[T], str | None],
) -> tuple[dict[GroupKey, list[T]], dict[IdentityKey, str]]:
    """Bucket observations by group key and cache a canonical name per identity.

    Behaviour invariants (shared by both per-modelo aggregators):
      - Iteration order of ``observations`` is preserved within each bucket.
      - The first non-empty ``name_fn(obs)`` per ``identity_key_fn(obs)``
        wins; later non-empty names for the same identity are discarded.
      - An empty / falsy name is skipped (does not overwrite a prior win).

    Args:
        observations: Iterable of observation records.
        group_key_fn: Composite key for bucketing (e.g. (source_kind,
            nif, scheme)).
        identity_key_fn: Sub-key for the name cache (e.g. (source_kind,
            nif)).
        name_fn: Extractor for the human-readable name on each observation.

    Returns:
        A two-tuple ``(grouped, names)`` where ``grouped`` maps each
        ``group_key_fn(obs)`` to the list of observations sharing that
        key (insertion order), and ``names`` maps each
        ``identity_key_fn(obs)`` to the first non-empty name observed.
    """
    grouped: dict[GroupKey, list[T]] = {}
    names: dict[IdentityKey, str] = {}
    for observation in observations:
        group_key = group_key_fn(observation)
        grouped.setdefault(group_key, []).append(observation)
        identity_key = identity_key_fn(observation)
        name = name_fn(observation)
        if name and not names.get(identity_key):
            names[identity_key] = name
    return grouped, names


def filter_observations_for_modelo[T, AttrValue](
    observations: tuple[T, ...],
    *,
    modelo: str,
    catalogue: Mapping[str, Container[AttrValue]],
    attribute_fn: Callable[[T], AttrValue],
    aggregator_label: str,
) -> tuple[T, ...]:
    """Keep observations whose classifying attribute is in-scope for ``modelo``.

    Shared by both per-modelo aggregators: ``_counterpart`` filters on
    ``operation_kind`` against an :class:`OperationKind347` / ``349``
    catalogue; ``_retenciones`` filters on ``scheme`` against a
    :class:`RetencionScheme` catalogue. The only per-domain inputs are
    the catalogue, the attribute getter, and the label used in the
    unsupported-modelo error.

    Args:
        observations: Typed observation records to filter.
        modelo: The requested modelo code; must key into ``catalogue``.
        catalogue: Maps each supported modelo code to the container of
            eligible attribute values.
        attribute_fn: Extracts the classifying attribute from each
            observation.
        aggregator_label: Human-readable aggregator name for the
            :class:`AggregationUnsupportedModeloError` message.

    Raises:
        AggregationUnsupportedModeloError: When ``modelo`` is not a key
            in ``catalogue``.

    Returns:
        The observations whose classifying attribute is eligible for
        ``modelo``, in input order.
    """
    if modelo not in catalogue:
        raise AggregationUnsupportedModeloError(
            t("aggregation.grouping.errors.unsupported_modelo"),
            context={"aggregator_label": aggregator_label, "modelo": modelo},
        )
    eligible = catalogue[modelo]
    return tuple(o for o in observations if attribute_fn(o) in eligible)


class LedgerCasillaObservation(Protocol):
    """The read surface a ledger observation exposes to :func:`fold_casilla_observations`.

    Every ledger projection declares its own strict observation model carrying
    domain-specific fields (gross amount, deductible amount, withheld amount,
    source jurisdiction). Only these two are load-bearing for the fold: the
    casilla the row feeds, and the transaction id recorded in its provenance.

    Domain-qualified to stay distinct from
    :class:`~domain.calculations.registry.CasillaObservation`, the concrete
    formula-runtime carrier: this is a structural read surface over the
    ledger-projection models, keyed on ``target_casilla_id``, not that model's
    ``casilla_id`` value shape.
    """

    @property
    def target_casilla_id(self) -> CasillaId:
        """The canonical casilla id this observation contributes to."""
        ...

    @property
    def transaction_id(self) -> str:
        """The originating ledger transaction id, recorded in provenance."""
        ...


def fold_casilla_observations[ObservationT: LedgerCasillaObservation](
    observations: Sequence[ObservationT],
    *,
    modelo: str,
    period: Period,
    amount_fn: Callable[[ObservationT], Decimal],
) -> CasillaAggregation:
    """Fold single-casilla observations into per-casilla totals and provenance.

    Behaviour invariants (shared by every ledger-projection consumer):
      - Each observation contributes ``amount_fn(observation)`` to the total
        for its ``target_casilla_id``.
      - Exactly one :class:`CasillaProvenance` row is emitted per contributing
        casilla, in sorted casilla order, with ``category_id`` unset — this
        fold groups on the casilla axis alone.
      - Each provenance row carries its contributing transaction ids sorted,
        and a ``subtotal`` summed through the same ``amount_fn``, so a row's
        subtotal and the casilla total cannot diverge.

    Args:
        observations: The eligible observations to fold, in any order.
        modelo: The modelo identifier the aggregation belongs to, as
            ``Modelo.<member>.value``.
        period: The :class:`Period` the aggregation covers.
        amount_fn: Extracts the fiscally computable amount one observation
            contributes. Callers pass their own accessor, so an
            IVA-exclusive base and a gross amount stay distinct concepts.

    Returns:
        The :class:`CasillaAggregation` carrying the summed casilla values and
        their provenance rows.
    """
    totals: dict[CasillaId, Decimal] = {}
    grouped: dict[CasillaId, list[ObservationT]] = {}
    for observation in observations:
        casilla_id = observation.target_casilla_id
        totals[casilla_id] = totals.get(casilla_id, Decimal("0")) + amount_fn(observation)
        grouped.setdefault(casilla_id, []).append(observation)
    provenance = tuple(
        CasillaProvenance(
            casilla_id=casilla_id,
            category_id=None,
            transaction_ids=tuple(sorted(row.transaction_id for row in rows)),
            subtotal=sum((amount_fn(row) for row in rows), start=Decimal("0")),
        )
        for casilla_id, rows in sorted(grouped.items())
    )
    return CasillaAggregation(
        modelo=modelo,
        period=period,
        casilla_values=totals,
        provenance=provenance,
    )


__all__ = [
    "LedgerCasillaObservation",
    "filter_observations_for_modelo",
    "fold_casilla_observations",
    "group_and_collect_names",
]
