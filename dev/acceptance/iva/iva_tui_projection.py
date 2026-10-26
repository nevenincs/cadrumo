"""Strict installed IVA receipt projection and sanitized refusal readback."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import cast

from dev.acceptance.income_tax.installed_tui_child import (
    reportable_child_failure_reason,
)

from .iva_tui_contracts import IvaInstalledTuiError


def _canonical_ledger_decimal_text(value: str) -> str:
    """Render independent expected fixed-point text for the public Ledger view."""
    return format(Decimal(value).normalize(), "f")


def _object(value: object, *, label: str) -> dict[str, object]:
    """Require one public JSON object without retaining the whole command output."""
    if not isinstance(value, dict):
        raise IvaInstalledTuiError(f"{label} returned no object")
    return cast(dict[str, object], value)


def _reported_reason(receipt: Path, *, returncode: int) -> str:
    """The child's recorded cause and exit status, for the driver's refusal."""
    reason = reportable_child_failure_reason(receipt)
    return f" (exit {returncode}): {reason}" if reason is not None else f" (exit {returncode})"


def _required_text(document: Mapping[str, object], key: str) -> str:
    """Read a nonempty value-free identity string from a validated child receipt."""
    value = document.get(key)
    if not isinstance(value, str) or not value:
        raise IvaInstalledTuiError("installed TUI receipt is missing a required identity value")
    return value
