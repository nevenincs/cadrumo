"""Negotiated MCP capability posture is pinned.

Builds the real server via :func:`build_server` and asserts the EXACT capability
set the server negotiates through ``create_initialization_options()``: tools,
prompts, and resources are advertised (their handlers are registered);
logging is asserted-ABSENT (no handler is registered); and every
``listChanged`` / ``subscribe`` sub-flag is pinned to its current value so a
future capability shift cannot land silently.

When the ``cadrumo[agent]`` SDK extra is absent the SDK-dependent build is
asserted to refuse at the optional-dependency boundary — the same
graceful-degradation contract the sibling handshake tests follow, never a skip.
"""

from __future__ import annotations

import importlib.util
from typing import Any, cast

import pytest

from .._server import build_server, server_initialization_options
from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SDK_PRESENT = importlib.util.find_spec("mcp") is not None


def test_negotiated_capability_set_is_pinned() -> None:
    descriptors = build_tool_descriptors()
    if not _SDK_PRESENT:
        with pytest.raises(ModuleNotFoundError, match="mcp"):
            build_server(descriptors)
        return

    server = cast("Any", build_server(descriptors))
    capabilities = server_initialization_options(server).capabilities

    # Advertised: the three handler families the server registers.
    assert capabilities.tools is not None
    assert capabilities.prompts is not None
    assert capabilities.resources is not None

    # completions IS declared: the server registers a completion handler for
    # the guided-workflow prompt arguments. logging stays absent; pinning None
    # makes its arrival a caught change.
    assert capabilities.completions is not None
    assert capabilities.logging is None

    # tools.listChanged IS declared: the console emits tools/list_changed on a
    # toolset activation. The remaining list-changed / subscribe sub-flags stay
    # off and are pinned so a future capability shift cannot land silently.
    assert capabilities.tools.list_changed is True
    assert capabilities.prompts.list_changed is False
    assert capabilities.resources.list_changed is False
    assert capabilities.resources.subscribe is False

    # No experimental capabilities are declared.
    assert capabilities.experimental == {}
