"""``config provision`` renders the rows and refusals of the real components role of a built Cadrumo binary.

``just test-components-role IMAGE`` runs these cases with the built binary
(:mod:`cadrumo.tests.components_role_package`), each with its own throwaway
storage root and a local proxy that refuses every tunnel.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cadrumo.tests.components_role_package import (
    CountingProxy,
    components_role_fixture,
    counting_proxy_fixture,
    refusing_proxy_fixture,
    staged_components_role_fixture,
)
from cadrumo.tests.english_locale_fixture import english_locale_fixture

from .cli_runner import invoke_cached_cli, semantic_cli_text

__all__ = [
    "components_role_fixture",
    "counting_proxy_fixture",
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
    assert [(item["item_id"], item["state"], item["recovery"], item["command"]) for item in items] == [
        ("browser", "absent", "set_up", "aeat config provision browser"),
        ("local_ai", "absent", "set_up_in_desktop", None),
    ]
    assert setup.exit_code == 2, setup.output
    assert semantic_cli_text(setup.stdout).splitlines()[-1] == (
        "Browser for the tax agency website: Your network blocked the download."
    )
    assert declined.exit_code == 2, declined.output
    assert "Cadrumo will set up:" not in semantic_cli_text(declined.stderr)


def test_the_command_line_gives_the_role_the_proxy_and_never_writes_its_address(
    components_role: Path, counting_proxy: CountingProxy
) -> None:
    setup = invoke_cached_cli(["config", "provision", "browser", "--yes"])
    relayed = invoke_cached_cli(["--format", "json", "config", "provision", "setup", "--yes"])

    assert setup.exit_code == 2, setup.output
    assert semantic_cli_text(setup.stdout).splitlines()[-1] == (
        "Browser for the tax agency website: Your network blocked the download."
    )
    assert relayed.exit_code == 2, relayed.output
    assert counting_proxy.tunnels
    assert set(counting_proxy.tunnels.values()) == {2}
    assert counting_proxy.unauthenticated == 0
    forms = counting_proxy.credential_forms()
    outputs = {"text": setup.stdout + setup.stderr, "json": relayed.stdout + relayed.stderr}
    assert [name for name, text in outputs.items() if any(form in text for form in forms)] == []
    written = [path for path in components_role.rglob("*") if path.is_file()]
    assert [path for path in written if any(form.encode() in path.read_bytes() for form in forms)] == []


@pytest.mark.usefixtures("components_role")
def test_the_command_line_removes_through_the_real_role() -> None:
    removed = invoke_cached_cli(["config", "provision", "remove", "browser", "--yes"])
    unconfirmed = invoke_cached_cli(["config", "provision", "remove", "browser"])
    local_ai = invoke_cached_cli(["config", "provision", "remove", "local_ai", "--yes"])

    assert removed.exit_code == 0, removed.output
    assert (
        semantic_cli_text(removed.stdout).splitlines()[-1]
        == "Browser for the tax agency website: deleted from this computer."
    )
    assert unconfirmed.exit_code == 2, unconfirmed.output
    assert local_ai.exit_code == 2, local_ai.output
    assert "choose one of: browser" in semantic_cli_text(local_ai.output)
