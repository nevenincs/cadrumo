"""A ``bracket_kind`` fixes the sign contract of a bracket table's marginal rates.

``progressive`` keeps the escala rule (non-negative rates). ``phase_out`` carries a
printed amount that shrinks as the base grows: rates are non-positive and each
row stays non-negative at both bounds. The expected values are the printed
tramos of a work-income reduction schedule, computed by hand from the manual's
lines and independent of the table's own arithmetic.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ..authority_component_codec import json_value
from ..formula_runtime_ops import resolve_bracket
from ..schema_formula import BracketEntry, BracketKind, DatedValue, ParameterDefinition
from .authored_editions import filing_year_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FROM = date(filing_year_envelope().floor, 1, 1)
_CONTEXT = {"devengo_date": _FROM}
_LEGAL_REF = "ley-35-2006:art-20"
_SOURCE_REF = "aeat-renta-2024-manual-parte1"


def _row(lower: str, upper: str | None, fixed: str, rate: str) -> BracketEntry:
    return BracketEntry(
        lower_bound=Decimal(lower),
        upper_bound=None if upper is None else Decimal(upper),
        fixed_addition=Decimal(fixed),
        marginal_rate=Decimal(rate),
        valid_from=_FROM,
    )


def _table(rows: tuple[BracketEntry, ...], bracket_kind: BracketKind | None = None) -> ParameterDefinition:
    return ParameterDefinition.model_validate(_document(rows, bracket_kind))


def _document(rows: tuple[BracketEntry, ...], bracket_kind: object) -> dict[str, object]:
    document: dict[str, object] = {
        "id": "test-bracket-kind",
        "data_type": "bracket_table",
        "unit": "eur",
        "brackets": rows,
        "bracket_axis": "devengo_date",
        "legal_refs": (_LEGAL_REF,),
        "source_refs": (_SOURCE_REF,),
    }
    if bracket_kind is not None:
        document["bracket_kind"] = bracket_kind
    return document


_ART_20_SHAPED = (
    _row("0", "14852", "7302", "0"),
    _row("14852", "17673.52", "7302", "-1.75"),
    _row("17673.52", "19747.5", "2364.34", "-1.14"),
    _row("19747.5", None, "0", "0"),
)


@pytest.mark.parametrize(
    ("base", "expected"),
    [
        ("0", "7302"),
        ("13640", "7302"),
        ("14852", "7302"),
        ("16000", "5293"),
        ("17673.52", "2364.34"),
        ("19747.5", "0.0028"),
        ("25000", "0"),
    ],
)
def test_phase_out_table_returns_the_printed_amount(base: str, expected: str) -> None:
    table = _table(_ART_20_SHAPED, bracket_kind=BracketKind.PHASE_OUT)

    assert resolve_bracket(table, Decimal(base), _CONTEXT) == Decimal(expected)


def test_bracket_kind_defaults_to_progressive() -> None:
    assert _table((_row("0", None, "0", "0.19"),)).bracket_kind is BracketKind.PROGRESSIVE


def test_progressive_table_still_resolves_cumulative_cuota() -> None:
    table = _table((_row("0", "12450", "0", "0.19"), _row("12450", None, "2365.5", "0.24")))

    assert resolve_bracket(table, Decimal("20000"), _CONTEXT) == Decimal("4177.5")


def test_progressive_table_refuses_a_negative_rate() -> None:
    with pytest.raises(ValidationError, match="non-negative"):
        _table((_row("0", "100", "50", "-0.1"),))


def test_phase_out_refuses_a_positive_rate() -> None:
    with pytest.raises(ValidationError, match="non-positive"):
        _table((_row("0", "100", "50", "0.1"),), bracket_kind=BracketKind.PHASE_OUT)


def test_phase_out_refuses_a_row_negative_at_its_upper_bound() -> None:
    with pytest.raises(ValidationError, match="negative at its upper bound"):
        _table((_row("0", "100", "50", "-1"),), bracket_kind=BracketKind.PHASE_OUT)


def test_phase_out_refuses_a_negative_fixed_addition() -> None:
    with pytest.raises(ValidationError, match="fixed_addition must be non-negative"):
        _table((_row("0", "100", "-1", "0"),), bracket_kind=BracketKind.PHASE_OUT)


def test_phase_out_refuses_a_sloped_open_last_row() -> None:
    with pytest.raises(ValidationError, match="open bracket"):
        _table((_row("0", None, "50", "-0.1"),), bracket_kind=BracketKind.PHASE_OUT)


def test_unknown_bracket_kind_is_refused() -> None:
    with pytest.raises(ValidationError):
        ParameterDefinition.model_validate(_document((_row("0", None, "0", "0"),), "regressive"))


def test_bracket_kind_is_refused_on_a_scalar_parameter() -> None:
    with pytest.raises(ValidationError, match="not a bracket_table"):
        ParameterDefinition.model_validate(
            {
                "id": "test-scalar",
                "data_type": "decimal",
                "unit": "eur",
                "values": (DatedValue(value=Decimal("1"), valid_from=_FROM, date_axis="devengo_date"),),
                "bracket_kind": "phase_out",
                "legal_refs": (_LEGAL_REF,),
                "source_refs": (_SOURCE_REF,),
            }
        )


def test_default_bracket_kind_is_omitted_from_the_published_authority_projection() -> None:
    progressive = json_value(_table((_row("0", None, "0", "0.19"),)))
    phase_out = json_value(_table((_row("0", None, "0", "0"),), bracket_kind=BracketKind.PHASE_OUT))

    assert isinstance(progressive, dict)
    assert isinstance(phase_out, dict)
    assert "bracket_kind" not in progressive
    assert phase_out["bracket_kind"] == "phase_out"
