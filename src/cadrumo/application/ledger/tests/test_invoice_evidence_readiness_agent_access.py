"""Reader readiness is open to every frontend and never releases the configured address in full."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ....core.config import override_settings
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.time.clock import now
from ...local_reader import LocalReaderStatus, read_local_reader_status
from ...operations import profile_guard
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessAction, Availability
from ..invoice_evidence_readiness_operation import (
    LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID,
    LedgerEvidenceReaderReadinessExecutionResult,
    LedgerEvidenceReaderReadinessExecutor,
    LedgerEvidenceReaderReadinessProjection,
    LedgerEvidenceReaderReadinessRequest,
    _reader_endpoint_origin,
    build_ledger_evidence_reader_readiness_definition,
    build_ledger_evidence_reader_readiness_registration,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_USER = "synthetic-reader-user"
_USER_CREDENTIAL = "synthetic-reader-credential"
_PATH_CREDENTIAL = "synthetic-path-credential"
_QUERY_CREDENTIAL = "synthetic-query-credential"
# Port 1 is closed, so the probe is refused at once and nothing is contacted.
_ENDPOINT = f"http://{_USER}:{_USER_CREDENTIAL}@127.0.0.1:1/{_PATH_CREDENTIAL}/api/chat?key={_QUERY_CREDENTIAL}"
_CREDENTIAL_FRAGMENTS = (_USER, _USER_CREDENTIAL, _PATH_CREDENTIAL, _QUERY_CREDENTIAL, "api/chat", "key=")


def _status() -> LocalReaderStatus:
    """Measure the real reader status against an endpoint that answers nothing."""
    with override_settings(cadrumo_llm_ollama_chat_url=_ENDPOINT):
        return read_local_reader_status(assess_load=False)


def _unread_status() -> LocalReaderStatus:
    raise AssertionError("registration and access resolution must not measure the reader")


def _registry() -> OperationRegistry:
    definition = build_ledger_evidence_reader_readiness_definition(_unread_status)
    registration = build_ledger_evidence_reader_readiness_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,))


def _request() -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=LedgerEvidenceReaderReadinessRequest(profile_id=_PROFILE),
    )


@pytest.mark.parametrize("frontend", sorted(OperationFrontendProjection))
def test_readiness_is_admitted_alike_on_every_frontend_for_either_kind_of_session(
    frontend: OperationFrontendProjection,
) -> None:
    registry = _registry()
    contract = registry.lookup_public_contract(LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID)

    resolved = resolve_operation_access(
        registry=registry,
        request=_request(),
        context=OperationAccessContext(
            profile_id=_PROFILE,
            destination_id=uuid4(),
            action=AccessAction.SUBMIT,
            frontend=frontend,
            contract=contract,
            published_authority=Availability.AVAILABLE,
        ),
    )

    assert contract.permitted_frontends == frozenset(OperationFrontendProjection)
    assert resolved.request.frontend is frontend
    assert resolved.request.profile_id == _PROFILE
    # A session under the person's sign-in and one under an enrolled key differ
    # in kind alone, and only a human-only policy tells the two apart.
    assert resolved.policy.requires_human is False
    assert AccessAction.COMMIT not in resolved.policy.actions


def test_the_projection_names_where_the_reader_answers_and_nothing_else_of_the_configured_address() -> None:
    status = _status()
    assert status.host.endpoint_url == _ENDPOINT

    projection = LedgerEvidenceReaderReadinessProjection.from_status(_PROFILE, status)

    assert projection.host.endpoint_url == "http://127.0.0.1:1"
    assert projection.host.endpoint_local is True
    assert projection.host.reachable is False and projection.host.available is False
    assert projection.host.failed_condition_id
    assert projection.extraction_ready is status.extraction_ready
    assert [row.role for row in projection.roles] == [row.role.value for row in status.roles]
    assert [row.model for row in projection.roles] == [row.model for row in status.roles]
    released = projection.model_dump_json()
    assert [fragment for fragment in _CREDENTIAL_FRAGMENTS if fragment in released] == []


@pytest.mark.parametrize(
    ("endpoint", "origin"),
    [
        ("http://127.0.0.1:11434/api/chat", "http://127.0.0.1:11434"),
        ("https://reader.example.invalid/api/chat", "https://reader.example.invalid"),
        (
            "https://user:credential@reader.example.invalid:8443/v1/credential?key=credential#credential",
            "https://reader.example.invalid:8443",
        ),
        ("http://[::1]:11434/api/chat", "http://[::1]:11434"),
        ("reader.example.invalid:11434", None),
        ("/var/run/synthetic-reader/socket", None),
        (r"C:\Users\synthetic-operator\reader.sock", None),
        ("http://reader.example.invalid:not-a-port/api/chat", None),
        ("http:///api/chat", None),
    ],
)
def test_only_the_scheme_host_and_port_of_an_address_are_kept_and_one_without_a_host_is_absent(
    endpoint: str, origin: str | None
) -> None:
    assert _reader_endpoint_origin(endpoint) == origin


@pytest.mark.parametrize(
    ("reported", "released", "withheld"),
    [
        ("0.5.7", "0.5.7", False),
        ("0.6.0-rc1+build.3", "0.6.0-rc1+build.3", False),
        ("unknown", "unknown", False),
        ("0.5.7 and a sentence the endpoint added for whoever reads this", None, True),
        ("<b>0.5.7</b>", None, True),
        ("9" * 65, None, True),
    ],
)
def test_what_the_endpoint_reports_as_its_version_is_released_only_when_it_reads_as_one(
    reported: str, released: str | None, withheld: bool
) -> None:
    measured = _status()
    answering = measured.host.model_copy(
        update={"reachable": True, "available": True, "version": reported, "precondition_verdict": None}
    )

    projection = LedgerEvidenceReaderReadinessProjection.from_status(
        _PROFILE, measured.model_copy(update={"host": answering})
    )

    assert (projection.host.version, projection.host.version_withheld) == (released, withheld)
    assert projection.host.reachable is True
    if withheld:
        assert reported not in projection.model_dump_json()


def test_an_endpoint_that_answers_nothing_reports_no_version_and_withholds_none() -> None:
    projection = LedgerEvidenceReaderReadinessProjection.from_status(_PROFILE, _status())

    assert (projection.host.version, projection.host.version_withheld) == (None, False)


@pytest.mark.asyncio
async def test_the_executor_and_the_registered_projector_release_the_reduced_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    stored: list[BaseModel] = []
    effects: list[OperationEffect] = []

    class Operands:
        async def put(self, value: BaseModel, *, written_at: datetime) -> str:
            assert written_at.tzinfo is not None
            stored.append(value)
            return "d" * 64

    class Events:
        async def phase(self, _code: str) -> None:
            return None

        async def effect(self, effect: OperationEffect) -> None:
            effects.append(effect)

    identity = OperationIdentity(
        operation_id="e" * 64,
        definition_id=LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
    )
    context = cast(
        OperationExecutorContext,
        cast(object, SimpleNamespace(identity=identity, events=Events(), operands=Operands())),
    )
    request = OperationRequest[LedgerEvidenceReaderReadinessRequest](
        definition_id=LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=LedgerEvidenceReaderReadinessRequest(profile_id=_PROFILE),
    )

    reference = await LedgerEvidenceReaderReadinessExecutor(_status).execute(request, context)

    assert reference == "d" * 64 and effects == [OperationEffect.NONE]
    (private,) = stored
    assert isinstance(private, LedgerEvidenceReaderReadinessExecutionResult)
    projector = (
        _registry()
        .lookup_public_registration(LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID)
        .result_projector
    )
    assert projector is not None
    released = projector(
        private,
        OperationTerminalReceipt(
            identity=identity,
            revision=1,
            condition=OperationTerminalCondition.SUCCEEDED,
            effect=OperationEffect.NONE,
            settled_at=now(),
            result_ref="d" * 64,
        ),
    )
    assert isinstance(released, LedgerEvidenceReaderReadinessProjection)
    assert released.host.endpoint_url == "http://127.0.0.1:1"
    document = released.model_dump_json()
    assert [fragment for fragment in _CREDENTIAL_FRAGMENTS if fragment in document] == []
