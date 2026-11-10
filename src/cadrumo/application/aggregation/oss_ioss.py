"""Modelo 369 OSS/IOSS source-mesh resolver and candidate validator.

The ``ledger_oss_aggregation`` source reads OSS/IOSS-tagged issued invoices
through the required application-owned catalogue-read capability and projects
them into substrate-classified :class:`OssIossLedgerCandidate`
rows. Pre-classified callers can also pass candidates directly. Each candidate
is validated against the destination Member State's published IVA rate through
:func:`domain.iva.lookup.lookup_rate` and becomes a registry-ready
:class:`~domain.calculations.registry.ledger_oss_bindings.OssIossLedgerObservation`.

Per the OSS / IOSS regulation suite, the IVA amount on each line MUST
match a rate the destination Member State applies in the chosen tier on the
supply date. A tier can hold more than one (France's reduced 5.5 and 10), and the
cuota says which. A persisted IVA amount no rate explains is a data-quality
blocker, rejected before the registry resolver sees it. On a date the rate table
has no edition for, a figure matching the nearest edition is accepted with a
warning, and a differing one is a coverage gap rather than a mismatch.

A factura rectificativa is made when it is issued. Issued in the period of the invoice
it names, it takes its lines off that invoice's row at that invoice's rate. Issued
later, it is a row of DR369's corrections section on the return of the period it was
issued in, naming the destination and the earlier period, because Orden HAC/610/2021
art. 7.5 forbids modifying a filed return. The invoice record states magnitudes with no
direction, so a rectificativa is always a reduction; a pre-classified candidate or a row
the operator enters can raise a period as well.

The :class:`OssIossLedgerSourceResolver` returns a
:class:`~.source_mesh.CalculationSourceResolution` with resolved binding values,
transaction provenance, and non-blocking diagnostics for empty live catalogues or
declarable OSS observations that no detail table of the revision can take.
"""

from __future__ import annotations

from calendar import monthrange
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated, NamedTuple

from pydantic import BaseModel, Field, StringConstraints

from ...core.aggregation import BindingSourceKind, InvoiceDevengoRank
from ...core.i18n.translatable import Translatable as tr
from ...core.identity.bucket import BucketId
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.money.rounding import CENT, round_to_cents
from ...core.period import Period, PeriodError, PeriodKind, quarter_code
from ...domain.calculations.record_row_membership import ClosedRecordRowSet, RecordRowMembership
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.ledger_oss_bindings import (
    OssIossLedgerObservation,
    OssLineEffect,
    resolve_ledger_oss_aggregation_binding_values,
)
from ...domain.calculations.registry.manual_input_selector import ManualInputProvider
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.invoices.models import Invoice
from ...domain.iva.classification import TransactionKind, require_transaction_kind
from ...domain.iva.errors import IvaRateNotFoundError
from ...domain.iva.lookup import coexisting_tier_rates, lookup_published_rate, lookup_rate, tier_rates_within
from ...domain.iva.oss import OssIossRegime, require_oss_ioss_regime, resolve_oss_ioss_regime_catalogue
from ...domain.iva.schema import EUMemberState, InvoiceKind, IvaRateKind, IvaRateRecord
from .errors import AggregationValidationError
from .invoice_devengo import (
    resolve_invoice_devengo,
)
from .oss_ioss_wire_geometry import ROW_SHAPES, record_row_slots, require_slot_coverage, require_wire_geometry
from .source_mesh import (
    CalculationSourceContext,
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
            :class:`domain.iva.classification.TransactionKind` the line resolves
            to.
        base_amount: Taxable base in EUR. Must be non-negative.
        iva_amount: IVA amount in EUR persisted on the ledger. Must
            be non-negative.
        effect: Whether the amounts add a supply or take a correction off one.
        corrected_period: The earlier period the amounts adjust, or ``None`` for the
            period being filed.
    """

    model_config = STRICT_FROZEN_CONFIG

    ledger_id: _LedgerId
    transaction_date: date
    regime: OssIossRegime
    destination_member_state: EUMemberState
    rate_kind: IvaRateKind
    invoice_direction: InvoiceKind
    transaction_kind: TransactionKind
    base_amount: Decimal = Field(ge=Decimal("0"))
    iva_amount: Decimal = Field(ge=Decimal("0"))
    effect: OssLineEffect = OssLineEffect.SUPPLY
    corrected_period: Period | None = None


def _cuota_at(base: Decimal, rate: IvaRateRecord) -> Decimal:
    return round_to_cents(base * rate.pct / Decimal("100"))


def _ordinary_rate(
    member_state: EUMemberState, rate_kind: IvaRateKind, on_date: date, *, operation: PinnedAuthorityOperation
) -> IvaRateRecord:
    """Return the ordinary rate of the tier, refusing a tier the Member State never had."""
    try:
        return lookup_rate(member_state, rate_kind, on_date, operation=operation)
    except IvaRateNotFoundError as exc:
        # The table answers every date of a tier a state has, so this state never had the tier.
        raise AggregationValidationError(
            tr("aggregation.oss_ioss.errors.rate_tier_absent"),
            context={
                "destination_member_state": member_state.value,
                "rate_kind": rate_kind.value,
                "transaction_date": on_date.isoformat(),
            },
        ) from exc


def _closest_rates(rates: Sequence[IvaRateRecord], base: Decimal, persisted: Decimal) -> list[IvaRateRecord]:
    """Return the rates giving exactly the persisted cuota, else those within a cent of it."""
    exact = [rate for rate in rates if _cuota_at(base, rate) == persisted]
    return exact or [rate for rate in rates if abs(_cuota_at(base, rate) - persisted) <= CENT]


def _applied_rate(
    member_state: EUMemberState,
    rate_kind: IvaRateKind,
    on_date: date,
    *,
    base: Decimal,
    iva: Decimal,
    operation: PinnedAuthorityOperation,
) -> IvaRateRecord | None:
    """Return the rate of the tier that explains the cuota, or ``None`` when none does.

    A tier's rates are its ordinary one and those coexisting with it, and the cuota tells
    them apart. The closest reading wins; two rates giving the same cuota leave the row's
    percentage unknown, so that refuses, as does a tier the Member State never had.
    A nil line says nothing and reads the ordinary rate.
    """
    ordinary = _ordinary_rate(member_state, rate_kind, on_date, operation=operation)
    persisted = round_to_cents(iva)
    if base == Decimal("0") and persisted == Decimal("0"):
        return ordinary
    rates = (ordinary, *coexisting_tier_rates(member_state, rate_kind, on_date, operation=operation))
    near = _closest_rates(rates, base, persisted)
    if len(near) > 1:
        raise AggregationValidationError(
            tr("aggregation.oss_ioss.errors.rate_tier_ambiguous"),
            context={
                "destination_member_state": member_state.value,
                "rate_kind": rate_kind.value,
                "transaction_date": on_date.isoformat(),
                "rates": ",".join(str(rate.pct) for rate in near),
            },
        )
    return near[0] if near else None


def validate_oss_ioss_observation(
    candidate: OssIossLedgerCandidate,
    *,
    operation: PinnedAuthorityOperation | None = None,
) -> OssIossLedgerObservation:
    """Validate ``candidate`` and return the registry-ready observation.

    Looks up the destination Member State's rates at the supply date
    and rejects the candidate if the persisted ``iva_amount`` deviates by
    more than ``CENT`` from what every one of them derives from
    ``base_amount``. On a date with no edition, a figure the nearest edition
    explains passes and any other raises the coverage gap.

    Args:
        candidate: The substrate-classified ledger line to validate.
        operation: Existing generation-pinned authority operation. When omitted,
            one indexed operation is opened at this composition boundary.

    Returns:
        A registry-ready :class:`OssIossLedgerObservation` carrying
        the same identifier, supply date, classification axes, base
        amount, and persisted IVA amount as the candidate.

    Raises:
        AggregationValidationError: When the persisted IVA amount
            disagrees with the destination MS rate by more than the
            one-cent tolerance.
        IvaRateNotFoundError: When it differs from a rate the table only projects.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return validate_oss_ioss_observation(candidate, operation=indexed_operation)
    regime = require_oss_ioss_regime(
        candidate.regime,
        effective_date=candidate.transaction_date,
        authority=operation,
    )
    transaction_kind = require_transaction_kind(
        candidate.transaction_kind,
        effective_date=candidate.transaction_date,
        operation=operation,
    )
    catalogue = resolve_oss_ioss_regime_catalogue(
        effective_date=candidate.transaction_date,
        authority=operation,
    )
    if transaction_kind.value not in catalogue.transaction_kinds_for(regime):
        raise AggregationValidationError(
            tr("aggregation.oss_ioss.errors.invoice_line_rate_kind_unclassifiable"),
        )
    # Ledger amounts are rounded to two decimal places at persistence time, so a
    # difference of one cent or less is rounding noise rather than a data-quality
    # blocker. Larger gaps fail validation and the line is rejected before the
    # registry resolver aggregates it. The quantum is CENT because it is the same
    # cent the rounding produced, not a threshold this module chose.
    if (
        _applied_rate(
            candidate.destination_member_state,
            candidate.rate_kind,
            candidate.transaction_date,
            base=candidate.base_amount,
            iva=candidate.iva_amount,
            operation=operation,
        )
        is None
    ):
        ordinary = lookup_rate(
            candidate.destination_member_state,
            candidate.rate_kind,
            candidate.transaction_date,
            operation=operation,
        )
        if not ordinary.published_on_date:
            # Raises: the table cannot refute a figure on a rate it only projects.
            lookup_published_rate(
                candidate.destination_member_state,
                candidate.rate_kind,
                candidate.transaction_date,
                operation=operation,
            )
        persisted = round_to_cents(candidate.iva_amount)
        expected = _cuota_at(candidate.base_amount, ordinary)
        raise AggregationValidationError(
            tr("aggregation.oss_ioss.errors.iva_amount_mismatches_destination_rate"),
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
        effect=candidate.effect,
        corrected_period=candidate.corrected_period,
    )


def _refuse_consignments_over_ceiling(
    observations: Sequence[OssIossLedgerObservation],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Refuse a consignment whose value is above its regime's published intrinsic-value ceiling.

    One invoice is read as one consignment, the unit the law limits, so its lines
    are summed; the line identifier carries the invoice as its leading segment.
    The base includes any shipping the invoice charged in its lines, which can
    refuse a consignment the law admits but never admits one it excludes.
    """
    consignments: dict[tuple[str, str], Decimal] = {}
    dated: dict[tuple[str, str], date] = {}
    for observation in observations:
        key = (observation.regime, observation.ledger_id.split(":", 1)[0])
        consignments[key] = consignments.get(key, Decimal("0")) + observation.base_amount
        dated[key] = observation.transaction_date
    for key, value in consignments.items():
        regime, invoice_id = key
        catalogue = resolve_oss_ioss_regime_catalogue(effective_date=dated[key], authority=operation)
        ceiling = catalogue.definition(regime).intrinsic_value_ceiling_eur
        if ceiling is not None and value > Decimal(ceiling):
            raise AggregationValidationError(
                tr("aggregation.oss_ioss.errors.consignment_exceeds_ceiling"),
                context={
                    "invoice_id": invoice_id,
                    "regime": regime,
                    "consignment_value_eur": str(value),
                    "intrinsic_value_ceiling_eur": ceiling,
                },
            )


def validate_oss_ioss_observations(
    candidates: Iterable[OssIossLedgerCandidate],
    *,
    operation: PinnedAuthorityOperation | None = None,
) -> tuple[OssIossLedgerObservation, ...]:
    """Validate every candidate; raise on the first failure.

    Args:
        candidates: The substrate-classified ledger lines to validate.
        operation: Existing generation-pinned authority operation. When omitted,
            one indexed operation is opened at this composition boundary.

    Returns:
        A tuple of registry-ready
        :class:`OssIossLedgerObservation` records in input order.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return validate_oss_ioss_observations(candidates, operation=indexed_operation)
    observations = tuple(validate_oss_ioss_observation(candidate, operation=operation) for candidate in candidates)
    _refuse_consignments_over_ceiling(observations, operation=operation)
    return observations


def aggregate_oss_ioss_bindings(
    revision: ModeloRevision,
    candidates: Sequence[OssIossLedgerCandidate],
    *,
    operation: PinnedAuthorityOperation | None = None,
) -> dict[BindingId, Decimal]:
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
        operation: Existing generation-pinned authority operation. When omitted,
            one indexed operation is opened at this composition boundary.

    Returns:
        A mapping from each binding id on the revision to its
        aggregated Decimal value.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return aggregate_oss_ioss_bindings(revision, candidates, operation=indexed_operation)
    observations = validate_oss_ioss_observations(candidates, operation=operation)
    return resolve_ledger_oss_aggregation_binding_values(
        revision, observations_at_row_level(observations, operation=operation)
    )


def row_level_binding_values(
    revision: ModeloRevision,
    observations: Iterable[OssIossLedgerObservation],
) -> dict[BindingId, Decimal]:
    """Resolve the ledger OSS aggregation bindings of ``revision`` from row-level observations.

    ``revision`` is the :class:`ModeloRevision`, the registry revision a modelo is calculated against.
    """
    return resolve_ledger_oss_aggregation_binding_values(revision, observations)


def observations_at_row_level(
    observations: Sequence[OssIossLedgerObservation],
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[OssIossLedgerObservation, ...]:
    """Fold the lines of each state, rate and kind into the one figure the return declares.

    LIVA arts. 163 noniesdecies, duovicies and septvicies ask for the total value and the
    "cantidad global" per state of consumption and rate, and convert at one rate for the
    period. No bundled source says at which level cents are taken, or states the cuota's
    relation to its base, so the base is rounded on the row and the cuota is that base at the
    row's rate: the only reading that keeps a declared cuota equal to its base times its rate.
    """
    grouped: dict[
        tuple[str, EUMemberState, IvaRateKind, InvoiceKind, TransactionKind, Period | None, Decimal],
        list[OssIossLedgerObservation],
    ] = {}
    for observation in observations:
        applied = _applied_rate(
            observation.destination_member_state,
            observation.rate_kind,
            observation.transaction_date,
            base=observation.base_amount,
            iva=observation.iva_amount,
            operation=operation,
        )
        if applied is None:
            raise AggregationValidationError(tr("aggregation.oss_ioss.errors.iva_amount_mismatches_destination_rate"))
        key = (
            observation.regime,
            observation.destination_member_state,
            observation.rate_kind,
            observation.invoice_direction,
            observation.transaction_kind,
            # A correction of an earlier period answers on that period's row, never this one's.
            observation.corrected_period,
            applied.pct,
        )
        grouped.setdefault(key, []).append(observation)
    settled: list[OssIossLedgerObservation] = []
    for key, members in grouped.items():
        net = sum((member.signed_base_amount for member in members), Decimal("0"))
        base = round_to_cents(abs(net))
        corrected = any(member.effect is OssLineEffect.CORRECTION for member in members)
        settled.append(
            members[0].model_copy(
                update={
                    "base_amount": base,
                    "iva_amount": round_to_cents(base * key[-1] / Decimal("100")),
                    "effect": OssLineEffect.CORRECTION if net < 0 or (corrected and net == 0) else OssLineEffect.SUPPLY,
                }
            )
        )
    return tuple(settled)


def detail_binding_values(
    revision: ModeloRevision,
    observations: Sequence[OssIossLedgerObservation],
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[dict[BindingId, Decimal], dict[BindingId, str]]:
    """Project the rows of the revision's detail tables from validated observations.

    Which table takes an observation is a dated declaration keyed by its
    transaction kind, and the table's slots come from the revision's own wire
    geometry, so every regime goes through this one path. One row is one
    destination and applied rate; repeated lines at that rate are summed.

    ``revision`` is the :class:`ModeloRevision`, the registry revision a modelo is calculated against.
    """
    decimal_values: dict[BindingId, Decimal] = {}
    enum_values: dict[BindingId, str] = {}
    # Each line answers for its own placement first: a folded row cannot name the line a refusal is about.
    _group_detail_observations(revision, observations, operation=operation)
    at_row_level = observations_at_row_level(observations, operation=operation)
    for record_id, all_rows in _group_detail_observations(revision, at_row_level, operation=operation).items():
        slots = record_row_slots(revision, record_id)
        grouped = _rows_left_by_corrections(all_rows)
        if len(grouped) > len(slots):
            # The design's continuation page has no slots here: the settlement
            # formulas read these slots alone. Refuse rather than export a prefix.
            raise AggregationValidationError(
                tr("aggregation.oss_ioss.errors.detail_rows_exceed_page"),
                context={"record": record_id, "rows": str(len(grouped)), "capacity": str(len(slots))},
            )
        for slot, (key, rows) in zip(slots, sorted(grouped.items(), key=lambda item: item[0]), strict=False):
            _assign_detail_row(slot, key, rows, decimal_values, enum_values)
    return decimal_values, enum_values


_MODELO_369_PROJECTION_FACT_ID = "modelo-369-exterior-oss-projection-catalogue"
_PROJECTED_ROW_COLUMNS = len(ROW_SHAPES[0])
_CORRECTION_ROW_COLUMNS = len(ROW_SHAPES[2])
_QUARTER_PERIOD_TYPE = "T"
_MONTH_PERIOD_TYPE = "M"


def _rows_left_by_corrections(
    rows: dict[_DetailRowKey, list[OssIossLedgerObservation]],
) -> dict[_DetailRowKey, list[OssIossLedgerObservation]]:
    """Drop a row its corrections cancel, and refuse one they take below nothing."""
    left: dict[_DetailRowKey, list[OssIossLedgerObservation]] = {}
    for key, observations in rows.items():
        base = sum((item.signed_base_amount for item in observations), Decimal("0"))
        cuota = sum((item.signed_iva_amount for item in observations), Decimal("0"))
        if base < Decimal("0") or cuota < Decimal("0"):
            raise AggregationValidationError(
                tr("aggregation.oss_ioss.errors.rectificativa_above_row"),
                context={
                    "destination_member_state": key.member_state.value,
                    "rate": str(key.rate),
                    "net_base": str(base),
                    "net_cuota": str(cuota),
                },
            )
        corrected = any(item.effect is OssLineEffect.CORRECTION for item in observations)
        if not (corrected and base == Decimal("0") and cuota == Decimal("0")):
            left[key] = observations
    return left


def _projection_declarations(
    effective_date: date,
    *,
    operation: PinnedAuthorityOperation,
) -> dict[str, str]:
    """Resolve the dated Modelo 369 rate-code, country-code and section catalogue."""
    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_MODELO_369_PROJECTION_FACT_ID,
            date_axis=DateAxis.TRANSACTION_DATE,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise AggregationValidationError(
            tr("aggregation.oss_ioss.errors.invoice_line_rate_kind_unclassifiable"),
        )
    declarations = {
        entry.key: entry.value
        for entry in resolved.payload.entries
        if isinstance(entry.key, str) and isinstance(entry.value, str)
    }
    required = {"rate_code.general", "rate_code.reduced", "detail_row.capacity"}
    missing = sorted(required - declarations.keys())
    if missing:
        raise AggregationValidationError(
            tr("aggregation.oss_ioss.errors.invoice_line_rate_kind_unclassifiable"),
            context={"missing": ",".join(missing)},
        )
    return declarations


class _DetailRowKey(NamedTuple):
    """What makes two lines of one detail table one row of the return.

    The percentage is part of the key because LIVA art. 90.Dos takes each
    operation's rate at its own devengo and arts. 163 noniesdecies.Uno.c),
    duovicies.Uno.c) and septvicies.c) require the tax per Member State
    "desglosado por tipos impositivos". The rate tier alone cannot do this: a
    Member State can change a tier's percentage inside a period. The wire codes
    are dated declarations, so they are part of it too.
    """

    member_state: EUMemberState
    rate_kind: IvaRateKind
    rate: Decimal
    country_code: str
    rate_code: str


def _revision_records(revision: ModeloRevision) -> frozenset[str]:
    return frozenset(
        binding.provider.record
        for binding in revision.bindings
        if isinstance(binding.provider, ManualInputProvider) and binding.provider.record is not None
    )


def _detail_record_for(
    observation: OssIossLedgerObservation,
    revision: ModeloRevision,
    *,
    operation: PinnedAuthorityOperation,
) -> str | None:
    """Return this revision's table for the observation, or ``None`` when it has none.

    A kind no section declares is one this module cannot place: Union goods go to
    T36905 or T36907 by the state of dispatch, which an invoice does not record.
    A correction's table belongs to its regime, since it names no kind of operation.
    """
    declarations = _projection_declarations(observation.transaction_date, operation=operation)
    record_id = (
        declarations.get(f"section.{observation.transaction_kind.value}.record")
        if observation.corrected_period is None
        else declarations.get(f"correction_records.{observation.regime.value}")
    )
    return record_id if record_id in _revision_records(revision) else None


def _wire_country_code(observation: OssIossLedgerObservation, declarations: Mapping[str, str]) -> str:
    """Return the destination's wire code, refusing a state this kind of operation cannot be consumed in."""
    member_state = observation.destination_member_state
    excluded = declarations.get(f"section.{observation.transaction_kind.value}.excluded_consumption_states", "")
    if member_state.value in excluded.split(","):
        raise AggregationValidationError(
            tr("aggregation.oss_ioss.errors.detail_consumption_state_excluded"),
            context={
                "ledger_id": observation.ledger_id,
                "destination_member_state": member_state.value,
                "transaction_kind": observation.transaction_kind.value,
            },
        )
    # The design writes ISO-3166 alpha-2 codes with its own exceptions ("EL" for
    # Greece, "XI" for Northern Ireland), so the wire code is the dated
    # declaration's, never the member-state token itself.
    country_code = declarations.get(f"country_code.{member_state.value}")
    if country_code is None:
        raise AggregationValidationError(
            tr("aggregation.oss_ioss.errors.detail_country_code_undeclared"),
            context={"member_state": member_state.value},
        )
    return country_code


def _detail_row_key(
    observation: OssIossLedgerObservation,
    *,
    operation: PinnedAuthorityOperation,
) -> _DetailRowKey:
    """Resolve an observation's row from the rate and wire codes on its own date."""
    declarations = _projection_declarations(observation.transaction_date, operation=operation)
    rate_code = declarations.get(f"rate_code.{observation.rate_kind.value}")
    if rate_code is None:
        # DR369 lets a row say only "R" or "S", and neither names this tier.
        raise AggregationValidationError(
            tr("aggregation.oss_ioss.errors.detail_rate_kind_unsupported"),
            context={
                "ledger_id": observation.ledger_id,
                "rate_kind": observation.rate_kind.value,
            },
        )
    member_state = observation.destination_member_state
    country_code = _wire_country_code(observation, declarations)
    applied = _applied_rate(
        member_state,
        observation.rate_kind,
        observation.transaction_date,
        base=observation.base_amount,
        iva=observation.iva_amount,
        operation=operation,
    )
    if applied is None:
        raise AggregationValidationError(tr("aggregation.oss_ioss.errors.iva_amount_mismatches_destination_rate"))
    return _DetailRowKey(member_state, observation.rate_kind, applied.pct, country_code, rate_code)


def _group_detail_observations(
    revision: ModeloRevision,
    observations: Sequence[OssIossLedgerObservation],
    *,
    operation: PinnedAuthorityOperation,
) -> dict[str, dict[_DetailRowKey, list[OssIossLedgerObservation]]]:
    """Group the observations this revision can place, by table and then by row."""
    grouped: dict[str, dict[_DetailRowKey, list[OssIossLedgerObservation]]] = {}
    for observation in observations:
        if observation.corrected_period is not None:
            continue
        record_id = _detail_record_for(observation, revision, operation=operation)
        if record_id is not None:
            rows = grouped.setdefault(record_id, {})
            rows.setdefault(_detail_row_key(observation, operation=operation), []).append(observation)
    return grouped


def observations_without_detail_row(
    revision: ModeloRevision,
    observations: Sequence[OssIossLedgerObservation],
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[OssIossLedgerObservation, ...]:
    """Return declarable observations no table of this revision can take.

    ``revision`` is the :class:`ModeloRevision`, the registry revision a modelo is calculated against.
    """
    return tuple(
        observation
        for observation in observations
        if (observation.base_amount != Decimal("0") or observation.iva_amount != Decimal("0"))
        and _detail_record_for(observation, revision, operation=operation) is None
    )


def _assign_detail_row(
    slot: tuple[BindingId, ...],
    key: _DetailRowKey,
    rows: Sequence[OssIossLedgerObservation],
    decimal_values: dict[BindingId, Decimal],
    enum_values: dict[BindingId, str],
) -> None:
    """Write one row into its slot, whose columns follow the design's line order."""
    if len(slot) != _PROJECTED_ROW_COLUMNS:
        raise AggregationValidationError(tr("aggregation.oss_ioss.errors.detail_not_representable"))
    country_code, rate, rate_code, base, cuota = slot
    enum_values[country_code] = key.country_code
    enum_values[rate_code] = key.rate_code
    decimal_values[rate] = key.rate
    decimal_values[base] = sum((item.signed_base_amount for item in rows), Decimal("0"))
    decimal_values[cuota] = sum((item.signed_iva_amount for item in rows), Decimal("0"))


def refuse_rate_chosen_by_issue_date(
    context: CalculationSourceContext,
    projection: OssIossInvoiceProjection,
    observations: Sequence[OssIossLedgerObservation],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Refuse a row whose rate would rest on an issue date standing in for the devengo.

    Elsewhere that substitution stays advisory because it only risks the period.
    Here it would also choose the percentage written on the row, so where the
    period has more than one rate for the tier the record cannot answer art.
    90.Dos. A period with one rate gives the same percentage on any of its days.
    """
    undated = {
        invoice.invoice_id: invoice
        for invoice in projection.contributing_invoices
        if resolve_invoice_devengo(invoice).rank is InvoiceDevengoRank.ISSUE_DATE_PROXY
    }
    if not undated:
        return
    span = projection_period(context.period)
    for observation in observations:
        # A correction row states no percentage, so no rate rests on its dates.
        if observation.corrected_period is not None:
            continue
        invoice = undated.get(observation.ledger_id.split(":", 1)[0])
        if invoice is None or _detail_record_for(observation, context.revision, operation=operation) is None:
            continue
        rates = tier_rates_within(
            observation.destination_member_state,
            observation.rate_kind,
            span.start_date,
            span.end_date,
            operation=operation,
        )
        if len(rates) > 1:
            raise AggregationValidationError(
                tr("aggregation.oss_ioss.errors.rate_change_devengo_undeclared"),
                context={
                    "invoice_id": invoice.invoice_id,
                    "invoice_number": invoice.invoice_number,
                    "destination_member_state": observation.destination_member_state.value,
                    "rate_kind": observation.rate_kind.value,
                    "period": context.period.registry_token,
                    "rates": ",".join(str(rate) for rate in rates),
                },
            )


def _closable_records(
    revision: ModeloRevision,
    effective_date: date,
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[str, ...]:
    """Return every detail table a complete read of this revision's invoices settles."""
    declarations = _projection_declarations(effective_date, operation=operation)
    records = _revision_records(revision)
    return tuple(
        record_id
        for key, value in declarations.items()
        if key.startswith("detail_records.")
        for record_id in value.split(",")
        if record_id in records
    )


def _correction_record(
    revision: ModeloRevision,
    effective_date: date,
    *,
    operation: PinnedAuthorityOperation,
) -> str | None:
    """Return the table of corrections this revision files, or ``None`` when it declares none."""
    records = _revision_records(revision)
    return next(
        (
            value
            for key, value in _projection_declarations(effective_date, operation=operation).items()
            if key.startswith("correction_records.") and value in records
        ),
        None,
    )


def _period_type(period: Period) -> str:
    return _QUARTER_PERIOD_TYPE if period.quarter_ordinal is not None else _MONTH_PERIOD_TYPE


def _wire_period(period: Period) -> str:
    """DR369's "Periodo" of a correction: alphanumeric, 1 .. 4 or 1 .. 12, without the header's zero."""
    return str(period.quarter_ordinal or period.start_date.month)


def period_holding(day: date, filed: Period) -> Period:
    """Return the period of the same length as ``filed`` that holds ``day``."""
    return Period.containing(day, PeriodKind.QUARTERLY if filed.quarter_ordinal is not None else PeriodKind.MONTHLY)


def _correction_limit(corrected: Period, years: int) -> date:
    """Return the last day a correction of ``corrected`` can be filed.

    Orden HAC/610/2021 art. 3 closes each return with the natural month after its
    period, and art. 7.5 counts three years from there.
    """
    months = corrected.end_date.year * 12 + corrected.end_date.month + years * 12
    year, month = months // 12, months % 12 + 1
    return date(year, month, monthrange(year, month)[1])


def _require_correctable(corrected: Period, filed: Period, *, years: int, context: dict[str, str]) -> None:
    """Refuse a period the return cannot correct: not earlier than it, or beyond the limit.

    The return can be filed from the day after its period, so the limit is met when
    that day is inside it. Art. 7.5 sends an older correction straight to the state
    of consumption, which is outside this return.
    """
    if corrected.end_date >= filed.start_date:
        raise AggregationValidationError(tr("aggregation.oss_ioss.errors.correction_row_invalid"), context=context)
    limit = _correction_limit(corrected, years)
    if filed.end_date + timedelta(days=1) > limit:
        raise AggregationValidationError(
            tr("aggregation.oss_ioss.errors.correction_beyond_limit"),
            context={**context, "limit": limit.isoformat()},
        )


def _caller_correction_slots(
    context: CalculationSourceContext,
    slots: tuple[tuple[BindingId, ...], ...],
    declarations: Mapping[str, str],
    filed: Period,
) -> frozenset[int]:
    """Check each section row the operator entered, and return the slots they hold."""
    numbers, texts = context.caller_binding_values, context.caller_enum_binding_values
    held: set[int] = set()
    country_codes = {value for key, value in declarations.items() if key.startswith("country_code.")}
    for index, row in enumerate(slots):
        given = [binding for binding in row if binding in numbers or binding in texts]
        if not given:
            continue
        held.add(index)
        details = {"row": str(index + 1)}
        if not _correction_row_is_complete(context, row, len(given), country_codes, filed):
            raise AggregationValidationError(tr("aggregation.oss_ioss.errors.correction_row_invalid"), context=details)
        corrected = _entered_corrected_period(context, row, filed, details)
        _require_correctable(corrected, filed, years=int(declarations["correction.limit_years"]), context=details)
    return frozenset(held)


def _correction_row_is_complete(
    context: CalculationSourceContext,
    row: tuple[BindingId, ...],
    given: int,
    country_codes: set[str],
    filed: Period,
) -> bool:
    """Whether the operator entered every column of a corrections row, each in its column's form."""
    numbers, texts = context.caller_binding_values, context.caller_enum_binding_values
    country, year, period_type, period, cuota = row
    return not (
        given != _CORRECTION_ROW_COLUMNS
        or texts.get(country) not in country_codes
        or texts.get(period_type) != _period_type(filed)
        or not str(texts.get(period, "")).isdecimal()
        or year not in numbers
        or cuota not in numbers
    )


def _entered_corrected_period(
    context: CalculationSourceContext, row: tuple[BindingId, ...], filed: Period, details: dict[str, str]
) -> Period:
    """Return the period an entered corrections row corrects, refusing one that is no period."""
    _, year, _, period, _ = row
    number = int(context.caller_enum_binding_values[period])
    try:
        code = quarter_code(number).value if _period_type(filed) == _QUARTER_PERIOD_TYPE else f"{number:02d}"
        return Period.from_year_and_code(int(context.caller_binding_values[year]), code)
    except (PeriodError, ValueError) as exc:
        raise AggregationValidationError(
            tr("aggregation.oss_ioss.errors.correction_row_invalid"), context=details
        ) from exc


def correction_binding_values(
    context: CalculationSourceContext,
    observations: Sequence[OssIossLedgerObservation],
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[dict[BindingId, Decimal], dict[BindingId, str]]:
    """Project the rows of the revision's corrections table.

    One row is one destination and corrected period, its cuota the net of what the
    lines do to that period: below zero for a reduction, above it for an increase. A
    net of nothing corrects nothing and takes no row. Slots the operator filled stay
    the operator's, and the projected rows take the others.
    """
    decimal_values: dict[BindingId, Decimal] = {}
    enum_values: dict[BindingId, str] = {}
    filed = projection_period(context.period)
    if not filed.has_date_span():
        return decimal_values, enum_values
    record_id = _correction_record(context.revision, filed.end_date, operation=operation)
    if record_id is None:
        return decimal_values, enum_values
    declarations = _projection_declarations(filed.end_date, operation=operation)
    slots = record_row_slots(context.revision, record_id)
    held = _caller_correction_slots(context, slots, declarations, filed)
    nets = _correction_nets(context, observations, record_id, declarations, filed, operation=operation)
    rows = sorted(item for item in nets.items() if item[1] != Decimal("0"))
    free = [slot for index, slot in enumerate(slots) if index not in held]
    if len(rows) > len(free):
        raise AggregationValidationError(
            tr("aggregation.oss_ioss.errors.detail_rows_exceed_page"),
            context={"record": record_id, "rows": str(len(rows)), "capacity": str(len(free))},
        )
    for slot, ((country_code, year, period_type, period), cuota) in zip(free, rows, strict=False):
        country, year_slot, period_type_slot, period_slot, cuota_slot = slot
        enum_values[country] = country_code
        decimal_values[year_slot] = Decimal(year)
        enum_values[period_type_slot] = period_type
        enum_values[period_slot] = period
        decimal_values[cuota_slot] = cuota
    return decimal_values, enum_values


def _correction_nets(
    context: CalculationSourceContext,
    observations: Sequence[OssIossLedgerObservation],
    record_id: str,
    declarations: Mapping[str, str],
    filed: Period,
    *,
    operation: PinnedAuthorityOperation,
) -> dict[tuple[str, int, str, str], Decimal]:
    """Return the net cuota the lines do to each destination and corrected period, refusing a late one."""
    nets: dict[tuple[str, int, str, str], Decimal] = {}
    for observation in observations:
        corrected = observation.corrected_period
        if corrected is None or _detail_record_for(observation, context.revision, operation=operation) != record_id:
            continue
        _require_correctable(
            corrected,
            filed,
            years=int(declarations["correction.limit_years"]),
            context={"ledger_id": observation.ledger_id, "corrected_period": corrected.registry_token},
        )
        key = (
            _wire_country_code(observation, declarations),
            corrected.start_date.year,
            _period_type(corrected),
            _wire_period(corrected),
        )
        nets[key] = nets.get(key, Decimal("0")) + observation.signed_iva_amount
    return nets


def _can_close_detail_rows(
    context: CalculationSourceContext, projection: OssIossInvoiceProjection, supplied_binding_ids: frozenset[BindingId]
) -> bool:
    return not (
        context.work_unit_id is None
        or projection.source_bucket_id != context.bucket_id
        or projection.catalogue_fingerprint is None
    )


def _layout_hydrated_revision(
    context: CalculationSourceContext, *, operation: PinnedAuthorityOperation
) -> ModeloRevision:
    """Return the context's revision carrying its export layouts."""
    if context.revision.export_layouts:
        return context.revision
    # Membership verification also uses the authority's lightweight revision
    # projection. Hydrate its wire geometry through the same pinned snapshot,
    # while requiring the binding declarations we already resolved to agree.
    revision = operation.snapshot(
        context.modelo,
        filing_year=context.filing_year,
        period=context.period.registry_token,
    ).revision
    if revision.id != context.revision.id or revision.bindings != context.revision.bindings:
        raise AggregationValidationError(tr("aggregation.oss_ioss.errors.detail_not_representable"))
    return revision


def closed_detail_record_rows(
    context: CalculationSourceContext,
    projection: OssIossInvoiceProjection,
    *,
    supplied_binding_ids: frozenset[BindingId],
    operation: PinnedAuthorityOperation,
) -> tuple[ClosedRecordRowSet, ...]:
    """Close this source's tables after a complete bound read placed every line.

    A Union table that takes goods or a foreign establishment closes empty here on
    the same read: any goods line stops the closure at its caller, and no invoice
    names an establishment other than the taxpayer's own.
    """
    if not _can_close_detail_rows(context, projection, supplied_binding_ids):
        return ()
    work_unit_id, fingerprint = context.work_unit_id, projection.catalogue_fingerprint
    if work_unit_id is None or fingerprint is None:
        return ()
    revision = _layout_hydrated_revision(context, operation=operation)
    effective_date = projection_period(context.period).end_date
    capacity = int(_projection_declarations(effective_date, operation=operation)["detail_row.capacity"])
    closed: list[ClosedRecordRowSet] = []
    covered: set[BindingId] = set()
    correction_record = _correction_record(revision, effective_date, operation=operation)
    corrections = () if correction_record is None else (correction_record,)
    # The operator's rows of the corrections table belong to the table's membership.
    entered = frozenset(context.caller_binding_values) | frozenset(context.caller_enum_binding_values)
    for record_id in (*_closable_records(revision, effective_date, operation=operation), *corrections):
        slots = _validated_record_slots(revision, record_id, capacity)
        occupying = supplied_binding_ids | entered if record_id in corrections else supplied_binding_ids
        require_slot_coverage(slots, occupying)
        covered.update(binding for row in slots for binding in row)
        closed.append(_closed_row_set(context, record_id, slots, occupying, work_unit_id, fingerprint, operation))
    if not supplied_binding_ids.issubset(covered):
        raise AggregationValidationError(tr("aggregation.oss_ioss.errors.detail_not_representable"))
    return tuple(closed)


def _validated_record_slots(
    revision: ModeloRevision, record_id: str, capacity: int
) -> tuple[tuple[BindingId, ...], ...]:
    """Return the record's row slots once they are the page's size and agree with the wire geometry."""
    slots = record_row_slots(revision, record_id)
    if len(slots) != capacity:
        raise AggregationValidationError(tr("aggregation.oss_ioss.errors.detail_not_representable"))
    require_wire_geometry(revision, record_id, slots)
    return slots


def _closed_row_set(
    context: CalculationSourceContext,
    record_id: str,
    slots: tuple[tuple[BindingId, ...], ...],
    occupying: frozenset[BindingId],
    work_unit_id: str,
    fingerprint: ContentDigest,
    operation: PinnedAuthorityOperation,
) -> ClosedRecordRowSet:
    """Close one record's table, marking the rows an occupying binding sits in."""
    return ClosedRecordRowSet(
        record_id=record_id,
        bucket_id=context.bucket_id,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=context.modelo,
            revision_id=context.revision.id,
            modelo_year=context.filing_year,
            period=context.period.registry_token,
        ),
        authority_generation=operation.pin().logical_generation,
        source_kind=BindingSourceKind.LEDGER_OSS_AGGREGATION,
        # The actual profile-local singleton catalogue, not a synthesized
        # aggregate pretending to be an independently persisted source.
        source_ref="invoice_catalogue:catalogue",
        source_fingerprint=fingerprint,
        rows=tuple(
            RecordRowMembership(
                row_index=index,
                binding_ids=row,
                occupied=bool(occupying.intersection(row)),
            )
            for index, row in enumerate(slots, start=1)
        ),
    )


class OssIossInvoiceProjection(BaseModel):
    """The Modelo 369 candidates for a period, beside the invoices they came from.

    The invoices ride along because the candidate cannot answer for its own
    provenance: it carries a resolved devengo date but not whether that date
    was declared or substituted, and the advisory the resolver owes the
    operator is about exactly that distinction.

    Attributes:
        candidates: The substrate-classified OSS/IOSS ledger lines.
        contributing_invoices: The invoices at least one candidate came from.
    """

    model_config = STRICT_FROZEN_CONFIG

    candidates: tuple[OssIossLedgerCandidate, ...] = ()
    contributing_invoices: tuple[Invoice, ...] = ()
    source_bucket_id: BucketId | None = Field(default=None, exclude=True, repr=False)
    catalogue_fingerprint: ContentDigest | None = Field(default=None, exclude=True, repr=False)


def projection_period(period: Period) -> Period:
    """Return the calendar period an Exterior token such as ``EXT-3T`` files."""
    if period.registry_token.startswith("EXT-"):
        return Period.from_year_and_code(
            period.filing_year,
            period.registry_token.removeprefix("EXT-"),
        )
    return period


__all__ = [
    "OssIossInvoiceProjection",
    "OssIossLedgerCandidate",
    "aggregate_oss_ioss_bindings",
    "closed_detail_record_rows",
    "correction_binding_values",
    "detail_binding_values",
    "observations_at_row_level",
    "observations_without_detail_row",
    "period_holding",
    "projection_period",
    "refuse_rate_chosen_by_issue_date",
    "row_level_binding_values",
    "validate_oss_ioss_observation",
    "validate_oss_ioss_observations",
]
