"""A stale operation contract is refused apart from a malformed runtime frame."""

from __future__ import annotations

import logging

import pytest
from pydantic import BaseModel

from cadrumo.application.operations.contract_manifest import load_operation_contract_manifest
from cadrumo.application.operations.registry import OperationPublicDefinitionContractV1
from cadrumo.application.operations.schema_identity import OperationSchemaIdentityV1
from cadrumo.core.errors.error_codes import ErrorCategory, get_registered_error_code
from cadrumo.core.models import STRICT_FROZEN_CONFIG
from cadrumo_client.commands.errors import (
    OPERATION_CONTRACT_STALE_REASON,
    CliOperationContractStaleError,
    boundary_failure_level,
)
from cadrumo_client.commands.registered_operation_admission import require_registered_definition_contract
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.operation_access import OperationContractReply
from cadrumo_client.transport.frame_io import decode_document

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _DriftedResult(BaseModel):
    """A result model the shipped contract was not generated from."""

    model_config = STRICT_FROZEN_CONFIG

    drifted_member: str


def _plain_contract() -> OperationPublicDefinitionContractV1:
    """Return a shipped contract that takes neither a secret nor a financial operand."""
    for entry in load_operation_contract_manifest().operations:
        contract = entry.contract
        if (
            not contract.ephemeral_secret_required
            and contract.transient_financial_operand is None
            and contract.result_schema is not None
        ):
            return contract
    raise AssertionError("the shipped manifest declares no plain operation contract")


def _drifted(identity: OperationSchemaIdentityV1) -> OperationSchemaIdentityV1:
    return OperationSchemaIdentityV1.from_model(
        schema_id=identity.schema_id, schema_version=identity.schema_version, model_type=_DriftedResult
    )


def test_exact_contract_is_admitted() -> None:
    contract = _plain_contract()
    assert contract.result_schema is not None
    require_registered_definition_contract(
        contract, contract.definition_id, contract.request_schema, contract.result_schema, None
    )


def test_result_schema_from_another_model_is_a_stale_contract_naming_the_operation() -> None:
    contract = _plain_contract()
    assert contract.result_schema is not None
    expected_result = _drifted(contract.result_schema)
    assert expected_result.schema_fingerprint != contract.result_schema.schema_fingerprint

    with pytest.raises(CliOperationContractStaleError) as refused:
        require_registered_definition_contract(
            contract, contract.definition_id, contract.request_schema, expected_result, None
        )

    assert refused.value.context == {
        "reason": OPERATION_CONTRACT_STALE_REASON,
        "operation": contract.definition_id,
        "field": "result_schema",
        "effect": "none",
    }
    code = get_registered_error_code(refused.value)
    assert code.code == "REFUSED_CLI_OPERATION_CONTRACT_STALE"
    assert code.category is ErrorCategory.REFUSED
    assert boundary_failure_level(refused.value) == logging.ERROR
    assert not isinstance(refused.value, RefusalError)


def test_request_and_secret_requirements_name_their_own_field() -> None:
    contract = _plain_contract()
    assert contract.result_schema is not None
    with pytest.raises(CliOperationContractStaleError) as request_refused:
        require_registered_definition_contract(
            contract, contract.definition_id, _drifted(contract.request_schema), contract.result_schema, None
        )
    assert request_refused.value.context is not None
    assert request_refused.value.context["field"] == "request_schema"

    with pytest.raises(CliOperationContractStaleError) as secret_refused:
        require_registered_definition_contract(
            contract, contract.definition_id, contract.request_schema, contract.result_schema, bytearray(b"x")
        )
    assert secret_refused.value.context is not None
    assert secret_refused.value.context["field"] == "ephemeral_secret_required"


def test_contract_answered_for_another_operation_stays_an_invalid_frame() -> None:
    contract = _plain_contract()
    assert contract.result_schema is not None
    with pytest.raises(RefusalError) as refused:
        require_registered_definition_contract(
            contract, contract.definition_id + ".other", contract.request_schema, contract.result_schema, None
        )
    assert refused.value.reason is RefusalCode.INVALID_FRAME


def test_malformed_contract_frame_stays_an_invalid_frame() -> None:
    with pytest.raises(RefusalError) as refused:
        decode_document(b'{"kind":"operation_contract","contract":', OperationContractReply)
    assert refused.value.reason is RefusalCode.INVALID_FRAME
