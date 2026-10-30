"""A recorded activity-asset refusal rebuilds the domain error that produced it."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cadrumo.application.actividad_asset import activity_asset_executors
from cadrumo.application.actividad_asset.activity_asset_contracts import ActivityAssetRefusal
from cadrumo.application.actividad_asset.activity_asset_read_models import project_reason_facts
from cadrumo.application.actividad_asset.registered_operations import _project_refusal
from cadrumo.core.errors.error_codes import get_registered_error_code_by_code
from cadrumo.domain.renta.actividad_asset.errors import (
    ActividadAssetAcceleratedDa18DepreciationError,
    ActividadAssetClaimConflictError,
    ActividadAssetError,
    ActividadAssetIncompleteError,
    ActividadAssetPeriodElapsedError,
    ActividadAssetUnsupportedError,
    ActividadAssetValidationError,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CONTEXT = {"operation_id": "d" * 64, "effect": "none", "refusal_code": "REFUSED_EXAMPLE"}


def test_elapsed_period_has_a_distinct_registered_error_identity() -> None:
    error = ActividadAssetPeriodElapsedError("maximum amortization period elapsed")

    assert error.code.code == "REFUSED_ACTIVIDAD_ASSET_PERIOD_ELAPSED"
    assert error.code is get_registered_error_code_by_code("REFUSED_ACTIVIDAD_ASSET_PERIOD_ELAPSED")
    assert ActividadAssetUnsupportedError.code.code == "REFUSED_ACTIVIDAD_ASSET_UNSUPPORTED"


def test_elapsed_period_projects_the_public_unsupported_refusal() -> None:
    refusal = activity_asset_executors._refusal(ActividadAssetPeriodElapsedError("period elapsed"))

    assert refusal is not None
    assert refusal.code == "REFUSED_ACTIVIDAD_ASSET_UNSUPPORTED"
    public_refusal = _project_refusal(refusal)
    assert public_refusal is not None
    public_error = public_refusal.to_domain_error(context=_CONTEXT)
    assert type(public_error) is ActividadAssetUnsupportedError
    assert public_error.context == _CONTEXT


@pytest.mark.parametrize(
    ("code", "error_type"),
    [
        ("REFUSED_ACTIVIDAD_ASSET_VALIDATION", ActividadAssetValidationError),
        ("REFUSED_ACTIVIDAD_ASSET_UNSUPPORTED", ActividadAssetUnsupportedError),
        ("REFUSED_ACTIVIDAD_ASSET_INCOMPLETE", ActividadAssetIncompleteError),
        ("REFUSED_ACTIVIDAD_ASSET_CLAIM_CONFLICT", ActividadAssetClaimConflictError),
    ],
)
def test_each_refusal_code_rebuilds_its_own_domain_error_with_the_receipt_facts(
    code: str, error_type: type[ActividadAssetError]
) -> None:
    error = ActivityAssetRefusal.model_validate({"code": code}).to_domain_error(context=_CONTEXT)

    assert type(error) is error_type
    assert error.context == _CONTEXT


def test_an_incomplete_refusal_without_a_verdict_carries_no_recovery_verdict() -> None:
    error = ActivityAssetRefusal.model_validate({"code": "REFUSED_ACTIVIDAD_ASSET_INCOMPLETE"}).to_domain_error(
        context=_CONTEXT
    )

    assert isinstance(error, ActividadAssetIncompleteError)
    assert error.terminal_precondition_verdict is None


_DA18_FACTS = {
    "asset_id": "van-2023",
    "method": "electric_vehicle_free",
    "tax_year": 2023,
    "legal_reference": "ley-27-2014:da-18",
}


def test_a_da18_refusal_rebuilds_its_own_error_with_the_facts_it_names() -> None:
    error = ActivityAssetRefusal.model_validate(
        {"code": "REFUSED_ACTIVIDAD_ASSET_ACCELERATED_DA18_DEPRECIATION_NOT_COMPUTED", "accelerated_da18": _DA18_FACTS}
    ).to_domain_error(context=_CONTEXT)

    assert type(error) is ActividadAssetAcceleratedDa18DepreciationError
    assert error.context == {**_DA18_FACTS, **_CONTEXT}


@pytest.mark.parametrize(
    "document",
    [
        {"code": "REFUSED_ACTIVIDAD_ASSET_ACCELERATED_DA18_DEPRECIATION_NOT_COMPUTED"},
        {"code": "REFUSED_ACTIVIDAD_ASSET_UNSUPPORTED", "accelerated_da18": _DA18_FACTS},
    ],
)
def test_da18_facts_accompany_exactly_the_da18_refusal(document: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ActivityAssetRefusal.model_validate(document)


def test_reason_facts_round_trip_through_public_refusal() -> None:
    facts = {"z": "last", "a": "first"}
    refusal = ActivityAssetRefusal(code="REFUSED_ACTIVIDAD_ASSET_VALIDATION", reason_facts=project_reason_facts(facts))
    assert [(fact.key, fact.value) for fact in refusal.reason_facts] == [("a", "first"), ("z", "last")]
    restored = ActivityAssetRefusal.model_validate_json(refusal.model_dump_json())
    assert restored.to_domain_error(context=_CONTEXT).context == {**facts, **_CONTEXT}
    with pytest.raises(ValidationError):
        restored.reason_facts[0].value = "changed"
