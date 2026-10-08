"""Strict public result and scalar observation helpers for installed withholding campaigns."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any, cast

from dev.acceptance.installed_cli import InstalledCli

from .cli_contracts import RetencionesInstalledCliError
from .scenario import (
    money,
)


def _require_result(cli: InstalledCli, args: Sequence[str], *, stage: str) -> dict[str, Any]:
    """Run one fresh installed command without leaking raw diagnostics."""
    try:
        document = cli.run(args, allow_error=True)
    except Exception as exc:
        raise RetencionesInstalledCliError(
            stage=stage,
            diagnostic_code=f"installed_cli_{type(exc).__name__}",
        ) from exc
    if document.get("status") == "error":
        error = document.get("error")
        error_document: Mapping[str, object] = cast(Mapping[str, object], error) if isinstance(error, Mapping) else {}
        code: object | None = error_document.get("code")
        raise RetencionesInstalledCliError(
            stage=stage,
            diagnostic_code=str(code) if isinstance(code, str) and code else "installed_cli_error",
        )
    result = document.get("result")
    if not isinstance(result, dict):
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="installed_cli_result_missing")
    return cast(dict[str, Any], result)


def _required_text(result: Mapping[str, Any], *, key: str, stage: str) -> str:
    """Read a stable CLI result identity without retaining the result object."""
    value = result.get(key)
    if not isinstance(value, str) or not value:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code=f"missing_{key}")
    return value


def _required_nonnegative_int(result: Mapping[str, Any], *, key: str, stage: str) -> int:
    """Read an aggregate readback count from a public result envelope."""
    value: object = result.get(key)
    if isinstance(value, bool):
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code=f"invalid_{key}")
    if not isinstance(value, (str, int, float, Decimal)):
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code=f"invalid_{key}")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code=f"invalid_{key}") from exc
    if number < 0:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code=f"invalid_{key}")
    return number


def _as_decimal(value: object) -> Decimal:
    """Read numeric public/parser values without accepting booleans."""
    if isinstance(value, bool) or value is None:
        raise ValueError("expected a decimal value")
    return Decimal(str(value))


def _money_text(value: Decimal) -> str:
    """Render an independently authored money fact for a public request."""
    return f"{money(value):.2f}"


def _money_or_integer_text(value: Decimal) -> str:
    """Keep count casillas compact and monetary values to their cent precision."""
    if value == value.to_integral_value():
        return str(value.quantize(Decimal("1")))
    return _money_text(value)


def _percentage_text(rate: Decimal) -> str:
    """Render the invoice's supplied IVA rate in the CLI's percent unit."""
    percentage = rate * Decimal("100")
    return str(percentage.quantize(Decimal("1")))
