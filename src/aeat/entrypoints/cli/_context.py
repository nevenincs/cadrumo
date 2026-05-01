"""CLI-local shim around root-private Click-context helpers."""

from __future__ import annotations

from ...core.click_context import current_cli_flag, json_output_requested

__all__ = ["current_cli_flag", "json_output_requested"]
