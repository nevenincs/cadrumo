"""The installed import door previews a dry run and applies exactly the previewed bytes."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.ledger.actions_import import LedgerProviderID
from cadrumo.application.ledger.import_operation import (
    LEDGER_IMPORT_OPERATION_DEFINITION_ID,
    LedgerImportFileRefusal,
    LedgerImportOperationPortsFactory,
    LedgerImportRequest,
    LedgerImportResultProjection,
    LedgerImportSourceDigest,
    LedgerImportValidationProjection,
    build_ledger_import_definition,
    build_ledger_import_registration,
)
from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
)
from cadrumo.application.operations.frontend_requests import OperationObservationSuccessV1, OperationPublicEventPageV1
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.core.i18n.render import tr
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.domain.transactions.errors import TransactionValidationError
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError
from cadrumo.entrypoints.tui.ledger.models import (
    LedgerImportRequestV1,
    LedgerImportSourceBindingV1,
    LedgerImportSourceKind,
)
from cadrumo.entrypoints.tui.operations.runtime_controller import RuntimeOperationController
from cadrumo.entrypoints.tui.runtime_ledger_import import RuntimeLedgerImportTuiDoorV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE_ID = UUID("5aa00000-0000-4000-8000-0000000000aa")
_SESSION_ID = UUID("6bb00000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "a" * 64
_NOW = datetime(2026, 10, 4, tzinfo=UTC)


class _Client:
    frontend = OperationFrontendProjection.TUI

    def __init__(self) -> None:
        self.profile_id = _PROFILE_ID
        self.session_id = _SESSION_ID


class _Controller:
    operation_id = _OPERATION_ID

    def __init__(self, observation: OperationObservationSuccessV1, result: LedgerImportResultProjection) -> None:
        self.observation = observation
        self.result = result

    async def start(self) -> str:
        return self.operation_id

    async def observe(self, after_cursor: int, *, page_limit: int) -> OperationObservationSuccessV1:
        assert after_cursor == 0
        assert page_limit == 1
        return self.observation

    async def read_settled_result(
        self,
        projection: OperationPublicProjectionV1,
        result_type: type[BaseModel],
        *,
        result_version: int,
        allow_refusal_detail: bool = False,
    ) -> LedgerImportResultProjection:
        del result_type, result_version, allow_refusal_detail
        assert projection.operation_id == self.operation_id
        return self.result


def _observation(effect: OperationEffect) -> OperationObservationSuccessV1:
    factory = cast(LedgerImportOperationPortsFactory, cast(object, lambda **_kwargs: None))
    definition = build_ledger_import_definition(factory)
    registry = OperationRegistry(
        definitions=(definition,),
        public_registrations=(build_ledger_import_registration(definition),),
    )
    contract = registry.lookup_public_contract(LEDGER_IMPORT_OPERATION_DEFINITION_ID)
    state = OperationPublicProjectionV1(
        operation_id=_OPERATION_ID,
        definition_id=LEDGER_IMPORT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE_ID)),
        revision=1,
        anchor_cursor=0,
        definition_contract=contract,
        contract_set_digest=registry.public_contract_set.contract_set_digest,
        lifecycle=OperationLifecycle.TERMINAL,
        terminal_condition=OperationTerminalCondition.SUCCEEDED,
        effect=effect,
        phase_code=None,
        started_at=_NOW,
        updated_at=_NOW,
        progress=None,
        close_policy=contract.close_policy,
        cancellation=contract.cancellation,
        cancellable_now=False,
        cancellation_requested=False,
        cancellation_acknowledged=False,
        execution_deadline_at=None,
        cleanup_deadline_at=None,
        pending_interaction=OperationNoPendingInteractionV1(),
        result_ref="f" * 64,
        refusal_ref=None,
        failure_error_code=None,
        diagnostic_ref=None,
    )
    return OperationObservationSuccessV1(
        projection=state,
        event_page=OperationPublicEventPageV1(
            operation_id=_OPERATION_ID,
            anchor_cursor=0,
            requested_cursor=0,
            status=OperationReplayStatus.CAUGHT_UP,
            events=(),
            next_cursor=0,
            restart_cursor=None,
        ),
    )


def _result(
    *,
    dry_run: bool,
    imported: int,
    valid_files: int,
    digests: tuple[LedgerImportSourceDigest, ...] = (),
    refused: tuple[LedgerImportFileRefusal, ...] = (),
) -> LedgerImportResultProjection:
    return LedgerImportResultProjection(
        profile_id=_PROFILE_ID,
        rows=2 * valid_files,
        imported=imported,
        skipped=0,
        likely_duplicates=0,
        dry_run=dry_run,
        verify=False,
        bucket_id=str(_PROFILE_ID),
        validations=tuple(LedgerImportValidationProjection(valid=True, warning_count=0) for _ in range(valid_files)),
        sources=(),
        refused_files=refused,
        source_digests=digests,
    )


def _install(
    monkeypatch: pytest.MonkeyPatch,
    client: _Client,
    answers: list[tuple[OperationEffect, LedgerImportResultProjection]],
) -> list[dict[str, object]]:
    from cadrumo.entrypoints.tui.operations import runtime_profile_session as bridge

    def read_session(_client: RuntimeFrontendClient, *, profile_id: UUID, session_id: UUID, profile_label: str):
        assert profile_label == "Fixture profile"
        if client.profile_id != profile_id or client.session_id != session_id:
            raise AccountSessionExpiredError()
        return object()

    monkeypatch.setattr(bridge, "read_runtime_account_session", read_session)
    submissions: list[dict[str, object]] = []

    async def submit(
        _controller_type: type[RuntimeOperationController],
        received_client: RuntimeFrontendClient,
        **kwargs: object,
    ) -> _Controller:
        assert received_client is client
        submissions.append(kwargs)
        effect, result = answers.pop(0)
        return _Controller(_observation(effect), result)

    monkeypatch.setattr(RuntimeOperationController, "submit", classmethod(submit))
    return submissions


def _door(client: _Client) -> RuntimeLedgerImportTuiDoorV1:
    return RuntimeLedgerImportTuiDoorV1(cast(RuntimeFrontendClient, client), profile_label="Fixture profile")


def _folder(tmp_path: Path) -> tuple[Path, Path, Path]:
    folder = tmp_path / "statements"
    folder.mkdir()
    first, second = folder / "april.csv", folder / "may.csv"
    for path in (first, second):
        path.write_text("synthetic", encoding="utf-8")
    return folder, first, second


def test_preview_runs_a_dry_run_of_the_planned_files_and_keeps_each_parsed_digest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _Client()
    folder, first, second = _folder(tmp_path)
    preview = _result(
        dry_run=True,
        imported=2,
        valid_files=1,
        digests=(LedgerImportSourceDigest(file_index=0, sha256="b" * 64),),
        refused=(LedgerImportFileRefusal(file_name="may.csv", reason_code="own_account_mismatch"),),
    )
    submissions = _install(monkeypatch, client, [(OperationEffect.NONE, preview)])
    request = LedgerImportRequestV1(
        path=folder,
        source_kind=LedgerImportSourceKind.BANK_STATEMENT,
        provider=LedgerProviderID.CSV,
        own_account_id="acc-01",
    )

    outcome = asyncio.run(_door(client).preview(request))

    payload = cast(LedgerImportRequest, submissions[0]["payload"])
    assert payload.dry_run is True
    assert payload.files == (first.absolute(), second.absolute())
    assert payload.own_account_id == "acc-01"
    assert payload.expected_source_sha256 is None
    assert outcome.sources == (LedgerImportSourceBindingV1(path=first.absolute(), sha256="b" * 64),)
    assert [item.reason for item in outcome.refused_files] == [tr("tui.ledger.import.refusal.own_account_mismatch")]


def test_apply_submits_exactly_the_previewed_files_with_their_digests(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _Client()
    _folder_path, first, _second = _folder(tmp_path)
    applied = _result(
        dry_run=False,
        imported=2,
        valid_files=1,
        digests=(LedgerImportSourceDigest(file_index=0, sha256="b" * 64),),
    )
    submissions = _install(monkeypatch, client, [(OperationEffect.UPDATED, applied)])
    request = LedgerImportRequestV1(
        path=first.parent,
        source_kind=LedgerImportSourceKind.BANK_STATEMENT,
        previewed_sources=(LedgerImportSourceBindingV1(path=first, sha256="b" * 64),),
    )

    outcome = asyncio.run(_door(client).apply(request))

    payload = cast(LedgerImportRequest, submissions[0]["payload"])
    assert payload.dry_run is False
    assert payload.files == (first,)
    assert payload.expected_source_sha256 == ("b" * 64,)
    assert outcome.imported == 2


def test_a_changed_file_reports_its_refusal_rather_than_an_import(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _Client()
    _folder_path, first, _second = _folder(tmp_path)
    refused = _result(
        dry_run=False,
        imported=0,
        valid_files=0,
        refused=(LedgerImportFileRefusal(file_name="april.csv", reason_code="source_changed"),),
    )
    _install(monkeypatch, client, [(OperationEffect.NONE, refused)])
    request = LedgerImportRequestV1(
        path=first,
        source_kind=LedgerImportSourceKind.BANK_STATEMENT,
        previewed_sources=(LedgerImportSourceBindingV1(path=first, sha256="b" * 64),),
    )

    outcome = asyncio.run(_door(client).apply(request))

    assert outcome.imported == 0
    assert [item.reason for item in outcome.refused_files] == [tr("tui.ledger.import.refusal.source_changed")]


def test_a_result_whose_effect_disagrees_with_its_import_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _Client()
    _folder_path, first, _second = _folder(tmp_path)
    applied = _result(dry_run=False, imported=2, valid_files=1)
    _install(monkeypatch, client, [(OperationEffect.NONE, applied)])
    request = LedgerImportRequestV1(
        path=first,
        source_kind=LedgerImportSourceKind.BANK_STATEMENT,
        previewed_sources=(LedgerImportSourceBindingV1(path=first, sha256="b" * 64),),
    )

    with pytest.raises(RuntimeRefusalError) as raised:
        asyncio.run(_door(client).apply(request))

    assert raised.value.reason is RuntimeRefusalCode.INVALID_FRAME


def test_invoice_books_and_unpreviewed_applies_are_refused_before_anything_is_submitted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _Client()
    _folder_path, first, _second = _folder(tmp_path)
    submissions = _install(monkeypatch, client, [])
    door = _door(client)

    with pytest.raises(TransactionValidationError):
        asyncio.run(
            door.preview(
                LedgerImportRequestV1(path=first, source_kind=LedgerImportSourceKind.INVOICES_RECEIVED, country="ES")
            )
        )
    with pytest.raises(TransactionValidationError):
        asyncio.run(
            door.apply(
                LedgerImportRequestV1(
                    path=first, source_kind=LedgerImportSourceKind.BANK_STATEMENT, previewed_sources=()
                )
            )
        )
    with pytest.raises(RuntimeRefusalError):
        asyncio.run(door.apply(LedgerImportRequestV1(path=first, source_kind=LedgerImportSourceKind.BANK_STATEMENT)))
    assert submissions == []
