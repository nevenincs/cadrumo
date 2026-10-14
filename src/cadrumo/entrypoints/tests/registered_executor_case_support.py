"""Own the shared driver, isolated runtime, and request-submission setup for conformance cases."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Generator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from uuid import UUID

from pydantic import BaseModel

from cadrumo.adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope, default_browser_session_factory
from cadrumo.adapters.persistence.profile.tests.review_read_operation_test_support import (
    ReviewReadConformanceCase,
    prepare_review_read_conformance_case,
)
from cadrumo.adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts as _profile_contexts_for_test,
)
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from ...adapters.persistence.operations.journal import OperationJournalRepository
from ...adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ...adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ...adapters.persistence.operations.typed_financial_operand_custody import (
    OperationTypedFinancialOperandCustodyFilesystemRepository,
)
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ...adapters.persistence.profile.verify_observations import VerifyObservationRepository
from ...adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ...adapters.persistence.storage.tests.profile_session_setup import reset_test_profile_session
from ...adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ...application.auth.operation_definitions import build_auth_operation_definitions
from ...application.live.verify import VerifySurface
from ...application.live.verify_capture_operation import VerifyLiveObservation, build_verify_capture_definition
from ...application.modelo.amendment_action_ports import AmendmentActionPortsFactory
from ...application.modelo.edit_operator_input import ModeloEditOperatorInputV2, prepare_modelo_edit_operand
from ...application.operations.composition import (
    OperationComposedServices,
    OperationSubmission,
    compose_operation_services,
)
from ...application.operations.execution_actor import OperationExecutionCallerReader
from ...application.operations.frontend_projection import (
    OperationReviewAvailableInteractionV1,
    OperationReviewProjectionReferenceV1,
)
from ...application.operations.frontend_requests import (
    OperationCancellationRefusalV1,
    OperationCancellationRequestV1,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRequestV1,
    OperationResponseMutationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
    OperationReviewProjectionRefusalCode,
    OperationReviewProjectionRefusalV1,
    OperationReviewProjectionRequestV1,
)
from ...application.operations.models import OperationRequest
from ...application.operations.operation_definition import OperationDefinition
from ...application.operations.registry import OperationRegistry
from ...application.operations.subject_reference import OperationSubjectReferenceV1, expected_operation_subject
from ...application.user_profile.censal_observation import (
    CensalObservation,
    CensalObservationAddress,
    CensalObservationIdentity,
)
from ...application.user_profile.censal_operation import (
    CensalOperationAcquisition,
    CensalReviewProjectionV1,
    build_censal_operation_definition,
)
from ...application.user_profile.custody_ports import profile_custody_secure_object_repository
from ...application.user_profile.login_session import authenticate_profile_for_invocation
from ...application.user_profile.registration import register_profile_with_credentials
from ...core.identity_check_verdict import IdentityCheckVerdict
from ...core.operations import OperationLifecycle, profile_operation_subject
from ...core.time.clock import now
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.user_profile.values import UserProfileFact
from ...tests.aeat_literal_fixtures import aeat_url
from ..adapter_composition import build_amendment_action_ports, build_censal_fetch_port
from ..operation_composition import build_auth_operation_ports, build_production_operation_registry
from . import modelo_operation_test_support
from .conformance_diagnostics_repair_support import observe_synthetic_site
from .conformance_families import conformance_family_for
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    closed_model_runtime,
)
from .evidence_followup_operation_test_support import (
    EvidenceFollowupConformanceCase,
    prepare_evidence_followup_conformance_case,
)
from .invoice_evidence_operation_test_support import (
    InvoiceEvidenceConformanceCase,
    prepare_invoice_evidence_conformance_case,
)
from .ledger_attachment_operation_test_support import (
    LedgerAttachmentOperationConformanceCase,
    prepare_ledger_attachment_operation_conformance_case,
)
from .ledger_lifecycle_operation_test_support import LedgerLifecycleOperationConformanceCase
from .ledger_rule_operation_test_support import (
    LedgerRuleOperationConformanceCase,
    prepare_ledger_rule_operation_conformance_case,
)
from .modelo_projection_history_conformance_support import (
    ModeloProjectionHistoryConformanceCase,
    prepare_modelo_projection_history_conformance_case,
)
from .modelo_query_operation_test_support import ModeloQueryConformanceCase, prepare_modelo_query_conformance_case
from .prorrata_operation_test_support import ProrrataOperationConformanceCase
from .recipient_operation_test_support import RecipientOperationConformanceCase, prepare_recipient_operation_case
from .registered_executor_payload_support import _payload
from .registered_executor_scenario_constants import _CREDENTIAL_INPUT, _OPERATOR_SCOPE_PORTS
from .registered_executor_seeding_support import _ledger_lifecycle_case, _prorrata_case


@dataclass(slots=True)
class _CloseWitness:
    """Observe cleanup owned by the actual CENSO executor."""

    closed: bool = False

    async def close(self) -> None:
        self.closed = True


class _HeldClock:
    """A supervisor clock that stands still until released, then reads real time.

    The supervisor measures its execution deadline on this clock, so while it
    is held no amount of host slowness can expire the deadline before the
    executor has suspended at its review.
    """

    def __init__(self) -> None:
        self._held_at: datetime | None = now()

    def __call__(self) -> datetime:
        return now() if self._held_at is None else self._held_at

    def release(self) -> None:
        self._held_at = None


@dataclass(slots=True)
class _ExecutionDriver:
    """Single registered execution driver over the canonical composed supervisor."""

    services: OperationComposedServices

    async def prepare(self, *, definition_id: str, subject_ref: str, payload: BaseModel, secret: bytes | None = None):
        if isinstance(payload, ModeloEditOperatorInputV2):
            prepared = prepare_modelo_edit_operand(
                definition_id=definition_id,
                profile_id=UUID(payload.submission.baseline.bucket_id),
                subject_ref=subject_ref,
                input_json=payload.model_dump_json(),
            )
            try:
                submitted = await self.services.submission.submit(
                    OperationRequest(definition_id=definition_id, subject_ref=subject_ref, payload=prepared.request),
                    actor_ref=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                )
                assert prepared.operand is not None
                await self.services.submission.supervisor.bind_typed_financial_operand(
                    submitted.receipt.operation_id, prepared.operand
                )
                return submitted
            finally:
                prepared.release()
        submitted = await self.services.submission.submit(
            OperationRequest(definition_id=definition_id, subject_ref=subject_ref, payload=payload),
            actor_ref=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        )
        requirement = submitted.receipt.secret_requirement
        if requirement is not None:
            assert secret is not None
            buffer = bytearray(secret)
            await self.services.submission.submit_secret(requirement, buffer)
            assert buffer == bytearray(len(secret))
        else:
            assert secret is None
        return submitted

    async def run(self, *, definition_id: str, subject_ref: str, payload: BaseModel, secret: bytes | None = None):
        submitted = await self.prepare(
            definition_id=definition_id,
            subject_ref=subject_ref,
            payload=payload,
            secret=secret,
        )
        before_start = await self.observe(submitted.receipt.operation_id)
        if not isinstance(payload, ModeloEditOperatorInputV2):
            cancellation = await self.services.cancellation.request(
                OperationCancellationRequestV1(
                    operation_id=submitted.receipt.operation_id, expected_revision=before_start.projection.revision
                )
            )
            assert isinstance(cancellation, OperationCancellationRefusalV1)
        await self.services.submission.start(submitted.receipt.operation_id)
        await self.services.submission.settled(submitted.receipt.operation_id)
        return submitted, await self.observe(submitted.receipt.operation_id)

    async def observe(self, operation_id: str) -> OperationObservationSuccessV1:
        observed = await self.services.observation.observe(
            OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=256)
        )
        assert isinstance(observed, OperationObservationSuccessV1)
        return observed

    async def respond_apply(self, submitted: OperationSubmission, observed: OperationObservationSuccessV1) -> str:
        pending = observed.projection.pending_interaction
        assert isinstance(pending, OperationReviewAvailableInteractionV1)
        response = await self.services.response(
            OperationResponseControlRequestV1(
                operation_id=pending.operation_id,
                interaction_id=pending.interaction_id,
                revision=pending.revision,
                actor_ref=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            ),
            submitted.response_capability,
        )
        accepted = await response.apply(
            OperationResponseApplyRequestV1(
                operation_id=pending.operation_id,
                interaction_id=pending.interaction_id,
                revision=pending.revision,
                actor_ref=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                responded_at=now(),
            )
        )
        assert isinstance(accepted, OperationResponseMutationSuccessV1)
        return pending.operation_id

    async def apply_review(
        self, submitted: OperationSubmission, observed: OperationObservationSuccessV1
    ) -> OperationObservationSuccessV1:
        operation_id = await self.respond_apply(submitted, observed)
        return await self.await_terminal(operation_id)

    async def await_terminal(self, operation_id: str) -> OperationObservationSuccessV1:
        """Observe a public terminal projection after real executor work completes."""
        for _ in range(100):
            observed = await self.observe(operation_id)
            if observed.projection.lifecycle is OperationLifecycle.TERMINAL:
                return observed
            await asyncio.sleep(0)
        raise AssertionError("review continuation did not settle")

    async def review_not_pending(self, *, operation_id: str, revision: int, registry: OperationRegistry) -> None:
        """Prove the public REVIEW control truthfully refuses an operation without a pending review."""
        review_contract = registry.lookup_public_contract("user-profile.censo-review")
        assert review_contract.review_projection_schema is not None
        result = await self.services.review.resolve(
            OperationReviewProjectionRequestV1(
                reference=OperationReviewProjectionReferenceV1(
                    operation_id=operation_id,
                    interaction_id="0" * 64,
                    revision=revision,
                    review_projection_schema=review_contract.review_projection_schema,
                    definition_contract_digest=review_contract.definition_contract_digest,
                    expires_at=None,
                )
            ),
            CensalReviewProjectionV1,
        )
        assert isinstance(result, OperationReviewProjectionRefusalV1)
        assert result.code is OperationReviewProjectionRefusalCode.REVIEW_NOT_PENDING


def _resolve_result_projection[ProjectionT: BaseModel](
    driver: _ExecutionDriver,
    registry: OperationRegistry,
    *,
    definition_id: str,
    operation_id: str,
    terminal_revision: int,
    projection_type: type[ProjectionT],
) -> ProjectionT:
    """Resolve one typed public result through encrypted operand custody."""
    contract = registry.lookup_public_contract(definition_id)
    assert contract.result_schema is not None
    result = asyncio.run(
        driver.services.result.resolve(
            OperationResultProjectionRequestV1(
                operation_id=operation_id,
                terminal_revision=terminal_revision,
                definition_contract_digest=contract.definition_contract_digest,
                result_schema=contract.result_schema,
            ),
            projection_type,
        )
    )
    assert isinstance(result, OperationResultProjectionSuccessV1)
    assert isinstance(result.projection, projection_type)
    return result.projection


@dataclass(frozen=True, slots=True)
class _FamilyResultResolver:
    """Bind one settled operation's public result resolution for a family's own checks."""

    driver: _ExecutionDriver
    registry: OperationRegistry
    definition_id: str
    operation_id: str
    terminal_revision: int

    def __call__[ProjectionT: BaseModel](self, projection_type: type[ProjectionT], /) -> ProjectionT:
        projection = _resolve_result_projection(
            self.driver,
            self.registry,
            definition_id=self.definition_id,
            operation_id=self.operation_id,
            terminal_revision=self.terminal_revision,
            projection_type=projection_type,
        )
        assert isinstance(projection, projection_type)
        return projection


_MODEL_RUNTIME_CLOSED_DEFINITIONS = frozenset(
    {
        "local-reader.provision",
        "ledger.evidence.reader-readiness",
        "ledger.evidence.extract",
        "ledger.evidence.confirm",
    }
)


@contextmanager
def _model_runtime_for(definition_id: str) -> Generator[None]:
    """Close the local model runtime, and enter the family's own environment, for an operation that needs either."""
    family = conformance_family_for(definition_id)
    with ExitStack() as host:
        if definition_id in _MODEL_RUNTIME_CLOSED_DEFINITIONS or (family is not None and family.closes_model_runtime):
            host.enter_context(closed_model_runtime())
        if family is not None and family.host_environment is not None:
            host.enter_context(family.host_environment())
        yield


def _prepare_family_case(
    definition: OperationDefinition,
    *,
    profile_id: UUID,
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    family: ConformanceFamily | None = None,
) -> ConformancePreparation | None:
    """Seed and build the request of an operation whose family owns its scenario."""
    family = family or conformance_family_for(definition.definition_id)
    if family is None:
        return None
    input_root = tmp_path / "family-inputs"
    input_root.mkdir()
    return family.prepare(
        ConformanceFamilyContext(
            definition=definition,
            profile_id=profile_id,
            profile_passphrase=_CREDENTIAL_INPUT,
            input_root=input_root,
            operation=operation,
        )
    )


def _judge_family_outcome(
    preparation: ConformancePreparation | None,
    *,
    driver: _ExecutionDriver,
    registry: OperationRegistry,
    profile_id: UUID,
    operation_id: str,
    observed: OperationObservationSuccessV1,
) -> None:
    """Compare a family's independently built result, then run its own outcome checks."""
    if preparation is None:
        return
    outcome = ConformanceOutcome(
        profile_id=profile_id,
        operation_id=operation_id,
        observed=observed,
        resolve_result=_FamilyResultResolver(
            driver=driver,
            registry=registry,
            definition_id=observed.projection.definition_id,
            operation_id=operation_id,
            terminal_revision=observed.projection.revision,
        ),
    )
    expected = preparation.expected_result
    if expected is not None:
        actual = outcome.resolve_result(type(expected))
        actual_fields = actual.model_dump(mode="json")
        expected_fields = expected.model_dump(mode="json")
        assert actual == expected, {
            key: (actual_fields.get(key), expected_fields.get(key))
            for key in actual_fields.keys() | expected_fields.keys()
            if actual_fields.get(key) != expected_fields.get(key)
        }
    if preparation.verify is not None:
        preparation.verify(outcome)


def _observation() -> CensalObservation:
    return CensalObservation(
        identity=CensalObservationIdentity(nif="12345678Z"),
        domicilio_fiscal=CensalObservationAddress(
            tipo_via="CALLE",
            nombre_via="Mayor",
            numero_casa="7",
            codigo_postal="28013",
            referencia_catastral="1234567VK4713C0001AB",
        ),
        domicilio_notificacion=CensalObservationAddress(),
        captured_at=datetime(2026, 8, 24, 18, tzinfo=UTC),
        source_url=aeat_url("sede", "/censo/consulta"),
    )


@contextmanager
def _runtime(
    tmp_path: Path,
    *,
    cleanup: _CloseWitness,
    before_irreversible_section: Callable[[], Awaitable[None]] | None = None,
    execution_timeout: timedelta = timedelta(hours=1),
    amendment_action_ports_factory: AmendmentActionPortsFactory | None = None,
    clock: Callable[[], datetime] = now,
    execution_caller_reader: OperationExecutionCallerReader | None = None,
) -> Generator[tuple[_ExecutionDriver, OperationRegistry, UUID]]:
    """Fresh production profile, inventory, journal, lease, and operand custody per case."""
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()

    async def acquire_censo() -> CensalOperationAcquisition:
        return CensalOperationAcquisition(observation=_observation(), resource=cleanup)

    async def acquire_verify(surface, nif, expected, operation) -> VerifyLiveObservation:
        del surface, expected, operation
        return VerifyLiveObservation(nif=nif, verdict=IdentityCheckVerdict.VALID)

    def verify_definition(surface: VerifySurface) -> OperationDefinition:
        return build_verify_capture_definition(
            surface,
            persistence_factory=lambda bucket_id: VerifyObservationRepository(bucket_id=bucket_id),
            acquire=acquire_verify,
            browser_resources_factory=BrowserRuntimeResourceScope,
            provider_preflight=lambda _profile_id, _operation: None,
        )

    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        enrolled = register_profile_with_credentials(
            label="S45 registered executor subject",
            passphrase=_CREDENTIAL_INPUT,
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
            profile_create_context=_profile_create_context_for_test,
            profile_decode_context=_profile_decode_context_for_test,
        )
        profile_id = UUID(enrolled.profile_id)
        authenticate_profile_for_invocation(
            name=enrolled.profile_id,
            passphrase_callback=lambda: _CREDENTIAL_INPUT,
            profile_decode_context=_profile_decode_context_for_test,
        )
        registry = build_production_operation_registry(
            auth_definitions=build_auth_operation_definitions(ports=build_auth_operation_ports()),
            censal_definition=build_censal_operation_definition(
                certificate_secret_backend_factory=build_certificate_secret_backend,
                browser_session_factory=default_browser_session_factory,
                acquire=acquire_censo,
                before_irreversible_section=before_irreversible_section,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                censal_fetch_port=build_censal_fetch_port(),
                provider_preflight=lambda _profile_id, _operation: None,
            ),
            verify_nif_iva_definition=verify_definition(VerifySurface.NIF_IVA),
            verify_tgvi_definition=verify_definition(VerifySurface.TGVI),
            amendment_action_ports_factory=amendment_action_ports_factory or build_amendment_action_ports,
            execution_caller_reader=execution_caller_reader,
            connectivity_probe=observe_synthetic_site,
        )
        journal = OperationJournalRepository(storage_root=root / "operations")
        with profile_custody_secure_object_repository(profile_id=profile_id, dek=b"", root=root) as objects:
            authority_scope = bundled_indexed_authority().operation()
            authority_operation = authority_scope.__enter__()
            services = compose_operation_services(
                registry=registry,
                authority_operation=authority_operation,
                journal=journal,
                reader=journal,
                event_stream=journal,
                leases=OperationLeaseFilesystemRepository(storage_root=root / "operations"),
                operands=operation_secure_reference_repository(objects=cast(SecureObjectRepository, objects)),
                owner_id="1" * 64,
                lease_token_factory=lambda: "2" * 64,
                clock=clock,
                lease_duration=timedelta(minutes=10),
                execution_timeout=execution_timeout,
                cleanup_timeout=timedelta(minutes=2),
                typed_financial_operand_custody=OperationTypedFinancialOperandCustodyFilesystemRepository(
                    root=root / "operations" / "typed_financial_operand_custody",
                ),
            )
            try:
                yield _ExecutionDriver(services=services), registry, profile_id
            finally:
                asyncio.run(services.shutdown())
                authority_scope.__exit__(None, None, None)
                # The login above binds this process's live session; a runtime
                # that leaves it open hands every later test in the worker a
                # logged-in profile it never created.
                reset_test_profile_session()


@dataclass(frozen=True, slots=True)
class _ConformanceSubmission:
    """One seeded request, the subject its definition declares for it, and its family's scenario.

    ``payload`` is what the driver is handed; ``registered_payload`` is the
    request model the definition itself takes, which differs only where an
    intake turns operator input into that request.
    """

    subject_ref: str
    payload: BaseModel
    registered_payload: BaseModel
    secret: bytes | None
    family_preparation: ConformancePreparation | None
    projection_history_case: ModeloProjectionHistoryConformanceCase | None
    query_case: ModeloQueryConformanceCase | None
    review_case: ReviewReadConformanceCase | None
    followup_case: EvidenceFollowupConformanceCase | None
    recipient_case: RecipientOperationConformanceCase | None
    attachment_case: LedgerAttachmentOperationConformanceCase | None
    lifecycle_case: LedgerLifecycleOperationConformanceCase | None
    rule_case: LedgerRuleOperationConformanceCase | None
    prorrata_case: ProrrataOperationConformanceCase | None
    evidence_case: InvoiceEvidenceConformanceCase | None


def _registered_payload(definition_id: str, *, written_subject: str, payload: BaseModel) -> BaseModel:
    """The request model the definition takes; an edit arrives as operator input its intake turns into one."""
    if not isinstance(payload, ModeloEditOperatorInputV2):
        return payload
    prepared = prepare_modelo_edit_operand(
        definition_id=definition_id,
        profile_id=UUID(payload.submission.baseline.bucket_id),
        subject_ref=written_subject,
        input_json=payload.model_dump_json(),
    )
    try:
        return prepared.request
    finally:
        prepared.release()


def _stored_work_unit_id(
    reference: OperationSubjectReferenceV1, payload: BaseModel, *, operation: PinnedAuthorityOperation
) -> str:
    """Read from the real catalogues the work unit that owns the record the declared key names."""
    key: object = payload
    for name in reference.payload_path:
        key = getattr(key, name)
    assert isinstance(key, str)
    if reference.payload_path[-1] == "from_filing_record_id":
        filing = ModeloRecordCatalogueRepository().load().get(key)
        assert filing is not None
        return filing.work_unit_id
    revision = CalculationRevisionCatalogueRepository().load(operation=operation).get(key)
    assert revision is not None
    return revision.work_unit_id


def _declared_subject(
    definition: OperationDefinition, *, profile_id: UUID, payload: BaseModel, operation: PinnedAuthorityOperation
) -> str:
    """Render the subject from the definition's own declaration, asking the store only for a stored work unit."""
    declared = expected_operation_subject(definition.subject_reference, profile_id=profile_id, payload=payload)
    if declared is not None:
        return declared
    return _stored_work_unit_id(definition.subject_reference, payload, operation=operation)


def _seeded_conformance_submission(
    definition: OperationDefinition,
    *,
    profile_id: UUID,
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    family: ConformanceFamily | None = None,
) -> _ConformanceSubmission:
    """Seed one operation's scenario and address it by the subject its definition declares.

    Each scenario also writes the subject it expects by hand. The two are
    compared here, so the declaration is held to an independently written
    value before any executor or resolver sees the derived one.
    """
    family_preparation = _prepare_family_case(
        definition, profile_id=profile_id, tmp_path=tmp_path, operation=operation, family=family
    )
    projection_history_case = (
        prepare_modelo_projection_history_conformance_case(
            definition.definition_id, profile_id=profile_id, operation=operation
        )
        if definition.definition_id in {"modelo.history", "modelo.history.timeline", "modelo.project", "modelo.compare"}
        else None
    )
    query_case = (
        prepare_modelo_query_conformance_case(definition.definition_id, profile_id=profile_id, operation=operation)
        if definition.definition_id
        in {
            "modelo.bindings.list",
            "modelo.bindings.resolve",
            "modelo.bindings.resolve.typed",
            "modelo.requires",
            "modelo.readiness",
            "modelo.readiness.summary",
        }
        else None
    )
    review_case = (
        prepare_review_read_conformance_case(definition.definition_id, profile_id=profile_id, operation=operation)
        if definition.definition_id in {"app.review.queue", "app.review.view"}
        else None
    )
    followup_case = (
        prepare_evidence_followup_conformance_case(definition.definition_id, profile_id=profile_id, operation=operation)
        if definition.definition_id
        in {
            "ledger.evidence.attachment_queue",
            "ledger.evidence.attachment_view",
            "ledger.evidence.consent.list",
            "ledger.evidence.review.list",
            "ledger.evidence.review.view",
        }
        else None
    )
    recipient_case = (
        prepare_recipient_operation_case(definition.definition_id, profile_id)
        if definition.definition_id.startswith("config.collab.recipient.")
        else None
    )
    attachment_case = (
        prepare_ledger_attachment_operation_conformance_case(definition.definition_id, profile_id, operation=operation)
        if definition.definition_id in {"ledger.attach", "ledger.detach"}
        else None
    )
    lifecycle_case = (
        _ledger_lifecycle_case(definition.definition_id, profile_id=profile_id, operation=operation)
        if definition.definition_id in {"ledger.archive", "ledger.stash", "ledger.restore", "ledger.exclude"}
        else None
    )
    rule_case = (
        prepare_ledger_rule_operation_conformance_case(definition.definition_id, profile_id, operation=operation)
        if definition.definition_id in {"ledger.rule.add", "ledger.rule.list", "ledger.rule.apply"}
        else None
    )
    prorrata_case = (
        _prorrata_case(definition.definition_id, profile_id=profile_id, operation=operation)
        if definition.definition_id.startswith("ledger.prorrata.")
        else None
    )
    evidence_case = (
        prepare_invoice_evidence_conformance_case(definition.definition_id, profile_id=profile_id, operation=operation)
        if definition.definition_id
        in {"ledger.evidence.reader-readiness", "ledger.evidence.extract", "ledger.evidence.confirm"}
        else None
    )
    if family_preparation is not None:
        subject_ref, payload, secret = (
            family_preparation.subject_ref,
            family_preparation.request,
            family_preparation.secret,
        )
    elif query_case is not None:
        subject_ref, payload, secret = profile_operation_subject(str(profile_id)), query_case.request, None
    elif projection_history_case is not None:
        subject_ref, payload, secret = (
            profile_operation_subject(str(profile_id)),
            projection_history_case.request,
            None,
        )
    elif review_case is not None:
        subject_ref, payload, secret = profile_operation_subject(str(profile_id)), review_case.request, None
    elif followup_case is not None:
        subject_ref, payload, secret = profile_operation_subject(str(profile_id)), followup_case.request, None
    elif recipient_case is not None:
        subject_ref, payload, secret = profile_operation_subject(str(profile_id)), recipient_case.request, None
    elif attachment_case is not None:
        subject_ref, payload, secret = profile_operation_subject(str(profile_id)), attachment_case.request, None
    elif lifecycle_case is not None:
        subject_ref, payload, secret = profile_operation_subject(str(profile_id)), lifecycle_case.request, None
    elif rule_case is not None:
        subject_ref, payload, secret = profile_operation_subject(str(profile_id)), rule_case.request, None
    elif evidence_case is not None:
        subject_ref, payload, secret = profile_operation_subject(str(profile_id)), evidence_case.request, None
    elif prorrata_case is None:
        subject_ref, payload, secret = _payload(
            definition, profile_id=profile_id, tmp_path=tmp_path / definition.definition_id, operation=operation
        )
    else:
        subject_ref, payload, secret = profile_operation_subject(str(profile_id)), prorrata_case.request, None
    registered_payload = _registered_payload(definition.definition_id, written_subject=subject_ref, payload=payload)
    declared_subject = _declared_subject(
        definition, profile_id=profile_id, payload=registered_payload, operation=operation
    )
    assert declared_subject == subject_ref, (
        f"{definition.definition_id} declares {definition.subject_reference.model_dump(mode='json')}, "
        f"which renders {declared_subject!r}; its scenario addresses it as {subject_ref!r}"
    )
    return _ConformanceSubmission(
        subject_ref=declared_subject,
        payload=payload,
        registered_payload=registered_payload,
        secret=secret,
        family_preparation=family_preparation,
        projection_history_case=projection_history_case,
        query_case=query_case,
        review_case=review_case,
        followup_case=followup_case,
        recipient_case=recipient_case,
        attachment_case=attachment_case,
        lifecycle_case=lifecycle_case,
        rule_case=rule_case,
        prorrata_case=prorrata_case,
        evidence_case=evidence_case,
    )
