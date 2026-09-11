"""Typed-value contracts for authored governed mapping facts."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.facts.schema import MappingFactEntry
from dev.registry.compiler.fact_loader import load_governed_fact_file

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_authored_mapping_decimal_entries_materialise_without_float_coercion(tmp_path: Path) -> None:
    """A TOML mapping schedule keeps its monetary values as exact Decimals."""
    path = tmp_path / "0001-test-declaration-limit.toml"
    path.write_text(
        """
[fact]
fact_id = "test-declaration-limit"
family = "mapping"

[[fact.variants]]
variant_id = "test-declaration-limit:2025-01-01"
date_axis = "filing_period"
valid_from = 2025-01-01
legal_refs = ["test-law"]
source_refs = ["test-source"]
review_status = "agent_reviewed"
ownership = "authored"
[[fact.variants.source_citations]]
source_ref = "test-source"
required_text = ["15.876 euros"]
[fact.variants.payload]
kind = "mapping"
entries = [{ key = 2025, value_type = "decimal", value = "15876.00" }]
""".lstrip(),
        encoding="utf-8",
    )

    fact = load_governed_fact_file(path)

    assert fact.variants[0].payload.entries[0].value == Decimal("15876.00")


def test_mapping_decimal_annotation_refuses_non_string_values() -> None:
    """The author must make decimal intent explicit rather than relying on TOML float parsing."""
    with pytest.raises(ValidationError, match="decimal mapping value_type requires a decimal string"):
        MappingFactEntry.model_validate({"key": 2025, "value_type": "decimal", "value": 15876})


def test_generated_mapping_decimal_entries_remain_typed_without_an_authoring_annotation() -> None:
    """Generated providers retain their existing in-memory Decimal payload contract."""
    entry = MappingFactEntry.model_validate({"key": 2025, "value": Decimal("15876")})

    assert entry.value == Decimal("15876")
