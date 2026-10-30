"""A refusal's specific key and facts travel in the public result every frontend reads.

The command line, the terminal workbench and the MCP service all read a refused
operation's typed result through the definition's declared refusal-detail codes,
so the key and facts survive to each of them only if the public refusal schema
carries them and the definition lists every refusal code it can record.
"""

from __future__ import annotations

from typing import cast, get_args

import pytest

from cadrumo.application.actividad_asset.activity_asset_contracts import (
    ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_REFUSAL_CODES,
    ActivityAssetOperationPortsFactory,
    ActivityAssetRefusal,
    ActivityAssetRefusalCode,
)
from cadrumo.application.actividad_asset.registered_operations import (
    build_activity_asset_inspect_definition,
    build_activity_asset_inspect_registration,
)
from cadrumo.application.operations.registry import OperationRegistry

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_the_public_refusal_schema_carries_the_reason_key_and_facts() -> None:
    properties = ActivityAssetRefusal.model_json_schema()["properties"]

    assert {"reason_key", "reason_facts"} <= set(properties)


def test_every_refusal_code_is_a_declared_refusal_detail_code() -> None:
    assert set(get_args(ActivityAssetRefusalCode)) == ACTIVITY_ASSET_REFUSAL_CODES
    factory = cast(ActivityAssetOperationPortsFactory, cast(object, lambda **_kwargs: None))
    definition = build_activity_asset_inspect_definition(factory)
    registry = OperationRegistry(
        definitions=(definition,),
        public_registrations=(build_activity_asset_inspect_registration(definition),),
    )

    contract = registry.lookup_public_contract(ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID)

    assert contract.refusal_detail_codes == ACTIVITY_ASSET_REFUSAL_CODES
