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
from .published_authority import published_legal_reference

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
        "renta-estimacion-directa-simplificada-gastos-dificil-justificacion-rate",
        date_context={"filing_period": date(2025, 12, 31)},
    )
    assert isinstance(value, Decimal)
    # The registry stores the raw percent figure (5); the `percent` formula op divides by 100.
    # TOML: value = "5", unit = "percent", legal: rd-439-2007:art-30 / orden-hac-277-2026:art-3.
    assert value == Decimal("5"), (
        f"Expected the 5% gastos-difícil-justificación rate stored as Decimal('5'), got {value!r}. "
        "Check rd-439-2007:art-30 / orden-hac-277-2026:art-3 and the TOML parameter declaration."
    )


# Ley 35/2006 DA 56 raised the simplified-direct-estimation rate for the one tax
# period its in-force window covers; the published provision names that exercise.
_DA56_TEMPORARY_RATE_EXERCISE = published_legal_reference("ley-35-2006:da-56").effective_from.year


def test_read_parameter_returns_the_da56_temporary_rate() -> None:
    """The DA 56 exercise's EDS difficult-justification rate is the temporary 7%.

    Ley 35/2006 DA 56 elevated the RIRPF art. 30 percentage only for the 2023
    tax period. This guard prevents the current 5% rate from being flattened
    across all historical revisions.
    """
    value = read_parameter(
        "100",
        str(_DA56_TEMPORARY_RATE_EXERCISE),
        "renta-estimacion-directa-simplificada-gastos-dificil-justificacion-rate",
        date_context={"filing_period": date(_DA56_TEMPORARY_RATE_EXERCISE, 12, 31)},
    )
    assert isinstance(value, Decimal)
    assert value == Decimal("7"), (
        f"Expected the {_DA56_TEMPORARY_RATE_EXERCISE} DA 56 gastos-difícil-justificación rate stored as "
        f"Decimal('7'), got {value!r}."
    )


def test_read_parameter_reads_the_bundled_authority() -> None:
    """A public parameter read resolves an actual bundled, law-selected value."""
    value = read_parameter(
        "100",
        "2025",
        "renta-estimacion-directa-simplificada-gastos-dificil-justificacion-rate",
        date_context={"filing_period": date(2025, 12, 31)},
    )
    assert isinstance(value, Decimal)


def test_read_parameter_raises_for_unknown_modelo() -> None:
    with pytest.raises(RegistryValidationError, match="modelo '999' is not registered"):
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
