"""The descriptor-to-SDK-Tool adaptation builds correct MCP objects.

When the MCP SDK (the ``aeat-cli[agent]`` extra) is installed, this proves the
mutability-to-annotation projection lands on the real ``ToolAnnotations`` hint
fields. Without the SDK, the same test asserts the lazy import fails at the
optional dependency boundary.
"""

from __future__ import annotations

import importlib.util

import pytest

from .._server import build_sdk_tools
from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_descriptors_adapt_to_sdk_tools_with_annotations() -> None:
    descriptors = build_tool_descriptors()
    if importlib.util.find_spec("mcp") is None:
        with pytest.raises(ModuleNotFoundError, match="mcp"):
            build_sdk_tools(descriptors)
        return

    tools = build_sdk_tools(descriptors)
    assert len(tools) == len(descriptors)
    by_name = {tool.name: tool for tool in tools}

    contract = by_name["aeat_contract"]
    assert contract.annotations is not None
    assert contract.annotations.readOnlyHint is True
    assert contract.inputSchema["type"] == "object"
    assert contract.outputSchema

    remove = by_name["aeat_ledger_remove"]
    assert remove.annotations is not None
    assert remove.annotations.readOnlyHint is False
    assert remove.annotations.destructiveHint is True
