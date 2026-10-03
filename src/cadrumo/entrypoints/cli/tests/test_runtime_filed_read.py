"""Filed list/discover CLI routes preserve exact-profile worker results."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.live.filed_data import FiledDataListingRow
from ....application.live.filed_data_capture import FiledHistoryDiscoveryPair, FiledHistoryDiscoveryReport
from ....application.live.filed_read_operation import (
    FILED_DISCOVER_DEFINITION_ID,
    FILED_LIST_DEFINITION_ID,
    FiledDiscoverPairPublicV1,
    FiledDiscoverPublicResultV1,
    FiledDiscoverRequest,
    FiledListingFailurePublicV1,
    FiledListingRowPublicV1,
    FiledListPublicResultV1,
    FiledListRequest,
)
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.filed_history_discovery_signal import FiledHistoryDiscoverySignal
from ....core.json_contract import Notice, NoticeSeverity
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.period import Period
from ....core.register_scoping_signal import RegisterScopingSignal
from .. import _app_live as handler
from .. import runtime_filed_read as bridge
from .._app_live_filed_payloads import FiledDiscoverResult, FiledListResult
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OPERATION_ID = "a" * 64
_PRESENTED_AT = datetime(2025, 3, 6, 7, 8, tzinfo=UTC)


def _list_projection() -> FiledListPublicResultV1:
    return FiledListPublicResultV1(
        modelo_filter="303",
        year_from=2024,
        year_to=2025,
        row_count=1,
        failed_count=1,
        rows=(
            FiledListingRowPublicV1(
                modelo="303",
                year=2025,
                period="1T",
                expediente_id="202520013522222B",
                status="presented",
                presented_at=_PRESENTED_AT,
                has_submitted_file=True,
                has_declaration_copy=False,
                has_justificante=True,
            ),
        ),
        failures=(
            FiledListingFailurePublicV1(
                modelo="303",
                year=2024,
                period="4T",
                expediente_id="202420013522222B",
                error_type="TimeoutError",
                message="register request timed out",
            ),
        ),
    )


def _discover_projection() -> FiledDiscoverPublicResultV1:
    return FiledDiscoverPublicResultV1(
        pairs=(
            FiledDiscoverPairPublicV1(
                modelo="303",
                ejercicio=2025,
                signals=(FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY,),
            ),
        ),
        profile_year_span_determined=True,
        register_options_read=True,
        scoping_signal=RegisterScopingSignal.INCONCLUSIVE,
    )


def _bind_list(
    monkeypatch: pytest.MonkeyPatch,
    projection: FiledListPublicResultV1,
    *,
    effect: OperationEffect = OperationEffect.NONE,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    refusal_code: str | None = None,
) -> tuple[list[tuple[FiledListRequest, dict[str, object]]], list[UUID]]:
    monkeypatch.setattr(bridge, "require_active_bucket_id", lambda: str(_PROFILE))
    bound_profiles: list[UUID] = []

    def require_client(_ctx: object, *, expected_profile_id: UUID):
        bound_profiles.append(expected_profile_id)
        return object()

    monkeypatch.setattr(bridge, "require_profile_client", require_client)
    submitted: list[tuple[FiledListRequest, dict[str, object]]] = []

    def submit(_client: object, request: FiledListRequest, **kwargs: object):
        submitted.append((request, kwargs))
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=effect,
            terminal_condition=condition,
            refusal_code=refusal_code,
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    return submitted, bound_profiles


def _bind_discover(
    monkeypatch: pytest.MonkeyPatch,
    projection: FiledDiscoverPublicResultV1,
    *,
    effect: OperationEffect = OperationEffect.NONE,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    refusal_code: str | None = None,
) -> tuple[list[tuple[FiledDiscoverRequest, dict[str, object]]], list[UUID]]:
    monkeypatch.setattr(bridge, "require_active_bucket_id", lambda: str(_PROFILE))
    bound_profiles: list[UUID] = []

    def require_client(_ctx: object, *, expected_profile_id: UUID):
        bound_profiles.append(expected_profile_id)
        return object()

    monkeypatch.setattr(bridge, "require_profile_client", require_client)
    submitted: list[tuple[FiledDiscoverRequest, dict[str, object]]] = []

    def submit(_client: object, request: FiledDiscoverRequest, **kwargs: object):
        submitted.append((request, kwargs))
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=effect,
            terminal_condition=condition,
            refusal_code=refusal_code,
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    return submitted, bound_profiles


def _list_read() -> bridge.FiledListRead:
    return bridge.read_filed_list_for_cli(
        cast(typer.Context, cast(object, None)), modelo="303", year_from=2024, year_to=2025
    )


def _discover_read() -> bridge.FiledDiscoverRead:
    return bridge.read_filed_discover_for_cli(cast(typer.Context, cast(object, None)))


@pytest.mark.parametrize("effect", [OperationEffect.NONE, OperationEffect.UPDATED])
def test_list_submits_exact_profile_scope_and_restores_listing_rows(
    monkeypatch: pytest.MonkeyPatch, effect: OperationEffect
) -> None:
    submitted, bound_profiles = _bind_list(monkeypatch, _list_projection(), effect=effect)

    read = _list_read()

    assert bound_profiles == [_PROFILE]
    assert read.completion.operation_id == _OPERATION_ID
    assert read.projection == _list_projection()
    assert read.rows == (
        FiledDataListingRow(
            modelo="303",
            year=2025,
            period=Period.from_year_and_code(2025, "1T"),
            expediente_id="202520013522222B",
            status="presented",
            presented_at=_PRESENTED_AT,
            has_submitted_file=True,
            has_declaration_copy=False,
            has_justificante=True,
        ),
    )
    assert len(submitted) == 1
    request, options = submitted[0]
    assert request == FiledListRequest(profile_id=_PROFILE, modelo="303", year_from=2024, year_to=2025)
    assert options["definition_id"] == FILED_LIST_DEFINITION_ID
    assert options["subject_ref"] == profile_operation_subject(str(_PROFILE))
    assert options["result_type"] is FiledListPublicResultV1


def test_list_accepts_the_live_session_write_a_remote_read_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    """A read that drove an AEAT session settles ``updated``, and that is not a mismatch.

    The executor combines its live-session write receipt with
    ``OperationEffect.NONE`` before settling, so reaching the register can
    report ``updated`` without the read having written anything of the
    operator's. Refusing it here would fail the ordinary remote path, so the
    negative half above uses ``unknown`` -- an extent the bridge genuinely
    cannot trust.
    """
    _bind_list(monkeypatch, _list_projection(), effect=OperationEffect.UPDATED)

    read = _list_read()

    assert read.completion.effect is OperationEffect.UPDATED
    assert read.projection == _list_projection()


@pytest.mark.parametrize("mismatch", ["model", "year_range", "row_scope", "effect", "terminal", "refusal"])
def test_list_scope_or_receipt_mismatch_refuses_correlated_operation(
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    projection = _list_projection()
    effect = OperationEffect.NONE
    condition = OperationTerminalCondition.SUCCEEDED
    refusal_code = None
    if mismatch == "model":
        projection = projection.model_copy(update={"modelo_filter": None})
    elif mismatch == "year_range":
        projection = projection.model_copy(update={"year_to": 2024})
    elif mismatch == "row_scope":
        rows = (projection.rows[0].model_copy(update={"year": 2023}),)
        projection = projection.model_copy(update={"rows": rows})
    elif mismatch == "effect":
        effect = OperationEffect.UNKNOWN
    elif mismatch == "terminal":
        condition = OperationTerminalCondition.REFUSED
    elif mismatch == "refusal":
        refusal_code = RuntimeRefusalCode.UNAVAILABLE.value
    _bind_list(
        monkeypatch,
        projection,
        effect=effect,
        condition=condition,
        refusal_code=refusal_code,
    )

    with pytest.raises(CliRefusedBoundaryError) as error:
        _list_read()

    assert error.value.context is not None
    assert error.value.context["operation_id"] == _OPERATION_ID
    assert error.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


def test_discover_submits_exact_profile_and_restores_report(monkeypatch: pytest.MonkeyPatch) -> None:
    submitted, bound_profiles = _bind_discover(monkeypatch, _discover_projection())

    read = _discover_read()

    expected_pair = FiledHistoryDiscoveryPair(
        modelo="303",
        ejercicio=2025,
        signals=(FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY,),
    )
    assert bound_profiles == [_PROFILE]
    assert read.completion.operation_id == _OPERATION_ID
    assert read.report == FiledHistoryDiscoveryReport(
        pairs=(expected_pair,),
        profile_year_span_determined=True,
        register_options_read=True,
        scoping_signal=RegisterScopingSignal.INCONCLUSIVE,
    )
    assert len(submitted) == 1
    request, options = submitted[0]
    assert request == FiledDiscoverRequest(profile_id=_PROFILE)
    assert options["definition_id"] == FILED_DISCOVER_DEFINITION_ID
    assert options["subject_ref"] == profile_operation_subject(str(_PROFILE))
    assert options["result_type"] is FiledDiscoverPublicResultV1


@pytest.mark.parametrize(
    "condition,refusal_code",
    [(OperationTerminalCondition.REFUSED, None), (OperationTerminalCondition.SUCCEEDED, "unavailable")],
)
def test_discover_rejects_receipt_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    condition: OperationTerminalCondition,
    refusal_code: str | None,
) -> None:
    _bind_discover(
        monkeypatch,
        _discover_projection(),
        condition=condition,
        refusal_code=refusal_code,
    )

    with pytest.raises(CliRefusedBoundaryError) as error:
        _discover_read()

    assert error.value.context is not None
    assert error.value.context["operation_id"] == _OPERATION_ID
    assert error.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


def test_list_command_preserves_existing_result_and_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _list_projection()
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.NONE,
    )
    read = _list_read_for_command(projection, completion)
    monkeypatch.setattr(handler, "emit_live_auth_preflight", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(bridge, "read_filed_list_for_cli", lambda *_args, **_kwargs: read)
    envelopes: list[dict[str, object]] = []
    monkeypatch.setattr(handler, "emit_envelope", lambda *_args, **kwargs: envelopes.append(kwargs))

    handler.filed_list_cmd(cast(typer.Context, cast(object, None)), modelo="303", year_from=2024, year_to=2025)

    assert len(envelopes) == 1
    envelope = envelopes[0]
    assert envelope["command"] == "app.live.filed.list"
    result = cast(FiledListResult, envelope["result"])
    assert result.modelo_filter == "303"
    assert result.row_count == 1
    assert result.failed_count == 1
    assert result.rows[0].period == "1T"
    assert result.failures[0].period == "4T"
    lines = cast(tuple[str, ...], envelope["lines"])
    assert "row_count=1" in lines
    assert "failed_count=1" in lines
    assert "303\t2025\t1T\t202520013522222B" in lines[2]


def _list_read_for_command(
    projection: FiledListPublicResultV1,
    completion: RegisteredOperationCompletion[FiledListPublicResultV1],
) -> bridge.FiledListRead:
    listed = tuple(bridge._listing_row(row) for row in projection.rows)
    failures = tuple(bridge._listing_failure(row) for row in projection.failures)
    return bridge.FiledListRead(completion=completion, projection=projection, rows=listed, failures=failures)


def test_discover_command_preserves_result_lines_and_notices(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _discover_projection()
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.NONE,
    )
    read = bridge.FiledDiscoverRead(
        completion=completion,
        projection=projection,
        report=bridge._discover_report(projection),
    )
    monkeypatch.setattr(bridge, "read_filed_discover_for_cli", lambda *_args, **_kwargs: read)
    envelopes: list[dict[str, object]] = []
    monkeypatch.setattr(handler, "emit_envelope", lambda *_args, **kwargs: envelopes.append(kwargs))

    handler.filed_discover_cmd(cast(typer.Context, cast(object, None)))

    assert len(envelopes) == 1
    envelope = envelopes[0]
    assert envelope["command"] == "app.live.filed.discover"
    result = cast(FiledDiscoverResult, envelope["result"])
    assert result.pair_count == 1
    assert result.profile_expected_count == 1
    assert result.carries_a_taxpayer_specific_denominator is True
    lines = cast(tuple[str, ...], envelope["lines"])
    assert "pair_count=1" in lines
    assert FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY.value in lines[3]
    notices = cast(list[Notice], envelope["notices"])
    assert any(notice.severity is NoticeSeverity.INFO for notice in notices)
