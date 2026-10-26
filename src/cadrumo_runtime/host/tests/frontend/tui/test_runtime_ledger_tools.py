"""The runtime composer that gathers every domain's Ledger tools for the workbench."""

from __future__ import annotations

from typing import cast

import pytest

from cadrumo.application.ledger.workspace import LedgerWorkspaceArea
from cadrumo.entrypoints.tui.ledger.controller import LedgerWorkspaceController, LedgerWorkspaceScreen
from cadrumo.entrypoints.tui.ledger.tools import LedgerToolV1
from cadrumo_client.transport.frontend_client import FrontendClient

from ....frontend.tui.runtime_ledger_tools import compose_runtime_ledger_tools

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CLIENT = cast(FrontendClient, object())


def _never_opened(_controller: LedgerWorkspaceController) -> LedgerWorkspaceScreen:
    raise AssertionError("composing tools must not open them")


def _tool(name: str) -> LedgerToolV1:
    return LedgerToolV1(
        key=f"ledger.tool.test.{name}",
        label_key="tui.ledger.area.entries",
        area=LedgerWorkspaceArea.ENTRIES,
        build=_never_opened,
    )


def test_composers_run_in_order_with_the_workbench_client_and_label() -> None:
    seen: list[tuple[object, str]] = []

    def first(client: FrontendClient, label: str) -> tuple[LedgerToolV1, ...]:
        seen.append((client, label))
        return (_tool("a"), _tool("b"))

    def second(client: FrontendClient, label: str) -> tuple[LedgerToolV1, ...]:
        seen.append((client, label))
        return (_tool("c"),)

    tools = compose_runtime_ledger_tools(_CLIENT, profile_label="Synthetic", composers=(first, second))

    assert [tool.key for tool in tools] == ["ledger.tool.test.a", "ledger.tool.test.b", "ledger.tool.test.c"]
    assert seen == [(_CLIENT, "Synthetic"), (_CLIENT, "Synthetic")]


def test_two_domains_offering_one_key_are_refused() -> None:
    def first(_client: FrontendClient, _label: str) -> tuple[LedgerToolV1, ...]:
        return (_tool("same"),)

    with pytest.raises(ValueError, match="unique"):
        compose_runtime_ledger_tools(_CLIENT, profile_label="Synthetic", composers=(first, first))
