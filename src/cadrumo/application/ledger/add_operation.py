"""Registered exact-profile manual creation of one ledger transaction."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, overload
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.country_code import CountryCodeAlpha2
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.parsing.dates import require_iso8601_date
from ...core.time.clock import now
from ...core.unit_proportion import is_unit_proportion
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.iva_category_catalogue import require_iva_category
from ...domain.calculations.registry.iva_deduction_catalogue import require_iva_deduction_fact_kind
from ...domain.calculations.registry.prorrata_exclusions import require_art104_tres_exclusion
from ...domain.calculations.registry.prorrata_register_catalogue import especial_prorrata_register_regime
from ...domain.calculations.registry.prorrata_vocabulary import require_input_classification
from ...domain.categories.spending_category_catalogue import require_spending_category
from ...domain.transactions.enums import BusinessClassification, TransactionDirection, is_classified
from ...domain.transactions.errors import TransactionValidationError
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..prorrata_register.ports import ProrrataRegisterRepositoryFactory
from ..prorrata_register.service import ProrrataRegisterService
from ..review.filter import LedgerReviewStatus
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPorts, LedgerActionPortsFactory
from .actions_manual import create_manual_transaction, ledger_transaction_result_payload
from .models import LedgerTransactionResultPayload, ManualLedgerTransactionCommand
from .read_access import resolve_ledger_read_access
from .source_jurisdiction import SourceJurisdictionOutcome, resolve_source_jurisdiction
from .transaction_projection import LedgerTransactionProjection

LEDGER_ADD_OPERATION_DEFINITION_ID = "ledger.add"
LEDGER_ADD_PHASE = "ledger.add"
LEDGER_ADD_VALIDATION_REFUSAL_CODE = "REFUSED_CLI_VALIDATION_BOUNDARY"
_MAX_ADD_EVENT_IDS = 1
_MAX_ADD_ATTACHMENTS = 4096
_MAX_VALIDATION_MESSAGES = 32
_AddText = Annotated[str, Field(max_length=4096)]
_AddOptionalText = Annotated[str, Field(max_length=4096)] | None
_AddDecimalText = Annotated[str, Field(min_length=1, max_length=128)]
_AddOptionalDecimalText = _AddDecimalText | None
_AddDateText = Annotated[str, Field(min_length=10, max_length=10)]
_AddOptionalDateText = _AddDateText | None
_AddId = Annotated[str, Field(min_length=1, max_length=256)]
_AddOptionalId = _AddId | None
_AddDirection = Annotated[str, Field(min_length=1, max_length=32)]
_AddClassification = Annotated[str, Field(min_length=1, max_length=64)]
_AddIvaCategory = Annotated[str, Field(min_length=1, max_length=128)] | None
_AddEUMemberState = Annotated[str, Field(min_length=2, max_length=2)] | None
_AddAttachmentIds = Annotated[
    tuple[Annotated[str, Field(min_length=1, max_length=256)], ...], Field(max_length=_MAX_ADD_ATTACHMENTS)
]
_AddEventIds = Annotated[
    tuple[Annotated[str, Field(min_length=1, max_length=128)], ...], Field(max_length=_MAX_ADD_EVENT_IDS)
]
_ValidationMessage = Annotated[str, Field(min_length=1, max_length=2048)]
_ValidationMessages = Annotated[tuple[_ValidationMessage, ...], Field(max_length=_MAX_VALIDATION_MESSAGES)]


class LedgerAddRequest(BaseModel):
    """Bounded private CLI input; taxpayer-derived values are resolved in the worker."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    booked_date: _AddDateText
    amount: _AddDecimalText
    direction: _AddDirection
    description: Annotated[str, Field(min_length=1, max_length=4096)]
    value_date: _AddOptionalDateText = None
    currency: Annotated[str, Field(min_length=1, max_length=16)] = "EUR"
    counterparty: _AddOptionalText = None
    business_classification: _AddClassification = BusinessClassification.NOT_YET_PROCESSED.value
    business_pct: _AddOptionalDecimalText = None
    category_id: _AddOptionalId = None
    taxable_base: _AddOptionalDecimalText = None
    iva_rate: _AddOptionalDecimalText = None
    iva_amount: _AddOptionalDecimalText = None
    iva_category: _AddIvaCategory = None
    deduction_fact_kind: Annotated[str, Field(max_length=128)] | None = None
    investment_asset_id: _AddOptionalId = None
    counterparty_country: CountryCodeAlpha2 | None = None
    counterparty_identification_state: _AddEUMemberState = None
    recargo_amount: _AddOptionalDecimalText = None
    irpf_category: _AddOptionalText = None
    usage_ratio_id: _AddOptionalId = None
    prorrata_reference: Annotated[str, Field(max_length=256)] | None = None
    art_104_tres_exclusion: Annotated[str, Field(max_length=128)] | None = None
    input_classification: Annotated[str, Field(max_length=128)] | None = None
    prorrata_sector: Annotated[str, Field(max_length=64)] | None = None
    purchase_invoice_evidence_id: _AddOptionalId = None
    attachment_ids: _AddAttachmentIds = ()
    notes: _AddText = ""
    actor: Annotated[str, Field(max_length=64)] | None = None
    idempotency_key: Annotated[str, Field(max_length=256)] | None = None
    source_jurisdiction: Annotated[str, Field(max_length=16)] | None = None

    @field_validator("booked_date", "value_date")
    @classmethod
    def _extended_iso_dates(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            parsed = require_iso8601_date(value)
        except ValueError:
            raise ValueError("ledger add dates must use YYYY-MM-DD") from None
        if parsed.isoformat() != value.strip():
            raise ValueError("ledger add dates must use YYYY-MM-DD")
        return value

    @field_validator("amount", "business_pct", "taxable_base", "iva_rate", "iva_amount", "recargo_amount")
    @classmethod
    def _canonical_decimal_inputs(cls, value: str | None, info: object) -> str | None:
        if value is None:
            return None
        signed = getattr(info, "field_name", None) != "amount"
        if try_parse_canonical_decimal(value, signed=signed, max_fraction_digits=2) is None:
            raise ValueError("ledger add decimal values must use canonical decimal text")
        return value


class LedgerAddOperationResult(BaseModel):
    """Bounded successful add receipt or a refusal proven before the write call."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["created", "validation_error"]
    profile_id: UUID
    transaction: LedgerTransactionProjection | None = None
    review_status: LedgerReviewStatus | None = None
    bucket_event_ids: _AddEventIds = ()
    advisory_input_classification: _AddOptionalText = None
    advisory_input_classification_inert: bool = False
    advisory_sector_id: Annotated[str, Field(max_length=64)] | None = None
    advisory_sector_unmatched: bool = False
    validation_code: (
        Literal[
            "source_jurisdiction_required_irnr",
            "source_jurisdiction_required_beckham",
            "invalid_command",
        ]
        | None
    ) = None
    validation_messages: _ValidationMessages = ()

    @classmethod
    def validation_refusal(
        cls,
        profile_id: UUID,
        *,
        code: Literal[
            "source_jurisdiction_required_irnr",
            "source_jurisdiction_required_beckham",
            "invalid_command",
        ],
        messages: tuple[str, ...] = (),
    ) -> LedgerAddOperationResult:
        """Build a bounded refusal projection after validation and before writing."""
        return cls(
            outcome="validation_error",
            profile_id=profile_id,
            validation_code=code,
            validation_messages=messages or ("ledger add input is invalid",),
        )

    @classmethod
    def created(
        cls,
        profile_id: UUID,
        *,
        transaction: LedgerTransactionProjection,
        review_status: LedgerReviewStatus,
        bucket_event_ids: tuple[str, ...],
        advisory_input_classification: str | None = None,
        advisory_input_classification_inert: bool = False,
        advisory_sector_id: str | None = None,
        advisory_sector_unmatched: bool = False,
    ) -> LedgerAddOperationResult:
        """Build a successful transaction projection with its worker-resolved advisories."""
        return cls(
            outcome="created",
            profile_id=profile_id,
            transaction=transaction,
            review_status=review_status,
            bucket_event_ids=bucket_event_ids,
            advisory_input_classification=advisory_input_classification,
            advisory_input_classification_inert=advisory_input_classification_inert,
            advisory_sector_id=advisory_sector_id,
            advisory_sector_unmatched=advisory_sector_unmatched,
        )

    @model_validator(mode="after")
    def _complete_selected_outcome(self) -> LedgerAddOperationResult:
        if self.outcome == "created":
            if (
                self.transaction is None
                or self.review_status is None
                or self.validation_code is not None
                or self.validation_messages
                or (self.advisory_input_classification_inert and self.advisory_input_classification is None)
                or (self.advisory_sector_unmatched and self.advisory_sector_id is None)
            ):
                raise ValueError("created ledger add receipt is incomplete")
        elif (
            self.transaction is not None
            or self.review_status is not None
            or self.bucket_event_ids
            or self.advisory_input_classification is not None
            or self.advisory_input_classification_inert
            or self.advisory_sector_id is not None
            or self.advisory_sector_unmatched
            or self.validation_code is None
            or not self.validation_messages
        ):
            raise ValueError("ledger add validation result must contain no transaction or effect")
        return self


class LedgerAddExecutionResult(BaseModel):
    """Secure worker operand for success or a bounded pre-write refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["created", "validation_error"]
    profile_id: UUID
    result: LedgerAddOperationResult | None = None
    validation_code: (
        Literal[
            "source_jurisdiction_required_irnr",
            "source_jurisdiction_required_beckham",
            "invalid_command",
        ]
        | None
    ) = None
    validation_messages: _ValidationMessages = ()

    @model_validator(mode="after")
    def _complete_selected_outcome(self) -> LedgerAddExecutionResult:
        if self.outcome == "created":
            if (
                self.result is None
                or self.result.outcome != "created"
                or self.result.profile_id != self.profile_id
                or self.validation_code is not None
                or self.validation_messages
            ):
                raise ValueError("created ledger add execution requires its matching result")
        elif self.result is not None or self.validation_code is None or not self.validation_messages:
            raise ValueError("ledger add refusal requires only bounded validation facts")
        return self


class LedgerAddExecutor:
    """Create one canonical transaction under exact-profile COMMIT custody."""

    def __init__(
        self,
        ports_factory: LedgerActionPortsFactory,
        prorrata_register_repository_factory: ProrrataRegisterRepositoryFactory,
    ) -> None:
        """Retain exact-bucket ledger and prorrata repository factories."""
        self._ports_factory = ports_factory
        self._prorrata_register_repository_factory = prorrata_register_repository_factory

    async def execute(
        self,
        request: OperationRequest[LedgerAddRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Validate, resolve advisory state, and perform one guarded canonical add."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        subject = profile_operation_subject(bucket_id)
        if (
            request.definition_id != LEDGER_ADD_OPERATION_DEFINITION_ID
            or request.subject_ref != subject
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != subject
            or require_active_bucket_id() != bucket_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(LEDGER_ADD_PHASE)

        async def refuse(
            error: Exception,
            *,
            code: Literal[
                "source_jurisdiction_required_irnr",
                "source_jurisdiction_required_beckham",
                "invalid_command",
            ] = "invalid_command",
        ) -> OperationRefusalEvidence:
            detail = LedgerAddExecutionResult(
                outcome="validation_error",
                profile_id=payload.profile_id,
                validation_code=code,
                validation_messages=_validation_messages(error),
            )
            detail_ref = await context.operands.put(detail, written_at=now())
            return OperationRefusalEvidence(
                refusal_code=LEDGER_ADD_VALIDATION_REFUSAL_CODE,
                detail_ref=detail_ref,
            )

        async def commit() -> str | OperationRefusalEvidence:
            async with context.cancellation.irreversible_section():
                operation: PinnedAuthorityOperation = context.authority_operation
                try:
                    ports = await asyncio.to_thread(self._ports_factory, bucket_id=bucket_id, operation=operation)
                    _require_exact_ports(ports, bucket_id=bucket_id, operation=operation)
                    command = await asyncio.to_thread(_prepare_command, payload, ports, operation)
                    advisory_input_inert, advisory_sector_unmatched = await asyncio.to_thread(
                        _prorrata_advisory_facts,
                        payload,
                        command,
                        self._prorrata_register_repository_factory,
                        operation,
                    )
                except _SourceJurisdictionRequiredError as refusal:
                    return await refuse(refusal, code=refusal.code)
                except (TransactionValidationError, ValidationError, ValueError) as error:
                    return await refuse(error)

                # From this point the canonical service may have durably committed
                # the transaction/event even if a later attachment back-reference
                # or projection step fails. Preserve that uncertainty.
                await context.events.effect(OperationEffect.UNKNOWN)
                from ...application.exchange_rate_provider import exchange_rate_provider
                from ...domain.currency.service import CurrencyNormalizationService

                result = await asyncio.to_thread(
                    create_manual_transaction,
                    command,
                    ports=ports,
                    currency_normalizer=CurrencyNormalizationService(rate_provider=exchange_rate_provider()),
                    require_revision_guard=True,
                )
                projected = _operation_result(
                    payload.profile_id,
                    result,
                    advisory_input_inert=advisory_input_inert,
                    advisory_sector_unmatched=advisory_sector_unmatched,
                    advisory_input_classification=payload.input_classification,
                    advisory_sector_id=payload.prorrata_sector,
                )
                await context.events.effect(
                    OperationEffect.UPDATED if result.bucket_event_ids else OperationEffect.NONE
                )
                execution = LedgerAddExecutionResult(
                    outcome="created",
                    profile_id=payload.profile_id,
                    result=projected,
                )
                return await context.operands.put(
                    execution,
                    written_at=now(),
                )

        return await await_cancellation_complete(commit(), task_name="ledger-add-commit")


class _SourceJurisdictionRequiredError(Exception):
    def __init__(
        self,
        code: Literal["source_jurisdiction_required_irnr", "source_jurisdiction_required_beckham"],
        message: str,
    ) -> None:
        self.code: Literal["source_jurisdiction_required_irnr", "source_jurisdiction_required_beckham"] = code
        self.message = message


def _prepare_command(
    payload: LedgerAddRequest,
    ports: LedgerActionPorts,
    operation: PinnedAuthorityOperation,
) -> ManualLedgerTransactionCommand:
    """Resolve profile and registry facts, then construct the canonical command."""
    from ...application.ledger.ratios import resolve_business_share_pct
    from ...application.user_profile.censo_sync import bound_raw_afectacion_ratio
    from ...application.wizard.status import WizardStatusError, load_active_taxpayer_profile
    from ...application.workflow.persistence import workflow_state_repository
    from ...domain.calculations.registry.eu_member_state_catalogue import require_eu_member_state
    from ...domain.deadlines.models import TaxpayerProfile

    booked_date = require_iso8601_date(payload.booked_date)
    value_date = require_iso8601_date(payload.value_date) if payload.value_date is not None else None
    amount = _parse_add_decimal(payload.amount, label="amount", signed=False)
    if amount < Decimal("0"):
        raise TransactionValidationError(
            "manual ledger transaction amount must be a non-negative magnitude; "
            "set the flow with --direction (OUTGOING / INCOMING / INTERNAL_TRANSFER), not a negative amount",
        )
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
    operator_share = _parse_add_decimal(payload.business_pct, label="business-pct", signed=True)
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
            raise _SourceJurisdictionRequiredError(
                "source_jurisdiction_required_beckham",
                "source jurisdiction must be supplied for this taxpayer regime",
            )
        raise _SourceJurisdictionRequiredError(
            "source_jurisdiction_required_irnr",
            "source jurisdiction must be supplied for non-resident IRNR profiles",
        )

    try:
        classification = BusinessClassification(payload.business_classification)
        direction = TransactionDirection(payload.direction)
    except ValueError as error:
        raise TransactionValidationError("ledger add direction and classification must be canonical values") from error
    if not is_classified(classification) and classification is not BusinessClassification.NOT_YET_PROCESSED:
        raise TransactionValidationError("this classification is assigned by the ledger pipeline")

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
    command = ManualLedgerTransactionCommand(
        bucket_id=str(payload.profile_id),
        booked_date=booked_date,
        value_date=value_date,
        amount=amount,
        currency=payload.currency,
        direction=direction,
        counterparty=payload.counterparty,
        description=payload.description,
        business_classification=classification,
        business_pct=resolved_share,
        category_id=category.value if category is not None else None,
        taxable_base=_parse_add_decimal(payload.taxable_base, label="taxable-base"),
        iva_rate=_parse_add_decimal(payload.iva_rate, label="iva-rate"),
        iva_amount=_parse_add_decimal(payload.iva_amount, label="iva-amount"),
        iva_category=iva_category,
        deduction_fact_kind=deduction_kind,
        investment_asset_id=payload.investment_asset_id,
        counterparty_country=payload.counterparty_country,
        counterparty_identification_state=identification_state,
        recargo_amount=_parse_add_decimal(payload.recargo_amount, label="recargo-amount"),
        irpf_category=payload.irpf_category,
        usage_ratio_id=payload.usage_ratio_id,
        prorrata_reference=payload.prorrata_reference,
        art_104_tres_exclusion=exclusion,
        input_classification=effective_input_classification,
        prorrata_sector_id=payload.prorrata_sector,
        purchase_invoice_evidence_id=payload.purchase_invoice_evidence_id,
        attachment_ids=payload.attachment_ids,
        notes=payload.notes,
        actor=payload.actor or str(payload.profile_id) or "operator",
        source_command="aeat app ledger add",
        idempotency_key=payload.idempotency_key,
        source_jurisdiction=jurisdiction.jurisdiction,
    )
    return command


def _prorrata_advisory_facts(
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
def _parse_add_decimal(raw: str, *, label: str, signed: bool = True) -> Decimal: ...


@overload
def _parse_add_decimal(raw: None, *, label: str, signed: bool = True) -> None: ...


def _parse_add_decimal(raw: str | None, *, label: str, signed: bool = True) -> Decimal | None:
    if raw is None:
        return None
    parsed = try_parse_canonical_decimal(raw, signed=signed, max_fraction_digits=2)
    if parsed is None:
        raise TransactionValidationError(f"{label} must use canonical decimal text")
    return parsed


def _validation_messages(error: Exception) -> _ValidationMessages:
    """Retain bounded validation locations and messages without error context."""
    if isinstance(error, ValidationError):
        messages: tuple[str, ...] = tuple(
            str(item.get("msg", "invalid value")).removeprefix("Value error, ").strip()
            for item in error.errors(include_input=False, include_context=False, include_url=False)[
                :_MAX_VALIDATION_MESSAGES
            ]
        )
    else:
        messages = (str(error).strip() or "ledger add input is invalid",)
    bounded = tuple(message[:2048] for message in messages if message.strip())
    return bounded[:_MAX_VALIDATION_MESSAGES] or ("ledger add input is invalid",)


def _require_exact_ports(
    ports: LedgerActionPorts,
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
) -> None:
    if ports.operation is not operation or ports.transaction_repository.bucket_id != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    for repository in (
        ports.invoice_repository,
        ports.work_unit_repository,
        ports.calculation_repository,
    ):
        if getattr(repository, "bucket_id", None) != bucket_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _operation_result(
    profile_id: UUID,
    result: object,
    *,
    advisory_input_inert: bool,
    advisory_sector_unmatched: bool,
    advisory_input_classification: str | None,
    advisory_sector_id: str | None,
) -> LedgerAddOperationResult:
    from .models import ManualLedgerTransactionResult

    if not isinstance(result, ManualLedgerTransactionResult):
        raise TransactionValidationError("ledger add returned no canonical transaction receipt")
    canonical: LedgerTransactionResultPayload = ledger_transaction_result_payload(result)
    if (
        canonical.bucket_id != str(profile_id)
        or result.ref.bucket_id != canonical.bucket_id
        or result.ref.transaction_id != canonical.transaction_id
        or result.transaction.transaction_id != canonical.transaction_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    if len(result.bucket_event_ids) > _MAX_ADD_EVENT_IDS:
        raise TransactionValidationError("ledger add returned too many event identifiers")
    return LedgerAddOperationResult.created(
        profile_id,
        transaction=LedgerTransactionProjection.from_payload(canonical.transaction),
        review_status=canonical.review_status,
        bucket_event_ids=result.bucket_event_ids,
        advisory_input_classification=advisory_input_classification,
        advisory_input_classification_inert=advisory_input_inert,
        advisory_sector_id=advisory_sector_id,
        advisory_sector_unmatched=advisory_sector_unmatched,
    )


def _project_operation_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release a matching successful add result or its bounded refusal detail."""
    if (
        type(result) is not LedgerAddExecutionResult
        or receipt.identity.definition_id != LEDGER_ADD_OPERATION_DEFINITION_ID
    ):
        raise ValueError("invalid ledger add result or terminal receipt")
    if receipt.identity.subject_ref != profile_operation_subject(str(result.profile_id)):
        raise ValueError("ledger add result belongs to another subject")
    if result.outcome == "created":
        projected = result.result
        if (
            receipt.condition is not OperationTerminalCondition.SUCCEEDED
            or receipt.result_ref is None
            or receipt.refusal_ref is not None
            or receipt.refusal_detail_ref is not None
            or receipt.failure_error_code is not None
            or receipt.diagnostic_ref is not None
            or projected is None
            or receipt.effect is not (OperationEffect.UPDATED if projected.bucket_event_ids else OperationEffect.NONE)
        ):
            raise ValueError("ledger add success has an incompatible terminal receipt")
        return projected
    if (
        receipt.condition is not OperationTerminalCondition.REFUSED
        or receipt.refusal_ref != LEDGER_ADD_VALIDATION_REFUSAL_CODE
        or receipt.refusal_detail_ref is None
        or receipt.result_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
        or receipt.effect is not OperationEffect.NONE
        or result.validation_code is None
    ):
        raise ValueError("ledger add validation refusal has an incompatible terminal receipt")
    return LedgerAddOperationResult.validation_refusal(
        result.profile_id,
        code=result.validation_code,
        messages=result.validation_messages,
    )


def build_ledger_add_definition(
    ports_factory: LedgerActionPortsFactory,
    prorrata_register_repository_factory: ProrrataRegisterRepositoryFactory,
) -> OperationDefinition:
    """Build the private worker definition for exact-profile manual creation."""
    return OperationDefinition(
        definition_id=LEDGER_ADD_OPERATION_DEFINITION_ID,
        request_type=LedgerAddRequest,
        result_type=LedgerAddExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerAddRequest,
            executor_type=LedgerAddExecutor,
            build=lambda: LedgerAddExecutor(ports_factory, prorrata_register_repository_factory),
        ),
        phase_codes=(LEDGER_ADD_PHASE,),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
        refusal_detail_codes=frozenset({LEDGER_ADD_VALIDATION_REFUSAL_CODE}),
    )


def resolve_ledger_add_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Admit only the submitted manual add bound to its exact profile."""
    if request.definition_id != LEDGER_ADD_OPERATION_DEFINITION_ID or not isinstance(request.payload, LedgerAddRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(
        request,
        context,
        profile_id=request.payload.profile_id,
        periods=frozenset(),
    )
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return ResolvedOperationAccess(request=resolved.request, policy=policy)


def build_ledger_add_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the bounded public request/result wire contracts to the worker."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=LedgerAddRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=LedgerAddOperationResult,
        ),
        result_projector=_project_operation_result,
        access_resolver=resolve_ledger_add_access,
    )


__all__ = [
    "LEDGER_ADD_OPERATION_DEFINITION_ID",
    "LEDGER_ADD_PHASE",
    "LEDGER_ADD_VALIDATION_REFUSAL_CODE",
    "LedgerAddExecutionResult",
    "LedgerAddExecutor",
    "LedgerAddOperationResult",
    "LedgerAddRequest",
    "build_ledger_add_definition",
    "build_ledger_add_registration",
    "resolve_ledger_add_access",
]
