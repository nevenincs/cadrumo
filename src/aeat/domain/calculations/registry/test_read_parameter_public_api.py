"""Public-API contract for the registry's `read_parameter` delegate.

Non-formula consumers (rental tier resolver, IVA category resolver, etc.)
look up parameter values via this surface instead of going through the
formula runtime. The function delegates to the same `_resolve_parameter`
helper the runtime uses, so its semantics match for any date axis the
parameter declares.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aeat.core.paths import PROJECT_ROOT

from . import RegistryValidationError, read_parameter

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = PROJECT_ROOT / "registry" / "aeat"


def test_read_parameter_returns_a_decimal_for_a_registered_modelo_100_parameter() -> None:
    """The Modelo 100 estimación-directa-simplificada gastos-difícil-justificación rate parameter resolves cleanly."""
    value = read_parameter(
        "100",
        "2025",
        "renta-2025-estimacion-directa-simplificada-gastos-dificil-justificacion-rate",
        date_context={"filing_period": date(2025, 12, 31)},
        registry_root=_REGISTRY_ROOT,
    )
    assert isinstance(value, Decimal)
    assert value > Decimal("0")


def test_read_parameter_uses_default_registry_root_when_none_provided() -> None:
    """When `registry_root` is None, the function falls back to <PROJECT_ROOT>/registry/aeat."""
    value = read_parameter(
        "100",
        "2025",
        "renta-2025-estimacion-directa-simplificada-gastos-dificil-justificacion-rate",
        date_context={"filing_period": date(2025, 12, 31)},
    )
    assert isinstance(value, Decimal)


def test_read_parameter_raises_for_unknown_modelo() -> None:
    with pytest.raises(RegistryValidationError, match="modelo '999' not registered"):
        read_parameter(
            "999",
            "2025",
            "any-parameter-id",
            date_context={"filing_period": date(2025, 12, 31)},
            registry_root=_REGISTRY_ROOT,
        )


def test_read_parameter_raises_for_unknown_revision() -> None:
    with pytest.raises(RegistryValidationError, match="no revision '1999'"):
        read_parameter(
            "100",
            "1999",
            "any-parameter-id",
            date_context={"filing_period": date(1999, 12, 31)},
            registry_root=_REGISTRY_ROOT,
        )


def test_read_parameter_raises_for_unknown_parameter_id() -> None:
    with pytest.raises(RegistryValidationError, match="parameter 'does-not-exist'"):
        read_parameter(
            "100",
            "2025",
            "does-not-exist",
            date_context={"filing_period": date(2025, 12, 31)},
            registry_root=_REGISTRY_ROOT,
        )
