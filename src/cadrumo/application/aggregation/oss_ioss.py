"""Modelo 369 OSS/IOSS source-mesh resolver and candidate validator.

The ``ledger_oss_aggregation`` source reads OSS/IOSS-tagged issued invoices
through the required application-owned catalogue-read capability and projects
them into substrate-classified :class:`OssIossLedgerCandidate`
rows. Pre-classified callers can also pass candidates directly. Each candidate
is validated against the destination Member State's published IVA rate through
:func:`domain.iva.lookup.lookup_rate` and becomes a registry-ready
:class:`~domain.calculations.registry.ledger_oss_bindings.OssIossLedgerObservation`.

Per the OSS / IOSS regulation suite, the IVA amount on each line MUST
match the destination Member State's published rate for the chosen
rate tier on the supply date. A persisted IVA amount that disagrees
with the lookup is a data-quality blocker: the wrapper rejects it
before the registry resolver sees it, so calculation revisions never
land on inconsistent ledger facts.

The :class:`OssIossLedgerSourceResolver` returns a
:class:`~.source_mesh.CalculationSourceResolution` with resolved binding values,
transaction provenance, and non-blocking diagnostics for empty live catalogues or
declarable OSS observations that no detail table of the revision can take.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date
from decimal import Decimal
from typing import Annotated, ClassVar, NamedTuple

from pydantic import BaseModel, Field, StringConstraints

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole, InvoiceDevengoRank
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.hashing import content_hash_hex
from ...core.i18n.translatable import Translatable as tr
from ...core.identity.bucket import BucketId
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.money.rounding import CENT, round_to_cents
from ...core.period import Period
from ...domain.calculations.record_row_membership import ClosedRecordRowSet, RecordRowMembership
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.ledger_oss_bindings import (
    OssIossLedgerObservation,
    resolve_ledger_oss_aggregation_binding_values,
)
from ...domain.calculations.registry.manual_input_selector import ManualInputProvider
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.currency.errors import ExchangeRateProviderError
from ...domain.currency.models import EurRateLookupStatus
from ...domain.currency.service import published_eur_rate_on_day_or_next_publication
from ...domain.invoices.enums import iva_rate_kind
from ...domain.invoices.models import Invoice, InvoiceLine
from ...domain.iva.classification import TransactionKind, require_transaction_kind
from ...domain.iva.lookup import lookup_published_rate, lookup_rate, tier_rates_within
from ...domain.iva.oss import OssIossRegime, require_oss_ioss_regime, resolve_oss_ioss_regime_catalogue
from ...domain.iva.schema import EUMemberState, InvoiceKind, IvaRateKind
from ..exchange_rate_provider import exchange_rate_provider
from ..invoices.catalogue_reads_ports import (
    BucketBoundCatalogueReader,
    InvoiceCatalogueReadPersistenceError,
    InvoiceCatalogueReadPorts,
)
from .errors import AggregationValidationError
from .invoice_devengo import (
    devengo_proxy_attribution_diagnostics,
    invoice_devengo_in_period,
    resolve_invoice_devengo,
)
from .oss_ioss_wire_geometry import ROW_SHAPES, record_row_slots, require_slot_coverage, require_wire_geometry
from .source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from .source_resolution_operations import source_context_operation, storage_degradation_resolution

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


def _expected_iva_amount(
    candidate: OssIossLedgerCandidate,
    *,
    operation: PinnedAuthorityOperation,
) -> Decimal:
    """Return the IVA amount derived from the candidate's base and rate.

    Looks up the destination Member State's rate for the candidate's
    rate tier on the supply date, multiplies by ``base_amount``, and
    rounds to two decimal places — the precision at which ledger
    amounts are persisted.

    Args:
        candidate: The substrate-classified ledger line whose base amount
            and rate kind are used to derive the expected IVA amount.
        operation: Generation-pinned authority operation used for the rate lookup.

    Returns:
        The expected IVA amount rounded to two decimal places.
    """
    rate = lookup_published_rate(
        candidate.destination_member_state,
        candidate.rate_kind,
        candidate.transaction_date,
        operation=operation,
    )
    derived = candidate.base_amount * rate.pct / Decimal("100")
    return round_to_cents(derived)


def validate_oss_ioss_observation(
    candidate: OssIossLedgerCandidate,
    *,
    operation: PinnedAuthorityOperation | None = None,
) -> OssIossLedgerObservation:
    """Validate ``candidate`` and return the registry-ready observation.

    Looks up the destination Member State's rate at the supply date,
    derives the expected IVA amount from ``base_amount`` and the
    looked-up rate, and rejects the candidate if the persisted
    ``iva_amount`` deviates from the derived value by more than
    ``CENT``.

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
    expected = _expected_iva_amount(candidate, operation=operation)
    persisted = round_to_cents(candidate.iva_amount)
    # Ledger amounts are rounded to two decimal places at persistence time, so a
    # difference of one cent or less is rounding noise rather than a data-quality
    # blocker. Larger gaps fail validation and the line is rejected before the
    # registry resolver aggregates it. The quantum is CENT because it is the same
    # cent the rounding produced, not a threshold this module chose.
    if abs(persisted - expected) > CENT:
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
    return resolve_ledger_oss_aggregation_binding_values(revision, observations)


def _detail_binding_values(
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
    """
    decimal_values: dict[BindingId, Decimal] = {}
    enum_values: dict[BindingId, str] = {}
    for record_id, grouped in _group_detail_observations(revision, observations, operation=operation).items():
        slots = record_row_slots(revision, record_id)
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
    """
    declarations = _projection_declarations(observation.transaction_date, operation=operation)
    record_id = declarations.get(f"section.{observation.transaction_kind.value}.record")
    return record_id if record_id in _revision_records(revision) else None


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
    rate = lookup_rate(
        member_state,
        observation.rate_kind,
        observation.transaction_date,
        operation=operation,
    ).pct
    return _DetailRowKey(member_state, observation.rate_kind, rate, country_code, rate_code)


def _group_detail_observations(
    revision: ModeloRevision,
    observations: Sequence[OssIossLedgerObservation],
    *,
    operation: PinnedAuthorityOperation,
) -> dict[str, dict[_DetailRowKey, list[OssIossLedgerObservation]]]:
    """Group the observations this revision can place, by table and then by row."""
    grouped: dict[str, dict[_DetailRowKey, list[OssIossLedgerObservation]]] = {}
    for observation in observations:
        record_id = _detail_record_for(observation, revision, operation=operation)
        if record_id is not None:
            rows = grouped.setdefault(record_id, {})
            rows.setdefault(_detail_row_key(observation, operation=operation), []).append(observation)
    return grouped


def _observations_without_detail_row(
    revision: ModeloRevision,
    observations: Sequence[OssIossLedgerObservation],
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[OssIossLedgerObservation, ...]:
    """Return declarable observations no table of this revision can take."""
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
    decimal_values[base] = sum((item.base_amount for item in rows), Decimal("0"))
    decimal_values[cuota] = sum((item.iva_amount for item in rows), Decimal("0"))


def _refuse_rate_chosen_by_issue_date(
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
    span = _projection_period(context.period)
    for observation in observations:
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


def _closed_detail_record_rows(
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
    if context.work_unit_id is None or projection.catalogue_fingerprint is None:
        return ()
    revision = _layout_hydrated_revision(context, operation=operation)
    effective_date = _projection_period(context.period).end_date
    capacity = int(_projection_declarations(effective_date, operation=operation)["detail_row.capacity"])
    closed: list[ClosedRecordRowSet] = []
    covered: set[BindingId] = set()
    for record_id in _closable_records(revision, effective_date, operation=operation):
        slots = record_row_slots(revision, record_id)
        if len(slots) != capacity:
            raise AggregationValidationError(tr("aggregation.oss_ioss.errors.detail_not_representable"))
        require_wire_geometry(revision, record_id, slots)
        require_slot_coverage(slots, supplied_binding_ids)
        covered.update(binding for row in slots for binding in row)
        closed.append(
            ClosedRecordRowSet(
                record_id=record_id,
                bucket_id=context.bucket_id,
                work_unit_id=context.work_unit_id,
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
                source_fingerprint=projection.catalogue_fingerprint,
                rows=tuple(
                    RecordRowMembership(
                        row_index=index,
                        binding_ids=row,
                        occupied=bool(supplied_binding_ids.intersection(row)),
                    )
                    for index, row in enumerate(slots, start=1)
                ),
            ),
        )
    if not supplied_binding_ids.issubset(covered):
        raise AggregationValidationError(tr("aggregation.oss_ioss.errors.detail_not_representable"))
    return tuple(closed)


def _candidate_for_invoice_line(
    invoice: Invoice,
    line: InvoiceLine,
    *,
    line_index: int,
    devengo_date: date,
    period_last_day: date,
) -> OssIossLedgerCandidate | None:
    """Project one invoice line into an OSS/IOSS candidate, or ``None`` when not applicable.

    The regime / destination checks mean the line is not an OSS/IOSS
    operation at all -- correctly silent, nothing to declare. A line that
    passes both IS a real, declarable OSS/IOSS operation, so a missing
    rate_kind or a missing period-close rate from that point on REFUSES rather
    than silently drops it. A would-be-silently-dropped declarable line is a
    hard stop, not an advisory beside a smaller-but-green figure.
    """
    if invoice.oss_ioss_regime is None or invoice.oss_transaction_kind is None:
        return None
    destination = invoice.counterparty_eu_member_state
    if destination is None:
        return None
    rate_kind = line.oss_rate_kind or iva_rate_kind(line.iva_rate, devengo_date)
    if rate_kind is None:
        raise AggregationValidationError(
            tr("aggregation.oss_ioss.errors.invoice_line_rate_kind_unclassifiable"),
            context={
                "invoice_id": invoice.invoice_id,
                "invoice_number": invoice.invoice_number,
                "line_index": str(line_index),
                "iva_rate": line.iva_rate.value,
            },
        )
    # OSS/IOSS is cross-border B2C, where invoicing in the destination's own
    # currency is the ordinary case. Art. 163 noniesdecies, duovicies and
    # septvicies fix one rate for the whole return, the period's last day (or the
    # next day of publication when none is published that day), so the rate
    # stamped on the invoice at its operation date does not apply here.
    rate = _period_close_rate(invoice, line_index=line_index, last_day=period_last_day)
    return OssIossLedgerCandidate(
        ledger_id=f"{invoice.invoice_id}:{line_index}",
        transaction_date=devengo_date,
        regime=invoice.oss_ioss_regime,
        destination_member_state=destination,
        rate_kind=rate_kind,
        invoice_direction=invoice.kind,
        transaction_kind=invoice.oss_transaction_kind,
        base_amount=line.subtotal if rate is None else round_to_cents(line.subtotal * rate),
        iva_amount=line.iva_amount if rate is None else round_to_cents(line.iva_amount * rate),
    )


def _period_close_rate(invoice: Invoice, *, line_index: int, last_day: date) -> Decimal | None:
    """Return the ECB rate the return converts this invoice at, or ``None`` for a euro invoice."""
    if invoice.currency == DEFAULT_CURRENCY:
        return None
    context = {
        "invoice_id": invoice.invoice_id,
        "invoice_number": invoice.invoice_number,
        "currency": invoice.currency,
        "line_index": str(line_index),
        "rate_date": last_day.isoformat(),
    }
    try:
        lookup = published_eur_rate_on_day_or_next_publication(
            invoice.currency, last_day, rate_provider=exchange_rate_provider()
        )
    except ExchangeRateProviderError as exc:
        # An unreachable authority answers nothing about the rate: the same refusal, never a default.
        raise AggregationValidationError(
            tr("aggregation.oss_ioss.errors.invoice_line_currency_unconverted"), context=context
        ) from exc
    if lookup.status is not EurRateLookupStatus.FOUND or lookup.rate is None:
        raise AggregationValidationError(
            tr("aggregation.oss_ioss.errors.invoice_line_currency_unconverted"), context=context
        )
    return lookup.rate


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


def _project_oss_invoice(invoice: Invoice, projection_period: Period) -> list[OssIossLedgerCandidate]:
    if invoice.kind is not InvoiceKind.ISSUED:
        return []
    if not invoice_devengo_in_period(invoice, period=projection_period):
        return []
    devengo_date = resolve_invoice_devengo(invoice).devengo_date
    return [
        candidate
        for index, line in enumerate(invoice.lines, start=1)
        if (
            candidate := _candidate_for_invoice_line(
                invoice,
                line,
                line_index=index,
                devengo_date=devengo_date,
                period_last_day=projection_period.end_date,
            )
        )
        is not None
    ]


def _projection_period(period: Period) -> Period:
    """Return the calendar period an Exterior token such as ``EXT-3T`` files."""
    if period.registry_token.startswith("EXT-"):
        return Period.from_year_and_code(
            period.filing_year,
            period.registry_token.removeprefix("EXT-"),
        )
    return period


def project_oss_ioss_invoices_from_repositories(
    *,
    period: Period,
    ports: InvoiceCatalogueReadPorts,
) -> OssIossInvoiceProjection:
    """Project OSS/IOSS-tagged issued invoices into Modelo 369 ledger candidates.

    Attribution is by the LIVA art. 75 devengo date through the shared
    :func:`~application.aggregation.invoice_devengo.invoice_devengo_in_period` predicate, so an
    operation performed in one quarter and invoiced in the next is declared in
    the quarter it was performed, and every path that folds invoices into a
    period answers that question the same way.

    Args:
        period: Filing period whose date span filters issued invoices.
        ports: Required application-owned catalogue read capabilities for the
            composed profile bucket.

    Returns:
        The candidates for the period beside the invoices they were projected
        from.
    """
    projection_period = _projection_period(period)
    if not projection_period.has_date_span():
        return OssIossInvoiceProjection()
    candidates: list[OssIossLedgerCandidate] = []
    contributing: list[Invoice] = []
    catalogue = ports.invoice_reader.load()
    for invoice in catalogue:
        projected = _project_oss_invoice(invoice, projection_period)
        if projected:
            candidates.extend(projected)
            contributing.append(invoice)
    source_bucket_id = (
        ports.invoice_reader.bucket_id if isinstance(ports.invoice_reader, BucketBoundCatalogueReader) else None
    )
    return OssIossInvoiceProjection(
        candidates=tuple(candidates),
        contributing_invoices=tuple(contributing),
        source_bucket_id=source_bucket_id,
        catalogue_fingerprint=content_hash_hex(catalogue.model_dump(mode="json"))
        if (source_bucket_id is not None and source_bucket_id)
        else None,
    )


def oss_ioss_candidates_from_repositories(
    *,
    period: Period,
    ports: InvoiceCatalogueReadPorts,
) -> tuple[OssIossLedgerCandidate, ...]:
    """Return only the Modelo 369 candidates for the period.

    The narrow accessor for callers that aggregate but emit no diagnostics.
    Delegates to :func:`project_oss_ioss_invoices_from_repositories` rather
    than repeating its selection, so the two cannot attribute a period
    differently.

    Args:
        period: Filing period whose date span filters issued invoices.
        ports: Required application-owned catalogue read capabilities for the
            composed profile bucket.

    Returns:
        A tuple of :class:`OssIossLedgerCandidate` rows projected from issued
        invoices devengando in the period.
    """
    return project_oss_ioss_invoices_from_repositories(
        period=period,
        ports=ports,
    ).candidates


def aggregate_oss_ioss_from_repositories(
    revision: ModeloRevision,
    *,
    period: Period,
    ports: InvoiceCatalogueReadPorts,
    operation: PinnedAuthorityOperation | None = None,
) -> dict[BindingId, Decimal]:
    """Resolve Modelo 369 OSS/IOSS bindings from the live invoice catalogue.

    Args:
        revision: The :class:`ModeloRevision` whose OSS/IOSS bindings are resolved.
        period: Filing period whose date span filters issued invoices.
        ports: Required application-owned catalogue read capabilities for the
            composed profile bucket.
        operation: Existing generation-pinned authority operation. When omitted,
            one indexed operation is opened at this composition boundary.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return aggregate_oss_ioss_from_repositories(
                revision,
                period=period,
                ports=ports,
                operation=indexed_operation,
            )
    return aggregate_oss_ioss_bindings(
        revision,
        oss_ioss_candidates_from_repositories(period=period, ports=ports),
        operation=operation,
    )


class OssIossLedgerSourceResolver:
    """Source mesh resolver for Modelo 369 OSS / IOSS ledger candidates."""

    resolver_id: ClassVar[str] = "ledger_oss_aggregation"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (BindingSourceKind.LEDGER_OSS_AGGREGATION,)

    def __init__(
        self,
        *,
        ports: InvoiceCatalogueReadPorts,
        candidates: Sequence[OssIossLedgerCandidate] | None = None,
    ) -> None:
        """Construct the resolver with a pre-classified ledger candidate sequence.

        Args:
            candidates: The substrate-classified ledger lines for the
                current period. The resolver validates and aggregates
                these on each :meth:`resolve` call.
            ports: Required application-owned catalogue read capabilities used
                to project OSS/IOSS-tagged invoices when ``candidates`` is not
                supplied.
        """
        self._ports = ports
        self._candidates = tuple(candidates) if candidates is not None else None

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Validate candidates and return the resolved OSS/IOSS binding values.

        Validates every candidate through :func:`validate_oss_ioss_observation`
        then delegates to the registry's
        ``resolve_ledger_oss_aggregation_binding_values`` to aggregate the
        matched lines per binding selector.

        When the resolver is constructed with explicit ``candidates``, those
        candidates are folded directly. When ``candidates`` is omitted, the live
        operator path projects OSS/IOSS-tagged issued invoices from the
        application catalogue read capability into candidates first. If no
        candidate is available, the
        resolver still CLAIMS ``ledger_oss_aggregation`` (so the binding
        compiles and is not flagged as a novel source) but surfaces one
        non-blocking ``oss_no_live_source`` advisory per declared OSS binding.
        This keeps a Modelo 369 OSS cuota from resolving to a SILENT
        claimed-zero when the catalogue carries no classifiable OSS invoices.

        Args:
            context: The :class:`CalculationSourceContext` carrying the
                ``ModeloRevision`` whose ``ledger_oss_aggregation`` bindings
                should be resolved.

        Returns:
            A :class:`CalculationSourceResolution` with resolved
            binding values, source transaction ids, and per-observation
            provenance records — or, when no candidates were supplied, an
            empty resolution carrying one ``oss_no_live_source`` advisory per
            declared OSS binding when no candidates can be projected.

        Raises:
            AggregationValidationError: When any candidate's persisted IVA
                amount disagrees with the destination Member State rate by
                more than one cent.
        """
        try:
            with source_context_operation(context) as indexed_operation:
                self._require_source_bucket(context)
                projection = (
                    project_oss_ioss_invoices_from_repositories(
                        period=context.period,
                        ports=self._ports,
                    )
                    if self._candidates is None
                    else OssIossInvoiceProjection(candidates=self._candidates)
                )
                candidates = projection.candidates
                observations = validate_oss_ioss_observations(candidates, operation=indexed_operation)
                _refuse_rate_chosen_by_issue_date(
                    context,
                    projection,
                    observations,
                    operation=indexed_operation,
                )
                detail_values, detail_enum_values = _detail_binding_values(
                    context.revision,
                    observations,
                    operation=indexed_operation,
                )
                unrouted = _observations_without_detail_row(
                    context.revision,
                    observations,
                    operation=indexed_operation,
                )
                closed_rows = (
                    _closed_detail_record_rows(
                        context,
                        projection,
                        supplied_binding_ids=frozenset(detail_values) | frozenset(detail_enum_values),
                        operation=indexed_operation,
                    )
                    if not unrouted
                    else ()
                )
        except InvoiceCatalogueReadPersistenceError as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        if not candidates:
            return CalculationSourceResolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                closed_record_row_sets=closed_rows,
                diagnostics=self._no_live_source_diagnostics(context),
            )
        # Fail-closed advisory parity with the IVA screen: a non-zero declarable
        # OSS line that no detail table can take would otherwise be silently
        # dropped (no-silent-under-declaration).
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values={
                **resolve_ledger_oss_aggregation_binding_values(context.revision, observations),
                **detail_values,
            },
            enum_binding_values=detail_enum_values,
            closed_record_row_sets=closed_rows,
            source_transaction_ids=tuple(
                sorted({observation.ledger_id.split(":", 1)[0] for observation in observations}),
            ),
            diagnostics=devengo_proxy_attribution_diagnostics(
                projection.contributing_invoices,
                source_kind="ledger_oss_aggregation",
                resolver_id=self.resolver_id,
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="unrouted_observation",
                    source_kind="ledger_oss_aggregation",
                    resolver_id=self.resolver_id,
                    source_ref=f"transaction:{observation.ledger_id}",
                    message=(
                        f"declarable OSS observation {observation.ledger_id!r} "
                        f"(regime={observation.regime.value!r}, "
                        f"destination={observation.destination_member_state.value!r}, "
                        f"rate_kind={observation.rate_kind.value!r}, "
                        f"invoice_direction={observation.invoice_direction.value!r}, "
                        f"transaction_kind={observation.transaction_kind.value!r}) has no detail table "
                        f"on revision {context.revision.id!r}: a Union goods line needs its state of "
                        "dispatch, which the invoice does not record, and a line of another regime "
                        "belongs to that regime's revision; its base/cuota is not declared on this calculation"
                    ),
                )
                for observation in unrouted
            ),
            provenance=tuple(
                CalculationSourceProvenance(
                    resolver_id=self.resolver_id,
                    resolved_binding_source=BindingSourceKind.LEDGER_OSS_AGGREGATION,
                    contributor_source_kind="ledger_oss_aggregation",
                    contributor_binding_source=BindingSourceKind.LEDGER_OSS_AGGREGATION,
                    lineage_role=CalculationSourceLineageRole.PRIMARY,
                    source_ref=f"transaction:{observation.ledger_id}",
                    parent_source_ref=None,
                    terminal_origin=TerminalOriginClass.LEDGER_AGGREGATE,
                )
                for observation in observations
            ),
        )

    def _require_source_bucket(self, context: CalculationSourceContext) -> None:
        if (
            self._candidates is None
            and isinstance(self._ports.invoice_reader, BucketBoundCatalogueReader)
            and self._ports.invoice_reader.bucket_id is not None
            and self._ports.invoice_reader.bucket_id != context.bucket_id
        ):
            raise AggregationValidationError(tr("aggregation.source_mesh.errors.closed_record_rows_unadmitted"))

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
                    "OSS/IOSS-tagged issued invoice line was available for the filing period; "
                    "the OSS cuota is NOT auto-computed from the invoice catalogue"
                ),
            )
            for binding in context.revision.bindings
            if str(binding.source) == "ledger_oss_aggregation"
        )


__all__ = [
    "OssIossInvoiceProjection",
    "OssIossLedgerCandidate",
    "OssIossLedgerSourceResolver",
    "aggregate_oss_ioss_bindings",
    "aggregate_oss_ioss_from_repositories",
    "oss_ioss_candidates_from_repositories",
    "project_oss_ioss_invoices_from_repositories",
    "validate_oss_ioss_observation",
    "validate_oss_ioss_observations",
]
