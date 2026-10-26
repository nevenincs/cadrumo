"""Independence gates for the activity-asset acceptance oracles."""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

import pytest

from dev.acceptance.assets import oracles
from dev.acceptance.assets.oracles import (
    first_year_constant_percentage_oracle,
    first_year_machinery_constant_percentage,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_machinery_constant_percentage_pins_the_installed_journey_amounts() -> None:
    # 12% x 2.5 = 30%: the export, CLI-first and corrected TUI bases.
    assert first_year_machinery_constant_percentage(Decimal("1000.00")) == Decimal("300.00")
    assert first_year_machinery_constant_percentage(Decimal("2000.00")) == Decimal("600.00")
    assert first_year_machinery_constant_percentage(Decimal("1800.00")) == Decimal("540.00")


def test_the_oracle_rounds_half_up_to_cents() -> None:
    assert first_year_constant_percentage_oracle(
        allocated_basis=Decimal("0.05"),
        linear_coefficient=Decimal("0.1"),
        weighting=Decimal("1.0"),
    ) == Decimal("0.01")


def test_the_oracles_import_nothing_from_the_product() -> None:
    tree = ast.parse(Path(oracles.__file__).read_text(encoding="utf-8"))
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names} | {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }

    assert not any(name.split(".")[0] == "cadrumo" for name in imported)
