"""Canonical real-lifecycle conformance matrix for the censal operation."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.application.operations.interactions import (
    OperationApplyResponse,
    OperationRejectResponse,
)
from cadrumo.application.operations.models import (
    OperationRequest,
    OperationTerminalReceipt,
)
from cadrumo.application.operations.persistence.leases import operation_conflict_scope_reference
from cadrumo.application.user_profile.capsule_record import ProfileRecordStore
from cadrumo.application.user_profile.censal_operation import (
    CENSAL_OPERATION_DEFINITION,
    CensalFieldIntent,
    CensalOperationAcquisition,
    CensalOperationExecutor,
    CensalReviewedFieldIntent,
)
from cadrumo.application.user_profile.censo_sync import CENSO_SOURCE_TAG
from cadrumo.application.user_profile.cotejo_apply import CensoDivergence, apply_cotejo, open_censo_divergences
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.projections import record_to_path_values

from ....adapters.outbound.aeat.sede import parse_censal_datos
from ....core import OperationEffect, OperationLifecycle, OperationTerminalCondition
from ....domain.buckets import BucketEventType
from ....tests import FIXTURES_DIR
from .test_censal_operation_executor import (
    _NOW,
    _RESPONSE_TOKEN,
    _payload,
    _start,
    _subject,
    _supervisor,
    _wait_for_phase,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PATHS = (
    "contact.fiscal_address",
    "contact.postcode",
    "contact.fiscal_address_cadastral_reference",
)
_VALUES = {
    "contact.fiscal_address": "CALLE NOMBRE VIA EJEMPLO NUM 1 7 9, 28001 28079 - MADRID MADRID",
    "contact.postcode": "28001",
    "contact.fiscal_address_cadastral_reference": "0000001AA0000A0001AA",
}


class _LocalHttpResource:
    """Real local HTTP server retained until supervisor settlement."""

    def __init__(self, server: asyncio.Server) -> None:
        self.server = server
        self.closed = False

    async def close(self) -> None:
        self.server.close()
        await self.server.wait_closed()
        self.closed = True


class _LocalHttpCensalAcquisition:
    """Fetch the captured AEAT page over a real socket and parse it canonically."""

    def __init__(self) -> None:
        self.calls = 0

        self.resources: list[_LocalHttpResource] = []

    async def __call__(self) -> CensalOperationAcquisition:
        self.calls += 1
        html = (
            (FIXTURES_DIR / "aeat-sede" / "censal-datos-mdcacceso.html")
            .read_bytes()
            .replace(b"Y0000001Z", b"12345678Z")
        )

        async def serve(_reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            await _reader.readuntil(b"\r\n\r\n")
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: "
                + str(len(html)).encode()
                + b"\r\nConnection: close\r\n\r\n"
                + html
            )
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(serve, "127.0.0.1", 0)
        resource = _LocalHttpResource(server)
        self.resources.append(resource)
        port = server.sockets[0].getsockname()[1]
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"GET /censo/consulta HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
        await writer.drain()
        raw = await reader.read()
        writer.close()
        await writer.wait_closed()
        _headers, body = raw.split(b"\r\n\r\n", 1)
        observation = parse_censal_datos(
            body.decode("utf-8"),
            source_url=f"http://127.0.0.1:{port}/censo/consulta",
        )
        return CensalOperationAcquisition(observation=observation, resource=resource)


class _PreEntryBoundary:
    """Deterministic typed seam controlling entry to the irreversible section."""

    def __init__(self) -> None:
        self.reached = asyncio.Event()
        self.release = asyncio.Event()

    async def __call__(self) -> None:
        self.reached.set()
        await self.release.wait()


def _request(profile_id: str, adopted_paths: frozenset[str]):
    payload = _payload(profile_id).model_copy(
        update={
            "field_intents": tuple(
                CensalReviewedFieldIntent(
                    path=path,
                    intent=CensalFieldIntent.ADOPT if path in adopted_paths else CensalFieldIntent.PRESERVE,
                )
                for path in _PATHS
            )
        }
    )
    return OperationRequest(
        definition_id=CENSAL_OPERATION_DEFINITION.definition_id,
        subject_ref=profile_id,
        payload=payload,
    )


def _apply_response(operation_id: str, pending):
    return OperationApplyResponse(
        interaction_id=pending.request.interaction_id,
        operation_id=operation_id,
        revision=pending.request.revision,
        response_token=_RESPONSE_TOKEN,
        continuation_digest=pending.request.continuation_digest,
        reviewed_proposal_digest=pending.reviewed_proposal_digest,
        actor_ref="operator:s33-conformance",
        responded_at=_NOW + timedelta(minutes=2),
        baseline_digest=pending.baseline_digest,
        proposed_effect_digest=pending.proposed_effect_digest,
    )


async def _settle_when_stopped(supervisor, operation_id: str, receipt: OperationTerminalReceipt):
    for _ in range(100):
        try:
            return await supervisor.settle(operation_id, receipt)
        except ValueError as exc:
            if "requires completed executor work" not in str(exc):
                raise
        await asyncio.sleep(0)
    raise AssertionError("censal continuation did not stop before settlement")


@pytest.mark.parametrize(
    "adopted_paths",
    [*(frozenset({path}) for path in _PATHS), frozenset(_PATHS)],
    ids=["address-only", "postcode-only", "cadastral-only", "apply-all"],
)
def test_censal_operation_exact_apply_matrix_detaches_resumes_and_cleans_up(
    tmp_path: Path,
    adopted_paths: frozenset[str],
) -> None:
    acquisition = _LocalHttpCensalAcquisition()
    with _subject(tmp_path) as (profile_id, objects, session):
        durable_root = tmp_path / "operations"
        before = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
        history_before = ProfileRecordStore(session=session).history()
        executor = CensalOperationExecutor(acquire=acquisition)
        owner = _supervisor(
            root=durable_root,
            objects=objects,
            executor=executor,
            owner="1" * 64,
            token="2" * 64,
        )
        request = _request(profile_id, adopted_paths)

        async def run():
            operation_id = await owner.submit(request, operation_id="3" * 64)
            waiting = await _start(owner, operation_id)
            assert waiting.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
            assert waiting.effect is OperationEffect.NONE
            assert ProfileRecordRepository.for_current_session(profile_id).load(profile_id) == before
            assert ProfileRecordStore(session=session).history() == history_before

            pending = waiting.pending_interaction
            assert pending is not None
            assert acquisition.calls == 1
            await owner.respond(_apply_response(operation_id, pending))
            stopped = await _wait_for_phase(owner, operation_id, "censo.settlement")
            terminal = await _settle_when_stopped(
                owner,
                operation_id,
                OperationTerminalReceipt(
                    identity=stopped.identity,
                    revision=stopped.revision + 1,
                    condition=OperationTerminalCondition.SUCCEEDED,
                    effect=OperationEffect.UPDATED,
                    settled_at=_NOW,
                    result_ref=f"censo-review:{operation_id}:applied",
                ),
            )
            assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
            assert terminal.effect is OperationEffect.UPDATED
            assert terminal.cleanup_deadline is None

            leases = OperationLeaseFilesystemRepository(storage_root=durable_root)
            observed = await leases.inspect(
                operation_conflict_scope_reference(
                    definition_id=CENSAL_OPERATION_DEFINITION.definition_id,
                    subject_ref=profile_id,
                ),
                operation_id,
                observed_at=_NOW,
            )
            assert observed.current is None

        asyncio.run(run())
        after = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
        values = record_to_path_values(after)
        assert after.record_revision == before.record_revision + 1
        assert {path: values[path] for path in adopted_paths} == {path: _VALUES[path] for path in adopted_paths}
        for path in set(_PATHS) - adopted_paths:
            assert path not in values
        assert open_censo_divergences(after) == tuple(
            CensoDivergence(axis=path, artefact_value=_VALUES[path], source=CENSO_SOURCE_TAG)
            for path in _PATHS
            if path not in adopted_paths
        )
        history_after = ProfileRecordStore(session=session).history()
        assert len(history_after) == len(history_before) + 1
        assert history_after[-1].event_type is BucketEventType.CENSO_APPLIED
        expected_counts = {
            "adopted_count": str(len(adopted_paths)),
            "divergence_count": str(len(_PATHS) - len(adopted_paths)),
        }
        assert {key: history_after[-1].payload[key] for key in expected_counts} == expected_counts
        assert acquisition.calls == 1
        assert all(resource.closed for resource in acquisition.resources)


def test_censal_operation_reject_and_stale_paths_never_apply_reviewed_effects(tmp_path: Path) -> None:
    acquisition = _LocalHttpCensalAcquisition()
    with _subject(tmp_path) as (profile_id, objects, session):
        before = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
        history_before = ProfileRecordStore(session=session).history()

        async def reject_run() -> None:
            supervisor = _supervisor(
                root=tmp_path / "reject",
                objects=objects,
                executor=CensalOperationExecutor(acquire=acquisition),
                owner="6" * 64,
                token="7" * 64,
            )
            operation_id = await supervisor.submit(_request(profile_id, frozenset(_PATHS)), operation_id="8" * 64)
            waiting = await _start(supervisor, operation_id)
            pending = waiting.pending_interaction
            assert pending is not None
            await supervisor.respond(
                OperationRejectResponse(
                    interaction_id=pending.request.interaction_id,
                    operation_id=operation_id,
                    revision=pending.request.revision,
                    response_token=_RESPONSE_TOKEN,
                    continuation_digest=pending.request.continuation_digest,
                    reviewed_proposal_digest=pending.reviewed_proposal_digest,
                    actor_ref="operator:s33-conformance",
                    responded_at=_NOW,
                )
            )
            stopped = await _wait_for_phase(supervisor, operation_id, "censo.settlement")
            terminal = await _settle_when_stopped(
                supervisor,
                operation_id,
                OperationTerminalReceipt(
                    identity=stopped.identity,
                    revision=stopped.revision + 1,
                    condition=OperationTerminalCondition.SUCCEEDED,
                    effect=OperationEffect.NONE,
                    settled_at=_NOW,
                    result_ref=f"censo-review:{operation_id}:rejected",
                ),
            )
            assert terminal.effect is OperationEffect.NONE

        asyncio.run(reject_run())
        assert ProfileRecordRepository.for_current_session(profile_id).load(profile_id) == before
        assert ProfileRecordStore(session=session).history() == history_before

        def competing_commit(operand) -> None:
            apply_cotejo(None, adopted=(), divergences=())
            apply_cotejo(None, reviewed_proposal=operand)

        async def stale_run() -> None:
            supervisor = _supervisor(
                root=tmp_path / "stale",
                objects=objects,
                executor=CensalOperationExecutor(acquire=acquisition, apply=competing_commit),
                owner="9" * 64,
                token="a" * 64,
            )
            operation_id = await supervisor.submit(_request(profile_id, frozenset(_PATHS)), operation_id="b" * 64)
            waiting = await _start(supervisor, operation_id)
            pending = waiting.pending_interaction
            assert pending is not None
            await supervisor.respond(_apply_response(operation_id, pending))
            terminal = await supervisor.await_terminal(operation_id)
            assert terminal.terminal_condition is OperationTerminalCondition.FAILED
            assert terminal.effect is OperationEffect.NONE

        asyncio.run(stale_run())
        after = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
        assert after.record_revision == before.record_revision + 1
        assert not any(path in {fact.path for fact in after.facts} for path in _PATHS)
        assert len(ProfileRecordStore(session=session).history()) == len(history_before) + 1
        assert all(resource.closed for resource in acquisition.resources)


def test_censal_operation_detach_takeover_reuses_operand_and_releases_each_owner(tmp_path: Path) -> None:
    acquisition = _LocalHttpCensalAcquisition()
    with _subject(tmp_path) as (profile_id, objects, session):
        durable_root = tmp_path / "restart"
        history_before = ProfileRecordStore(session=session).history()
        executor = CensalOperationExecutor(acquire=acquisition)
        owner = _supervisor(
            root=durable_root,
            objects=objects,
            executor=executor,
            owner="a" * 64,
            token="b" * 64,
        )

        async def run() -> None:
            operation_id = await owner.submit(_request(profile_id, frozenset(_PATHS)), operation_id="c" * 64)
            waiting = await _start(owner, operation_id)
            assert waiting.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
            assert waiting.effect is OperationEffect.NONE
            assert acquisition.calls == 1
            assert all(resource.closed for resource in acquisition.resources)
            assert await owner.detach(operation_id) == waiting

            replacement = _supervisor(
                root=durable_root,
                objects=objects,
                executor=executor,
                owner="d" * 64,
                token="e" * 64,
                now=_NOW + timedelta(minutes=2),
            )
            recovered = await replacement.reconcile(operation_id)
            pending = recovered.pending_interaction
            assert recovered.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
            assert pending is not None
            assert pending.request.revision == recovered.revision
            assert pending.request.revision > waiting.revision
            assert acquisition.calls == 1

            await replacement.respond(_apply_response(operation_id, pending))
            stopped = await _wait_for_phase(replacement, operation_id, "censo.settlement")
            terminal = await _settle_when_stopped(
                replacement,
                operation_id,
                OperationTerminalReceipt(
                    identity=stopped.identity,
                    revision=stopped.revision + 1,
                    condition=OperationTerminalCondition.SUCCEEDED,
                    effect=OperationEffect.UPDATED,
                    settled_at=_NOW + timedelta(minutes=2),
                    result_ref=f"censo-review:{operation_id}:applied",
                ),
            )
            assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
            assert terminal.cleanup_deadline is None
            observed = await OperationLeaseFilesystemRepository(storage_root=durable_root).inspect(
                operation_conflict_scope_reference(
                    definition_id=CENSAL_OPERATION_DEFINITION.definition_id,
                    subject_ref=profile_id,
                ),
                operation_id,
                observed_at=_NOW + timedelta(minutes=2),
            )
            assert observed.current is None

        asyncio.run(run())
        after = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
        values = record_to_path_values(after)
        assert {path: values[path] for path in _PATHS} == _VALUES
        history_after = ProfileRecordStore(session=session).history()
        assert len(history_after) == len(history_before) + 1
        assert history_after[-1].event_type is BucketEventType.CENSO_APPLIED
        assert history_after[-1].payload["adopted_count"] == str(len(_PATHS))
        assert history_after[-1].payload["divergence_count"] == "0"
        assert acquisition.calls == 1
        assert all(resource.closed for resource in acquisition.resources)


def test_censal_operation_cancellation_before_irreversible_entry_cleans_up_without_effect(tmp_path: Path) -> None:
    acquisition = _LocalHttpCensalAcquisition()
    boundary = _PreEntryBoundary()
    with _subject(tmp_path) as (profile_id, objects, session):
        durable_root = tmp_path / "cancel"
        before = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
        history_before = ProfileRecordStore(session=session).history()
        supervisor = _supervisor(
            root=durable_root,
            objects=objects,
            executor=CensalOperationExecutor(
                acquire=acquisition,
                before_irreversible_section=boundary,
            ),
            owner="c" * 64,
            token="d" * 64,
        )

        async def run() -> None:
            operation_id = await supervisor.submit(_request(profile_id, frozenset(_PATHS)), operation_id="e" * 64)
            waiting = await _start(supervisor, operation_id)
            pending = waiting.pending_interaction
            assert pending is not None
            await supervisor.respond(_apply_response(operation_id, pending))
            await boundary.reached.wait()
            requested = await supervisor.request_cancel(operation_id)
            assert requested.effect is OperationEffect.NONE
            boundary.release.set()
            for _ in range(100):
                stopped = await supervisor.inspect(operation_id)
                if stopped.cancellation_acknowledged_at is not None:
                    break
                await asyncio.sleep(0)
            else:
                raise AssertionError("censal cancellation was not acknowledged")
            terminal = await _settle_when_stopped(
                supervisor,
                operation_id,
                OperationTerminalReceipt(
                    identity=stopped.identity,
                    revision=stopped.revision + 1,
                    condition=OperationTerminalCondition.CANCELLED,
                    effect=OperationEffect.NONE,
                    settled_at=_NOW,
                ),
            )
            assert terminal.effect is OperationEffect.NONE
            leases = OperationLeaseFilesystemRepository(storage_root=durable_root)
            observed = await leases.inspect(
                operation_conflict_scope_reference(
                    definition_id=CENSAL_OPERATION_DEFINITION.definition_id,
                    subject_ref=profile_id,
                ),
                operation_id,
                observed_at=_NOW,
            )
            assert observed.current is None

        asyncio.run(run())
        assert ProfileRecordRepository.for_current_session(profile_id).load(profile_id) == before
        assert ProfileRecordStore(session=session).history() == history_before
        assert all(resource.closed for resource in acquisition.resources)
