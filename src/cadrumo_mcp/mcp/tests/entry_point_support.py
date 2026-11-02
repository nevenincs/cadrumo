"""Run the installed MCP entry point on given arguments without serving."""

from __future__ import annotations

import sys

import pytest

from cadrumo.core import logging as cadrumo_logging

from .. import main as mcp_main
from .. import server as mcp_server


def run_entry_point(monkeypatch: pytest.MonkeyPatch, arguments: list[str]) -> list[dict[str, object]]:
    """Run the installed entry point on these arguments and return what it asked to be served."""
    served: list[dict[str, object]] = []
    monkeypatch.setenv("PYDANTIC_DISABLE_PLUGINS", "__all__")
    monkeypatch.delenv("CADRUMO_MCP_REQUIRED_VERSION", raising=False)
    monkeypatch.setattr(sys, "argv", ["cadrumo-mcp", *arguments])
    monkeypatch.setattr(cadrumo_logging, "configure_logging", lambda: None)
    monkeypatch.setattr(mcp_server, "serve", lambda **options: served.append(options))
    mcp_main.main()
    return served
