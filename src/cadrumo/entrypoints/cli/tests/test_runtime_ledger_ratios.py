"""Ratio runtime bridges bind profile, public schemas, and terminal effects."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
import typer
from pydantic import BaseModel

from ....application.ledger import ratios_operation as ratios
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .. import runtime_ledger_ratios as bridge
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OPERATION_ID = "a" * 64
_CATEGORY = "vehiculo_combustible"


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    *,
    completion: RegisteredOperationCompletion[Any],
    definition_id: str,
    request_type: type[BaseModel],
    allow_refusal_detail: bool = False,
) -> list[BaseModel]:
    submitted: list[BaseModel] = []
    monkeypatch.setattr(bridge, "active_bucket_id_or_refuse", lambda: str(_PROFILE))
    monkeypatch.setattr(
        bridge,
        "require_profile_client",
        lambda _ctx, *, expected_profile_id: SimpleNamespace(profile_id=expected_profile_id),
    )

    def submit(_client: object, request: BaseModel, **kwargs: object) -> RegisteredOperationCompletion[Any]:
        submitted.append(request)
        assert isinstance(request, request_type)
        assert kwargs["definition_id"] == definition_id
        assert kwargs["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert kwargs["result_type"] is type(completion.projection)
        assert kwargs["request_version"] == kwargs["result_version"] == 1
        assert kwargs["timeout"] == 120
        assert kwargs.get("allow_refusal_detail", False) is allow_refusal_detail
        return completion

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    return submitted


def _ctx() -> typer.Context:
    return cast(typer.Context, cast(object, None))


def test_list_bridge_submits_exact_profile_and_accepts_registered_censo_refusal_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = ratios.LedgerRatiosListProjection(
        profile_id=_PROFILE,
        year=2026,
        outcome="censo_mismatch",
        rows=(),
        count=0,
    )
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.NONE,
        terminal_condition=OperationTerminalCondition.REFUSED,
        refusal_code=ratios.LEDGER_RATIOS_CENSO_MISMATCH_REFUSAL_CODE,
    )
    submitted = _bind(
        monkeypatch,
        completion=completion,
        definition_id=ratios.LEDGER_RATIOS_LIST_OPERATION_DEFINITION_ID,
        request_type=ratios.LedgerRatiosListRequest,
        allow_refusal_detail=True,
    )

    assert bridge.list_ratios(_ctx(), year=2026) is completion
    request = cast(ratios.LedgerRatiosListRequest, submitted[0])
    assert request.profile_id == _PROFILE
    assert request.year == 2026


def test_set_bridge_correlates_raw_category_alias_ratio_and_updated_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = ratios.LedgerRatiosSetProjection(
        profile_id=_PROFILE,
        requested_category="vehicle-alias",
        category=_CATEGORY,
        ratio="0.50",
        prior_ratio=None,
    )
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.UPDATED,
    )
    submitted = _bind(
        monkeypatch,
        completion=completion,
        definition_id=ratios.LEDGER_RATIOS_SET_OPERATION_DEFINITION_ID,
        request_type=ratios.LedgerRatiosSetRequest,
    )

    assert bridge.set_ratio(_ctx(), category="vehicle-alias", ratio="0.50", year=2026) is completion
    request = cast(ratios.LedgerRatiosSetRequest, submitted[0])
    assert request.profile_id == _PROFILE
    assert request.category == "vehicle-alias"
    assert request.ratio == "0.50"
    assert request.year == 2026


def test_unset_bridge_preserves_the_registered_no_override_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = ratios.LedgerRatiosUnsetProjection(
        profile_id=_PROFILE,
        requested_category="vehicle-alias",
        category=_CATEGORY,
        outcome="no_override",
        prior_ratio=None,
    )
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.NONE,
        terminal_condition=OperationTerminalCondition.REFUSED,
        refusal_code=ratios.LEDGER_RATIOS_NO_OVERRIDE_REFUSAL_CODE,
    )
    submitted = _bind(
        monkeypatch,
        completion=completion,
        definition_id=ratios.LEDGER_RATIOS_UNSET_OPERATION_DEFINITION_ID,
        request_type=ratios.LedgerRatiosUnsetRequest,
        allow_refusal_detail=True,
    )

    assert bridge.unset_ratio(_ctx(), category="vehicle-alias") is completion
    request = cast(ratios.LedgerRatiosUnsetRequest, submitted[0])
    assert request.profile_id == _PROFILE
    assert request.category == "vehicle-alias"


def test_eligible_bridge_correlates_pinned_year_and_read_only_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = ratios.LedgerRatiosEligibleProjection(profile_id=_PROFILE, year=2026, rows=(), count=0)
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.NONE,
    )
    submitted = _bind(
        monkeypatch,
        completion=completion,
        definition_id=ratios.LEDGER_RATIOS_ELIGIBLE_OPERATION_DEFINITION_ID,
        request_type=ratios.LedgerRatiosEligibleRequest,
    )

    assert bridge.list_eligible_ratios(_ctx(), year=2026) is completion
    request = cast(ratios.LedgerRatiosEligibleRequest, submitted[0])
    assert request.profile_id == _PROFILE
    assert request.year == 2026


def test_validate_bridge_rejects_a_mutation_effect_on_a_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = ratios.LedgerRatiosValidateProjection(
        profile_id=_PROFILE,
        profile_present=False,
        eligible_count=0,
        overrides_count=0,
        missing_overrides=(),
        findings=(),
    )
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.UPDATED,
    )
    submitted = _bind(
        monkeypatch,
        completion=completion,
        definition_id=ratios.LEDGER_RATIOS_VALIDATE_OPERATION_DEFINITION_ID,
        request_type=ratios.LedgerRatiosValidateRequest,
    )

    with pytest.raises(CliRefusedBoundaryError) as refused:
        bridge.validate_ratios(_ctx())

    request = cast(ratios.LedgerRatiosValidateRequest, submitted[0])
    assert request.profile_id == _PROFILE
    assert refused.value.context is not None
    assert refused.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value
