"""Exact-profile disclosure and bounded local verify read contracts."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.identity_check_verdict import IdentityCheckVerdict, IdentityCheckVerdictValue
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...operations.access_resolution import OperationAccessContext
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationFrontendProjection
from ...user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..verify import VerifyObservation, VerifySurface
from ..verify_read_operation import (
    VERIFY_LATEST_DEFINITION_ID,
    VERIFY_LIST_DEFINITION_ID,
    VERIFY_VIEW_DEFINITION_ID,
    VerifyLatestExecutor,
    VerifyLatestOperationReport,
    VerifyLatestPublicResultV1,
    VerifyLatestRequest,
    VerifyListExecutor,
    VerifyListOperationReport,
    VerifyListPublicResultV1,
    VerifyListRequest,
    VerifyObservationPublicV1,
    VerifyObservationSummaryPublicV1,
    VerifyViewOperationReport,
    VerifyViewRequest,
    build_verify_latest_definition,
    build_verify_latest_registration,
    build_verify_list_definition,
    build_verify_list_registration,
    build_verify_view_definition,
    build_verify_view_registration,
    resolve_verify_latest_access,
    resolve_verify_list_access,
    resolve_verify_view_access,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_NOW = datetime(2026, 9, 29, 10, 30, tzinfo=UTC)
_NIF = "B12345674"


def _observation(
    identity: str,
    *,
    surface: VerifySurface = VerifySurface.NIF_IVA,
    nif: str = _NIF,
    verdict: IdentityCheckVerdictValue = IdentityCheckVerdict.VALID,
    expected: IdentityCheckVerdictValue | None = IdentityCheckVerdict.VALID,
    checked_at: datetime = _NOW,
    bucket_id: UUID = _PROFILE,
) -> VerifyObservation:
    return VerifyObservation(
        observation_id=identity,
        bucket_id=str(bucket_id),
        surface=surface,
        nif=nif,
        verdict=verdict,
        expected=expected,
        matched_expectation=(expected == verdict) if expected is not None else None,
        checked_at=checked_at,
        raw_evidence_locator="synthetic-private-evidence-locator",
        persisted_at=checked_at,
    )


class _MemoryPersistence:
    def __init__(self, observations: tuple[VerifyObservation, ...]) -> None:
        self.observations = observations

    def load(self, *, bucket_id: str, observation_id: str) -> VerifyObservation | None:
        return next(
            (row for row in self.observations if row.bucket_id == bucket_id and row.observation_id == observation_id),
            None,
        )

    def list_observations(self, *, bucket_id: str) -> tuple[VerifyObservation, ...]:
        return tuple(row for row in self.observations if row.bucket_id == bucket_id)

    def save(self, observation: VerifyObservation) -> None:
        self.observations += (observation,)


class _Events:
    def __init__(self) -> None:
        self.phases: list[str] = []
        self.effects: list[OperationEffect] = []

    async def phase(self, value: str) -> None:
        self.phases.append(value)

    async def effect(self, value: OperationEffect) -> None:
        self.effects.append(value)


class _Operands:
    def __init__(self) -> None:
        self.values: list[BaseModel] = []

    async def put(self, value: BaseModel, *, written_at: datetime) -> str:
        assert written_at.tzinfo is not None
        self.values.append(value)
        return "encrypted-result-reference"


def _registration(definition_id: str):
    def unused_factory(_bucket_id: str) -> _MemoryPersistence:
        raise AssertionError("registration construction must not compose persistence")

    if definition_id == VERIFY_LIST_DEFINITION_ID:
        definition = build_verify_list_definition(unused_factory)
        return build_verify_list_registration(definition)
    if definition_id == VERIFY_VIEW_DEFINITION_ID:
        definition = build_verify_view_definition(unused_factory)
        return build_verify_view_registration(definition)
    definition = build_verify_latest_definition(unused_factory)
    return build_verify_latest_registration(definition)


def _request(definition_id: str) -> OperationRequest[BaseModel]:
    if definition_id == VERIFY_LIST_DEFINITION_ID:
        payload: BaseModel = VerifyListRequest(profile_id=_PROFILE, surface=VerifySurface.NIF_IVA, nif=_NIF)
    elif definition_id == VERIFY_VIEW_DEFINITION_ID:
        payload = VerifyViewRequest(profile_id=_PROFILE, observation_id="a" * 12)
    else:
        payload = VerifyLatestRequest(profile_id=_PROFILE, surface=VerifySurface.NIF_IVA, nif=_NIF)
    return OperationRequest[BaseModel](
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=payload,
    )


def _access_context(registration) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )


def _receipt(definition_id: str) -> OperationTerminalReceipt:
    return OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="f" * 64,
            definition_id=definition_id,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        settled_at=_NOW,
        result_ref="encrypted-result-reference",
    )


def test_result_access_discloses_only_tax_values_for_the_exact_profile() -> None:
    resolvers = (
        (VERIFY_LIST_DEFINITION_ID, resolve_verify_list_access),
        (VERIFY_VIEW_DEFINITION_ID, resolve_verify_view_access),
        (VERIFY_LATEST_DEFINITION_ID, resolve_verify_latest_access),
    )

    for definition_id, resolver in resolvers:
        registration = _registration(definition_id)
        context = _access_context(registration)
        result = resolver(_request(definition_id), context)
        schema = registration.contract.result_schema
        assert schema is not None
        assert result.policy.disclosures == frozenset(
            {
                DisclosurePermission(
                    destination_id=context.destination_id,
                    projection_id=schema.schema_id,
                    category=DisclosureCategory.TAX_VALUES,
                )
            }
        )


def test_result_access_refuses_another_profile() -> None:
    registration = _registration(VERIFY_LIST_DEFINITION_ID)
    request = OperationRequest[BaseModel](
        definition_id=VERIFY_LIST_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=VerifyListRequest(profile_id=_OTHER_PROFILE),
    )

    with pytest.raises(ProfileAccessRefusedError) as error:
        resolve_verify_list_access(request, _access_context(registration))

    assert error.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_projectors_preserve_existing_fields_and_hide_raw_evidence_locator() -> None:
    observation = _observation("a" * 64)
    summary = VerifyObservationSummaryPublicV1(
        observation_id=observation.observation_id,
        surface=observation.surface,
        nif=observation.nif,
        verdict=observation.verdict,
        expected=observation.expected,
        matched_expectation=observation.matched_expectation,
        checked_at=observation.checked_at,
    )
    list_report = VerifyListOperationReport(bucket_id=str(_PROFILE), rows=(summary,))
    list_registration = _registration(VERIFY_LIST_DEFINITION_ID)
    assert list_registration.result_projector is not None
    listed = list_registration.result_projector(list_report, _receipt(VERIFY_LIST_DEFINITION_ID))

    assert isinstance(listed, VerifyListPublicResultV1)
    assert listed.count == 1
    assert listed.rows[0].model_dump(mode="json") == {
        "observation_id": "a" * 64,
        "surface": "nif_iva",
        "nif": _NIF,
        "verdict": "valid",
        "expected": "valid",
        "matched_expectation": True,
        "checked_at": _NOW.isoformat().replace("+00:00", "Z"),
    }

    view_registration = _registration(VERIFY_VIEW_DEFINITION_ID)
    assert view_registration.result_projector is not None
    viewed = view_registration.result_projector(
        VerifyViewOperationReport(observation=observation), _receipt(VERIFY_VIEW_DEFINITION_ID)
    )
    assert isinstance(viewed, VerifyObservationPublicV1)
    assert viewed.bucket_id == str(_PROFILE)
    assert set(viewed.model_dump(mode="json")) == {
        "bucket_id",
        "observation_id",
        "surface",
        "nif",
        "verdict",
        "expected",
        "matched_expectation",
        "checked_at",
    }
    assert "synthetic-private-evidence-locator" not in str(viewed.model_dump(mode="json"))


def test_latest_projector_preserves_the_stable_empty_shape() -> None:
    registration = _registration(VERIFY_LATEST_DEFINITION_ID)
    assert registration.result_projector is not None
    empty = registration.result_projector(
        VerifyLatestOperationReport(
            bucket_id=str(_PROFILE),
            surface=VerifySurface.TGVI,
            nif=_NIF,
            observation=None,
        ),
        _receipt(VERIFY_LATEST_DEFINITION_ID),
    )

    assert isinstance(empty, VerifyLatestPublicResultV1)
    assert empty.model_dump(mode="json") == {
        "bucket_id": str(_PROFILE),
        "observation_id": None,
        "surface": "tgvi",
        "nif": _NIF,
        "verdict": None,
        "expected": None,
        "matched_expectation": None,
        "checked_at": None,
    }


def _executor_context(definition_id: str) -> tuple[OperationExecutorContext, _Operands]:
    identity = OperationIdentity(
        operation_id="e" * 64,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(_PROFILE)),
    )
    events = _Events()
    operands = _Operands()
    context = cast(OperationExecutorContext, SimpleNamespace(identity=identity, events=events, operands=operands))
    return context, operands


def test_list_executor_preserves_service_filtering_and_capture_order(monkeypatch: pytest.MonkeyPatch) -> None:
    import cadrumo.application.live.verify_read_operation as operation

    observations = (
        _observation("a" * 64, checked_at=datetime(2026, 9, 28, tzinfo=UTC)),
        _observation("b" * 64, surface=VerifySurface.TGVI),
        _observation("c" * 64, checked_at=datetime(2026, 9, 29, tzinfo=UTC)),
    )
    persistence = _MemoryPersistence(observations)
    factory_buckets: list[str] = []

    def persistence_factory(bucket_id: str) -> _MemoryPersistence:
        factory_buckets.append(bucket_id)
        return persistence

    monkeypatch.setattr(operation, "require_active_bucket_id", lambda: str(_PROFILE))
    request = _request(VERIFY_LIST_DEFINITION_ID).model_copy(
        update={
            "payload": VerifyListRequest(profile_id=_PROFILE, surface=VerifySurface.NIF_IVA, nif=_NIF),
        }
    )
    context, operands = _executor_context(VERIFY_LIST_DEFINITION_ID)

    asyncio.run(VerifyListExecutor(persistence_factory).execute(request, context))

    assert factory_buckets == [str(_PROFILE)]
    assert len(operands.values) == 1
    report = operands.values[0]
    assert isinstance(report, VerifyListOperationReport)
    assert [row.observation_id for row in report.rows] == ["a" * 64, "c" * 64]


def test_list_executor_refuses_overflow_without_truncating(monkeypatch: pytest.MonkeyPatch) -> None:
    import cadrumo.application.live.verify_read_operation as operation

    persistence = _MemoryPersistence((_observation("a" * 64), _observation("b" * 64)))
    monkeypatch.setattr(operation, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(operation, "_MAX_VERIFY_LIST_ROWS", 1)
    context, operands = _executor_context(VERIFY_LIST_DEFINITION_ID)

    with pytest.raises(ProfileAccessRefusedError) as error:
        asyncio.run(
            VerifyListExecutor(lambda _bucket_id: persistence).execute(
                OperationRequest[BaseModel](
                    definition_id=VERIFY_LIST_DEFINITION_ID,
                    subject_ref=profile_operation_subject(str(_PROFILE)),
                    payload=VerifyListRequest(profile_id=_PROFILE),
                ),
                context,
            )
        )

    assert error.value.reason is AccessDenialCode.OPERATION_DENIED
    assert operands.values == []


def test_latest_executor_records_an_explicit_empty_result(monkeypatch: pytest.MonkeyPatch) -> None:
    import cadrumo.application.live.verify_read_operation as operation

    persistence = _MemoryPersistence(())
    monkeypatch.setattr(operation, "require_active_bucket_id", lambda: str(_PROFILE))
    context, operands = _executor_context(VERIFY_LATEST_DEFINITION_ID)
    request = OperationRequest[BaseModel](
        definition_id=VERIFY_LATEST_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=VerifyLatestRequest(profile_id=_PROFILE, surface=VerifySurface.TGVI, nif=_NIF),
    )

    asyncio.run(VerifyLatestExecutor(lambda _bucket_id: persistence).execute(request, context))

    assert len(operands.values) == 1
    report = operands.values[0]
    assert isinstance(report, VerifyLatestOperationReport)
    assert report.observation is None
    assert report.surface is VerifySurface.TGVI
    assert report.nif == _NIF


def test_request_limits_reject_invalid_prefix_and_blank_tax_id() -> None:
    with pytest.raises(ValidationError):
        VerifyViewRequest(profile_id=_PROFILE, observation_id="not-a-digest-prefix")
    with pytest.raises(ValidationError):
        VerifyLatestRequest(profile_id=_PROFILE, surface=VerifySurface.NIF_IVA, nif="")
