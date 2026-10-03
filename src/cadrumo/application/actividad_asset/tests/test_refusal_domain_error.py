"""A recorded activity-asset refusal rebuilds the domain error that produced it."""

from __future__ import annotations

import pytest

from cadrumo.application.actividad_asset.activity_asset_contracts import ActivityAssetRefusal
from cadrumo.domain.renta.actividad_asset.errors import (
    ActividadAssetClaimConflictError,
    ActividadAssetError,
    ActividadAssetIncompleteError,
    ActividadAssetUnsupportedError,
    ActividadAssetValidationError,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CONTEXT = {"operation_id": "d" * 64, "effect": "none", "refusal_code": "REFUSED_EXAMPLE"}


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
