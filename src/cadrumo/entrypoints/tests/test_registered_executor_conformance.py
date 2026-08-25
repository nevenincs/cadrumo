"""Real-supervisor conformance matrix for every production executor."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.application.operations.composition import (
    OperationComposedServices,
    OperationSubmission,
    compose_operation_services,
)
from cadrumo.application.operations.frontend_contracts import (
    OperationCancellationRefusalV1,
    OperationCancellationRequestV1,
    OperationCancellationSuccessV1,
    OperationNoPendingInteractionV1,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationPublicPhaseEventV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRequestV1,
    OperationResponseMutationSuccessV1,
    OperationReviewAvailableInteractionV1,
    OperationReviewProjectionReferenceV1,
    OperationReviewProjectionRefusalCode,
    OperationReviewProjectionRefusalV1,
    OperationReviewProjectionRequestV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import (
    OperationDefinition,
    OperationRegistry,
)

from ...adapters.persistence.storage import SecureObjectRepository
from ...application.auth.operation_definitions import build_auth_operation_definitions
from ...application.export import build_google_sheets_export_operation_definition
from ...application.user_profile.censo_sync import CENSAL_ADOPTABLE_PATHS
from ...application.user_profile.censal_operation import CensalFieldIntent, CensalOperationAcquisition, CensalProfileBaseline, CensalReviewedFieldIntent, build_censal_operation_definition
from ...application.user_profile.censal_observation import CensalObservation, CensalObservationAddress, CensalObservationIdentity
from cadrumo.application.user_profile.bundle_export_contracts import ProfileBundleExportPurpose
from ...application.user_profile.profile_record_repository import ProfileRecordRepository
from ...application.user_profile.login_session import login_profile
from ...application.user_profile.custody_ports import profile_custody_secure_object_repository
from ...application.user_profile.registration import register_profile_with_credentials
from ...core import AuthProviderKind, OperationEffect, OperationLifecycle, OperationTerminalCondition
from ...core.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from ...core.time import now
from ...domain.user_profile.values import UserProfileFact
from ...tests.aeat_literal_fixtures import aeat_url
from ...tests.secure_sql import isolated_profile_storage_root
from .. import build_production_operation_registry
from .._censal_review import _run as run_censal_review_through_services

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PASSPHRASE = "s45-registered-executor-passphrase"  # noqa: S105 - isolated integration fixture
_ROTATED_PASSPHRASE = "s45-registered-executor-rotated-passphrase"  # noqa: S105
_ACTOR = "operator:s45"


@dataclass(frozen=True, slots=True)
class _RegisteredExecutorConformanceCase:
    definition_id: str
    expected_terminal: OperationTerminalCondition
    expected_effect: OperationEffect
    expected_phase_codes: tuple[str, ...] | None = None
    expected_refusal_ref: str | None = None


_MATRIX = (
    _RegisteredExecutorConformanceCase(
        "auth.profile.login", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
    ),
    _RegisteredExecutorConformanceCase(
        "auth.profile.passphrase-rotate", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
    ),
    _RegisteredExecutorConformanceCase(
        "auth.provider.configure", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
    ),
    _RegisteredExecutorConformanceCase(
        "auth.session.acquire",
        OperationTerminalCondition.REFUSED,
        OperationEffect.UNKNOWN,
        expected_refusal_ref="REFUSED_AUTH_LOGIN_LIVE_TESTS_DISABLED",
    ),
    _RegisteredExecutorConformanceCase(
        "auth.session.logout", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
    ),
    _RegisteredExecutorConformanceCase(
        "auth.session.reset", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
    ),
    _RegisteredExecutorConformanceCase(
        "user-profile.field-mutation", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
    ),
    _RegisteredExecutorConformanceCase(
        "user-profile.repeatable-row-mutation", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
    ),
    _RegisteredExecutorConformanceCase(
        "user-profile.bundle-export", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
    ),
    _RegisteredExecutorConformanceCase(
        "user-profile.logout", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
    ),
    _RegisteredExecutorConformanceCase(
        "live.filed-history.pull",
        OperationTerminalCondition.REFUSED,
        OperationEffect.NONE,
        expected_refusal_ref="REFUSED_ACCESS_GATE_LIVE_READ_NOT_ENABLED",
    ),
    _RegisteredExecutorConformanceCase(
        "export.google-sheets",
        OperationTerminalCondition.FAILED,
        OperationEffect.UNKNOWN,
        (
            "export.google-sheets.preflight",
            "export.google-sheets.plan",
            "export.google-sheets.apply",
        ),
    ),
    _RegisteredExecutorConformanceCase(
        "user-profile.censo-review", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
    ),
)


@dataclass(slots=True)
class _CloseWitness:
    """Observe cleanup owned by the actual CENSO executor."""

    closed: bool = False

    async def close(self) -> None:
        self.closed = True


@dataclass(slots=True)
class _ExecutionDriver:
    """Single registered execution driver over the canonical composed supervisor."""

    services: OperationComposedServices

    async def prepare(self, *, definition_id: str, subject_ref: str, payload: BaseModel, secret: bytes | None = None):
        submitted = await self.services.submission.submit(
            OperationRequest(definition_id=definition_id, subject_ref=subject_ref, payload=payload), actor_ref=_ACTOR
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
        cancellation = await self.services.cancellation.request(
            OperationCancellationRequestV1(
                operation_id=submitted.receipt.operation_id, expected_revision=before_start.projection.revision
            )
        )
        assert isinstance(cancellation, OperationCancellationRefusalV1)
        await self.services.submission.start(submitted.receipt.operation_id)
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
                actor_ref=_ACTOR,
            ),
            submitted.response_capability,
        )
        accepted = await response.apply(
            OperationResponseApplyRequestV1(
                operation_id=pending.operation_id,
                interaction_id=pending.interaction_id,
                revision=pending.revision,
                actor_ref=_ACTOR,
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
            )
        )
        assert isinstance(result, OperationReviewProjectionRefusalV1)
        assert result.code is OperationReviewProjectionRefusalCode.REVIEW_NOT_PENDING


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


def _payload(
    definition: OperationDefinition, *, profile_id: UUID, tmp_path: Path
) -> tuple[str, BaseModel, bytes | None]:
    """Use only the exact request type exported by the registered definition."""
    values: dict[str, object]
    secret: bytes | None = None
    subject_ref = f"profile:{profile_id}"
    match definition.definition_id:
        case "auth.profile.login":
            values = {"profile_id": profile_id}
            secret = _PASSPHRASE.encode()
        case "auth.profile.passphrase-rotate":
            values = {"profile_id": profile_id}
            secret = (
                '{"current_passphrase":"'
                + _PASSPHRASE
                + '","new_passphrase":"'
                + _ROTATED_PASSPHRASE
                + '","new_passphrase_confirmation":"'
                + _ROTATED_PASSPHRASE
                + '"}'
            ).encode()
        case "auth.provider.configure":
            values = {"provider": AuthProviderKind.CERTIFICATE}
        case "auth.session.acquire":
            values = {}
        case "auth.session.logout" | "auth.session.reset":
            values = {"all_providers": True}
        case "user-profile.field-mutation":
            values = {"profile_id": profile_id, "path": PROFILE_OUTPUT_LANGUAGE_PATH, "value": "es"}
        case "user-profile.repeatable-row-mutation":
            values = {
                "profile_id": profile_id,
                "section_key": "activities",
                "values": ({"field_key": "description", "value": "Consultoria"},),
            }
        case "user-profile.bundle-export":
            values = {
                "profile_id": profile_id,
                "destination": tmp_path / "profile.bundle",
                "purpose": ProfileBundleExportPurpose.PORTABLE_TRANSFER,
            }
            secret = _PASSPHRASE.encode()
        case "user-profile.logout":
            values = {"profile_id": profile_id}
        case "live.filed-history.pull":
            subject_ref = str(profile_id)
            values = {"output_root": tmp_path / "filed-history", "dry_run": True}
        case "export.google-sheets":
            values = {"profile_id": profile_id, "modelo": "130", "filing_year": 2025, "period": "1T", "dry_run": False}
        case "user-profile.censo-review":
            subject_ref = str(profile_id)
            record = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
            values = {
                "baseline": CensalProfileBaseline.from_record(record),
                "field_intents": tuple(
                    CensalReviewedFieldIntent(path=path, intent=CensalFieldIntent.ADOPT)
                    for path in CENSAL_ADOPTABLE_PATHS
                ),
            }
        case _:  # pragma: no cover - matrix completeness assertion below prevents this branch.
            raise AssertionError(f"no S45 public scenario for {definition.definition_id}")
    return subject_ref, definition.request_type.model_validate(values, strict=True), secret


@contextmanager
def _runtime(
    tmp_path: Path,
    *,
    cleanup: _CloseWitness,
    before_irreversible_section: Callable[[], Awaitable[None]] | None = None,
    execution_timeout: timedelta = timedelta(hours=1),
) -> Generator[tuple[_ExecutionDriver, OperationRegistry, UUID]]:
    """Fresh production profile, inventory, journal, lease, and operand custody per case."""

    async def acquire_censo() -> CensalOperationAcquisition:
        return CensalOperationAcquisition(observation=_observation(), resource=cleanup)

    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        enrolled = register_profile_with_credentials(
            label="S45 registered executor subject",
            passphrase=_PASSPHRASE,
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
        )
        profile_id = UUID(enrolled.profile_id)
        initial_login = login_profile(name=enrolled.profile_id, passphrase_callback=lambda: _PASSPHRASE)
        registry = build_production_operation_registry(
            auth_definitions=build_auth_operation_definitions(profile_login=lambda **_kwargs: initial_login),
            censal_definition=build_censal_operation_definition(
                acquire=acquire_censo,
                before_irreversible_section=before_irreversible_section,
            ),
            google_export_definition=build_google_sheets_export_operation_definition(),
        )
        journal = OperationJournalRepository(storage_root=root / "operations")
        with profile_custody_secure_object_repository(profile_id=profile_id, dek=b"", root=root) as objects:
            services = compose_operation_services(
                registry=registry,
                journal=journal,
                reader=journal,
                event_stream=journal,
                leases=OperationLeaseFilesystemRepository(storage_root=root / "operations"),
                operands=operation_secure_reference_repository(objects=cast(SecureObjectRepository, objects)),
                owner_id="1" * 64,
                lease_token_factory=lambda: "2" * 64,
                clock=now,
                lease_duration=timedelta(minutes=10),
                execution_timeout=execution_timeout,
                cleanup_timeout=timedelta(minutes=2),
            )
            try:
                yield _ExecutionDriver(services=services), registry, profile_id
            finally:
                asyncio.run(services.shutdown())


@pytest.mark.parametrize("apply", [True, False], ids=["apply", "reject"])
def test_censal_frontend_driver_reviews_one_acquisition_and_rolls_back_rejection(
    tmp_path: Path,
    apply: bool,
) -> None:
    """The public frontend driver answers the encrypted exact proposal once."""
    cleanup = _CloseWitness()
    with _runtime(tmp_path / f"frontend-{apply}", cleanup=cleanup) as (driver, _registry, profile_id):
        repository = ProfileRecordRepository.for_current_session(profile_id)
        before = repository.load(profile_id)
        decisions: list[tuple[str | None, ...]] = []

        def decide(projection) -> bool:
            decisions.append(tuple(field.observed_value for field in projection.fields))
            return apply

        result = asyncio.run(
            run_censal_review_through_services(
                actor_ref="operator:frontend-test",
                decide=decide,
                services=driver.services,
            )
        )

        assert result.applied is apply
        assert len(decisions) == 1
        assert len(decisions[0]) == len(CENSAL_ADOPTABLE_PATHS)
        assert decisions[0][0]
        assert decisions[0][1] == "28013"
        assert cleanup.closed is True
        after = repository.load(profile_id)
        if apply:
            assert after.record_revision == before.record_revision + 1
            assert after.content_digest != before.content_digest
        else:
            assert after == before


def test_censal_frontend_driver_never_reports_a_failed_terminal_as_applied(tmp_path: Path) -> None:
    """An accepted response followed by a failed continuation stays a failure."""
    cleanup = _CloseWitness()
    with _runtime(tmp_path / "frontend-failed", cleanup=cleanup) as (driver, _registry, _profile_id):
        delegate = driver.services.observation

        class _FailedTerminalObservation:
            async def observe(self, request):
                observed = await delegate.observe(request)
                if (
                    isinstance(observed, OperationObservationSuccessV1)
                    and observed.projection.lifecycle is OperationLifecycle.TERMINAL
                ):
                    return observed.model_copy(
                        update={
                            "projection": observed.projection.model_copy(
                                update={
                                    "terminal_condition": OperationTerminalCondition.FAILED,
                                    "effect": OperationEffect.UNKNOWN,
                                    "result_ref": None,
                                    "diagnostic_ref": "diagnostic:censo-stale",
                                }
                            )
                        }
                    )
                return observed

        failed_services = replace(driver.services, observation=_FailedTerminalObservation())
        with pytest.raises(RuntimeError, match="did not succeed"):
            asyncio.run(
                run_censal_review_through_services(
                    actor_ref="operator:frontend-failed-test",
                    decide=lambda _projection: True,
                    services=failed_services,
                )
            )


@pytest.mark.parametrize("case", _MATRIX, ids=lambda case: case.definition_id)
@pytest.mark.timeout(90)
def test_every_production_registered_executor_runs_through_the_shared_supervisor_matrix(
    tmp_path: Path, case: _RegisteredExecutorConformanceCase
) -> None:
    """Actual execution, effects, settlement, review, cleanup, and truthful control refusal."""
    assert len({case.definition_id for case in _MATRIX}) == len(_MATRIX)
    cleanup = _CloseWitness()
    with _runtime(tmp_path / case.definition_id, cleanup=cleanup) as (driver, registry, profile_id):
        definitions = {definition.definition_id: definition for definition in registry.definitions}
        assert set(definitions) == {item.definition_id for item in _MATRIX}
        definition = definitions[case.definition_id]
        subject_ref, payload, secret = _payload(
            definition, profile_id=profile_id, tmp_path=tmp_path / case.definition_id
        )
        submitted, observed = asyncio.run(
            driver.run(definition_id=definition.definition_id, subject_ref=subject_ref, payload=payload, secret=secret)
        )
        phase_codes = tuple(
            event.phase_code for event in observed.event_page.events if isinstance(event, OperationPublicPhaseEventV1)
        )
        if case.expected_phase_codes is None:
            assert set(phase_codes) & set(definition.phase_codes)
        else:
            assert phase_codes == case.expected_phase_codes
        if case.definition_id == "user-profile.censo-review":
            assert observed.projection.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
            assert isinstance(observed.projection.pending_interaction, OperationReviewAvailableInteractionV1)
            assert observed.projection.execution_deadline_at is not None
            assert cleanup.closed is True
            observed = asyncio.run(driver.apply_review(submitted, observed))
        assert observed.projection.lifecycle is OperationLifecycle.TERMINAL
        assert observed.projection.terminal_condition is case.expected_terminal, case.definition_id
        assert observed.projection.effect is case.expected_effect, case.definition_id
        assert observed.projection.refusal_ref == case.expected_refusal_ref, case.definition_id
        if case.expected_terminal is OperationTerminalCondition.FAILED:
            assert observed.projection.diagnostic_ref is not None
        assert isinstance(observed.projection.pending_interaction, OperationNoPendingInteractionV1)
        asyncio.run(
            driver.review_not_pending(
                operation_id=submitted.receipt.operation_id,
                revision=observed.projection.revision,
                registry=registry,
            )
        )


def test_censo_cooperative_cancellation_settles_after_its_irreversible_section(tmp_path: Path) -> None:
    """Drive manual cancellation through the public control service to its exact terminal receipt."""
    reached_boundary = asyncio.Event()
    release_boundary = asyncio.Event()

    async def before_irreversible_section() -> None:
        reached_boundary.set()
        await release_boundary.wait()

    cleanup = _CloseWitness()
    with _runtime(
        tmp_path / "censo-cancellation",
        cleanup=cleanup,
        before_irreversible_section=before_irreversible_section,
    ) as (driver, registry, profile_id):
        definition = registry.lookup("user-profile.censo-review")
        subject_ref, payload, secret = _payload(definition, profile_id=profile_id, tmp_path=tmp_path)

        async def run() -> None:
            submitted = await driver.prepare(
                definition_id=definition.definition_id,
                subject_ref=subject_ref,
                payload=payload,
                secret=secret,
            )
            await driver.services.submission.start(submitted.receipt.operation_id)
            waiting = await driver.observe(submitted.receipt.operation_id)
            operation_id = await driver.respond_apply(submitted, waiting)
            await reached_boundary.wait()
            running = await driver.observe(operation_id)
            requested = await driver.services.cancellation.request(
                OperationCancellationRequestV1(operation_id=operation_id, expected_revision=running.projection.revision)
            )
            assert isinstance(requested, OperationCancellationSuccessV1)
            assert requested.cancellation_acknowledged is False
            release_boundary.set()
            terminal = await driver.await_terminal(operation_id)
            assert terminal.projection.terminal_condition is OperationTerminalCondition.CANCELLED
            assert terminal.projection.effect is OperationEffect.NONE
            assert terminal.projection.cancellation_acknowledged is True
            assert terminal.projection.cleanup_deadline_at is not None
            assert cleanup.closed is True

        asyncio.run(run())


def test_censo_execution_deadline_settles_its_actual_cooperative_safe_stop(tmp_path: Path) -> None:
    """Let the supervisor-owned deadline drive the production CENSO continuation to timed out."""
    cleanup = _CloseWitness()
    with _runtime(
        tmp_path / "censo-deadline",
        cleanup=cleanup,
        execution_timeout=timedelta(milliseconds=50),
    ) as (driver, registry, profile_id):
        definition = registry.lookup("user-profile.censo-review")
        subject_ref, payload, secret = _payload(definition, profile_id=profile_id, tmp_path=tmp_path)

        async def run() -> None:
            submitted, waiting = await driver.run(
                definition_id=definition.definition_id,
                subject_ref=subject_ref,
                payload=payload,
                secret=secret,
            )
            assert waiting.projection.execution_deadline_at is not None
            await asyncio.sleep(max((waiting.projection.execution_deadline_at - now()).total_seconds(), 0) + 0.01)
            operation_id = await driver.respond_apply(submitted, waiting)
            terminal = await driver.await_terminal(operation_id)
            assert terminal.projection.terminal_condition is OperationTerminalCondition.TIMED_OUT
            assert terminal.projection.effect is OperationEffect.NONE
            assert terminal.projection.cancellation_requested is True
            assert terminal.projection.cancellation_acknowledged is True
            assert terminal.projection.cleanup_deadline_at is not None
            assert cleanup.closed is True

        asyncio.run(run())
