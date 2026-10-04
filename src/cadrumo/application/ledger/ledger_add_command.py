"""Canonical request-to-command resolution for manual ledger additions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import NamedTuple, overload

from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.iva_deduction_fact import IvaDeductionFactKind
from ...core.parsing.dates import require_iso8601_date
from ...core.prorrata_exclusions import Art104TresExclusion
from ...core.unit_proportion import is_unit_proportion
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.iva_category_catalogue import require_iva_category
from ...domain.calculations.registry.iva_deduction_catalogue import require_iva_deduction_fact_kind
from ...domain.calculations.registry.prorrata_exclusions import require_art104_tres_exclusion
from ...domain.calculations.registry.prorrata_register_catalogue import especial_prorrata_register_regime
from ...domain.calculations.registry.prorrata_vocabulary import require_input_classification
from ...domain.categories.spending_category_catalogue import require_spending_category
from ...domain.iva.prorrata import InputClassification
from ...domain.iva.schema import EUMemberState, IvaCategory
from ...domain.transactions.enums import BusinessClassification, TransactionDirection, is_classified
from ...domain.transactions.errors import TransactionValidationError
from ..prorrata_register.ports import ProrrataRegisterRepositoryFactory
from ..prorrata_register.service import ProrrataRegisterService
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .ledger_add_contracts import LedgerAddRequest, LedgerAddSourceJurisdictionCode
from .models import ManualLedgerTransactionCommand
from .source_jurisdiction import SourceJurisdictionOutcome, resolve_source_jurisdiction


class SourceJurisdictionRequiredError(Exception):
    """Signal that a taxpayer jurisdiction fact must be supplied before writing."""

    def __init__(
        self,
        code: LedgerAddSourceJurisdictionCode,
        message: str,
    ) -> None:
        """Store the validation code and the existing operator-facing prompt."""
        self.code: LedgerAddSourceJurisdictionCode = code
        self.message = message


class _ResolvedLedgerAddRegistryFacts(NamedTuple):
    input_classification: InputClassification | None
    exclusion: Art104TresExclusion | None
    deduction_kind: IvaDeductionFactKind | None
    iva_category: IvaCategory | None
    identification_state: EUMemberState | None


def prepare_ledger_add_command(
    payload: LedgerAddRequest,
    operation: PinnedAuthorityOperation,
) -> ManualLedgerTransactionCommand:
    """Resolve ordered profile facts, then construct the canonical command."""
    booked_date, value_date, amount = _resolve_ledger_add_dates(payload)
    category_id, business_pct = _resolve_ledger_add_business_share(
        payload,
        operation=operation,
        booked_date=booked_date,
    )
    source_jurisdiction = _resolve_ledger_add_jurisdiction(payload, operation=operation)
    classification, direction = _resolve_ledger_add_flow(payload)
    registry_facts = _resolve_ledger_add_registry_facts(payload, booked_date=booked_date, operation=operation)
    return ManualLedgerTransactionCommand(
        bucket_id=str(payload.profile_id),
        booked_date=booked_date,
        value_date=value_date,
        amount=amount,
        currency=payload.currency,
        direction=direction,
        counterparty=payload.counterparty,
        description=payload.description,
        business_classification=classification,
        business_pct=business_pct,
        category_id=category_id,
        taxable_base=parse_ledger_add_decimal(payload.taxable_base, label="taxable-base"),
        iva_rate=parse_ledger_add_decimal(payload.iva_rate, label="iva-rate"),
        iva_amount=parse_ledger_add_decimal(payload.iva_amount, label="iva-amount"),
        iva_category=registry_facts.iva_category,
        deduction_fact_kind=registry_facts.deduction_kind,
        investment_asset_id=payload.investment_asset_id,
        counterparty_country=payload.counterparty_country,
        counterparty_identification_state=registry_facts.identification_state,
        recargo_amount=parse_ledger_add_decimal(payload.recargo_amount, label="recargo-amount"),
        irpf_category=payload.irpf_category,
        usage_ratio_id=payload.usage_ratio_id,
        prorrata_reference=payload.prorrata_reference,
        art_104_tres_exclusion=registry_facts.exclusion,
        input_classification=registry_facts.input_classification,
        prorrata_sector_id=payload.prorrata_sector,
        purchase_invoice_evidence_id=payload.purchase_invoice_evidence_id,
        attachment_ids=payload.attachment_ids,
        notes=payload.notes,
        actor=payload.actor or str(payload.profile_id) or "operator",
        source_command="aeat app ledger add",
        idempotency_key=payload.idempotency_key,
        source_jurisdiction=source_jurisdiction,
        own_account_id=payload.own_account_id,
    )


def _resolve_ledger_add_dates(payload: LedgerAddRequest) -> tuple[date, date | None, Decimal]:
    booked_date = require_iso8601_date(payload.booked_date)
    value_date = require_iso8601_date(payload.value_date) if payload.value_date is not None else None
    amount = parse_ledger_add_decimal(payload.amount, label="amount", signed=False)
    if amount < Decimal("0"):
        raise TransactionValidationError(
            "manual ledger transaction amount must be a non-negative magnitude; "
            "set the flow with --direction (OUTGOING / INCOMING / INTERNAL_TRANSFER), not a negative amount",
        )
    return booked_date, value_date, amount


def _resolve_ledger_add_business_share(
    payload: LedgerAddRequest,
    *,
    operation: PinnedAuthorityOperation,
    booked_date: date,
) -> tuple[str | None, Decimal | None]:
    from ...application.ledger.ratios import resolve_business_share_pct
    from ...application.user_profile.censo_sync import bound_raw_afectacion_ratio

    category_id = payload.category_id.strip() if payload.category_id is not None else None
    category_id = category_id or None
    category = (
        require_spending_category(
            category_id,
            effective_date=date(booked_date.year, 12, 31),
            authority=operation,
        )
        if category_id is not None
        else None
    )
    operator_share = parse_ledger_add_decimal(payload.business_pct, label="business-pct", signed=True)
    if operator_share is not None and not is_unit_proportion(operator_share):
        raise TransactionValidationError("business_pct must be within the inclusive 0..1 range")
    censo_ratio = (
        bound_raw_afectacion_ratio(
            bucket_id=str(payload.profile_id), profile_id=str(payload.profile_id), operation=operation
        )
        if category is not None
        else None
    )
    resolved_share = resolve_business_share_pct(
        operator_supplied=operator_share,
        category=category,
        censo_afectacion_ratio=censo_ratio,
        year=booked_date.year,
        operation=operation,
    ).business_pct
    category_value = category.value if category is not None else None
    return category_value, resolved_share


def _resolve_ledger_add_jurisdiction(
    payload: LedgerAddRequest,
    *,
    operation: PinnedAuthorityOperation,
) -> str | None:
    from ...application.wizard.status import WizardStatusError, load_active_taxpayer_profile
    from ...application.workflow.persistence import workflow_state_repository
    from ...domain.deadlines.models import TaxpayerProfile

    state = workflow_state_repository().load()
    try:
        taxpayer: TaxpayerProfile = load_active_taxpayer_profile(state, schema=operation.profile_schema())
    except WizardStatusError as error:
        raise TransactionValidationError("ledger add requires an active taxpayer profile") from error
    jurisdiction = resolve_source_jurisdiction(
        payload.source_jurisdiction,
        fiscal_residency=taxpayer.fiscal_residency,
        irpf_special_regime=taxpayer.irpf_special_regime,
    )
    if jurisdiction.requires_operator_statement:
        if jurisdiction.outcome is SourceJurisdictionOutcome.REQUIRED_IMPATRIADO:
            raise SourceJurisdictionRequiredError(
                "source_jurisdiction_required_beckham",
                "source jurisdiction must be supplied for this taxpayer regime",
            )
        raise SourceJurisdictionRequiredError(
            "source_jurisdiction_required_irnr",
            "source jurisdiction must be supplied for non-resident IRNR profiles",
        )
    return jurisdiction.jurisdiction


def _resolve_ledger_add_flow(payload: LedgerAddRequest) -> tuple[BusinessClassification, TransactionDirection]:
    try:
        classification = BusinessClassification(payload.business_classification)
        direction = TransactionDirection(payload.direction)
    except ValueError as error:
        raise TransactionValidationError("ledger add direction and classification must be canonical values") from error
    if not is_classified(classification) and classification is not BusinessClassification.NOT_YET_PROCESSED:
        raise TransactionValidationError("this classification is assigned by the ledger pipeline")
    return classification, direction


def _resolve_ledger_add_registry_facts(
    payload: LedgerAddRequest,
    *,
    booked_date: date,
    operation: PinnedAuthorityOperation,
) -> _ResolvedLedgerAddRegistryFacts:
    from ...domain.calculations.registry.eu_member_state_catalogue import require_eu_member_state

    effective_input_classification = (
        require_input_classification(payload.input_classification, effective_date=booked_date, authority=operation)
        if payload.input_classification is not None
        else None
    )
    exclusion = (
        require_art104_tres_exclusion(payload.art_104_tres_exclusion, effective_date=booked_date, authority=operation)
        if payload.art_104_tres_exclusion is not None
        else None
    )
    deduction_kind = (
        require_iva_deduction_fact_kind(payload.deduction_fact_kind, effective_date=booked_date, authority=operation)
        if payload.deduction_fact_kind is not None
        else None
    )
    iva_category = (
        require_iva_category(payload.iva_category, effective_date=booked_date, authority=operation)
        if payload.iva_category is not None
        else None
    )
    identification_state = (
        require_eu_member_state(
            payload.counterparty_identification_state,
            effective_date=booked_date,
            authority=operation,
        )
        if payload.counterparty_identification_state is not None
        else None
    )
    return _ResolvedLedgerAddRegistryFacts(
        effective_input_classification,
        exclusion,
        deduction_kind,
        iva_category,
        identification_state,
    )


def resolve_ledger_add_prorrata_advisory_facts(
    payload: LedgerAddRequest,
    command: ManualLedgerTransactionCommand,
    repository_factory: ProrrataRegisterRepositoryFactory,
    operation: PinnedAuthorityOperation,
) -> tuple[bool, bool]:
    """Resolve advisory conditions from the exact profile before any ledger write."""
    input_classification = payload.input_classification
    sector_id = payload.prorrata_sector
    if input_classification is None and sector_id is None:
        return False, False

    bucket_id = str(payload.profile_id)
    repository = repository_factory(bucket_id=bucket_id)
    if repository.bucket_id != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    register = ProrrataRegisterService(repository=repository, operation=operation).list_all()

    input_inert = False
    if input_classification is not None:
        entry = register.entry_for(command.booked_date.year, sector_id=command.prorrata_sector_id)
        input_inert = entry is None or entry.regime != especial_prorrata_register_regime(
            effective_date=command.booked_date,
            authority=operation,
        )
    sector_unmatched = sector_id is not None and register.sector_definition_for(sector_id) is None
    return input_inert, sector_unmatched


@overload
def parse_ledger_add_decimal(raw: str, *, label: str, signed: bool = True) -> Decimal: ...


@overload
def parse_ledger_add_decimal(raw: None, *, label: str, signed: bool = True) -> None: ...


def parse_ledger_add_decimal(raw: str | None, *, label: str, signed: bool = True) -> Decimal | None:
    """Parse an optional canonical decimal and preserve its labeled refusal."""
    if raw is None:
        return None
    parsed = try_parse_canonical_decimal(raw, signed=signed, max_fraction_digits=2)
    if parsed is None:
        raise TransactionValidationError(f"{label} must use canonical decimal text")
    return parsed
