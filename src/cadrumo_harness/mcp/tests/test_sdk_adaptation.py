"""The descriptor-to-SDK-Tool adaptation builds correct MCP objects.

When the harness distribution's MCP runtime is installed, this proves the
mutability-to-annotation projection lands on the real ``ToolAnnotations`` hint
fields. Without the SDK, the same test asserts the lazy import fails at the
optional dependency boundary.
"""

from __future__ import annotations

import importlib.util

import pytest

from ..dispatch import tool_name_for_command
from ..server import build_sdk_tools
from ..tools import build_tool_descriptors

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

    categories_tool = by_name[tool_name_for_command("ledger.categories")]
    assert categories_tool.annotations is not None
    assert categories_tool.annotations.read_only_hint is True
    assert categories_tool.input_schema["type"] == "object"
    assert categories_tool.output_schema
    categories_branches = categories_tool.output_schema["oneOf"]
    assert isinstance(categories_branches, list) and len(categories_branches) == 2
    categories_success = categories_branches[0]
    assert isinstance(categories_success, dict)
    categories_properties = categories_success["properties"]
    assert isinstance(categories_properties, dict)
    assert set(categories_properties) == {
        "schema_version",
        "command",
        "active_profile",
        "status",
        "result",
        "notices",
    }
    assert categories_properties["command"]["const"] == "ledger.categories"

    calculate = by_name[tool_name_for_command("modelo.work.calculate")]
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

    remove = by_name[tool_name_for_command("ledger.remove")]
    assert remove.annotations is not None
    assert remove.annotations.read_only_hint is False
    assert remove.annotations.destructive_hint is True
