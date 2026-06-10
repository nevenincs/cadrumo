"""Application-layer wrapper for Modelo 369 OSS / IOSS aggregation.

Used by: :mod:`~._modelo_bindings` (Modelo 369 binding resolver) to validate and aggregate ledger candidates.

This module sits between the bucket's persisted ledger lines and the
Modelo 369 registry binding resolver. It accepts a sequence of
substrate-classified ledger candidates, validates each line's persisted
IVA amount against the destination Member State's published rate
through :func:`aeat.domain.iva.lookup_rate`, and produces validated
:class:`~aeat.domain.calculations.registry.OssIossLedgerObservation` records the registry can aggregate.

Per the OSS / IOSS regulation suite, the IVA amount on each line MUST
match the destination Member State's published rate for the chosen
rate tier on the supply date. A persisted IVA amount that disagrees
with the lookup is a data-quality blocker: the wrapper rejects it
before the registry resolver sees it, so calculation revisions never
land on inconsistent ledger facts.

The wrapper does not own classification, persistence, or event
emission; those concerns live in the modelo calculation orchestrator
the wrapper feeds.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from ...domain.calculations.registry import (
    ModeloRevision,
    OssIossLedgerObservation,
    resolve_ledger_oss_aggregation_binding_values,
)
from ...domain.iva import (
    EUMemberState,
    InvoiceKind,
    IvaRateKind,
    OssIossRegime,
    TransactionKind,
    lookup_rate,
)
from ._errors import AggregationValidationError, t
from ._source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)

_LedgerId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]


class OssIossLedgerCandidate(BaseModel):
    """One un-validated ledger line tagged with substrate classification.

    The candidate is the application-layer hand-off shape: a ledger
    line carrying the four classification axes the Modelo 369 binding
    selectors require, plus the base and IVA amounts the bucket
    persists. The :func:`validate_oss_ioss_observation` function
    turns a candidate into a registry-ready
    :class:`OssIossLedgerObservation` once the persisted IVA amount
    has been checked against the destination MS rate.

    Attributes:
        ledger_id: Stable id of the source ledger line.
        transaction_date: When the supply takes place. Drives the rate
            lookup.
        regime: OSS / IOSS Esquema the line is filed under.
        destination_member_state: Member State of consumption per the
            OSS / IOSS place-of-supply rules.
        rate_kind: Substrate rate tier (general / reduced / etc.).
        invoice_direction: Whether the autónomo issued or received the
            invoice.
        transaction_kind: Substrate
            :class:`aeat.domain.iva.TransactionKind` the line resolves
            to.
        base_amount: Taxable base in EUR. Must be non-negative.
        iva_amount: IVA amount in EUR persisted on the ledger. Must
            be non-negative.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    ledger_id: _LedgerId
    transaction_date: date
    regime: OssIossRegime
    destination_member_state: EUMemberState
    rate_kind: IvaRateKind
    invoice_direction: InvoiceKind
    transaction_kind: TransactionKind
    base_amount: Decimal = Field(ge=Decimal("0"))
    iva_amount: Decimal = Field(ge=Decimal("0"))


#: Tolerance applied when comparing a persisted IVA amount against the
#: amount derived from ``base_amount * lookup_rate(...) / 100``.
#:
#: Ledger amounts are rounded to two decimal places at persistence
#: time; a difference of one cent or less is treated as rounding
#: noise, not as a data-quality blocker. Larger gaps fail the
#: validation and the line is rejected before the registry resolver
#: aggregates it.
_IVA_TOLERANCE: Decimal = Decimal("0.01")


def _expected_iva_amount(candidate: OssIossLedgerCandidate) -> Decimal:
    """Return the IVA amount derived from the candidate's base and rate.

    Looks up the destination Member State's rate for the candidate's
    rate tier on the supply date, multiplies by ``base_amount``, and
    rounds to two decimal places — the precision at which ledger
    amounts are persisted.

    Args:
        candidate: The substrate-classified ledger line whose base amount
            and rate kind are used to derive the expected IVA amount.

    Returns:
        The expected IVA amount rounded to two decimal places.
    """
    rate = lookup_rate(
        candidate.destination_member_state,
        candidate.rate_kind,
        candidate.transaction_date,
    )
    derived = candidate.base_amount * rate.pct / Decimal("100")
    return derived.quantize(Decimal("0.01"))


def validate_oss_ioss_observation(
    candidate: OssIossLedgerCandidate,
) -> OssIossLedgerObservation:
    """Validate ``candidate`` and return the registry-ready observation.

    Looks up the destination Member State's rate at the supply date,
    derives the expected IVA amount from ``base_amount`` and the
    looked-up rate, and rejects the candidate if the persisted
    ``iva_amount`` deviates from the derived value by more than
    :data:`_IVA_TOLERANCE` (one cent).

    Args:
        candidate: The substrate-classified ledger line to validate.

    Returns:
        A registry-ready :class:`OssIossLedgerObservation` carrying
        the same identifier, supply date, classification axes, base
        amount, and persisted IVA amount as the candidate.

    Raises:
        AggregationValidationError: When the persisted IVA amount
            disagrees with the destination MS rate by more than the
            one-cent tolerance.
    """
    expected = _expected_iva_amount(candidate)
    persisted = candidate.iva_amount.quantize(Decimal("0.01"))
    if abs(persisted - expected) > _IVA_TOLERANCE:
        raise AggregationValidationError(
            t("oss_ioss_iva_amount_mismatches_destination_rate"),
            context={
                "ledger_id": candidate.ledger_id,
                "destination_member_state": candidate.destination_member_state.value,
                "rate_kind": candidate.rate_kind.value,
                "transaction_date": candidate.transaction_date.isoformat(),
                "base_amount": str(candidate.base_amount),
                "persisted_iva_amount": str(persisted),
                "expected_iva_amount": str(expected),
            },
        )
    return OssIossLedgerObservation(
        ledger_id=candidate.ledger_id,
        transaction_date=candidate.transaction_date,
        regime=candidate.regime,
        destination_member_state=candidate.destination_member_state,
        rate_kind=candidate.rate_kind,
        invoice_direction=candidate.invoice_direction,
        transaction_kind=candidate.transaction_kind,
        base_amount=candidate.base_amount,
        iva_amount=candidate.iva_amount,
    )


def validate_oss_ioss_observations(
    candidates: Iterable[OssIossLedgerCandidate],
) -> tuple[OssIossLedgerObservation, ...]:
    """Validate every candidate; raise on the first failure.

    Args:
        candidates: The substrate-classified ledger lines to validate.

    Returns:
        A tuple of registry-ready
        :class:`OssIossLedgerObservation` records in input order.
    """
    return tuple(validate_oss_ioss_observation(candidate) for candidate in candidates)


def aggregate_oss_ioss_bindings(
    revision: ModeloRevision,
    candidates: Sequence[OssIossLedgerCandidate],
) -> dict[str, Decimal]:
    """Validate candidates then resolve every ``ledger_oss_aggregation`` binding.

    Pipeline:

    1. Each candidate is validated through
       :func:`validate_oss_ioss_observation`, which checks the
       persisted IVA against the destination MS rate.
    2. The validated observations are handed off to the registry's
       :func:`resolve_ledger_oss_aggregation_binding_values`
       resolver, which filters by every binding's selector and
       aggregates the matched lines.

    Args:
        revision: The Modelo 369 :class:`ModeloRevision` whose
            ``ledger_oss_aggregation`` bindings should be resolved.
        candidates: Substrate-classified ledger lines for the period.

    Returns:
        A mapping from each binding id on the revision to its
        aggregated Decimal value.
    """
    observations = validate_oss_ioss_observations(candidates)
    return resolve_ledger_oss_aggregation_binding_values(revision, observations)


class OssIossLedgerSourceResolver:
    """Source mesh resolver for Modelo 369 OSS / IOSS ledger candidates."""

    resolver_id = "ledger_oss_aggregation"
    owned_sources = ("ledger_oss_aggregation",)

    def __init__(self, *, candidates: Sequence[OssIossLedgerCandidate]) -> None:
        """Construct the resolver with a pre-classified ledger candidate sequence.

        Args:
            candidates: The substrate-classified ledger lines for the
                current period. The resolver validates and aggregates
                these on each :meth:`resolve` call.
        """
        self._candidates = tuple(candidates)

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Validate candidates and return the resolved OSS/IOSS binding values.

        Validates every candidate through :func:`validate_oss_ioss_observation`
        then delegates to the registry's
        ``resolve_ledger_oss_aggregation_binding_values`` to aggregate the
        matched lines per binding selector.

        When the resolver is constructed with **no candidates** (the live
        operator calculate path always passes ``candidates=()`` — there is no
        bucket-substrate projection that can populate an
        :class:`OssIossLedgerCandidate`, because neither the invoice nor the
        transaction model carries the OSS ``regime`` or goods/services
        ``transaction_kind`` axis the binding selectors require), the resolver
        still CLAIMS ``ledger_oss_aggregation`` (so the binding compiles and is
        not flagged as a novel source) but surfaces one non-blocking
        ``oss_no_live_source`` advisory per declared OSS binding. This keeps a
        Modelo 369 OSS cuota from resolving to a SILENT claimed-zero: an
        operator with OSS sales is explicitly told the OSS cuotas are not
        auto-computed from the bucket and must be supplied manually
        (no-silent-under-declaration; parity with the deferred-detalle-kinds
        advisory). Pre-classified callers (the Sheets calc-sync caller) pass
        candidates and fold them normally with no advisory.

        Args:
            context: The :class:`CalculationSourceContext` carrying the
                ``ModeloRevision`` whose ``ledger_oss_aggregation`` bindings
                should be resolved.

        Returns:
            A :class:`CalculationSourceResolution` with resolved
            binding values, source transaction ids, and per-observation
            provenance records — or, when no candidates were supplied, an
            empty resolution carrying one ``oss_no_live_source`` advisory per
            declared OSS binding.

        Raises:
            AggregationValidationError: When any candidate's persisted IVA
                amount disagrees with the destination Member State rate by
                more than one cent.
        """
        if not self._candidates:
            return CalculationSourceResolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                diagnostics=self._no_live_source_diagnostics(context),
            )
        observations = validate_oss_ioss_observations(self._candidates)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=resolve_ledger_oss_aggregation_binding_values(context.revision, observations),
            source_transaction_ids=tuple(sorted(observation.ledger_id for observation in observations)),
            provenance=tuple(
                CalculationSourceProvenance(
                    source_kind="ledger_oss_aggregation",
                    source_ref=f"transaction:{observation.ledger_id}",
                )
                for observation in observations
            ),
        )

    def _no_live_source_diagnostics(self, context: CalculationSourceContext) -> tuple[CalculationSourceDiagnostic, ...]:
        """Return one ``oss_no_live_source`` advisory per OSS binding on the revision.

        Surfaced only when the resolver was constructed with no candidates and
        the revision actually declares ``ledger_oss_aggregation`` bindings, so
        a modelo with no OSS bindings produces no spurious advisory.
        """
        return tuple(
            CalculationSourceDiagnostic(
                reason="oss_no_live_source",
                source_kind="ledger_oss_aggregation",
                resolver_id=self.resolver_id,
                binding_id=binding.id,
                message=(
                    f"binding {binding.id!r} declares source 'ledger_oss_aggregation' but no "
                    "bucket substrate can be projected into an OSS/IOSS ledger candidate "
                    "(neither the invoice nor the transaction model carries the OSS regime or "
                    "goods/services transaction-kind axis the selector requires); the OSS cuota "
                    "is NOT auto-computed and must be supplied manually"
                ),
            )
            for binding in context.revision.bindings
            if str(binding.source) == "ledger_oss_aggregation"
        )


__all__ = [
    "OssIossLedgerCandidate",
    "OssIossLedgerSourceResolver",
    "aggregate_oss_ioss_bindings",
    "validate_oss_ioss_observation",
    "validate_oss_ioss_observations",
]
