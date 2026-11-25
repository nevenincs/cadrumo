"""Synthetic supervisor proof for exact-profile justificante snapshot reads."""

from __future__ import annotations

import asyncio
import base64
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.live.justificante import (
    JustificanteCaptureSnapshot,
    JustificanteCaptureSnapshotNotFoundError,
    JustificanteCaptureSnapshotRepository,
    JustificanteCaptureSnapshotService,
)
from cadrumo.application.live.justificante_read_operation import (
    JUSTIFICANTE_LIST_DEFINITION_ID,
    JUSTIFICANTE_SHOW_DEFINITION_ID,
    JustificanteListExecutor,
    JustificanteListPublicResultV1,
    JustificanteListRequest,
    JustificanteShowPublicResultV1,
    JustificanteShowRequest,
    build_justificante_list_definition,
    build_justificante_list_registration,
    build_justificante_show_definition,
    build_justificante_show_registration,
)
from cadrumo.application.live.snapshot_base import SnapshotLifecycleState
from cadrumo.application.live.tests.read_executor_support import ExecutorEvents, ExecutorOperands
from cadrumo.application.operations.access_resolution import resolve_operation_access
from cadrumo.application.operations.frontend_requests import (
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationIdentity, OperationRequest
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.errors.hierarchy import NoActiveProfileError
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction

from ...domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .supervised_operation_rig import (
    assert_foreign_profile_refused,
    build_supervised_operation,
    cli_submit_context,
    settle_and_project,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon

_NOW = datetime(_YEAR, 8, 24, 20, tzinfo=UTC)
_SNAPSHOT_ID = "9" * 64
_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")


class _SnapshotPersistence:
    """Small repository port for synthetic stored captures."""

    def __init__(self, *, bucket_id: str, snapshots: tuple[JustificanteCaptureSnapshot, ...]) -> None:
        self._bucket_id = bucket_id
        self.snapshots: list[object] = list(snapshots)

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def exists(self, snapshot_id: str) -> bool:
        return any(
            isinstance(snapshot, JustificanteCaptureSnapshot) and snapshot.snapshot_id == snapshot_id
            for snapshot in self.snapshots
        )

    def load(self, snapshot_id: str) -> object:
        for snapshot in self.snapshots:
            if isinstance(snapshot, JustificanteCaptureSnapshot) and snapshot.snapshot_id == snapshot_id:
                return snapshot
        raise KeyError(snapshot_id)

    def list_snapshots(self) -> tuple[object, ...]:
        return tuple(self.snapshots)

    def resolve(self, snapshot_id: str) -> object:
        matches = tuple(
            snapshot
            for snapshot in self.snapshots
            if isinstance(snapshot, JustificanteCaptureSnapshot)
            and (snapshot.snapshot_id == snapshot_id or snapshot.snapshot_id.startswith(snapshot_id))
        )
        if not matches:
            raise JustificanteCaptureSnapshotNotFoundError(
                translated_message="application.live.justificante.errors.snapshot_not_found",
                context={"snapshot_id": snapshot_id},
            )
        if len(matches) > 1:
            raise JustificanteCaptureSnapshotNotFoundError(
                translated_message="application.live.justificante.errors.snapshot_prefix_ambiguous",
                context={"snapshot_id": snapshot_id, "match_count": len(matches)},
            )
        resolved = matches[0]
        assert isinstance(resolved, JustificanteCaptureSnapshot)
        return resolved

    def save(self, snapshot: object) -> None:
        if not isinstance(snapshot, JustificanteCaptureSnapshot):
            raise TypeError("only justificante snapshots can be persisted")
        self.snapshots = [
            row
            for row in self.snapshots
            if not isinstance(row, JustificanteCaptureSnapshot) or row.snapshot_id != snapshot.snapshot_id
        ]
        self.snapshots.append(snapshot)


def _executor_context(
    definition_id: str,
    *,
    subject_ref: str | None = None,
    events: ExecutorEvents,
) -> tuple[OperationExecutorContext, ExecutorOperands]:
    identity = OperationIdentity(
        operation_id="e" * 64,
        definition_id=definition_id,
        subject_ref=subject_ref or profile_operation_subject(str(_PROFILE)),
    )
    operands = ExecutorOperands()
    return cast(
        OperationExecutorContext,
        SimpleNamespace(identity=identity, events=events, operands=operands),
    ), operands


def _snapshot(*, bucket_id: str, snapshot_id: str = _SNAPSHOT_ID) -> JustificanteCaptureSnapshot:
    pdf = b"%PDF-1.4\nsynthetic AEAT receipt\n%%EOF"
    return JustificanteCaptureSnapshot(
        snapshot_id=snapshot_id,
        bucket_id=bucket_id,
        modelo="130",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "1T"),
        expediente_id="202613000010001A",
        csv="ABCD1234EFGH5678",
        pdf_sha256=hashlib.sha256(pdf).hexdigest(),
        pdf_base64=base64.b64encode(pdf).decode("ascii"),
        captured_at=_NOW,
        state=SnapshotLifecycleState.ACTIVE,
    )


def _service_factory(bucket_id: str, snapshots: tuple[JustificanteCaptureSnapshot, ...]):
    service = JustificanteCaptureSnapshotService(
        bucket_id=bucket_id,
        repository=JustificanteCaptureSnapshotRepository(
            persistence=_SnapshotPersistence(bucket_id=bucket_id, snapshots=snapshots)
        ),
    )

    def build(_bucket_id: str) -> JustificanteCaptureSnapshotService:
        assert _bucket_id == bucket_id
        return service

    return build


@pytest.mark.parametrize(
    ("request_definition_id", "context_definition_id", "context_subject_ref"),
    [
        (
            "live.justificante.list.other",
            "live.justificante.list.other",
            profile_operation_subject(str(_PROFILE)),
        ),
        (
            JUSTIFICANTE_LIST_DEFINITION_ID,
            "live.justificante.other",
            profile_operation_subject(str(_PROFILE)),
        ),
        (
            JUSTIFICANTE_LIST_DEFINITION_ID,
            JUSTIFICANTE_LIST_DEFINITION_ID,
            profile_operation_subject(str(_OTHER_PROFILE)),
        ),
    ],
)
def test_list_executor_refuses_request_or_context_identity_mismatch_before_work(
    monkeypatch: pytest.MonkeyPatch,
    request_definition_id: str,
    context_definition_id: str,
    context_subject_ref: str,
) -> None:
    import cadrumo.application.live.justificante_read_operation as operation

    events = ExecutorEvents()
    factory_buckets: list[str] = []
    context, operands = _executor_context(
        context_definition_id,
        subject_ref=context_subject_ref,
        events=events,
    )
    request = OperationRequest[JustificanteListRequest](
        definition_id=request_definition_id,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=JustificanteListRequest(profile_id=_PROFILE),
    )
    monkeypatch.setattr(operation, "require_active_bucket_id", lambda: str(_PROFILE))

    def unexpected_factory(bucket_id: str) -> JustificanteCaptureSnapshotService:
        factory_buckets.append(bucket_id)
        raise AssertionError("identity refusal must happen before composing the snapshot service")

    with pytest.raises(ProfileAccessRefusedError) as refused:
        asyncio.run(JustificanteListExecutor(unexpected_factory).execute(request, context))

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert events.phases == []
    assert events.effects == []
    assert factory_buckets == []
    assert operands.values == []


def test_list_executor_preserves_missing_profile_precedence_before_work(monkeypatch: pytest.MonkeyPatch) -> None:
    import cadrumo.application.live.justificante_read_operation as operation

    events = ExecutorEvents()
    factory_buckets: list[str] = []
    context, operands = _executor_context(
        "live.justificante.other",
        subject_ref=profile_operation_subject(str(_OTHER_PROFILE)),
        events=events,
    )
    request = OperationRequest[JustificanteListRequest](
        definition_id=JUSTIFICANTE_LIST_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=JustificanteListRequest(profile_id=_PROFILE),
    )

    def no_active_profile() -> str:
        raise NoActiveProfileError(translated_message="synthetic missing active profile")

    monkeypatch.setattr(operation, "require_active_bucket_id", no_active_profile)

    def unexpected_factory(bucket_id: str) -> JustificanteCaptureSnapshotService:
        factory_buckets.append(bucket_id)
        raise AssertionError("missing active profile must refuse before composing the snapshot service")

    with pytest.raises(NoActiveProfileError):
        asyncio.run(JustificanteListExecutor(unexpected_factory).execute(request, context))

    assert events.phases == []
    assert events.effects == []
    assert factory_buckets == []
    assert operands.values == []


def test_registered_justificante_reads_project_only_existing_cli_fields(tmp_path: Path) -> None:
    """List and show use the local service, exact profile scope, and closed result schemas."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, bundled_indexed_authority().operation() as authority:
        profile_id = UUID(profile.bucket_id)
        snapshot = _snapshot(bucket_id=profile.bucket_id)
        factory = _service_factory(profile.bucket_id, (snapshot,))
        list_definition = build_justificante_list_definition(factory)
        show_definition = build_justificante_show_definition(factory)
        list_registration = build_justificante_list_registration(list_definition)
        show_registration = build_justificante_show_registration(show_definition)
        registry = OperationRegistry(
            definitions=tuple(sorted((list_definition, show_definition), key=lambda item: item.definition_id)),
            public_registrations=tuple(
                sorted((list_registration, show_registration), key=lambda item: item.contract.definition_id)
            ),
        )
        requests: tuple[tuple[OperationRequest[BaseModel], type[BaseModel]], ...] = (
            (
                OperationRequest(
                    definition_id=JUSTIFICANTE_LIST_DEFINITION_ID,
                    subject_ref=profile_operation_subject(profile.bucket_id),
                    payload=JustificanteListRequest(profile_id=profile_id),
                ),
                JustificanteListPublicResultV1,
            ),
            (
                OperationRequest(
                    definition_id=JUSTIFICANTE_SHOW_DEFINITION_ID,
                    subject_ref=profile_operation_subject(profile.bucket_id),
                    payload=JustificanteShowRequest(profile_id=profile_id, snapshot_id=_SNAPSHOT_ID[:12]),
                ),
                JustificanteShowPublicResultV1,
            ),
        )

        for request, _result_type in requests:
            registration = registry.lookup_public_registration(request.definition_id)
            access_context = cli_submit_context(
                profile_id=profile_id, contract=registration.contract, authority_operation=authority
            )
            admitted = resolve_operation_access(registry=registry, request=request, context=access_context)
            assert admitted.request.profile_id == profile_id
            assert admitted.request.period_independent
            assert admitted.policy.requires_all_periods
            assert AccessAction.COMMIT not in admitted.policy.actions

            assert_foreign_profile_refused(registry=registry, request=request, context=access_context)

        _, _, _, supervisor, result_service = build_supervised_operation(
            tmp_path=tmp_path, objects=profile.repository, authority=authority, registry=registry, now=_NOW
        )

        async def run(
            request: OperationRequest[BaseModel], operation_id: str, result_type: type[BaseModel]
        ) -> tuple[OperationPersistedSnapshot, OperationResultProjectionSuccessV1[BaseModel]]:
            terminal, projected = await settle_and_project(
                supervisor, result_service, registry, request, result_type, operation_id=operation_id
            )
            assert isinstance(projected, OperationResultProjectionSuccessV1)
            return terminal, cast(OperationResultProjectionSuccessV1[BaseModel], projected)

        list_terminal, listed_result = asyncio.run(run(requests[0][0], "3" * 64, requests[0][1]))
        show_terminal, shown_result = asyncio.run(run(requests[1][0], "4" * 64, requests[1][1]))

    for terminal in (list_terminal, show_terminal):
        assert terminal.lifecycle is OperationLifecycle.TERMINAL
        assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert terminal.effect is OperationEffect.NONE

    listed = listed_result.projection
    assert isinstance(listed, JustificanteListPublicResultV1)
    assert (listed.bucket_id, listed.count) == (profile.bucket_id, 1)
    assert (listed.rows[0].snapshot_id, listed.rows[0].period, listed.rows[0].state) == (
        _SNAPSHOT_ID,
        "1T",
        SnapshotLifecycleState.ACTIVE.value,
    )
    assert "pdf_base64" not in listed.model_dump()

    shown = shown_result.projection
    assert isinstance(shown, JustificanteShowPublicResultV1)
    assert (shown.bucket_id, shown.snapshot_id, shown.modelo, shown.period, shown.csv) == (
        profile.bucket_id,
        _SNAPSHOT_ID,
        "130",
        "1T",
        "ABCD1234EFGH5678",
    )
    assert set(shown.model_dump()) == {
        "bucket_id",
        "snapshot_id",
        "modelo",
        "filing_year",
        "period",
        "expediente_id",
        "csv",
        "pdf_sha256",
        "source_kind",
        "state",
        "captured_at",
    }
    assert "pdf_base64" not in shown.model_dump()
