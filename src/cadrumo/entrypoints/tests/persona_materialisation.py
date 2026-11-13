"""Replay a canonical persona into a registered profile through production operations only.

A persona (``dev/fixtures/personas``, read by :mod:`cadrumo.tests.personas`)
reaches its profile the way an operator's input does: the registered wizard
patch, field and repeatable-row mutations, the household replacements, the
own bank accounts and their designations, the suffered-withholding record, the statement import, single classification,
invoice recording and linking, evidence intake and attachment, and, in the
history scope, the local observations of returns the taxpayer holds, the
withholding capture of every rent payment on leased premises, the filed
capture of every return filed with the AEAT, and the work create, calculate,
verify and local file of every return the persona has already filed (create
and calculate only for a calculated return), each submitted to the production
registry's supervisor and settled. The filed capture reads a recorded AEAT
register in place of the AEAT Sede; nothing after that read is replaced.
Nothing is
written to storage by any other route. A persona block that no operation can
record is returned in :attr:`MaterialisedPersona.not_loaded` with its reason,
never written another way.

Every operation runs at the persona's scenario instant, including the
registration of the profile it runs against.
"""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import json
import logging
import re
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from enum import StrEnum
from functools import cache, partial
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final, cast, override
from uuid import UUID

from pydantic import BaseModel

from ...adapters.persistence.operations.journal import OperationJournalRepository
from ...adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ...adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ...adapters.persistence.operations.typed_financial_operand_custody import (
    OperationTypedFinancialOperandCustodyFilesystemRepository,
)
from ...adapters.persistence.profile.tests.sealed_profile_world import (
    SealedProfileWorld,
    copied_profile_world,
    derived_profile_world,
    sealed_profile_world,
)
from ...adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ...adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from ...adapters.persistence.storage.tests.profile_session_setup import reset_test_profile_session
from ...application.aggregation.invoice_retencion import InvoiceWithholdingEvidenceRequest
from ...application.aggregation.retenciones import Modelo180PropertyEvidence, Modelo180StructuredAddress
from ...application.aggregation.service import PerModeloAggregationCommand
from ...application.aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
)
from ...application.inventory.registered_evidence_operation import (
    INVENTORY_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
    InventoryEvidenceAddProjection,
    InventoryEvidenceAddRequest,
)
from ...application.inventory.registered_projections import (
    InventoryClosingAuthorityOperationProjection,
    InventoryCreateProjection,
)
from ...application.inventory.registered_requests import (
    INVENTORY_CLOSING_VALUE_RECORD_OPERATION_DEFINITION_ID,
    INVENTORY_CREATE_OPERATION_DEFINITION_ID,
    InventoryClosingValueFactsInput,
    InventoryClosingValueRecordRequest,
    InventoryCreateRequest,
)
from ...application.invoices.catalogue_add_contracts import (
    INVOICE_ADD_OPERATION_DEFINITION_ID,
    InvoiceAddRequest,
    InvoiceAddResult,
)
from ...application.ledger.actions_common import display_decimal
from ...application.ledger.actions_import import LedgerProviderID
from ...application.ledger.attachment_mutation_operation import (
    LEDGER_ATTACH_OPERATION_DEFINITION_ID,
    LedgerAttachRequest,
)
from ...application.ledger.classify_requests import (
    LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
    LedgerClassifyPatch,
    LedgerClassifyPatchField,
    LedgerClassifyRequest,
)
from ...application.ledger.counterparty_operation import (
    LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID,
    CounterpartyFilingNameRendering,
    LedgerCounterpartyRequest,
    LedgerCounterpartyResult,
)
from ...application.ledger.evidence_add_operation import (
    LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
    LedgerEvidenceAddProjection,
    LedgerEvidenceAddRequest,
)
from ...application.ledger.import_operation import (
    LEDGER_IMPORT_OPERATION_DEFINITION_ID,
    LedgerImportRequest,
    LedgerImportResultProjection,
)
from ...application.ledger.link_operation import LEDGER_LINK_OPERATION_DEFINITION_ID, LedgerLinkRequest
from ...application.ledger.update_contracts import (
    LEDGER_UPDATE_OPERATION_DEFINITION_ID,
    LedgerUpdatePatch,
    LedgerUpdateRequest,
)
from ...application.live.filed_single_capture_operation import (
    FILED_SINGLE_CAPTURE_DEFINITION_ID,
    FiledSingleCapturePublicResultV1,
    FiledSingleCaptureRequest,
)
from ...application.modelo.edit_operator_input import ModeloEditOperatorInputV2, prepare_modelo_edit_operand
from ...application.modelo.invoice_withholding_capture_contracts import (
    MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
    ModeloInvoiceWithholdingCaptureProjection,
    ModeloInvoiceWithholdingCaptureRequest,
)
from ...application.modelo.iva_wallet_override_operation import (
    MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID,
    ModeloIvaWalletOverrideRequest,
)
from ...application.modelo.iva_wallet_seed_operation import (
    MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
    ModeloIvaWalletSeedRequest,
)
from ...application.modelo.local_observation_contracts import (
    MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID,
    ModeloLocalObservationCasillaValue,
    ModeloLocalObservationMutationProjection,
    ModeloLocalObservationMutationRequest,
)
from ...application.modelo.m303_attestation_operation import (
    MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID,
    ModeloWorkM303AttestationPublicResultV2,
    ModeloWorkM303AttestationRequest,
)
from ...application.modelo.operation_shared import (
    MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
)
from ...application.modelo.work_calculation_contracts import (
    ModeloWorkCalculateOrdinaryM303EvidenceRequestV2,
    ModeloWorkCalculatePublicResultV3,
    ModeloWorkCalculateRequest,
)
from ...application.modelo.work_create_operation import (
    MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
    ModeloWorkCreateRequest,
    ModeloWorkCreateSuccess,
)
from ...application.modelo.work_filing_contracts import (
    ModeloWorkFileApproval,
    ModeloWorkFilePublicResultV2,
    ModeloWorkFileRequest,
)
from ...application.modelo.work_verification_contracts import ModeloWorkVerifyPublicResultV2, ModeloWorkVerifyRequest
from ...application.operations.composition import OperationComposedServices, compose_operation_services
from ...application.operations.error_detail import OperationErrorDetailV1, operation_error_detail_schema
from ...application.operations.frontend_projection import OperationPublicProjectionV1
from ...application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.models import OperationRequest
from ...application.operations.public_period import PublicPeriod
from ...application.operations.public_scalar import PublicDecimal
from ...application.operations.registry import OperationRegistry
from ...application.retencion_soportada_certificado.contracts import (
    RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID,
)
from ...application.retencion_soportada_certificado.requests import RetencionSoportadaRecordRequest
from ...application.retencion_soportada_certificado.results import RetencionSoportadaMutationProjection
from ...application.user_profile.ascendant_rows import ProfileAscendantFact, ProfileAscendantRow
from ...application.user_profile.custody_ports import profile_custody_secure_object_repository
from ...application.user_profile.descendant_rows import ProfileDescendantFact, ProfileDescendantRow
from ...application.user_profile.profile_operation_contracts import (
    PROFILE_ASCENDANTS_OPERATION_DEFINITION_ID,
    PROFILE_COMPLETE_SETUP_OPERATION_DEFINITION_ID,
    PROFILE_DESCENDANTS_OPERATION_DEFINITION_ID,
    PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
    PROFILE_PATCH_OPERATION_DEFINITION_ID,
    PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID,
    ProfileAscendantsOperationRequest,
    ProfileCompleteSetupOperationRequest,
    ProfileDescendantsOperationRequest,
    ProfileFieldMutationOperationRequest,
    ProfilePatchOperationRequest,
    ProfilePatchValue,
    ProfileRepeatableRowMutationOperationRequest,
    ProfileRepeatableRowValue,
)
from ...application.user_profile.profile_record_repository import ProfileRecordRepository
from ...application.user_profile.registration import create_registered_profile
from ...application.user_profile.validation import reject_invalid_profile_facts
from ...application.wizard.imputation_election import YEAR_QUESTION_ID
from ...core.aggregation import RetencionClave, RetencionScheme
from ...core.auth_provider import AuthProviderKind
from ...core.config import load_settings, override_settings
from ...core.logging import flush_logging
from ...core.operations import (
    TERMINAL_CONDITIONS_WITH_ERROR_DETAIL,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.period import Period
from ...core.retencion_soportada import RetencionSoportadaClase
from ...core.time.clock import frozen_clock, now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.withholding_bindings import WithholdingObservation
from ...domain.contribuyente.inventory.closing_foundations import (
    InventoryClosingAuthority,
    InventoryClosingDecisionEvidence,
    InventoryClosingDecisionEvidenceRole,
    PriorClosingContinuityEvidence,
)
from ...domain.filing_evidence import FilingEvidenceReference
from ...domain.iva.schema import InvoiceKind
from ...domain.renta.retencion_soportada import RetencionSoportadaOrigen
from ...domain.user_profile.errors import ProfileSchemaValidationError
from ...domain.user_profile.values import ProfileSetupState, UserProfileRecord, compose_legal_full_name
from ...tests.persona_invoices import render_facturae
from ...tests.personas import (
    AttestedPriorValue,
    CalculatedReturns,
    FiledReturns,
    HouseholdMember,
    IdentityRef,
    InventoryBook,
    LeasedPremises,
    LedgerRow,
    Persona,
    PersonaDate,
    PersonaDocument,
    ProfileValue,
    ProvisionPeriods,
    WithholdingCertificate,
    WorkIncomeNoneStatement,
    WorkInput,
    YearEnvelope,
    filed_period_order,
    governed_provisions,
    persona_inputs_digest,
    read_persona,
    values_in_force,
)
from ...tests.withholding_zero_blocks import zeroed_withholding_blocks
from ..ledger_action_composition import compose_ledger_action_ports
from ..operation_composition import build_production_operation_registry
from .persona_aeat_filings import PERSONA_AEAT_REGISTER, PERSONA_FILED_REGISTER, recorded_filing
from .persona_inventory_purchases import replay_inventory_purchases
from .persona_own_accounts import replay_own_accounts
from .persona_prior_values import (
    PriorValueAttestationError,
    attest_prior_values,
    attest_return_prior_values,
    check_prior_value_bindings,
    entries_on,
)
from .persona_rental_replay import replay_rentals
from .persona_work_income_statements import state_work_income_none
from .persona_work_inputs import WorkInputError, check_work_inputs, enter_work_inputs

PERSONA_ACTOR = "operator:persona"
"""The actor every replayed operation is submitted under."""

SCENARIO_TIME = time(9, 0, tzinfo=UTC)
"""The time of day of every persona's scenario instant; the date is the persona's ``[clock].as_of``."""

_PROFILE_CREDENTIAL = "persona-materialisation-passphrase"
_STATEMENT_HEADER = "Fecha operación;Fecha valor;Concepto;Importe;Saldo;Moneda;Referencia"


class PersonaMaterialisationError(RuntimeError):
    """A production operation refused a persona fact; the catalogue or the operation must change."""


class ReplayScope(StrEnum):
    """How much of a persona a replay records; each scope holds everything the narrower ones do."""

    PROFILE = "profile"
    """The wizard patch, its elections, the field mutations and the activity rows."""
    HOUSEHOLD = "household"
    """The profile scope and the descendant and ascendant replacements."""
    FULL = "full"
    """The household scope, the own bank accounts, the declared withholding, the statement import, invoices, evidence and inventory books."""
    RECORDS = "records"
    """The full scope, then the records the persona's returns read, without the returns.

    The local observations, the Modelo 303 compensation carried in, the rent
    and professional withholding and the returns filed with the AEAT are
    recorded; no return is created. A consumer that takes the persona's
    returns through their own operations, in order, replays this scope.
    """
    HISTORY = "history"
    """The full scope, then the persona's return history.

    The local observations are recorded and every rent payment on leased
    premises is captured as withholding; then every filed return is created,
    calculated, verified and filed locally, and every calculated return is
    created and calculated. Then every return the persona attests a prior value
    on that neither the history nor a stated value calculates is created and
    attested, which calculates it. Opt-in: a consumer that walks those periods
    itself replays the full scope.
    """

    def includes(self, other: ReplayScope) -> bool:
        """Whether replaying ``self`` records everything ``other`` does."""
        order = tuple(ReplayScope)
        return order.index(self) >= order.index(other)


@dataclass(frozen=True, slots=True)
class NotLoaded:
    """A persona block no production operation recorded, and why."""

    block: str
    reason: str


@dataclass(frozen=True, slots=True)
class PersonaWorld:
    """One registered, empty profile and the supervisor that runs operations against it."""

    profile_id: UUID
    storage_root: Path
    workdir: Path
    as_of: datetime
    envelope: YearEnvelope
    services: OperationComposedServices
    registry: OperationRegistry
    operation: PinnedAuthorityOperation
    attested_prior_values: tuple[AttestedPriorValue, ...] = ()
    """The persona's stated figures for earlier returns; :func:`run_operation` submits them after a calculation."""
    work_inputs: tuple[WorkInput, ...] = ()
    """The values the persona's operator enters on a return; :func:`run_operation` enters them before its first calculation."""
    work_income_none_statements: tuple[WorkIncomeNoneStatement, ...] = ()
    """The ejercicios whose unevidenced work income the persona states is none; submitted after a calculation."""


@dataclass(frozen=True, slots=True)
class MaterialisedPersona:
    """What replaying a persona left in its profile."""

    persona: Persona
    world: PersonaWorld
    scope: ReplayScope
    transactions: Mapping[str, str]
    """Ledger ``ref`` to the imported transaction id."""
    invoices: Mapping[str, str]
    """Ledger ``ref`` to the recorded and linked invoice id."""
    evidence: Mapping[str, str]
    """Document id to the stored evidence id."""
    not_loaded: tuple[NotLoaded, ...]
    """What no operation recorded, and ``setup`` when completing the setup was asked and the persona's answers refuse it."""
    filings: Mapping[str, str]
    """:func:`filing_key` of each return the history scope filed locally, to its filed calculation revision id."""
    calculations: Mapping[str, str]
    """:func:`filing_key` of each return the history scope calculated without filing, to its revision id."""


def year_envelope(operation: PinnedAuthorityOperation) -> YearEnvelope:
    """The registry's supported filing-year envelope, as the persona reader takes it.

    It carries the governed periods of every provision a persona's stated value is limited
    to, read from the legal register: absent a declared reach, the governed span is the
    provision's own in-force span.
    """
    support = operation.supported_filing_years()
    provisions: list[tuple[str, ProvisionPeriods]] = []
    for provision in sorted(governed_provisions()):
        reference = operation.legal_reference(provision)
        if reference.governs_periods_from is not None:
            periods = ProvisionPeriods(first=reference.governs_periods_from, last=reference.governs_periods_to)
        else:
            periods = ProvisionPeriods(first=reference.effective_from, last=reference.effective_to)
        provisions.append((provision, periods))
    return YearEnvelope(floor=support.floor, horizon=support.horizon, provisions=tuple(provisions))


def scenario_instant(persona: Persona, envelope: YearEnvelope) -> datetime:
    """The instant a persona's operations run at."""
    return datetime.combine(persona.as_of.resolve(envelope), SCENARIO_TIME)


@cache
def _registry() -> OperationRegistry:
    return build_production_operation_registry(filed_register=PERSONA_FILED_REGISTER)


def persona_profile_id(persona_id: str) -> UUID:
    """The profile identity every materialisation of the persona ``persona_id`` registers, on every run.

    A profile identity is a UUIDv4, so it is the version 4 UUID spelled by the digest of the persona id.
    """
    return UUID(bytes=hashlib.sha256(f"persona profile:{persona_id}".encode()).digest()[:16], version=4)


def _registered_world(persona: Persona, as_of: datetime) -> SealedProfileWorld:
    create_context, decode_context = profile_authority_contexts()
    profile_id = persona_profile_id(persona.id)

    def register() -> str:
        return create_registered_profile(
            profile_id=profile_id,
            label="persona",
            passphrase=_PROFILE_CREDENTIAL,
            profile_create_context=create_context,
            profile_decode_context=decode_context,
        ).profile_id

    key = ("persona world", str(profile_id), str(create_context.generation), as_of.isoformat())
    return sealed_profile_world(key, register)


@contextmanager
def _scenario(as_of: datetime) -> Generator[None]:
    """The clock and the sign-in provider every persona operation runs under."""
    with (
        frozen_clock(as_of),
        override_settings(cadrumo_auth_provider=AuthProviderKind.CERTIFICATE, cadrumo_certificate_path=None),
    ):
        yield


@contextmanager
def _operations_over(
    root: Path,
    profile_id: UUID,
    *,
    workdir: Path,
    as_of: datetime,
    envelope: YearEnvelope | None = None,
    attested_prior_values: tuple[AttestedPriorValue, ...] = (),
    work_inputs: tuple[WorkInput, ...] = (),
    work_income_none_statements: tuple[WorkIncomeNoneStatement, ...] = (),
) -> Generator[PersonaWorld]:
    """Compose a production supervisor over the profile already resumed in the isolated ``root``.

    ``envelope`` is the year envelope the persona was read under; the registry's own when omitted.
    ``attested_prior_values`` are the persona's stated figures for earlier returns,
    ``work_inputs`` the values its operator enters on a return, and
    ``work_income_none_statements`` the ejercicios whose unevidenced work income it states is none.
    """
    with (
        profile_custody_secure_object_repository(profile_id=profile_id, dek=b"", root=root) as objects,
        bundled_indexed_authority().operation() as operation,
    ):
        registry = _registry()
        journal = OperationJournalRepository(storage_root=root / "operations")
        operands = operation_secure_reference_repository(objects=cast(SecureObjectRepository, objects))
        services = compose_operation_services(
            registry=registry,
            authority_operation=operation,
            journal=journal,
            reader=journal,
            event_stream=journal,
            leases=OperationLeaseFilesystemRepository(storage_root=root / "operations"),
            operands=operands,
            owner_id="1" * 64,
            lease_token_factory=lambda: "2" * 64,
            clock=now,
            lease_duration=timedelta(minutes=10),
            execution_timeout=timedelta(hours=1),
            cleanup_timeout=timedelta(minutes=2),
            typed_financial_operand_custody=OperationTypedFinancialOperandCustodyFilesystemRepository(
                root=root / "operations" / "typed_financial_operand_custody",
            ),
        )
        workdir.mkdir(parents=True, exist_ok=True)
        try:
            yield PersonaWorld(
                profile_id=profile_id,
                storage_root=root,
                workdir=workdir,
                as_of=as_of,
                envelope=year_envelope(operation) if envelope is None else envelope,
                services=services,
                registry=registry,
                operation=operation,
                attested_prior_values=attested_prior_values,
                work_inputs=work_inputs,
                work_income_none_statements=work_income_none_statements,
            )
        finally:
            asyncio.run(services.shutdown())


@contextmanager
def persona_world(
    tmp_path: Path, persona: Persona, *, as_of: datetime, envelope: YearEnvelope | None = None
) -> Generator[PersonaWorld]:
    """Open ``persona``'s registered empty profile and a production supervisor over it, frozen at ``as_of``."""
    with bundled_indexed_authority().operation(), _scenario(as_of):
        _create_context, decode_context = profile_authority_contexts()
        world = _registered_world(persona, as_of)
        with copied_profile_world(world, tmp_path / "runtime", profile_decode_context=decode_context) as (
            root,
            profile_id,
        ):
            try:
                with _operations_over(
                    root,
                    profile_id,
                    workdir=tmp_path / "inputs",
                    as_of=as_of,
                    envelope=envelope,
                    attested_prior_values=persona.attested_prior_values,
                    work_inputs=persona.work_inputs,
                    work_income_none_statements=persona.work_income_none_statements,
                ) as opened:
                    yield opened
            finally:
                reset_test_profile_session()


# -- one settled operation -----------------------------------------------------------------------------------------


def settle_operation(
    world: PersonaWorld,
    definition_id: str,
    payload: BaseModel,
    *,
    subject: str | None = None,
) -> BaseModel | None:
    """Submit one registered operation, settle it, refuse anything but success, and return its public result.

    The operation addresses the profile unless ``subject`` names another subject, such as a work unit.
    A declaration edit travels as the window's volatile operator input: the
    operation is admitted on its amount-free request, then receives the staged
    intents as its financial operand.
    """
    subject_ref = subject or profile_operation_subject(str(world.profile_id))

    async def settle() -> OperationPublicProjectionV1:
        services = world.services
        if not isinstance(payload, ModeloEditOperatorInputV2):
            submitted = await services.submission.submit(
                OperationRequest(definition_id=definition_id, subject_ref=subject_ref, payload=payload),
                actor_ref=PERSONA_ACTOR,
            )
        else:
            prepared = prepare_modelo_edit_operand(
                definition_id=definition_id,
                profile_id=world.profile_id,
                subject_ref=subject_ref,
                input_json=payload.model_dump_json(),
            )
            try:
                submitted = await services.submission.submit(
                    OperationRequest(definition_id=definition_id, subject_ref=subject_ref, payload=prepared.request),
                    actor_ref=PERSONA_ACTOR,
                )
                if prepared.operand is None:
                    raise PersonaMaterialisationError(f"{definition_id} prepared no edit operand")
                await services.submission.supervisor.bind_typed_financial_operand(
                    submitted.receipt.operation_id, prepared.operand
                )
            finally:
                prepared.release()
        operation_id = submitted.receipt.operation_id
        await services.submission.start(operation_id)
        await services.submission.settled(operation_id)
        observed = await services.observation.observe(
            OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=256)
        )
        if not isinstance(observed, OperationObservationSuccessV1):
            raise PersonaMaterialisationError(f"{definition_id} could not be observed")
        return observed.projection

    with _failure_frames() as failures:
        terminal = asyncio.run(settle())
    result = public_result(world, terminal)
    if terminal.terminal_condition is not OperationTerminalCondition.SUCCEEDED:
        # A refusal names its registered code through its refusal reference; only a failure has an error code.
        code = (
            terminal.refusal_ref
            if terminal.terminal_condition is OperationTerminalCondition.REFUSED
            else terminal.failure_error_code
        )
        detail = _served_words(world, terminal)
        if detail is None and result is not None:
            # A refusal a definition records as its own typed result carries its sentence in that result.
            detail = _result_words(result.model_dump(mode="json", exclude={"profile_id"}))
            detail = result.model_dump_json(exclude={"profile_id"}) if detail is None else detail
        if detail is None:
            detail = failures.frames.get(str(terminal.operation_id), "no detail")
        raise PersonaMaterialisationError(f"{definition_id} settled {terminal.terminal_condition} ({code}): {detail}")
    return result


_EXECUTOR_LOGGER: Final[str] = "cadrumo.application.operations.supervisor_execution"
"""The logger the supervisor names a failed operation's exception type and code frames on."""
_FAILURE_RECORD: Final[re.Pattern[str]] = re.compile(
    r"^operation failed definition=\S+ operation=(?P<operation>\S+) diagnostic_ref=\S+ "
    r"exception_type=(?P<type>\S+) raising_frame=(?P<raising>\S+) application_frame=(?P<application>\S+)"
)


class _FailureFrames(logging.Handler):
    """Collect, per operation id, the exception type and code frames the supervisor logs for a failure.

    A failed operation serves no sentence and keeps its exception message out of every record by design, so
    these code coordinates are what makes a failure without a refusal code diagnosable from the table. The
    application delivers records to handlers formatted, on its dispatch thread, so the handler reads the
    formatted message and the caller flushes the dispatch before reading the frames.
    """

    def __init__(self) -> None:
        super().__init__(logging.ERROR)
        self.frames: dict[str, str] = {}

    @override
    def emit(self, record: logging.LogRecord) -> None:
        found = _FAILURE_RECORD.match(record.getMessage())
        if found is None:
            return
        self.frames[found["operation"]] = (
            f"{found['type']} raised at {found['raising']} (application frame {found['application']})"
        )


@contextmanager
def _failure_frames() -> Generator[_FailureFrames]:
    handler = _FailureFrames()
    logger = logging.getLogger(_EXECUTOR_LOGGER)
    logger.addHandler(handler)
    try:
        yield handler
        flush_logging()
    finally:
        logger.removeHandler(handler)


def _result_words(value: object) -> str | None:
    """The ``refusal_words`` sentence a typed refusal result carries, on one line, wherever it nests."""
    if isinstance(value, Mapping):
        words = str(value.get("refusal_words") or "")
        if words.strip():
            return " ".join(words.split())
        children: Sequence[object] = tuple(value.values())
    elif isinstance(value, list | tuple):
        children = value
    else:
        return None
    found: str | None = None
    for child in children:
        found = _result_words(child)
        if found is not None:
            break
    return found


def _served_words(world: PersonaWorld, terminal: OperationPublicProjectionV1) -> str | None:
    """The sentence the application serves an operator for a refused or failed operation, on one line.

    This reads the recorded error detail through the settled-result read, as the command line and the
    workbench do, so the words are those a frontend shows. ``None`` when the operation recorded none.
    """
    if terminal.terminal_condition not in TERMINAL_CONDITIONS_WITH_ERROR_DETAIL:
        return None
    contract = terminal.definition_contract
    resolved = asyncio.run(
        world.services.result.resolve(
            OperationResultProjectionRequestV1(
                operation_id=terminal.operation_id,
                terminal_revision=terminal.revision,
                definition_contract_digest=contract.definition_contract_digest,
                result_schema=operation_error_detail_schema(),
            ),
            OperationErrorDetailV1,
        )
    )
    if not isinstance(resolved, OperationResultProjectionSuccessV1):
        return None
    words = resolved.projection.refusal_words if isinstance(resolved.projection, OperationErrorDetailV1) else None
    return None if words is None else " ".join(words.split())


def run_operation[Projection: BaseModel](
    world: PersonaWorld,
    definition_id: str,
    payload: BaseModel,
    projection: type[Projection],
    *,
    subject: str | None = None,
) -> Projection:
    """Settle one registered operation and return its public result as ``projection``.

    A calculation of a return the persona gives values for is preceded, on its first
    calculation, by their entry through the declaration edit, as an operator enters them.
    A calculation of a return the persona states a prior value for is followed by the
    attestation of that value, where the application offers it, and calculated again so
    the result reads the stated figure.
    """
    if isinstance(payload, ModeloWorkCalculateRequest) and world.work_inputs:
        enter_return_work_inputs(world, payload.work_unit_id)
    result = settle_operation(world, definition_id, payload, subject=subject)
    if not isinstance(result, projection):
        raise PersonaMaterialisationError(f"{definition_id} published no {projection.__name__}")
    if isinstance(payload, ModeloWorkCalculateRequest) and isinstance(result, ModeloWorkCalculatePublicResultV3):
        result = _with_attested_prior_values(world, definition_id, payload, result, subject=subject)
        if not isinstance(result, projection):
            raise PersonaMaterialisationError(f"{definition_id} published no {projection.__name__}")
    return result


def attested_before_calculating(world: PersonaWorld, *, modelo: str, year: int, period: str) -> bool:
    """Whether the return's attested prior figures are stated before its first calculation.

    So they are for a return the persona attests figures on and enters no work input on: its calculation refuses
    while a required source return is neither held nor stated. A return with work inputs keeps the order an operator
    follows: its inputs are entered when it is first calculated, and its attestations follow that calculation.
    """
    if not entries_on(world.attested_prior_values, world.envelope, modelo=modelo, filing_year=year, period=period):
        return False
    return not any(
        item.modelo == modelo and item.period == period and item.year.resolve(world.envelope) == year
        for item in world.work_inputs
    )


def attest_before_first_calculation(
    world: PersonaWorld, *, modelo: str, year: int, period: str, work_unit_id: str
) -> None:
    """State the return's attested prior figures on its work unit before its first calculation, where they are so stated.

    An entry the admitted baseline does not offer the attestation on is not submitted, as after a calculation: the
    application then reads the figure from a source it holds, such as an earlier quarter of the same year, and that
    source governs. Every attested binding is one its edition declares (``check_prior_value_bindings``), so an
    unoffered entry cannot hide a binding the edition lacks.
    """
    if not attested_before_calculating(world, modelo=modelo, year=year, period=period):
        return

    def settle(definition_id: str, payload: BaseModel, *, subject: str | None = None) -> BaseModel | None:
        return settle_operation(world, definition_id, payload, subject=subject)

    try:
        attest_return_prior_values(
            world.attested_prior_values,
            envelope=world.envelope,
            profile_id=world.profile_id,
            work_unit_id=work_unit_id,
            modelo=modelo,
            filing_year=year,
            period=period,
            settle=settle,
        )
    except PriorValueAttestationError as error:
        raise PersonaMaterialisationError(f"{modelo} {year} {period}: {error}") from error


def enter_return_work_inputs(world: PersonaWorld, work_unit_id: str) -> None:
    """Enter the values the persona gives for the work unit's return, before its first calculation."""

    def settle(definition_id: str, payload: BaseModel, *, subject: str | None = None) -> BaseModel | None:
        return settle_operation(world, definition_id, payload, subject=subject)

    try:
        enter_work_inputs(
            world.work_inputs,
            envelope=world.envelope,
            operation=world.operation,
            profile_id=world.profile_id,
            work_unit_id=work_unit_id,
            settle=settle,
        )
    except WorkInputError as error:
        raise PersonaMaterialisationError(str(error)) from error


def _with_attested_prior_values(
    world: PersonaWorld,
    definition_id: str,
    payload: ModeloWorkCalculateRequest,
    calculated: ModeloWorkCalculatePublicResultV3,
    *,
    subject: str | None,
) -> BaseModel:
    """``calculated``, or its calculation again once the persona's stated prior values and work-income statements are made."""
    if not state_after_calculation(world, calculated):
        return calculated
    recalculated = settle_operation(world, definition_id, payload, subject=subject)
    if not isinstance(recalculated, ModeloWorkCalculatePublicResultV3):
        raise PersonaMaterialisationError(f"{definition_id} published no calculation after the attestation")
    return recalculated


def state_after_calculation(world: PersonaWorld, calculated: ModeloWorkCalculatePublicResultV3) -> bool:
    """Make the persona's stated prior values and work-income statements the calculation offers; whether any was made.

    A calculation that made one must be calculated again to read the stated figure.
    """

    def settle(
        definition_id: str,
        payload: BaseModel,
        *,
        subject: str | None = None,
    ) -> BaseModel | None:
        return settle_operation(world, definition_id, payload, subject=subject)

    try:
        attested = attest_prior_values(
            world.attested_prior_values,
            envelope=world.envelope,
            profile_id=world.profile_id,
            calculated=calculated,
            settle=settle,
        )
        stated = state_work_income_none(
            world.work_income_none_statements,
            envelope=world.envelope,
            profile_id=world.profile_id,
            calculated=calculated,
            settle=settle,
        )
    except PriorValueAttestationError as error:
        raise PersonaMaterialisationError(str(error)) from error
    return bool(attested or stated)


def public_result(world: PersonaWorld, terminal: OperationPublicProjectionV1) -> BaseModel | None:
    """The public result, or refusal detail, a settled operation publishes, in its registered model."""
    contract = terminal.definition_contract
    if contract.result_schema is None or (terminal.result_ref is None and terminal.refusal_ref is None):
        return None
    registration = world.registry.lookup_public_registration(terminal.definition_id)
    (model,) = (
        binding.model_type for binding in registration.schema_bindings if binding.identity == contract.result_schema
    )
    resolved = asyncio.run(
        world.services.result.resolve(
            OperationResultProjectionRequestV1(
                operation_id=terminal.operation_id,
                terminal_revision=terminal.revision,
                definition_contract_digest=contract.definition_contract_digest,
                result_schema=contract.result_schema,
            ),
            model,
        )
    )
    if not isinstance(resolved, OperationResultProjectionSuccessV1):
        return None
    projection = resolved.projection
    return projection if isinstance(projection, BaseModel) else None


def load_profile_record(world: PersonaWorld) -> UserProfileRecord:
    """Read the profile's current record, which every profile mutation names as its baseline."""
    return ProfileRecordRepository.for_current_session(
        world.profile_id, profile_decode_context=world.operation.profile_decode_context()
    ).load(world.profile_id)


# -- persona values as operations take them ------------------------------------------------------------------------


def submitted_answer(persona: Persona, value: ProfileValue, envelope: YearEnvelope) -> str:
    """Render one ``[profile]`` value as the profile patch takes it, as the catalogue README states."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    if isinstance(value, tuple):
        return ",".join(value)
    if isinstance(value, IdentityRef):
        return identity_text(persona, value)
    return value.resolve(envelope).isoformat()


def identity_text(persona: Persona, reference: IdentityRef) -> str:
    """One identity field as an operation takes it; ``full_name`` is the official surnames-first name or razón social."""
    if reference.field != "full_name":
        return persona.identity(reference)
    holder = persona.identities.role(reference.role)
    if holder.legal_name is not None:
        return holder.legal_name
    if holder.surnames is None or holder.name is None:
        raise PersonaMaterialisationError(f"identity {reference.role} carries no name to compose")
    return compose_legal_full_name(surnames=holder.surnames, name=holder.name)


def patch_answers(persona: Persona, envelope: YearEnvelope) -> tuple[tuple[str, str], ...]:
    """Every wizard answer the persona's patch submits: its ``[profile]`` answers, then its elections and their year."""
    answers = [(answer.question_id, submitted_answer(persona, answer.value, envelope)) for answer in persona.profile]
    years = {str(election.year.resolve(envelope)) for election in persona.elections}
    if len(years) > 1:
        raise PersonaMaterialisationError(f"{persona.id}: one patch states one election year, found {sorted(years)}")
    answers.extend((election.question, election.value) for election in persona.elections)
    answers.extend((YEAR_QUESTION_ID, year) for year in years)
    return tuple(answers)


def household_leaves(persona: Persona, member: HouseholdMember, envelope: YearEnvelope) -> tuple[tuple[str, str], ...]:
    """One household row as the operations take it: its identity's NIF and its surnames-first name."""
    leaves = [
        (key, value.resolve(envelope).isoformat() if isinstance(value, PersonaDate) else value)
        for key, value in member.leaves
    ]
    if member.identity is not None:
        person = persona.identities.role(member.identity)
        leaves.append(("nif", person.value))
        if person.name is not None and person.surnames is not None:
            leaves.append(("apellidos_nombre", compose_legal_full_name(surnames=person.surnames, name=person.name)))
    return tuple(leaves)


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def bank_statement(rows: Sequence[LedgerRow], envelope: YearEnvelope) -> str:
    """Bank movements in the statement columns ``app ledger import --file`` reads."""
    lines = [_STATEMENT_HEADER]
    balance = Decimal("0.00")
    for row in sorted(rows, key=lambda item: item.operation_date(envelope)):
        balance += row.amount
        day = row.operation_date(envelope).strftime("%d/%m/%Y")
        lines.append(
            ";".join(
                (
                    day,
                    day,
                    row.description,
                    _decimal_text(row.amount).replace(".", ","),
                    _decimal_text(balance).replace(".", ","),
                    row.currency,
                    row.ref,
                )
            )
        )
    return "\n".join(lines) + "\n"


def classify_patch(
    persona: Persona, row: LedgerRow
) -> tuple[LedgerClassifyPatch, tuple[LedgerClassifyPatchField, ...]]:
    values: dict[LedgerClassifyPatchField, str] = {"business_classification": row.classification}
    counterparty = None if row.counterparty is None else persona.identities.role(row.counterparty)
    if counterparty is not None and counterparty.country is not None:
        values["counterparty_country"] = counterparty.country
    optional: tuple[tuple[LedgerClassifyPatchField, str | Decimal | None], ...] = (
        ("category_id", row.category_id),
        ("irpf_category", row.irpf_category),
        ("iva_category", row.iva_category),
        ("taxable_base", row.taxable_base),
        ("iva_rate", row.iva_rate),
        ("iva_amount", row.iva_amount),
        ("recargo_amount", row.recargo_amount),
        ("deduction_fact_kind", row.deduction_kind),
    )
    for field, value in optional:
        if value is not None:
            values[field] = display_decimal(value) if isinstance(value, Decimal) else value
    return LedgerClassifyPatch.model_validate(values), tuple(sorted(values))


def _public_decimal(value: Decimal | None) -> PublicDecimal | None:
    return None if value is None else PublicDecimal(decimal=str(value))


def _public_percentage(fraction: Decimal | None) -> PublicDecimal | None:
    """A ledger fraction as the invoice operation takes a rate: a percentage."""
    return None if fraction is None else PublicDecimal(decimal=str(fraction * 100))


def party_name(persona: Persona, role: str) -> str:
    counterparty = persona.identities.role(role)
    return counterparty.razon_social or f"{counterparty.field('nombre')} {counterparty.field('surnames')}"


INFORMATIVE_MODELOS: Final = frozenset({"347", "349", "180", "190", "193"})
"""The informative returns whose design names a third party by its filing name."""


def informative_party_roles(persona: Persona) -> tuple[str, ...]:
    """The roles of the third parties the persona's informative returns name, in first-named order.

    A persona that files none of :data:`INFORMATIVE_MODELOS` names no party. Otherwise the counterparty
    of every ledger row is a declarado, operador or perceptor, and the landlord of leased premises is
    the perceptor of the Modelo 180. The payer of a withholding certificate is the taxpayer's source
    of income on the Modelo 100, not a party an informative return names.
    """
    if INFORMATIVE_MODELOS.isdisjoint(persona.modelos):
        return ()
    payers = {certificate.payer for certificate in persona.withholding_certificates}
    roles: dict[str, None] = {}
    for row in persona.ledger:
        if row.counterparty is not None and row.counterparty not in payers:
            roles[row.counterparty] = None
    for premises in persona.leased_premises:
        roles[premises.landlord] = None
    return tuple(roles)


def _filing_name_request(persona: Persona, role: str, world: PersonaWorld) -> LedgerCounterpartyRequest:
    """The statement of one party's filing name, in the identity's own words and order."""
    party = persona.identities.role(role)
    stated: dict[str, object]
    if party.is_entity:
        stated = {"party_kind": "entity", "razon_social": party.razon_social}
    else:
        stated = {
            "party_kind": "natural_person",
            "primer_apellido": party.primer_apellido,
            "segundo_apellido": party.segundo_apellido,
            "no_second_surname": party.no_second_surname,
            "nombre": party.nombre,
        }
    return LedgerCounterpartyRequest.model_validate(
        {
            "profile_id": world.profile_id,
            "action": "filing_name",
            "tax_identifier": party.value,
            "country_code": party.country,
            "asserted_by": PERSONA_ACTOR,
            "renderings": tuple(
                CounterpartyFilingNameRendering(width=width, text=text) for width, text in party.renderings
            ),
            **stated,
        }
    )


def _state_filing_names(persona: Persona, world: PersonaWorld) -> None:
    """State each informative-return party's filing name through the registered counterparty operation."""
    for role in informative_party_roles(persona):
        result = run_operation(
            world,
            LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID,
            _filing_name_request(persona, role, world),
            LedgerCounterpartyResult,
        )
        if result.filing_name is None or result.recorded is not True:
            raise PersonaMaterialisationError(f"{persona.id} {role}: the filing name was not recorded")


def _invoice_request(persona: Persona, row: LedgerRow, world: PersonaWorld) -> InvoiceAddRequest | None:
    """The invoice behind a row as ``ledger invoice add`` records it; ``None`` for a row no invoice backs."""
    if row.invoice_kind is None or row.invoice_number is None:
        return None
    if row.counterparty is None:
        raise PersonaMaterialisationError(f"{persona.id} {row.ref}: an invoice names its counterparty")
    counterparty = persona.identities.role(row.counterparty)
    name = party_name(persona, row.counterparty)
    return InvoiceAddRequest(
        profile_id=world.profile_id,
        kind=InvoiceKind(row.invoice_kind),
        counterparty_name=name,
        counterparty_tax_id=counterparty.value,
        counterparty_country=counterparty.country or "ES",
        invoice_number=row.invoice_number,
        issued_at=row.operation_date(world.envelope),
        taxable_base=_public_decimal(row.taxable_base),
        iva_rate=_public_percentage(row.iva_rate),
        currency=row.currency,
        iva_category=row.iva_category,
        retention_rate=_public_decimal(row.retencion_rate),
        retention_amount=_public_decimal(row.retencion_amount),
        recargo_amount=_public_decimal(row.recargo_amount),
    )


# -- replay --------------------------------------------------------------------------------------------------------


def _replay_profile(persona: Persona, world: PersonaWorld) -> None:
    envelope = world.envelope
    record = load_profile_record(world)
    settle_operation(
        world,
        PROFILE_PATCH_OPERATION_DEFINITION_ID,
        ProfilePatchOperationRequest(
            profile_id=world.profile_id,
            expected_revision=record.record_revision,
            expected_content_digest=record.content_digest,
            values=tuple(
                ProfilePatchValue(question_id=question_id, value=value)
                for question_id, value in patch_answers(persona, envelope)
            ),
        ),
    )
    for field in persona.fields:
        record = load_profile_record(world)
        settle_operation(
            world,
            PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
            ProfileFieldMutationOperationRequest(
                profile_id=world.profile_id,
                expected_revision=record.record_revision,
                expected_content_digest=record.content_digest,
                path=field.path,
                value=field.value,
            ),
        )
    for activity in persona.activities:
        record = load_profile_record(world)
        settle_operation(
            world,
            PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID,
            ProfileRepeatableRowMutationOperationRequest(
                profile_id=world.profile_id,
                expected_revision=record.record_revision,
                expected_content_digest=record.content_digest,
                section_key="activities",
                values=tuple(ProfileRepeatableRowValue(field_key=key, value=value) for key, value in activity.values),
            ),
        )
    for row in persona.profile_rows:
        record = load_profile_record(world)
        settle_operation(
            world,
            PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID,
            ProfileRepeatableRowMutationOperationRequest(
                profile_id=world.profile_id,
                expected_revision=record.record_revision,
                expected_content_digest=record.content_digest,
                section_key=row.section,
                values=tuple(
                    ProfileRepeatableRowValue(field_key=key, value=submitted_answer(persona, value, envelope))
                    for key, value in row.values
                ),
            ),
        )


def _replay_household(persona: Persona, world: PersonaWorld) -> None:
    """Replace each household family the persona states; a family it states as empty declares it has none."""
    envelope = world.envelope
    if "descendants" in persona.household_families:
        record = load_profile_record(world)
        settle_operation(
            world,
            PROFILE_DESCENDANTS_OPERATION_DEFINITION_ID,
            ProfileDescendantsOperationRequest(
                profile_id=world.profile_id,
                expected_revision=record.record_revision,
                expected_content_digest=record.content_digest,
                descendants=tuple(
                    ProfileDescendantRow(
                        facts=tuple(
                            ProfileDescendantFact(field_key=key, value=value)
                            for key, value in household_leaves(persona, member, envelope)
                        )
                    )
                    for member in persona.descendants
                ),
            ),
        )
    if "ascendants" in persona.household_families:
        record = load_profile_record(world)
        settle_operation(
            world,
            PROFILE_ASCENDANTS_OPERATION_DEFINITION_ID,
            ProfileAscendantsOperationRequest(
                profile_id=world.profile_id,
                expected_revision=record.record_revision,
                expected_content_digest=record.content_digest,
                ascendants=tuple(
                    ProfileAscendantRow(
                        facts=tuple(
                            ProfileAscendantFact(field_key=key, value=value)
                            for key, value in household_leaves(persona, member, envelope)
                        )
                    )
                    for member in persona.ascendants
                ),
            ),
        )


def declared_withholding(persona: Persona) -> list[WithholdingCertificate]:
    """The certificates the record operation takes: those the taxpayer declares, which need no certificate bytes."""
    return [item for item in persona.withholding_certificates if item.origin == "operator_declaration"]


def _stated_figure(figure: Decimal | None) -> PublicDecimal | None:
    return None if figure is None else PublicDecimal(decimal=str(figure))


def _replay_withholding(persona: Persona, world: PersonaWorld) -> None:
    zero = PublicDecimal(decimal="0.00")
    for certificate in declared_withholding(persona):
        payer = persona.identities.role(certificate.payer)
        recorded = run_operation(
            world,
            RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID,
            RetencionSoportadaRecordRequest(
                profile_id=world.profile_id,
                ejercicio=certificate.ejercicio.resolve(world.envelope),
                income_class=RetencionSoportadaClase(certificate.income_class),
                payer_tax_id=payer.value,
                payer_legal_name=party_name(persona, certificate.payer),
                importe_integro_dinerario=PublicDecimal(decimal=str(certificate.importe_integro)),
                valoracion_especie=zero,
                retencion=PublicDecimal(decimal=str(certificate.retencion)),
                ingreso_a_cuenta=zero,
                ingreso_a_cuenta_repercutido=zero,
                reducciones_aplicables=_stated_figure(certificate.reducciones_aplicables),
                gastos_deducibles=_stated_figure(certificate.gastos_deducibles),
                origin=RetencionSoportadaOrigen.OPERATOR_DECLARATION,
            ),
            RetencionSoportadaMutationProjection,
        )
        if recorded.outcome != "recorded":
            raise PersonaMaterialisationError(f"{persona.id} {certificate.payer}: {recorded.refusal}")


def _imported_transactions(persona: Persona, world: PersonaWorld) -> dict[str, str]:
    """Import the statement and map each ledger ref to the transaction it became."""
    rows = persona.ledger
    statement = world.workdir / f"{persona.id}-statement.csv"
    statement.write_text(bank_statement(rows, world.envelope), encoding="utf-8", newline="\n")
    result = run_operation(
        world,
        LEDGER_IMPORT_OPERATION_DEFINITION_ID,
        LedgerImportRequest(profile_id=world.profile_id, files=(statement,), provider=LedgerProviderID.CSV),
        LedgerImportResultProjection,
    )
    if result.imported != len(rows) or result.refused_files:
        raise PersonaMaterialisationError(
            f"{persona.id}: imported {result.imported} of {len(rows)} rows, refused {result.refused_files}"
        )
    stored = compose_ledger_action_ports(
        bucket_id=str(world.profile_id), operation=world.operation
    ).transaction_repository.load()
    refs = {row.ref for row in rows}
    by_ref = {
        transaction.raw.provider_transaction_id: transaction_id
        for transaction_id, transaction in stored.transactions.items()
        if transaction.raw.provider_transaction_id in refs
    }
    if set(by_ref) != refs:
        raise PersonaMaterialisationError(f"{persona.id}: refs not carried by the import: {sorted(refs - set(by_ref))}")
    return by_ref


def _replay_ledger(persona: Persona, world: PersonaWorld, transactions: Mapping[str, str]) -> dict[str, str]:
    """Classify every row, then record each row's invoice and link it; returns ledger ref to invoice id."""
    for row in persona.ledger:
        patch, fields = classify_patch(persona, row)
        settle_operation(
            world,
            LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
            LedgerClassifyRequest(
                profile_id=world.profile_id,
                transaction_id=transactions[row.ref],
                patch=patch,
                patch_fields=fields,
                actor=PERSONA_ACTOR,
            ),
        )
        if (accrued_on := row.accrual_date(world.envelope)) is not None:
            settle_operation(
                world,
                LEDGER_UPDATE_OPERATION_DEFINITION_ID,
                LedgerUpdateRequest(
                    profile_id=world.profile_id,
                    transaction_id=transactions[row.ref],
                    patch=LedgerUpdatePatch(accrual_date=accrued_on.isoformat()),
                    patch_fields=("accrual_date",),
                    actor=PERSONA_ACTOR,
                ),
            )
    invoices: dict[str, str] = {}
    for row in persona.ledger:
        request = _invoice_request(persona, row, world)
        if request is None:
            continue
        added = run_operation(world, INVOICE_ADD_OPERATION_DEFINITION_ID, request, InvoiceAddResult)
        if added.invoice is None:
            raise PersonaMaterialisationError(f"{persona.id} {row.ref}: no invoice was created")
        invoices[row.ref] = added.invoice.invoice_id
        settle_operation(
            world,
            LEDGER_LINK_OPERATION_DEFINITION_ID,
            LedgerLinkRequest(
                profile_id=world.profile_id,
                transaction_id=transactions[row.ref],
                invoice_id=added.invoice.invoice_id,
                actor=PERSONA_ACTOR,
            ),
        )
    return invoices


def document_path(persona: Persona, document: PersonaDocument, *, envelope: YearEnvelope, workdir: Path) -> Path:
    """The file evidence intake reads: the specimen itself, or the generated invoice written to the workdir."""
    if document.path is not None:
        return document.path
    generated = render_facturae(persona, document, envelope)
    target = workdir / "documents" / generated.file_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(generated.text, encoding="utf-8", newline="\n")
    return target


def _replay_documents(persona: Persona, world: PersonaWorld, transactions: Mapping[str, str]) -> dict[str, str]:
    evidence: dict[str, str] = {}
    for document in persona.documents:
        source = document_path(persona, document, envelope=world.envelope, workdir=world.workdir)
        added = run_operation(
            world,
            LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
            LedgerEvidenceAddRequest(
                profile_id=world.profile_id,
                source_path=str(source),
                source_directory=str(source.parent),
                notes=f"persona {persona.id} document {document.id} ({document.relation})",
                idempotency_key=f"persona-{persona.id}-{document.id}",
            ),
            LedgerEvidenceAddProjection,
        )
        evidence[document.id] = added.record.evidence_id
        for ref in document.attach_to:
            settle_operation(
                world,
                LEDGER_ATTACH_OPERATION_DEFINITION_ID,
                LedgerAttachRequest(
                    profile_id=world.profile_id,
                    transaction_id=transactions[ref],
                    purchase_invoice_evidence_id=added.record.evidence_id,
                    actor=PERSONA_ACTOR,
                ),
            )
    return evidence


def inventory_statement(persona: Persona, book: InventoryBook, *, envelope: YearEnvelope, workdir: Path) -> Path:
    """The taxpayer's statement behind one inventory book, written to the workdir as the PDF evidence intake keeps."""
    year = book.year.resolve(envelope)
    target = workdir / "inventory" / f"{persona.id}-{book.activity}-{year}.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(f"%PDF-1.4\n% {book.statement} ({year})\n%%EOF\n".encode())
    return target


def _replay_inventory(persona: Persona, world: PersonaWorld, transactions: Mapping[str, str]) -> None:
    """Open each inventory book, add its purchases, and record its closing on its movements, evidenced by the statement.

    Each purchase claims the ledger row that books it, and rests on the invoice
    attached to that row. The statement also evidences the prior year's closing
    the opening continues from, since no earlier book holds one.
    """
    for book in persona.inventory:
        year = book.year.resolve(world.envelope)
        where = f"{persona.id} inventory {book.activity} {year}"
        created = run_operation(
            world,
            INVENTORY_CREATE_OPERATION_DEFINITION_ID,
            InventoryCreateRequest(
                profile_id=world.profile_id,
                actividad_id=book.activity,
                year=year,
                valuation_method=book.valuation_method,
                opening_stock=PublicDecimal(decimal=_decimal_text(book.opening_stock)),
            ),
            InventoryCreateProjection,
        )
        if created.outcome != "created":
            raise PersonaMaterialisationError(f"{where}: create refused: {created.model_dump_json()}")
        replay_inventory_purchases(
            persona,
            book,
            year=year,
            profile_id=world.profile_id,
            workdir=world.workdir,
            transactions=transactions,
            invoice_source=lambda ref: document_path(
                persona,
                next(document for document in persona.documents if ref in document.attach_to),
                envelope=world.envelope,
                workdir=world.workdir,
            ),
            settle=partial(settle_operation, world),
        )
        source = inventory_statement(persona, book, envelope=world.envelope, workdir=world.workdir)
        stored = run_operation(
            world,
            INVENTORY_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
            InventoryEvidenceAddRequest(
                profile_id=world.profile_id, source_path=str(source), source_directory=str(source.parent)
            ),
            InventoryEvidenceAddProjection,
        )
        if stored.reference is None or stored.content_digest is None:
            raise PersonaMaterialisationError(f"{where}: statement refused: {stored.model_dump_json()}")
        reference = FilingEvidenceReference(reference=stored.reference)
        recorded = run_operation(
            world,
            INVENTORY_CLOSING_VALUE_RECORD_OPERATION_DEFINITION_ID,
            InventoryClosingValueRecordRequest(
                profile_id=world.profile_id,
                actividad_id=book.activity,
                year=year,
                facts=InventoryClosingValueFactsInput(
                    decision_id=f"persona-{book.activity}-{year}",
                    authority=InventoryClosingAuthority.MOVEMENT_DERIVED,
                    reason=book.statement,
                    decision_evidence=(
                        InventoryClosingDecisionEvidence(
                            reference=reference,
                            role=InventoryClosingDecisionEvidenceRole.AUTHORITY_RECONCILIATION,
                            content_digest=stored.content_digest,
                        ),
                    ),
                    prior_evidence=(
                        PriorClosingContinuityEvidence(reference=reference, content_digest=stored.content_digest),
                    ),
                ),
            ),
            InventoryClosingAuthorityOperationProjection,
        )
        if recorded.outcome != "recorded":
            raise PersonaMaterialisationError(f"{where}: closing refused: {recorded.model_dump_json()}")


def filing_key(modelo: str, year: int, period: str) -> str:
    """The key :attr:`MaterialisedPersona.filings` and :attr:`MaterialisedPersona.calculations` name one return by."""
    return f"{modelo}:{year}:{period}"


def history_periods(
    persona: Persona, envelope: YearEnvelope
) -> list[tuple[int, str, FiledReturns | CalculatedReturns]]:
    """Every filed and calculated return of the persona, in the order the windows of their periods close."""
    blocks: tuple[FiledReturns | CalculatedReturns, ...] = (*persona.filed_returns, *persona.calculated_returns)
    found = [(block.year.resolve(envelope), period, block) for block in blocks for period in block.periods]
    return sorted(found, key=lambda item: (item[0], filed_period_order(item[1])))


def preceding_quarter(year: int, period: str) -> PublicPeriod:
    """The quarter before ``period``, whose compensation balance a Modelo 303 period starts from."""
    quarter = int(period[0])
    if quarter == 1:
        return PublicPeriod(filing_year=year - 1, code="4T")
    return PublicPeriod(filing_year=year, code=f"{quarter - 1}T")


def _m303_evidence(
    world: PersonaWorld, *, work_unit_id: str, year: int, period: str, last_period: str
) -> ModeloWorkCalculateOrdinaryM303EvidenceRequestV2:
    """The ordinary Modelo 303 filing facts: no joint return, and the Modelo 390 attestation in the year's last period."""
    if period != "4T" or period != last_period:
        return ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(joint_return_elected=False)
    attestation = ModeloWorkM303AttestationRequest(
        profile_id=world.profile_id,
        work_unit_id=work_unit_id,
        observed_at=datetime(year, 12, 31, 12, tzinfo=UTC),
        actor=PERSONA_ACTOR,
    )
    attested = run_operation(
        world,
        MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID,
        attestation,
        ModeloWorkM303AttestationPublicResultV2,
        subject=attestation.subject_ref,
    )
    return ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(
        joint_return_elected=False,
        m303_exonerado_390_attachment_id=attested.attachment_id,
        m303_exonerado_390_sha256=attested.sha256,
    )


def _seed_compensation_carried_in(persona: Persona, world: PersonaWorld) -> None:
    """Declare the Modelo 303 compensation balance each filed block starts from, where the persona states one.

    A balance carried into the first supported quarter comes from a quarter below the registry's support floor,
    which has no Modelo 303 edition to seed; it is stated as the taxpayer's override on the consuming period.
    """
    for filed in persona.filed_returns:
        if filed.iva_compensation_carried_in is None:
            continue
        year = filed.year.resolve(world.envelope)
        amount = _decimal_text(filed.iva_compensation_carried_in.normalize())
        preceding = preceding_quarter(year, filed.periods[0])
        if preceding.filing_year >= world.envelope.floor:
            settle_operation(
                world,
                MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
                ModeloIvaWalletSeedRequest(profile_id=world.profile_id, period=preceding, amount=amount),
            )
            continue
        settle_operation(
            world,
            MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID,
            ModeloIvaWalletOverrideRequest(
                profile_id=world.profile_id,
                period=PublicPeriod(filing_year=year, code=filed.periods[0]),
                amount=amount,
                reason="Compensation balance carried in from before the first supported period, as the taxpayer states it",
                evidence_locator=f"synthetic:persona:{persona.id}:iva-compensation-carried-in",
            ),
        )


def _record_local_observations(persona: Persona, world: PersonaWorld) -> None:
    """Record the casilla values of each return the taxpayer knows from his own copy, as a local observation."""
    for observation in persona.local_observations:
        run_operation(
            world,
            MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID,
            ModeloLocalObservationMutationRequest(
                profile_id=world.profile_id,
                action="record",
                modelo=observation.modelo,
                period=PublicPeriod(filing_year=observation.year.resolve(world.envelope), code=observation.period),
                casilla_values=tuple(
                    ModeloLocalObservationCasillaValue(casilla_id=casilla, value=value)
                    for casilla, value in observation.casillas
                ),
                actor=PERSONA_ACTOR,
                reason=observation.reason,
            ),
            ModeloLocalObservationMutationProjection,
        )


RENT_WITHHOLDING_MODELO = "115"
"""The modelo whose evidence the retención on a rent payment for leased premises is captured as."""
PROFESSIONAL_WITHHOLDING_MODELO = "111"
"""The modelo whose evidence the retención on a professional's fees is captured as."""
_URBAN_RENT_SCHEME = RetencionScheme("arrendamiento_urbano")
_PROFESSIONAL_SCHEME = RetencionScheme("actividades_profesionales")
#: Modelo 190 clave G, subclave 01: professional income withheld at the general rate of RIRPF art. 95.1.
_PROFESSIONAL_CLAVE = "G"
_PROFESSIONAL_GENERAL_RATE_SUBCLAVE = "01"
_PERCENT = Decimal("100")
_CENTS = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class WithholdingCapture:
    """The withholding one payment's retención is captured as: its modelo, the quarter paid and the evidence."""

    modelo: str
    period: Period
    evidence: InvoiceWithholdingEvidenceRequest
    kind: str
    """``rent`` or ``professional``, naming the capture in a refusal."""


def rent_payments(persona: Persona, premises: LeasedPremises) -> list[LedgerRow]:
    """The received ledger rows from the premises' landlord that carry a retención: one per rent payment."""
    return [
        row
        for row in persona.ledger
        if row.counterparty == premises.landlord
        and row.invoice_kind == "received"
        and row.retencion_amount is not None
        and row.retencion_amount > 0
    ]


def _paid_quarter(paid_on: date) -> Period:
    return Period.from_year_and_code(paid_on.year, f"{(paid_on.month - 1) // 3 + 1}T")


def rent_withholding_capture(
    persona: Persona,
    premises: LeasedPremises,
    row: LedgerRow,
    *,
    envelope: YearEnvelope,
    operation: PinnedAuthorityOperation,
    invoice_id: str,
    payment_event_id: str,
) -> WithholdingCapture:
    """The withholding capture of one rent payment: its invoice, its bank movement and the premises it pays for."""
    if row.taxable_base is None or row.retencion_amount is None or row.retencion_rate is None:
        raise PersonaMaterialisationError(f"{persona.id} {row.ref}: a rent payment states its base and retención")
    paid_on = row.operation_date(envelope)
    with validating_governed_facts(operation):
        evidence = InvoiceWithholdingEvidenceRequest(
            invoice_id=invoice_id,
            income_kind=WithholdingIncomeKind.URBAN_RENT,
            scheme=_URBAN_RENT_SCHEME,
            recipient_tax_status=WithholdingRecipientTaxStatus(premises.landlord_tax_status),
            recipient_tax_regime=WithholdingRecipientTaxRegime(premises.landlord_tax_regime),
            payment_event_id=payment_event_id,
            payment_occurred_on=paid_on,
            allocation_id=row.ref,
            allocated_base=row.taxable_base,
            allocated_withholding=row.retencion_amount,
            allocated_settlement=abs(row.amount),
            idempotency_key=f"{persona.id}:{row.ref}",
            modelo_180_property=Modelo180PropertyEvidence(
                property_key=premises.key,
                situation=premises.situation,
                cadastral_reference=premises.cadastral_reference,
                address=Modelo180StructuredAddress.model_validate(dict(premises.address)),
                recipient_province_code=premises.landlord_province,
                modality=premises.modality,
                accrual_year=paid_on.year,
                withholding_percentage=(row.retencion_rate * _PERCENT).quantize(_CENTS),
            ),
        )
    return WithholdingCapture(
        modelo=RENT_WITHHOLDING_MODELO, period=_paid_quarter(paid_on), evidence=evidence, kind="rent"
    )


def professional_fee_payments(persona: Persona) -> list[LedgerRow]:
    """The received ledger rows carrying a retención that pay no leased premises: a professional's fees.

    A received invoice bears a retención the taxpayer practises only as the
    payer of rent or of professional fees; with no employees, the rows that pay
    no landlord are the professional fees.
    """
    landlords = {premises.landlord for premises in persona.leased_premises}
    return [
        row
        for row in persona.ledger
        if row.invoice_kind == "received"
        and row.counterparty not in landlords
        and row.retencion_amount is not None
        and row.retencion_amount > 0
    ]


def professional_withholding_capture(
    persona: Persona,
    row: LedgerRow,
    *,
    envelope: YearEnvelope,
    operation: PinnedAuthorityOperation,
    invoice_id: str,
    payment_event_id: str,
) -> WithholdingCapture:
    """The withholding capture of one professional's invoice paid by the taxpayer, for the Modelo 111 of its quarter.

    The persona's professionals are resident individuals taxed under the IRPF,
    the only recipients whose fees carry the retención of RIRPF art. 95, at its
    general rate; the Modelo 190 annual detail names them under clave G,
    subclave 01. Their domicile province and the payer's Ceuta/Melilla
    determination come from the professional's identity; an identity that
    states neither leaves them absent, so the 190 refuses rather than guesses.
    """
    if (
        row.counterparty is None
        or row.taxable_base is None
        or row.retencion_amount is None
        or row.retencion_rate is None
    ):
        raise PersonaMaterialisationError(f"{persona.id} {row.ref}: a professional fee states its base and retención")
    paid_on = row.operation_date(envelope)
    perceptor = persona.identities.role(row.counterparty)
    with validating_governed_facts(operation):
        evidence = InvoiceWithholdingEvidenceRequest(
            invoice_id=invoice_id,
            income_kind=WithholdingIncomeKind.PROFESSIONAL,
            scheme=_PROFESSIONAL_SCHEME,
            recipient_tax_status=WithholdingRecipientTaxStatus.RESIDENT,
            recipient_tax_regime=WithholdingRecipientTaxRegime.IRPF,
            payment_event_id=payment_event_id,
            payment_occurred_on=paid_on,
            allocation_id=row.ref,
            allocated_base=row.taxable_base,
            allocated_withholding=row.retencion_amount,
            allocated_settlement=abs(row.amount),
            idempotency_key=f"{persona.id}:{row.ref}",
            modelo_190_detail=WithholdingObservation(
                source_id=invoice_id,
                source_allocation_id=row.ref,
                perceptor_tax_id=perceptor.value,
                perceptor_legal_name=party_name(persona, row.counterparty),
                country_code="ES",
                transaction_date=paid_on,
                clave=RetencionClave.from_registry(_PROFESSIONAL_CLAVE),
                subclave=_PROFESSIONAL_GENERAL_RATE_SUBCLAVE,
                percibido_dinerario=row.taxable_base,
                retencion_practicada=row.retencion_amount,
                **zeroed_withholding_blocks(),
                base_retenciones=row.taxable_base,
                porcentaje_retencion=(row.retencion_rate * _PERCENT).quantize(_CENTS),
                province_code=perceptor.province,
                territorial_deduction_clave=(
                    None if perceptor.ceuta_melilla_deduction is None else int(perceptor.ceuta_melilla_deduction)
                ),
            ),
        )
    return WithholdingCapture(
        modelo=PROFESSIONAL_WITHHOLDING_MODELO, period=_paid_quarter(paid_on), evidence=evidence, kind="professional"
    )


def _capture(persona: Persona, world: PersonaWorld, row: LedgerRow, capture: WithholdingCapture) -> None:
    captured = run_operation(
        world,
        MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
        ModeloInvoiceWithholdingCaptureRequest.from_inputs(
            profile_id=world.profile_id,
            command=PerModeloAggregationCommand(modelo=capture.modelo, period=capture.period),
            evidence=capture.evidence,
        ),
        ModeloInvoiceWithholdingCaptureProjection,
    )
    if captured.outcome != "captured":
        raise PersonaMaterialisationError(
            f"{persona.id} {row.ref}: {capture.kind} withholding refused ({captured.refusal_reason}, "
            f"{captured.refusal_defects})"
        )


def _capture_rent_withholding(
    persona: Persona, world: PersonaWorld, *, transactions: Mapping[str, str], invoices: Mapping[str, str]
) -> None:
    """Capture the retención the taxpayer withheld on every rent payment for leased premises, as Modelo 115 evidence."""
    for premises in persona.leased_premises:
        for row in rent_payments(persona, premises):
            capture = rent_withholding_capture(
                persona,
                premises,
                row,
                envelope=world.envelope,
                operation=world.operation,
                invoice_id=invoices[row.ref],
                payment_event_id=transactions[row.ref],
            )
            _capture(persona, world, row, capture)


def _capture_professional_withholding(
    persona: Persona, world: PersonaWorld, *, transactions: Mapping[str, str], invoices: Mapping[str, str]
) -> None:
    """Capture the retención the taxpayer withheld on every professional's invoice, as Modelo 111 evidence."""
    for row in professional_fee_payments(persona):
        capture = professional_withholding_capture(
            persona,
            row,
            envelope=world.envelope,
            operation=world.operation,
            invoice_id=invoices[row.ref],
            payment_event_id=transactions[row.ref],
        )
        _capture(persona, world, row, capture)


def _finding_names(verified: ModeloWorkVerifyPublicResultV2) -> str:
    """The verification findings by kind, severity, casilla and message key, named for a refusal message."""
    return ", ".join(
        f"{finding.kind}/{finding.severity} {finding.casilla_id or finding.expectation_id or '-'} "
        f"{finding.message_locale_key}"
        for finding in verified.verification.report.findings
    )


def _unresolved(calculated: ModeloWorkCalculatePublicResultV3) -> str:
    """The bindings and boxes a calculation left without a value, named for a refusal message; empty when none."""
    names = [f"binding {row.binding_id}" for row in calculated.unresolved_bindings]
    names += [f"casilla {row.casilla_id} ({row.reason})" for row in calculated.unresolved_casillas]
    return ", ".join(names)


def _capture_aeat_filings(persona: Persona, world: PersonaWorld) -> None:
    """Capture each return the taxpayer filed with the AEAT through the registered filed capture.

    The capture reads the persona's filings from the recorded AEAT register
    and admits each through the production receipt checks. A filing whose
    justificante those checks do not take as the return's verified receipt is
    refused with the capture's own notices.
    """
    recorded = tuple(
        recorded_filing(persona, filing, envelope=world.envelope, operation=world.operation)
        for filing in persona.aeat_filings
    )
    with PERSONA_AEAT_REGISTER.serving(world.profile_id, recorded):
        for filing, held in zip(persona.aeat_filings, recorded, strict=True):
            declaration = held.declaration
            where = f"{persona.id} AEAT filing of Modelo {filing.modelo} {declaration.ejercicio} {filing.period}"
            try:
                captured = run_operation(
                    world,
                    FILED_SINGLE_CAPTURE_DEFINITION_ID,
                    FiledSingleCaptureRequest(
                        profile_id=world.profile_id,
                        output_root=world.workdir / "aeat-filed-capture",
                        modelo=filing.modelo,
                        year=declaration.ejercicio,
                        period=filing.period,
                        expediente_id=declaration.expediente_id,
                        limit=1,
                    ),
                    FiledSingleCapturePublicResultV1,
                )
            except PersonaMaterialisationError as error:
                raise PersonaMaterialisationError(f"{where}: {error}") from error
            if (
                captured.captured_count != 1
                or captured.justificante_csvs != (filing.csv,)
                or captured.filing_evidence_stamped_count != 1
                or captured.calculation_observation_count != 1
            ):
                raise PersonaMaterialisationError(
                    f"{where}: the capture did not admit its justificante: {captured.model_dump_json()}"
                )


def _replay_records(
    persona: Persona, world: PersonaWorld, *, transactions: Mapping[str, str], invoices: Mapping[str, str]
) -> None:
    """Record what the persona's returns read: observations, compensation carried in, withholding and AEAT filings."""
    _seed_compensation_carried_in(persona, world)
    _record_local_observations(persona, world)
    _capture_rent_withholding(persona, world, transactions=transactions, invoices=invoices)
    _capture_professional_withholding(persona, world, transactions=transactions, invoices=invoices)
    _capture_aeat_filings(persona, world)


def _replay_history(persona: Persona, world: PersonaWorld) -> tuple[dict[str, str], dict[str, str]]:
    """Replay the persona's returns; returns the filed and the calculated returns, key to revision id.

    The records of :func:`_replay_records` come first. Then each
    filed return is created, calculated, verified and filed locally, and each
    calculated return created and calculated, in the order their windows close.
    Each figure comes from the persona's replayed ledger, profile and recorded
    observations, and from the values the persona's operator enters on it
    (``work_inputs``), entered through the declaration edit before its first
    calculation; nothing else is entered at calculation. A filed return that
    cannot verify or file from that data is refused with the operation's own
    reason, never overridden. Local filing records a PRESENTADO revision whose
    AEAT status stays pending; no receipt is made.
    """
    filings: dict[str, str] = {}
    calculations: dict[str, str] = {}
    for year, period, filed in history_periods(persona, world.envelope):
        where = f"{persona.id} Modelo {filed.modelo} {year} {period}"
        created = settle_operation(
            world,
            MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
            ModeloWorkCreateRequest(
                profile_id=world.profile_id,
                modelo=filed.modelo,
                period=PublicPeriod(filing_year=year, code=period),
                actor=PERSONA_ACTOR,
            ),
        )
        outcome = getattr(created, "outcome", None)
        if not isinstance(outcome, ModeloWorkCreateSuccess):
            raise PersonaMaterialisationError(f"{where}: work creation refused: {outcome}")
        work_unit_id = outcome.unit.work_unit_id
        evidence = (
            _m303_evidence(world, work_unit_id=work_unit_id, year=year, period=period, last_period=filed.periods[-1])
            if filed.modelo == "303"
            else None
        )
        try:
            calculated = run_operation(
                world,
                MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
                ModeloWorkCalculateRequest(
                    work_unit_id=work_unit_id, actor=PERSONA_ACTOR, ordinary_m303_filing_evidence=evidence
                ),
                ModeloWorkCalculatePublicResultV3,
                subject=work_unit_id,
            )
        except PersonaMaterialisationError as error:
            raise PersonaMaterialisationError(f"{where}: {error}") from error
        revision_id = calculated.calculation_revision_id
        unresolved = _unresolved(calculated)
        if isinstance(filed, CalculatedReturns):
            if unresolved:
                raise PersonaMaterialisationError(f"{where}: the calculation left {unresolved} without a value")
            calculations[filing_key(filed.modelo, year, period)] = revision_id
            continue
        verified = run_operation(
            world,
            MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
            ModeloWorkVerifyRequest(calculation_revision_id=revision_id, actor=PERSONA_ACTOR),
            ModeloWorkVerifyPublicResultV2,
            subject=work_unit_id,
        )
        if not verified.granted_verificado_completo:
            raise PersonaMaterialisationError(
                f"{where}: verification did not complete ({verified.completeness_status}, "
                f"{verified.finding_count} findings, "
                f"{verified.missing_required_casilla_count} required casillas missing; unresolved: {unresolved or 'none'}; "
                f"findings: {_finding_names(verified)})"
            )
        run_operation(
            world,
            MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
            ModeloWorkFileRequest(
                approval=ModeloWorkFileApproval(
                    calculation_revision_id=revision_id,
                    verification_report_id=verified.verification_report_id,
                ),
                actor=PERSONA_ACTOR,
            ),
            ModeloWorkFilePublicResultV2,
            subject=work_unit_id,
        )
        filings[filing_key(filed.modelo, year, period)] = revision_id
    return filings, calculations


def attested_returns_to_replay(persona: Persona, envelope: YearEnvelope) -> tuple[tuple[str, int, str], ...]:
    """Each ``(modelo, year, period)`` the persona attests a prior value on that nothing else calculates.

    A return of the history is calculated by the history replay, and a return a
    stated value names is calculated where that value is assessed; each attests
    its prior values after that calculation. Any other attested return would
    never be calculated, so its attestation is replayed on its own.
    """
    calculated = {(block.modelo, year, period) for year, period, block in history_periods(persona, envelope)}
    calculated |= {
        (value.modelo, year, value.period) for year, value in values_in_force(persona.expectations.values, envelope)
    }
    attested = {(item.modelo, item.year.resolve(envelope), item.period) for item in persona.attested_prior_values}
    return tuple(sorted(attested - calculated, key=lambda item: (item[1], item[0], item[2])))


def _replay_attested_returns(persona: Persona, world: PersonaWorld) -> dict[str, str]:
    """Create and attest each return of :func:`attested_returns_to_replay`; returns key to calculated revision id.

    The attestation is submitted before any calculation, as a calculating edit:
    such a return may refuse its calculation until the figure is stated. The
    values the persona enters on the return are entered first, as before any
    first calculation. A stated figure the application does not offer to
    attest refuses the replay; it is never skipped.
    """
    calculations: dict[str, str] = {}

    def settle(definition_id: str, payload: BaseModel, *, subject: str | None = None) -> BaseModel | None:
        return settle_operation(world, definition_id, payload, subject=subject)

    for modelo, year, period in attested_returns_to_replay(persona, world.envelope):
        where = f"{persona.id} Modelo {modelo} {year} {period}"
        created = settle_operation(
            world,
            MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
            ModeloWorkCreateRequest(
                profile_id=world.profile_id,
                modelo=modelo,
                period=PublicPeriod(filing_year=year, code=period),
                actor=PERSONA_ACTOR,
            ),
        )
        outcome = getattr(created, "outcome", None)
        if not isinstance(outcome, ModeloWorkCreateSuccess):
            raise PersonaMaterialisationError(f"{where}: work creation refused: {outcome}")
        work_unit_id = outcome.unit.work_unit_id
        try:
            if world.work_inputs:
                enter_return_work_inputs(world, work_unit_id)
            attested = attest_return_prior_values(
                world.attested_prior_values,
                envelope=world.envelope,
                profile_id=world.profile_id,
                work_unit_id=work_unit_id,
                modelo=modelo,
                filing_year=year,
                period=period,
                settle=settle,
            )
        except (PersonaMaterialisationError, PriorValueAttestationError) as error:
            raise PersonaMaterialisationError(f"{where}: {error}") from error
        if attested.unoffered:
            raise PersonaMaterialisationError(
                f"{where}: the application does not offer the attestation of {', '.join(attested.unoffered)}"
            )
        if attested.applied is None:
            raise PersonaMaterialisationError(f"{where}: the attestation was not applied")
        revision_id = attested.applied.calculation_revision_id
        if revision_id is None:
            raise PersonaMaterialisationError(f"{where}: the attesting edit published no calculation")
        calculations[filing_key(modelo, year, period)] = revision_id
    return calculations


def _complete_setup(world: PersonaWorld) -> bool:
    """Declare the replayed profile's setup complete through the production operation; whether it now is.

    The setup flow ends with that declaration, which modelo work waits on. The
    operation refuses a profile its complete-profile judgement rejects, so that
    same judgement decides first whether to ask it.
    """
    record = load_profile_record(world)
    if record.setup_state is ProfileSetupState.COMPLETE:
        return True
    try:
        reject_invalid_profile_facts(
            str(world.profile_id),
            record.facts,
            require_complete=True,
            schema=world.operation.profile_decode_context().schema,
        )
    except ProfileSchemaValidationError:
        return False
    settle_operation(
        world,
        PROFILE_COMPLETE_SETUP_OPERATION_DEFINITION_ID,
        ProfileCompleteSetupOperationRequest(
            profile_id=world.profile_id,
            expected_revision=record.record_revision,
            expected_content_digest=record.content_digest,
        ),
    )
    return load_profile_record(world).setup_state is ProfileSetupState.COMPLETE


def _not_loaded(
    persona: Persona, scope: ReplayScope, envelope: YearEnvelope, *, setup_complete: bool | None
) -> tuple[NotLoaded, ...]:
    """The persona facts no production operation recorded within ``scope``, and why.

    A block outside the scope was never attempted, so it is absent from the
    scope's result rather than reported as one no operation can record. A
    return-history record a lowered horizon put below the floor is reported
    within the records scope: the application refuses its year.
    """
    found = [
        NotLoaded(block=block, reason="no production operation records this block")
        for block in persona.declared_blocks()
    ]
    if scope.includes(ReplayScope.RECORDS):
        found.extend(
            NotLoaded(block=record.block, reason=record.reason(envelope))
            for record in persona.below_floor
            if record.history
        )
    if setup_complete is False:
        found.append(
            NotLoaded(
                block="setup",
                reason="the persona leaves a profile answer a complete profile requires missing, so its setup cannot be completed",
            )
        )
    if not scope.includes(ReplayScope.FULL):
        return tuple(found)
    if any(item.origin == "payer_certificate" for item in persona.withholding_certificates):
        found.append(
            NotLoaded(
                block="withholding_certificates",
                reason=(
                    "the retención-soportada record operation takes a payer certificate's bytes for origin "
                    "payer_certificate and the persona references no certificate document"
                ),
            )
        )
    if any(item.cotizaciones_seguridad_social is not None for item in persona.withholding_certificates):
        found.append(
            NotLoaded(
                block="withholding_certificates.cotizaciones_seguridad_social",
                reason=(
                    "no operation records an employee's Seguridad Social contributions and no Modelo 100 binding "
                    "sources the work-income deductible expense they enter"
                ),
            )
        )
    return tuple(found)


def materialise_persona(
    persona: Persona, world: PersonaWorld, scope: ReplayScope = ReplayScope.FULL, *, complete_setup: bool = True
) -> MaterialisedPersona:
    """Replay ``persona`` into ``world``'s profile through production operations, as far as ``scope`` reaches.

    With ``complete_setup`` the replay ends as the setup flow does, declaring
    the setup complete; without it the profile stays in setup, the state the
    onboarding review opens.
    """
    try:
        check_work_inputs(persona, world.envelope, world.operation)
    except WorkInputError as error:
        raise PersonaMaterialisationError(str(error)) from error
    try:
        check_prior_value_bindings(persona.attested_prior_values, world.envelope, world.operation)
    except PriorValueAttestationError as error:
        raise PersonaMaterialisationError(f"{persona.id}: {error}") from error
    transactions: dict[str, str] = {}
    invoices: dict[str, str] = {}
    evidence: dict[str, str] = {}
    filings: dict[str, str] = {}
    calculations: dict[str, str] = {}
    with frozen_clock(world.as_of):
        _replay_profile(persona, world)
        if scope.includes(ReplayScope.HOUSEHOLD):
            _replay_household(persona, world)
        if scope.includes(ReplayScope.FULL):
            replay_own_accounts(persona, world.profile_id, partial(settle_operation, world))
            _replay_withholding(persona, world)
            transactions = _imported_transactions(persona, world)
            invoices = _replay_ledger(persona, world, transactions)
            replay_rentals(
                persona,
                world.profile_id,
                world.envelope,
                transactions,
                actor=PERSONA_ACTOR,
                settle=partial(settle_operation, world),
                load_record=partial(load_profile_record, world),
            )
            _state_filing_names(persona, world)
            evidence = _replay_documents(persona, world, transactions)
            _replay_inventory(persona, world, transactions)
        setup_complete = _complete_setup(world) if complete_setup else None
        if scope.includes(ReplayScope.RECORDS) and (
            persona.filed_returns
            or persona.calculated_returns
            or persona.local_observations
            or persona.aeat_filings
            or (scope.includes(ReplayScope.HISTORY) and attested_returns_to_replay(persona, world.envelope))
        ):
            if setup_complete is not True:
                raise PersonaMaterialisationError(f"{persona.id}: replaying its returns needs a completed setup")
            _replay_records(persona, world, transactions=transactions, invoices=invoices)
            if scope.includes(ReplayScope.HISTORY):
                filings, calculations = _replay_history(persona, world)
                calculations |= _replay_attested_returns(persona, world)
    return MaterialisedPersona(
        persona=persona,
        world=world,
        scope=scope,
        transactions=transactions,
        invoices=invoices,
        evidence=evidence,
        not_loaded=_not_loaded(persona, scope, world.envelope, setup_complete=setup_complete),
        filings=filings,
        calculations=calculations,
    )


_REPLAYED_IDS = "persona-materialisation.json"
"""Beside the storage root of a sealed replay: the ids the replay minted, which a copy reads back."""


def _sealed_replay(
    persona: Persona,
    scope: ReplayScope,
    as_of: datetime,
    base: SealedProfileWorld,
    decode_context: ProfileDecodeContext,
    *,
    complete_setup: bool,
    envelope: YearEnvelope,
) -> SealedProfileWorld:
    """This run's world holding ``persona`` replayed to ``scope`` into ``base``, replayed on first use anywhere in the run."""

    def replay(profile_id: UUID) -> None:
        root = load_settings().cadrumo_storage_root
        if root is None:
            raise PersonaMaterialisationError("a sealed replay runs inside an isolated storage root")
        with (
            TemporaryDirectory(prefix="persona-inputs-") as inputs,
            _operations_over(
                root,
                profile_id,
                workdir=Path(inputs),
                as_of=as_of,
                envelope=envelope,
                attested_prior_values=persona.attested_prior_values,
                work_inputs=persona.work_inputs,
                work_income_none_statements=persona.work_income_none_statements,
            ) as world,
        ):
            replayed = materialise_persona(persona, world, scope, complete_setup=complete_setup)
        ids = {
            "transactions": replayed.transactions,
            "invoices": replayed.invoices,
            "evidence": replayed.evidence,
            "filings": replayed.filings,
            "calculations": replayed.calculations,
            "setup_complete": (all(item.block != "setup" for item in replayed.not_loaded) if complete_setup else None),
        }
        (root.parent / _REPLAYED_IDS).write_text(json.dumps(ids, sort_keys=True), encoding="utf-8")

    key = (
        "persona replay",
        persona.id,
        scope.value,
        persona_inputs_digest(persona),
        as_of.isoformat(),
        f"envelope {envelope.floor}..{envelope.horizon}",
        "setup completed" if complete_setup else "setup open",
    )
    return derived_profile_world(base, key, replay, profile_decode_context=decode_context)


@contextmanager
def _reused_persona_world(
    persona: Persona,
    scope: ReplayScope,
    tmp_path: Path,
    *,
    as_of: datetime,
    complete_setup: bool,
    envelope: YearEnvelope,
) -> Generator[MaterialisedPersona]:
    """Open this consumer's own copy of the run's replay of ``persona``, replaying it only when the run has none."""
    with bundled_indexed_authority().operation(), _scenario(as_of):
        _create_context, decode_context = profile_authority_contexts()
        sealed = _sealed_replay(
            persona,
            scope,
            as_of,
            _registered_world(persona, as_of),
            decode_context,
            complete_setup=complete_setup,
            envelope=envelope,
        )
        with copied_profile_world(sealed, tmp_path / "runtime", profile_decode_context=decode_context) as (
            root,
            profile_id,
        ):
            ids = json.loads((root.parent / _REPLAYED_IDS).read_text(encoding="utf-8"))
            try:
                with _operations_over(
                    root,
                    profile_id,
                    workdir=tmp_path / "inputs",
                    as_of=as_of,
                    envelope=envelope,
                    attested_prior_values=persona.attested_prior_values,
                    work_inputs=persona.work_inputs,
                    work_income_none_statements=persona.work_income_none_statements,
                ) as world:
                    yield MaterialisedPersona(
                        persona=persona,
                        world=world,
                        scope=scope,
                        transactions=ids["transactions"],
                        invoices=ids["invoices"],
                        evidence=ids["evidence"],
                        not_loaded=_not_loaded(persona, scope, envelope, setup_complete=ids["setup_complete"]),
                        filings=ids["filings"],
                        calculations=ids["calculations"],
                    )
            finally:
                reset_test_profile_session()


@contextmanager
def materialised_persona(
    persona_id: str,
    tmp_path: Path,
    scope: ReplayScope = ReplayScope.FULL,
    *,
    reuse: bool = False,
    complete_setup: bool = True,
    read_on: datetime | None = None,
    horizon: int | None = None,
) -> Generator[MaterialisedPersona]:
    """Read one persona, open its world at its scenario instant and replay it there as far as ``scope`` reaches.

    With ``read_on`` the world is opened, and the persona signs in, on that
    later day instead, for a scenario read when the persona's own instant has
    passed: a session opened at that instant would have ended by then.

    A replay of the full ledger takes tens of seconds. With ``reuse`` the run
    replays a persona at a scope once into a sealed world keyed by the
    persona's input files, the scope, the scenario instant and the authority
    generation, and every consumer receives its own filesystem copy of it: a
    write to one copy reaches no other and never the sealed world. A consumer
    that mutates the profile may reuse; one that needs the replay to run
    afresh does not. ``complete_setup`` is as :func:`materialise_persona` takes it.

    With ``horizon`` the persona is read as if the registry's horizon were that
    earlier supported year: its year tokens and its scenario clock move down
    with it, so a scenario written against ``horizon-1`` is replayed for an
    earlier supported year. The floor stays the registry's own, so a return
    history record or expectation that moves below it is left out of the
    replay and listed in :attr:`Persona.below_floor`, its history records
    also in :attr:`MaterialisedPersona.not_loaded`; a return that depends on
    one meets the application's own refusal.
    """
    with bundled_indexed_authority().operation() as operation:
        envelope = year_envelope(operation)
    lowered = horizon is not None and horizon != envelope.horizon
    if horizon is not None:
        if not envelope.floor <= horizon <= envelope.horizon:
            raise PersonaMaterialisationError(f"horizon {horizon} lies outside {envelope.floor}..{envelope.horizon}")
        envelope = dataclasses.replace(envelope, horizon=horizon)
    persona = read_persona(persona_id, envelope=envelope, omit_below_floor=lowered)
    as_of = scenario_instant(persona, envelope) if read_on is None else read_on
    if reuse:
        with _reused_persona_world(
            persona, scope, tmp_path, as_of=as_of, complete_setup=complete_setup, envelope=envelope
        ) as reused:
            yield reused
        return
    with persona_world(tmp_path, persona, as_of=as_of, envelope=envelope) as world:
        yield materialise_persona(persona, world, scope, complete_setup=complete_setup)


__all__ = [
    "PERSONA_ACTOR",
    "SCENARIO_TIME",
    "MaterialisedPersona",
    "NotLoaded",
    "PersonaMaterialisationError",
    "PersonaWorld",
    "ReplayScope",
    "attest_before_first_calculation",
    "attested_before_calculating",
    "enter_return_work_inputs",
    "filing_key",
    "household_leaves",
    "load_profile_record",
    "materialise_persona",
    "materialised_persona",
    "patch_answers",
    "persona_profile_id",
    "persona_world",
    "public_result",
    "run_operation",
    "scenario_instant",
    "settle_operation",
    "state_after_calculation",
    "submitted_answer",
    "year_envelope",
]
