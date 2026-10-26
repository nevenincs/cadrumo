"""Custody result contracts resolve without loading profile health or authority execution."""

from __future__ import annotations

import pytest

from cadrumo.core.json_contract import OutputSchema
from cadrumo_client.commands.custody_payloads import ConfigLoginResult, ConfigLogoutResult

from ..command_schema import command_schema_type

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    ("identity", "schema"),
    [
        ("config.login", ConfigLoginResult),
        ("config.logout", ConfigLogoutResult),
    ],
)
def test_custody_graph_resolves_the_canonical_result_owner(identity: str, schema: type[OutputSchema]) -> None:
    assert command_schema_type(identity) is schema
    assert schema.__module__ == "cadrumo_client.commands.custody_payloads"
