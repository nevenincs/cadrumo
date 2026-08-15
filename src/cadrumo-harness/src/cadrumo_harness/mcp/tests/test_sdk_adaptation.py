"""The descriptor-to-SDK-Tool adaptation builds correct MCP objects.

When the MCP SDK (the ``cadrumo[agent]`` extra) is installed, this proves the
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

    inspect_tool = by_name["cadrumo_registry_inspect"]
    assert inspect_tool.annotations is not None
    assert inspect_tool.annotations.read_only_hint is True
    assert inspect_tool.input_schema["type"] == "object"
    assert inspect_tool.output_schema
    inspect_branches = inspect_tool.output_schema["oneOf"]
    assert isinstance(inspect_branches, list) and len(inspect_branches) == 2
    inspect_success = inspect_branches[0]
    assert isinstance(inspect_success, dict)
    inspect_properties = inspect_success["properties"]
    assert isinstance(inspect_properties, dict)
    assert set(inspect_properties) == {
        "schema_version",
        "command",
        "active_profile",
        "status",
        "result",
        "notices",
    }
    assert inspect_properties["command"]["const"] == "registry.inspect"

    calculate = by_name["cadrumo_modelo_work_calculate"]
    assert calculate.output_schema
    calculate_branches = calculate.output_schema["oneOf"]
    assert isinstance(calculate_branches, list) and len(calculate_branches) == 2
    calculate_success = calculate_branches[0]
    assert isinstance(calculate_success, dict)
    calculate_properties = calculate_success["properties"]
    assert isinstance(calculate_properties, dict)
    assert calculate_properties["command"]["const"] == "modelo.work.calculate"
    calculate_result = calculate_properties["result"]
    assert isinstance(calculate_result, dict)
    result_branches = calculate_result["oneOf"]
    assert isinstance(result_branches, list) and len(result_branches) == 2
    # Thinning declares the property bodies ONCE on the result and puts only the
    # inline-versus-linked discriminator in the branches, so the shared shape is
    # read here rather than from a branch.
    shared_properties = calculate_result["properties"]
    assert isinstance(shared_properties, dict)
    assert "calculation_revision_id" in shared_properties
    assert shared_properties["observations"] == {"type": "array", "maxItems": 0}
    inline_result = result_branches[0]
    assert isinstance(inline_result, dict)
    # ``False`` as a property schema forbids the key: the inline shape bars the
    # resource markers, the linked shape bars the array.
    assert inline_result["properties"]["observations_resource"] is False
    assert result_branches[1]["properties"]["observations"] is False

    remove = by_name["cadrumo_ledger_remove"]
    assert remove.annotations is not None
    assert remove.annotations.read_only_hint is False
    assert remove.annotations.destructive_hint is True
