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

from ..errors import RegistryValidationError
from ..formula_runtime_ops import read_parameter

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_read_parameter_returns_a_decimal_for_a_registered_modelo_100_parameter() -> None:
    """The gastos-difícil-justificación rate for estimación directa simplificada is 5% (RIRPF art. 30).

    The TOML source declares value = "5" with unit = "percent" and data_type = "ratio",
    so the registry resolves it as Decimal("0.05"). A mis-declared or mis-parsed rate
    must break this test.
    """
    value = read_parameter(
        "100",
        "2025",
        "renta-2025-estimacion-directa-simplificada-gastos-dificil-justificacion-rate",
        date_context={"filing_period": date(2025, 12, 31)},
    )
    assert isinstance(value, Decimal)
    # The registry stores the raw percent figure (5); the `percent` formula op divides by 100.
    # TOML: value = "5", unit = "percent", legal: rd-439-2007:art-30 / orden-hac-277-2026:art-3.
    assert value == Decimal("5"), (
        f"Expected the 5% gastos-difícil-justificación rate stored as Decimal('5'), got {value!r}. "
        "Check rd-439-2007:art-30 / orden-hac-277-2026:art-3 and the TOML parameter declaration."
    )


def test_read_parameter_returns_2023_temporary_da56_rate() -> None:
    """The 2023 EDS difficult-justification rate is the DA 56 temporary 7%.

    Ley 35/2006 DA 56 elevated the RIRPF art. 30 percentage only for the 2023
    tax period. This guard prevents the current 5% rate from being flattened
    across all historical revisions.
    """
    value = read_parameter(
        "100",
        "2023",
        "renta-2023-estimacion-directa-simplificada-gastos-dificil-justificacion-rate",
        date_context={"filing_period": date(2023, 12, 31)},
    )
    assert isinstance(value, Decimal)
    assert value == Decimal("7"), (
        f"Expected the 2023 DA 56 gastos-difícil-justificación rate stored as Decimal('7'), got {value!r}."
    )


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
        )


def test_read_parameter_raises_for_unknown_revision() -> None:
    with pytest.raises(RegistryValidationError, match="no revision '1999'"):
        read_parameter(
            "100",
            "1999",
            "any-parameter-id",
            date_context={"filing_period": date(1999, 12, 31)},
        )


def test_read_parameter_raises_for_unknown_parameter_id() -> None:
    with pytest.raises(RegistryValidationError, match="parameter 'does-not-exist'"):
        read_parameter(
            "100",
            "2025",
            "does-not-exist",
            date_context={"filing_period": date(2025, 12, 31)},
        )
