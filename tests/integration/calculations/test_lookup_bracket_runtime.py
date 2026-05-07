"""Runtime contract for the `lookup_bracket` op + `BracketEntry` schema.

The op evaluates a piecewise-linear bracket schedule (e.g. an IRPF escala
progresiva) against a runtime base amount. Each bracket entry encodes
(lower_bound, upper_bound, fixed_addition, marginal_rate, valid_from,
valid_to). The runtime selects the bracket whose date window covers the
``bracket_axis`` date in the date_context AND whose [lower_bound,
upper_bound] interval covers the base amount, then computes
``fixed_addition + marginal_rate * (base - lower_bound)``.

These tests exercise the runtime + schema invariants directly without
requiring a published BOE escala in registry/aeat/. Once the escala
parameters are authored (#66/#68/#70), the synthetic-profile chain tests
will exercise the same runtime through the calculate_registry_snapshot
entry point.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aeat.domain.calculations.registry import (
    BracketEntry,
    ParameterDefinition,
    RegistryValidationError,
)
from aeat.domain.calculations.registry._formula_runtime import _resolve_bracket

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _three_bracket_table() -> ParameterDefinition:
    """Synthetic 2025 IRPF-shape escala: 19% / 24% / 30% on first 12450 / 7750 / 15000."""
    return ParameterDefinition(
        id="test-escala-three-brackets",
        data_type="bracket_table",
        unit="EUR",
        bracket_axis="filing_period",
        brackets=(
            BracketEntry(
                lower_bound=Decimal("0"),
                upper_bound=Decimal("12450"),
                fixed_addition=Decimal("0"),
                marginal_rate=Decimal("0.19"),
                valid_from=date(2025, 1, 1),
                valid_to=date(2025, 12, 31),
            ),
            BracketEntry(
                lower_bound=Decimal("12450"),
                upper_bound=Decimal("20200"),
                fixed_addition=Decimal("2365.50"),  # 12450 * 0.19
                marginal_rate=Decimal("0.24"),
                valid_from=date(2025, 1, 1),
                valid_to=date(2025, 12, 31),
            ),
            BracketEntry(
                lower_bound=Decimal("20200"),
                upper_bound=None,
                fixed_addition=Decimal("4225.50"),  # 2365.50 + 7750 * 0.24
                marginal_rate=Decimal("0.30"),
                valid_from=date(2025, 1, 1),
                valid_to=date(2025, 12, 31),
            ),
        ),
        legal_refs=("ley-35-2006:art-63",),
        source_refs=("lirpf-cuota-chain-authority",),
    )


def test_lookup_bracket_returns_zero_at_lower_bound() -> None:
    table = _three_bracket_table()
    cuota = _resolve_bracket(table, Decimal("0"), {"filing_period": date(2025, 12, 31)})
    assert cuota == Decimal("0.00")


def test_lookup_bracket_first_bracket_applies_marginal_rate() -> None:
    table = _three_bracket_table()
    cuota = _resolve_bracket(table, Decimal("10000"), {"filing_period": date(2025, 12, 31)})
    # 0 + 0.19 * (10000 - 0) = 1900
    assert cuota == Decimal("1900.00")


def test_lookup_bracket_second_bracket_continues_from_fixed_addition() -> None:
    table = _three_bracket_table()
    cuota = _resolve_bracket(table, Decimal("15000"), {"filing_period": date(2025, 12, 31)})
    # 2365.50 + 0.24 * (15000 - 12450) = 2365.50 + 612 = 2977.50
    assert cuota == Decimal("2977.50")


def test_lookup_bracket_top_bracket_unbounded_upper() -> None:
    table = _three_bracket_table()
    cuota = _resolve_bracket(table, Decimal("100000"), {"filing_period": date(2025, 12, 31)})
    # 4225.50 + 0.30 * (100000 - 20200) = 4225.50 + 23940 = 28165.50
    assert cuota == Decimal("28165.50")


def test_lookup_bracket_rejects_negative_base() -> None:
    table = _three_bracket_table()
    with pytest.raises(RegistryValidationError, match="negative base"):
        _resolve_bracket(table, Decimal("-1"), {"filing_period": date(2025, 12, 31)})


def test_lookup_bracket_rejects_missing_date_axis() -> None:
    table = _three_bracket_table()
    with pytest.raises(RegistryValidationError, match="requires date axis"):
        _resolve_bracket(table, Decimal("10000"), {})


def test_lookup_bracket_rejects_date_outside_validity_window() -> None:
    table = _three_bracket_table()
    with pytest.raises(RegistryValidationError, match="no bracket valid"):
        _resolve_bracket(table, Decimal("10000"), {"filing_period": date(2024, 1, 1)})


def test_bracket_table_parameter_validates_no_overlap_within_same_window() -> None:
    """Two brackets with overlapping [lower, upper] in the same valid_from window must be rejected."""
    with pytest.raises(ValueError, match="overlap within the same window"):
        ParameterDefinition(
            id="test-overlapping-brackets",
            data_type="bracket_table",
            unit="EUR",
            bracket_axis="filing_period",
            brackets=(
                BracketEntry(
                    lower_bound=Decimal("0"),
                    upper_bound=Decimal("10000"),
                    fixed_addition=Decimal("0"),
                    marginal_rate=Decimal("0.19"),
                    valid_from=date(2025, 1, 1),
                ),
                BracketEntry(
                    lower_bound=Decimal("5000"),  # overlaps prior bracket
                    upper_bound=Decimal("15000"),
                    fixed_addition=Decimal("950"),
                    marginal_rate=Decimal("0.24"),
                    valid_from=date(2025, 1, 1),
                ),
            ),
            legal_refs=("ley-35-2006:art-63",),
            source_refs=("lirpf-cuota-chain-authority",),
        )


def test_bracket_table_parameter_rejects_brackets_without_axis() -> None:
    with pytest.raises(ValueError, match="requires a bracket_axis"):
        ParameterDefinition(
            id="test-no-axis",
            data_type="bracket_table",
            unit="EUR",
            brackets=(
                BracketEntry(
                    lower_bound=Decimal("0"),
                    upper_bound=Decimal("10000"),
                    fixed_addition=Decimal("0"),
                    marginal_rate=Decimal("0.19"),
                    valid_from=date(2025, 1, 1),
                ),
            ),
            legal_refs=("ley-35-2006:art-63",),
            source_refs=("lirpf-cuota-chain-authority",),
        )


def test_non_bracket_parameter_rejects_brackets() -> None:
    """A money/decimal parameter cannot carry brackets — they belong to bracket_table type only."""
    with pytest.raises(ValueError, match="data_type is 'money'"):
        ParameterDefinition(
            id="test-money-with-brackets",
            data_type="money",
            unit="EUR",
            brackets=(
                BracketEntry(
                    lower_bound=Decimal("0"),
                    upper_bound=Decimal("10000"),
                    fixed_addition=Decimal("0"),
                    marginal_rate=Decimal("0.19"),
                    valid_from=date(2025, 1, 1),
                ),
            ),
            legal_refs=("ley-35-2006:art-63",),
            source_refs=("lirpf-cuota-chain-authority",),
        )
