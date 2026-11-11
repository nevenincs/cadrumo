"""A stopped executor's public error detail, settled and read over real durable operation storage.

The journal keeps only a refusal's code or a failure's code and opaque digest.
The bounded public detail a frontend renders -- the registered code, its
catalogue key, the envelope's scrubbed context and the typed verdict, or a
record fault naming the record and broken rule -- is stored as an encrypted
operand and released only through the settled result read under its own
public schema identity.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import NoReturn
from uuid import UUID

import pytest
from pydantic import BaseModel, Field, ValidationError, model_validator

from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.errors import AggregationUnsupportedModeloError
from cadrumo.application.cli_exception_preconditions import (
    CliExceptionPrecondition,
    cli_exception_no_recovery_verdict,
)
from cadrumo.application.modelo.action_errors import ModeloDomiciliationPastCutoffError
from cadrumo.application.modelo.calculation_note_gate import ModeloCalculationBlockedError
from cadrumo.application.modelo.preconditions import build_modelo_precondition_failure_for_scenario
from cadrumo.application.modelo.projection import ModeloProjectNoM130UnitsError
from cadrumo.application.modelo.projection_next_steps import create_work_step
from cadrumo.application.modelo.query_read_contracts import ModeloReadinessOperationRequest
from cadrumo.application.modelo.query_read_operation import (
    build_modelo_readiness_definition,
    build_modelo_readiness_registration,
)
from cadrumo.application.modelo.work_create_operation import (
    ModeloWorkCreateRequest,
    build_modelo_work_create_definition,
    build_modelo_work_create_registration,
)
from cadrumo.application.operations.capabilities import OperationOwnedResource
from cadrumo.application.operations.error_detail import (
    RECORD_FAULT_WORDS_LOCALE_KEY,
    UNWORDED_REGISTERED_ERROR_LOCALE_KEY,
    OperationErrorDetailKind,
    OperationErrorDetailV1,
    operation_error_detail_schema,
)
from cadrumo.application.operations.frontend_requests import (
    OperationResultProjectionRefusalCode,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.next_step import OperationCreateWorkStepV1
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.projection_services import OperationResultProjectionService
from cadrumo.application.operations.public_period import PublicPeriod
from cadrumo.application.operations.registry import (
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
    OperationSchemaBindingV1,
)
from cadrumo.core.config import override_settings
from cadrumo.core.errors.error_codes import get_registered_error_code, resolve_error_message
from cadrumo.core.errors.hierarchy import CadrumoError, pydantic_validation_boundary
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import lookup_translation
from cadrumo.core.i18n.translatable import Translatable as tr
from cadrumo.core.models import STRICT_FROZEN_CONFIG
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.core.operator_action_enums import ActionEvidenceProvenance
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.errors import NoRevisionForPeriodError
from cadrumo.domain.calculations.registry.tests.authored_editions import authored_revisions, filing_year_envelope
from cadrumo.domain.invoices.errors import InvoiceValidationError
from cadrumo.domain.invoices.rule_findings import (
    InvoiceRuleFindingCode,
    advance_payment_collection_finding,
    raise_first_rule_finding,
    rule_finding_words_key,
)

from .supervision_support import run_to_settlement
from .supervisor_test_support import (
    SENSITIVE_EXCEPTION_DETAIL,
    SupervisorRequest,
    SupervisorResult,
    UnexpectedFailureExecutor,
    assert_sensitive_detail_absent_from_operation_bytes,
    operation_repositories,
    operation_supervisor,
    supervisor_capabilities,
    supervisor_registry,
    supervisor_request,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon
_AVAILABLE_REVISION_IDS = tuple(revision.id for revision in authored_revisions("210"))
_CUTOFF_ON = date(_YEAR, 4, 15).isoformat()
_EXPORT_ON = date(_YEAR, 4, 16).isoformat()

#: A distinctive context value: it reaches the encrypted detail and never the journal bytes.
_ROW_IDENTITY = "ledger-row-7f3a9c"
#: An offending record value: it reaches neither the detail nor the journal.
_OFFENDING_VALUE = "SE556677889901-" + "x" * 80
#: The catalogue key the refusing site supplies, distinct from its registry fallback key.
_REFUSAL_MESSAGE_KEY = "aggregation.grouping.errors.unsupported_modelo"
#: What the envelope's redaction leaves of a secret-looking context key.
_REDACTED_VALUE = "<redacted>"


class _BoundedRecord(BaseModel):
    """A record the application builds with a declared bound."""

    model_config = STRICT_FROZEN_CONFIG

    actor: str = Field(max_length=64)


class _ContextualRefusalExecutor:
    """Refuse with a registered error carrying context, a catalogue key and a typed verdict."""

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request, context
        raise AggregationUnsupportedModeloError(
            tr(_REFUSAL_MESSAGE_KEY),
            context={"modelo": "111", "transaction_id": _ROW_IDENTITY, "api_token": "never-shown"},
            precondition_verdict=cli_exception_no_recovery_verdict(
                CliExceptionPrecondition.REFUSAL_RETRIED, facts={"boundary_error_type": "probe"}
            ),
        )


class _RecordFaultExecutor:
    """Fail by building an application record that breaks its own contract."""

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request, context
        _BoundedRecord(actor=_OFFENDING_VALUE)
        return None


class _SettledCase:
    """One operation settled over real storage, with its detail read through the public service."""

    def __init__(self, terminal: OperationPersistedSnapshot, storage_root: Path, detail: object) -> None:
        self.terminal = terminal
        self.storage_root = storage_root
        self.detail = detail


def _settle_and_read(
    tmp_path: Path,
    registry: OperationRegistry,
    *,
    authority_operation: PinnedAuthorityOperation,
    result_schema: object | None = None,
    language: str = "en",
) -> _SettledCase:
    storage_root = tmp_path / "durable-state"
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, override_settings(cadrumo_output_language=language):
        journal, leases, operands = operation_repositories(
            storage_root=storage_root, profile_objects=profile.repository
        )
        supervisor = operation_supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            authority_operation=authority_operation,
        )
        operation_id = asyncio.run(supervisor.submit(supervisor_request(), operation_id="3" * 64))
        terminal = asyncio.run(run_to_settlement(supervisor, operation_id))
        contract = registry.lookup_public_contract(terminal.identity.definition_id)
        service = OperationResultProjectionService(reader=journal, registry=registry, operands=operands)
        detail = asyncio.run(
            service.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=operation_id,
                    terminal_revision=terminal.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=operation_error_detail_schema() if result_schema is None else result_schema,
                ),
                OperationErrorDetailV1,
            )
        )
    return _SettledCase(terminal, storage_root, detail)


def _opted_in(registry: OperationRegistry) -> OperationRegistry:
    """The same supervisor test definition, opted in to recording its public error detail."""
    item = registry.lookup("operation.supervisor.test").model_copy(update={"public_error_detail": True})
    registration = OperationPublicDefinitionRegistrationV1.compose(
        definition=item,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="operation.supervisor.test.request", schema_version=1, model_type=SupervisorRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="operation.supervisor.test.result", schema_version=1, model_type=SupervisorResult
        ),
    )
    return OperationRegistry(definitions=(item,), public_registrations=(registration,))


def _executor_registry(executor_type: type[object], build: Callable[[], object]) -> OperationRegistry:
    return _opted_in(supervisor_registry(executor_type=executor_type, build=build))


def test_a_registered_refusal_releases_its_code_key_scrubbed_context_and_verdict(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """The refusal a frontend renders is the executor's own, without the journal learning it."""
    case = _settle_and_read(
        tmp_path,
        _executor_registry(_ContextualRefusalExecutor, _ContextualRefusalExecutor),
        authority_operation=authority_operation,
    )

    receipt = case.terminal.terminal_receipt
    assert case.terminal.terminal_condition is OperationTerminalCondition.REFUSED
    assert receipt is not None and receipt.error_detail_ref is not None
    registered = get_registered_error_code(AggregationUnsupportedModeloError)
    assert receipt.refusal_ref == registered.code
    assert isinstance(case.detail, OperationResultProjectionSuccessV1)
    detail = case.detail.projection
    assert isinstance(detail, OperationErrorDetailV1)
    assert detail.kind is OperationErrorDetailKind.REGISTERED_ERROR
    assert detail.error_code == registered.code
    assert detail.message_key == _REFUSAL_MESSAGE_KEY
    context = detail.context_mapping()
    assert context["modelo"] == "111"
    assert context["transaction_id"] == _ROW_IDENTITY
    # The envelope's own redaction applies before the detail is stored.
    assert context["api_token"] == _REDACTED_VALUE
    verdict = detail.precondition_verdict()
    assert verdict is not None
    assert verdict.failed_condition_id == CliExceptionPrecondition.REFUSAL_RETRIED.value
    # The context value is in the encrypted detail, never the credential-free journal.
    journal_bytes = b"".join(path.read_bytes() for path in case.storage_root.rglob("*") if path.is_file())
    assert _ROW_IDENTITY.encode() not in journal_bytes


def test_an_application_record_fault_releases_the_record_and_rule_but_never_the_value(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """A record the application built that broke its contract is named, with the value withheld."""
    case = _settle_and_read(
        tmp_path,
        _executor_registry(_RecordFaultExecutor, _RecordFaultExecutor),
        authority_operation=authority_operation,
    )

    receipt = case.terminal.terminal_receipt
    assert case.terminal.terminal_condition is OperationTerminalCondition.FAILED
    assert receipt is not None and receipt.failure_error_code is None and receipt.error_detail_ref is not None
    assert isinstance(case.detail, OperationResultProjectionSuccessV1)
    detail = case.detail.projection
    assert isinstance(detail, OperationErrorDetailV1)
    assert detail.kind is OperationErrorDetailKind.RECORD_VALIDATION
    assert detail.error_code is None and detail.message_key is None
    context = detail.context_mapping()
    assert context["failing_record"] == "_BoundedRecord"
    assert "String should have at most 64 characters" in context["violations"]
    assert _OFFENDING_VALUE not in detail.model_dump_json()
    assert _OFFENDING_VALUE[:20] not in detail.model_dump_json()
    journal_bytes = b"".join(path.read_bytes() for path in case.storage_root.rglob("*") if path.is_file())
    assert _OFFENDING_VALUE.encode() not in journal_bytes


def test_an_unexpected_failure_records_no_detail_and_keeps_its_prose_out_of_storage(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """An exception with no public facts leaves only the opaque correlation the journal already had."""
    executor = UnexpectedFailureExecutor()
    registry = _opted_in(
        supervisor_registry(
            executor_type=UnexpectedFailureExecutor,
            build=lambda: executor,
            capabilities=supervisor_capabilities(
                owned_resources=frozenset({OperationOwnedResource.ASYNC_TASK}),
                permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            ),
        )
    )
    case = _settle_and_read(tmp_path, registry, authority_operation=authority_operation)

    receipt = case.terminal.terminal_receipt
    assert case.terminal.terminal_condition is OperationTerminalCondition.FAILED
    assert receipt is not None and receipt.error_detail_ref is None and receipt.diagnostic_ref is not None
    assert isinstance(case.detail, OperationResultProjectionRefusalV1)
    assert case.detail.code is OperationResultProjectionRefusalCode.RESULT_PROJECTION_UNAVAILABLE
    assert SENSITIVE_EXCEPTION_DETAIL not in case.terminal.model_dump_json()
    assert_sensitive_detail_absent_from_operation_bytes(case.storage_root)


def test_the_detail_is_read_only_under_its_own_schema_identity(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """Asking for the detail under any other schema refuses rather than releasing it."""
    registry = _executor_registry(_ContextualRefusalExecutor, _ContextualRefusalExecutor)
    result_schema = registry.lookup_public_contract("operation.supervisor.test").result_schema
    case = _settle_and_read(tmp_path, registry, result_schema=result_schema, authority_operation=authority_operation)

    assert case.terminal.terminal_receipt is not None
    assert case.terminal.terminal_receipt.error_detail_ref is not None
    assert isinstance(case.detail, OperationResultProjectionRefusalV1)
    assert case.detail.code is OperationResultProjectionRefusalCode.OPERATION_NOT_SUCCESSFUL


def test_a_definition_that_does_not_opt_in_records_no_detail(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """Without the opt-in, the same refusal keeps only its registered code, as before."""
    registry = supervisor_registry(executor_type=_ContextualRefusalExecutor, build=_ContextualRefusalExecutor)
    case = _settle_and_read(tmp_path, registry, authority_operation=authority_operation)

    receipt = case.terminal.terminal_receipt
    assert case.terminal.terminal_condition is OperationTerminalCondition.REFUSED
    assert receipt is not None and receipt.error_detail_ref is None
    assert receipt.refusal_ref == get_registered_error_code(AggregationUnsupportedModeloError).code
    assert isinstance(case.detail, OperationResultProjectionRefusalV1)


@pytest.mark.parametrize("definition_id", ["modelo.work.create", "modelo.readiness"])
def test_modelo_scope_failure_retains_its_public_detail_over_durable_settlement(
    tmp_path: Path, definition_id: str, authority_operation: PinnedAuthorityOperation
) -> None:
    """Real owner definitions record the registry fault before any result or effect.

    The injected ports factory fails at its defining boundary. Both real
    executors, their request schemas, encrypted journal and result projection
    run unchanged; frontend admission is independently covered by CLI journeys.
    """
    profile_id = UUID("a0347100-3a01-4b0a-aeee-347102030405")
    error = NoRevisionForPeriodError(
        modelo_id="210",
        filing_year=_YEAR,
        period="1T",
        revision_id=None,
        available_revision_ids=_AVAILABLE_REVISION_IDS,
    )

    attempts: list[NoRevisionForPeriodError] = []

    def unavailable_ports(*_args: object, **_kwargs: object) -> NoReturn:
        attempts.append(error)
        raise error

    period = PublicPeriod(filing_year=_YEAR, code="1T")
    if definition_id == "modelo.work.create":
        definition = build_modelo_work_create_definition(unavailable_ports)
        registration = build_modelo_work_create_registration(definition)
        payload = ModeloWorkCreateRequest(profile_id=profile_id, modelo="210", period=period, actor="operator")
    else:
        definition = build_modelo_readiness_definition(unavailable_ports)
        registration = build_modelo_readiness_registration(definition)
        payload = ModeloReadinessOperationRequest(profile_id=profile_id, modelo="210", filing_year=_YEAR, period=period)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(profile_id)) as profile:
        journal, leases, operands = operation_repositories(
            storage_root=tmp_path / "scope-state", profile_objects=profile.repository
        )
        supervisor = operation_supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            execution_timeout=timedelta(minutes=1),
            authority_operation=authority_operation,
        )

        async def settle_and_read():
            operation_id = await supervisor.submit(
                OperationRequest[BaseModel](
                    definition_id=definition_id, subject_ref=profile_operation_subject(str(profile_id)), payload=payload
                ),
                operation_id="4" * 64,
            )
            await run_to_settlement(supervisor, operation_id)
            assert attempts == [error]
            terminal = await supervisor.inspect(operation_id)
            service = OperationResultProjectionService(reader=journal, registry=registry, operands=operands)
            result = await service.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=operation_id,
                    terminal_revision=terminal.revision,
                    definition_contract_digest=registration.contract.definition_contract_digest,
                    result_schema=operation_error_detail_schema(),
                ),
                OperationErrorDetailV1,
            )
            return terminal, result

        terminal, result = asyncio.run(settle_and_read())
        assert terminal.terminal_condition is OperationTerminalCondition.FAILED
        assert terminal.effect is OperationEffect.NONE
        assert terminal.terminal_receipt is not None
        assert terminal.terminal_receipt.result_ref is None
        assert terminal.terminal_receipt.error_detail_ref is not None
        assert isinstance(result, OperationResultProjectionSuccessV1)
        detail = result.projection
        assert isinstance(detail, OperationErrorDetailV1)
        assert detail.error_code == "ERROR_CALCULATIONS_REGISTRY_NO_REVISION_FOR_PERIOD"
        assert detail.message_key == "errors.snapshot.no_revision_for_period"
        context = {entry.key: entry.value for entry in detail.context}
        assert context["modelo_id"] == "210"
        assert context["filing_year"] == str(_YEAR)
        assert context["period"] == "1T"
        assert context["available_revision_ids"] == ", ".join(_AVAILABLE_REVISION_IDS)
        assert OperationErrorDetailV1.model_validate_json(detail.model_dump_json()) == detail


#: A synthetic NIF-IVA: a private identifier a served sentence must never carry.
_PRIVATE_NIF = "ESB00015016"

#: Context of a direct debit refused past its cutoff, every placeholder of its sentence filled.
_PAST_CUTOFF_CONTEXT: dict[str, object] = {
    "calculation_revision_id": "calc-0001",
    "modelo": "303",
    "filing_year": str(_YEAR),
    "period": "1T",
    "payment_cutoff_on": _CUTOFF_ON,
    "payment_cutoff_source": "filing_window",
    "payment_cutoff_legal_refs": "Orden HAC/3625/2003, art. 3",
    "export_on": _EXPORT_ON,
}


def _past_cutoff_refusal(**context: object) -> ModeloDomiciliationPastCutoffError:
    return ModeloDomiciliationPastCutoffError(
        translated_message="errors.refused.refused_modelo_domiciliation_past_cutoff", context=context
    )


class _AdvancePaymentRecord(BaseModel):
    """A record whose own validator refuses an advance payment on a partly collected price."""

    model_config = STRICT_FROZEN_CONFIG

    paid_in_full: bool

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _advance_collected(self) -> _AdvancePaymentRecord:
        raise_first_rule_finding(
            (advance_payment_collection_finding(advance_role=True, fully_collected=self.paid_in_full),)
        )
        return self


def _raising(make: Callable[[], BaseException]) -> type[object]:
    """An executor class that stops by raising what ``make`` builds."""

    class _Raising:
        async def execute(self, request: OperationRequest[BaseModel], context: OperationExecutorContext) -> NoReturn:
            del request, context
            raise make()

    return _Raising


def _served(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    make: Callable[[], BaseException],
    *,
    language: str,
) -> OperationErrorDetailV1:
    executor = _raising(make)
    case = _settle_and_read(
        tmp_path, _executor_registry(executor, executor), authority_operation=authority_operation, language=language
    )
    assert isinstance(case.detail, OperationResultProjectionSuccessV1)
    detail = case.detail.projection
    assert isinstance(detail, OperationErrorDetailV1)
    return detail


def _record_fault() -> BaseException:
    try:
        _BoundedRecord(actor=_OFFENDING_VALUE)
    except ValidationError as error:
        return error
    raise AssertionError("the bounded record admitted an over-long value")


def _advance_payment_fault() -> BaseException:
    try:
        _AdvancePaymentRecord(paid_in_full=False)
    except ValidationError as error:
        return error
    raise AssertionError("a partly collected advance payment was admitted")


@pytest.mark.parametrize("language", ["en", "es", "ca", "hu"])
def test_a_catalogue_refusal_serves_its_finished_sentence_in_the_worker_language(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation, language: str
) -> None:
    """The sentence is the one the in-process command prints, legal references included, in that language."""
    detail = _served(
        tmp_path, authority_operation, lambda: _past_cutoff_refusal(**_PAST_CUTOFF_CONTEXT), language=language
    )

    assert detail.refusal_words_language is OutputLanguage(language)
    assert detail.refusal_words == resolve_error_message(_past_cutoff_refusal(**_PAST_CUTOFF_CONTEXT), locale=language)
    assert detail.refusal_words is not None
    assert "Orden HAC/3625/2003, art. 3" in detail.refusal_words
    assert _CUTOFF_ON in detail.refusal_words
    # The machine-readable facts the CLI and MCP read are unchanged.
    assert detail.error_code == get_registered_error_code(ModeloDomiciliationPastCutoffError).code
    assert detail.message_key == "errors.refused.refused_modelo_domiciliation_past_cutoff"


def test_a_free_text_refusal_falls_back_to_its_code_sentence_and_never_serves_the_text(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """Prose an error site wrote is not catalogue wording: its code's own sentence is served instead."""
    prose = f"no contract for {_ROW_IDENTITY}"
    detail = _served(tmp_path, authority_operation, lambda: InvoiceValidationError(prose), language="es")

    registered = get_registered_error_code(InvoiceValidationError)
    assert detail.message_key is None
    assert detail.refusal_words == lookup_translation(registered.message_key, locale="es")
    assert _ROW_IDENTITY not in detail.model_dump_json()


def test_a_sentence_its_context_cannot_finish_names_the_code_rather_than_a_template(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """With its dates missing neither the key nor the code's sentence can be finished, so neither is served."""
    detail = _served(tmp_path, authority_operation, lambda: _past_cutoff_refusal(modelo="303"), language="ca")

    code = get_registered_error_code(ModeloDomiciliationPastCutoffError).code
    template = lookup_translation(UNWORDED_REGISTERED_ERROR_LOCALE_KEY, locale="ca")
    assert template is not None
    assert detail.refusal_words == template.replace("{error_code}", code)


def test_a_private_value_reaches_the_sentence_only_as_the_redaction_leaves_it(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """The sentence is filled from the scrubbed context, never from the error's raw values."""

    def refusal() -> CadrumoError:
        return ModeloCalculationBlockedError(
            translated_message="application.modelo.errors.calculate_m349_invalid_nif",
            context={"nif": _PRIVATE_NIF, "pais": "ES"},
        )

    detail = _served(tmp_path, authority_operation, refusal, language="en")

    assert detail.refusal_words is not None
    assert _REDACTED_VALUE in detail.refusal_words
    assert _PRIVATE_NIF[2:] not in detail.model_dump_json()


def test_a_rule_refused_inside_a_record_validator_serves_the_rule_sentence(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """The record fault keeps its shape, and the sentence is the refused rule's, not a generic fault."""
    detail = _served(tmp_path, authority_operation, _advance_payment_fault, language="hu")

    assert detail.kind is OperationErrorDetailKind.RECORD_VALIDATION
    assert detail.error_code is None and detail.message_key is None
    assert detail.refusal_words == lookup_translation(
        rule_finding_words_key(InvoiceRuleFindingCode.ADVANCE_PAYMENT_NOT_FULLY_COLLECTED), locale="hu"
    )


def test_a_record_fault_with_no_registered_rule_serves_the_record_fault_sentence(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """A record the application built that broke a plain field bound is worded as such, without its value."""
    detail = _served(tmp_path, authority_operation, _record_fault, language="en")

    assert detail.refusal_words == lookup_translation(RECORD_FAULT_WORDS_LOCALE_KEY, locale="en")
    assert _OFFENDING_VALUE[:20] not in detail.model_dump_json()


def _quarterless_refusal() -> BaseException:
    """The refusal the Modelo 100 estimate raises for a year with no quarterly declaration, with its step."""
    year = _YEAR
    return ModeloProjectNoM130UnitsError(
        context={"year": year},
        translated_message="application.modelo.projection_words.no_m130_units",
        precondition_verdict=build_modelo_precondition_failure_for_scenario(
            subject_leaf_key="modelo.project",
            scenario_id="modelo.project.m130_quarters.no_work_units",
            evidence_id="modelo.project.m130_quarters",
            evidence_values={"modelo": "130", "year": year, "work_units_present": False},
            provenance=ActionEvidenceProvenance.PERSISTED_STATE,
            action_argument_values={"modelo": "130", "period": "1T", "year": year},
        ).verdict,
        next_step=create_work_step(modelo="130", period=Period.from_year_and_code(year, "1T")),
    )


def test_a_refusal_releases_the_step_it_serves_worded_in_the_worker_language(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """The step reads back from the stored detail with the same address in every language and its own words."""
    served = {
        language: _served(tmp_path / language, authority_operation, _quarterless_refusal, language=language)
        for language in ("en", "es", "ca", "hu")
    }

    words: dict[str, str] = {}
    for language, detail in served.items():
        step = detail.next_step
        assert isinstance(step, OperationCreateWorkStepV1)
        assert (step.modelo, step.filing_year, step.period_code) == ("130", _YEAR, "1T")
        assert detail.refusal_words_language is OutputLanguage(language)
        assert "130" in step.words and str(_YEAR) in step.words
        words[language] = step.words
    assert len(set(words.values())) == len(words)


def test_a_refusal_with_no_step_releases_none_and_a_record_fault_cannot_carry_one(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    refused = _served(
        tmp_path / "refused",
        authority_operation,
        lambda: _past_cutoff_refusal(**_PAST_CUTOFF_CONTEXT),
        language="en",
    )
    fault = _served(tmp_path / "fault", authority_operation, _record_fault, language="en")
    carried = _served(tmp_path / "carried", authority_operation, _quarterless_refusal, language="en")
    assert refused.next_step is None and fault.next_step is None
    assert carried.next_step is not None

    with pytest.raises(ValidationError):
        OperationErrorDetailV1.model_validate(
            {**fault.model_dump(mode="json"), "next_step": carried.next_step.model_dump(mode="json")}
        )
