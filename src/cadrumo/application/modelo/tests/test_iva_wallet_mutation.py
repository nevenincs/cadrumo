"""The shared IVA-wallet mutation contract: amounts, profile ports and write receipts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest

from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.models import OperationIdentity, OperationTerminalReceipt
from ...user_profile.access_contracts import AccessDenialCode
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..iva_wallet_mutation import (
    bind_iva_wallet_profile_ports,
    require_iva_wallet_write_receipt,
    validate_iva_wallet_amount,
)
from ..iva_wallet_seed_ports import ModeloIvaWalletSeedPorts, ModeloIvaWalletSeedPortsFactory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = uuid4()
_DEFINITION_ID = "modelo.iva-wallet.test"
_MESSAGE = "IVA wallet test result contradicts its terminal receipt"


def _write_receipt() -> OperationTerminalReceipt:
    return OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE_ID)),
        ),
        revision=1,
        settled_at=datetime(2026, 1, 2, tzinfo=UTC),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        result_ref="d" * 64,
    )


def test_a_matching_write_receipt_is_accepted() -> None:
    require_iva_wallet_write_receipt(
        _write_receipt(), definition_id=_DEFINITION_ID, profile_id=_PROFILE_ID, message=_MESSAGE
    )


@pytest.mark.parametrize(
    "update",
    [
        {"effect": OperationEffect.NONE},
        {"condition": OperationTerminalCondition.REFUSED},
        {"diagnostic_ref": "e" * 64},
        {"result_ref": None},
        {"refusal_ref": "REFUSED_TEST"},
        {"refusal_detail_ref": "f" * 64},
        {"failure_error_code": "E_TEST"},
    ],
)
def test_a_contradicting_or_unvalidated_write_receipt_is_refused(update: dict[str, object]) -> None:
    receipt = _write_receipt().model_copy(update=update)

    with pytest.raises(ValueError, match=_MESSAGE):
        require_iva_wallet_write_receipt(
            receipt, definition_id=_DEFINITION_ID, profile_id=_PROFILE_ID, message=_MESSAGE
        )


def test_a_receipt_for_another_profile_or_operation_is_refused() -> None:
    for definition_id, profile_id in ((_DEFINITION_ID, uuid4()), ("modelo.iva-wallet.other", _PROFILE_ID)):
        with pytest.raises(ValueError, match=_MESSAGE):
            require_iva_wallet_write_receipt(
                _write_receipt(), definition_id=definition_id, profile_id=profile_id, message=_MESSAGE
            )


@pytest.mark.parametrize("value", ["0", "12.5", "-3.40"])
def test_canonical_wallet_amounts_are_kept(value: str) -> None:
    assert validate_iva_wallet_amount(value) == value


@pytest.mark.parametrize("value", ["1,5", "1.", "1.234", "+1"])
def test_non_canonical_wallet_amounts_are_refused(value: str) -> None:
    with pytest.raises(ValueError, match="canonical decimal text"):
        validate_iva_wallet_amount(value)


@dataclass(frozen=True)
class _Repository:
    bucket_id: str


def _factory(work_unit_bucket: str, calculation_bucket: str) -> ModeloIvaWalletSeedPortsFactory:
    def build(*, bucket_id: str, operation: PinnedAuthorityOperation) -> ModeloIvaWalletSeedPorts:
        return cast(
            ModeloIvaWalletSeedPorts,
            _Ports(_Repository(work_unit_bucket), _Repository(calculation_bucket)),
        )

    return build


@dataclass(frozen=True)
class _Ports:
    work_unit_repository: _Repository
    calculation_repository: _Repository


def test_profile_ports_are_returned_only_when_every_repository_is_the_profiles() -> None:
    profile = str(_PROFILE_ID)
    operation = cast(PinnedAuthorityOperation, object())

    ports = bind_iva_wallet_profile_ports(_factory(profile, profile), profile_id=profile, operation=operation)
    assert ports.work_unit_repository.bucket_id == profile
    for foreign in (_factory("other", profile), _factory(profile, "other")):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            bind_iva_wallet_profile_ports(foreign, profile_id=profile, operation=operation)
        assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
