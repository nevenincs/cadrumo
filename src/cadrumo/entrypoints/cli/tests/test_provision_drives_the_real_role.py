"""``config provision`` renders the rows and refusals of the real components role of a built Cadrumo binary.

``just test-components-role IMAGE`` runs these cases with the built binary
(:mod:`cadrumo.tests.components_role_package`), each with its own throwaway
storage root and a local proxy that refuses every tunnel.
"""

from __future__ import annotations

import json

import pytest

from cadrumo.tests.components_role_package import (
    components_role_fixture,
    refusing_proxy_fixture,
    staged_components_role_fixture,
)
from cadrumo.tests.english_locale_fixture import english_locale_fixture

from .cli_runner import invoke_cached_cli, semantic_cli_text

__all__ = [
    "components_role_fixture",
    "english_locale_fixture",
    "refusing_proxy_fixture",
    "staged_components_role_fixture",
]

pytestmark = [pytest.mark.integration, pytest.mark.external_tool, pytest.mark.hex_entrypoint]


@pytest.mark.usefixtures("components_role", "refusing_proxy")
def test_the_command_line_renders_the_real_roles_rows_and_refusal() -> None:
    status = invoke_cached_cli(["--format", "json", "config", "provision", "status"])
    setup = invoke_cached_cli(["config", "provision", "browser", "--yes"])
    declined = invoke_cached_cli(["config", "provision", "setup"])

    assert status.exit_code == 0, status.output
    items = json.loads(status.stdout)["result"]["items"]
    assert [(item["item_id"], item["state"], item["command"]) for item in items] == [
        ("browser", "absent", "aeat config provision browser"),
        ("local_ai", "absent", "aeat config provision pull"),
    ]
    assert setup.exit_code == 2, setup.output
    assert semantic_cli_text(setup.stdout).splitlines()[-1] == (
        "Browser for the tax agency website: Your network blocked the download."
    )
    assert declined.exit_code == 2, declined.output
    assert "Cadrumo will set up:" not in semantic_cli_text(declined.stderr)
