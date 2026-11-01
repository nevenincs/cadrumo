"""The relation_prefill validator holds a copy to one source and every period to a source window."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from ..bindings import validate_binding_selector_shape
from .binding_family_support import family_binding

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_QUARTERS = ["1T", "2T", "3T", "4T"]


def _provider(*, temporal: Mapping[str, object], casillas: tuple[str, ...] | None = None) -> dict[str, object]:
    provider: dict[str, object] = {
        "kind": "relation_prefill",
        "relation_kind": "cross_model_output",
        "dependency_role": "instalment_to_final_settlement",
        "source_modelo": "130",
        "temporal": temporal,
    }
    if casillas is None:
        provider["source_casilla_id"] = "19"
    else:
        provider["source_casilla_ids"] = casillas
    return provider


_SAME_YEAR = {"kind": "same_filing_year_periods", "source_periods": _QUARTERS}
_ONE_QUARTER = {"kind": "same_filing_year_periods", "source_periods": ["1T"]}


def test_a_summed_fold_over_a_year_of_sources_passes() -> None:
    binding = family_binding(
        _provider(temporal=_SAME_YEAR),
        aggregation={"op": "sum"},
        applicability={"kind": "target_periods", "periods": ["0A"]},
    )

    assert validate_binding_selector_shape(binding) == []


def test_a_copy_of_one_source_over_one_anchor_passes() -> None:
    binding = family_binding(
        _provider(temporal=_ONE_QUARTER),
        aggregation={"op": "copy"},
        applicability={"kind": "target_periods", "periods": ["2T"]},
    )

    assert validate_binding_selector_shape(binding) == []


def test_a_copy_with_two_source_casillas_is_refused() -> None:
    binding = family_binding(
        _provider(temporal=_ONE_QUARTER, casillas=("19", "20")),
        aggregation={"op": "copy"},
        binding_id="test.relation.copy-two-sources",
    )

    failures = validate_binding_selector_shape(binding)

    assert len(failures) == 1
    assert "test.relation.copy-two-sources" in failures[0]
    assert "exactly one source casilla" in failures[0]


def test_a_sum_over_two_source_casillas_passes() -> None:
    binding = family_binding(_provider(temporal=_ONE_QUARTER, casillas=("19", "20")), aggregation={"op": "sum"})

    assert validate_binding_selector_shape(binding) == []


def test_a_copy_over_four_source_periods_is_refused_for_a_target_period() -> None:
    binding = family_binding(
        _provider(temporal=_SAME_YEAR),
        aggregation={"op": "copy"},
        applicability={"kind": "target_periods", "periods": ["0A"]},
        binding_id="test.relation.copy-four-anchors",
    )

    failures = validate_binding_selector_shape(binding)

    assert len(failures) == 1
    assert "test.relation.copy-four-anchors" in failures[0]
    assert "exactly one source anchor for target period '0A', found 4" in failures[0]


def test_a_target_period_with_no_source_window_is_refused() -> None:
    temporal = {
        "kind": "filing_year_offset_by_target_period",
        "offsets": {"1P": -2},
        "source_periods": ["0A"],
    }
    binding = family_binding(
        _provider(temporal=temporal),
        aggregation={"op": "sum"},
        applicability={"kind": "target_periods", "periods": ["1P", "2P"]},
        binding_id="test.relation.empty-window",
    )

    failures = validate_binding_selector_shape(binding)

    assert len(failures) == 1
    assert "test.relation.empty-window" in failures[0]
    assert "no source window for target period '2P'" in failures[0]


def test_every_target_period_with_a_source_window_passes() -> None:
    temporal = {
        "kind": "filing_year_offset_by_target_period",
        "offsets": {"1P": -2, "2P": -1},
        "source_periods": ["0A"],
    }
    binding = family_binding(
        _provider(temporal=temporal),
        aggregation={"op": "sum"},
        applicability={"kind": "target_periods", "periods": ["1P", "2P"]},
    )

    assert validate_binding_selector_shape(binding) == []
