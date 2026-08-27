"""Parity gate: the describe envelope carries the whole canonical report.

``aeat app modelo describe`` is the operator's revision-justification surface,
so its ``--json`` payload must carry the same regulatory grounding the domain
:class:`ModeloDescribeReport` holds --
notably the ``legal_refs`` / ``source_refs`` provenance, the revision validity
bounds, and the per-input-kind casilla counts. The payload previously
re-declared a reduced subset field-by-field and silently dropped nine of them.

These tests pin the report -> payload field-superset contract and the value
fidelity of :meth:`ModeloDescribeResult.from_report` on real populated models
(no mocks), plus the bounds the canonical report now refuses, so a field added
to the report cannot stop at the CLI boundary unnoticed.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from ....core import Period
from ....domain.calculations.registry.query_reports import ModeloDescribeReport
from .._modelo_aux_payloads import ModeloDescribeResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LEGAL_REF = "ley-35-2006:art-27"
_SOURCE_REF = "aeat-manual-renta-2024"


def _report(**overrides: Any) -> ModeloDescribeReport:
    """Build a fully populated describe report, no field left at a default."""
    fields: dict[str, Any] = {
        "code": "100",
        "title": "Renta",
        "official_name": "Impuesto sobre la Renta de las Personas Fisicas",
        "tax_domain": "renta",
        "cadence": "anual",
        "jurisdiction": "ES",
        "revision": "2025-y-siguientes",
        "revision_ids": ("2024-y-siguientes", "2025-y-siguientes"),
        "filing_year": 2025,
        "filing_period": Period(filing_year=2025, code="0A"),
        "period": "0A",
        "valid_from": date(2025, 1, 1),
        "valid_to": date(2025, 12, 31),
        "periods": ("0A",),
        "casilla_count": 12,
        "manual_casilla_count": 5,
        "bound_casilla_count": 4,
        "computed_casilla_count": 3,
        "binding_count": 2,
        "formula_count": 1,
        "legal_refs": (_LEGAL_REF,),
        "source_refs": (_SOURCE_REF,),
    }
    fields.update(overrides)
    return ModeloDescribeReport(**fields)  # type: ignore[arg-type]


def test_payload_mirrors_every_canonical_report_field() -> None:
    """No field of the canonical describe report may stop at the CLI boundary."""
    dropped = set(ModeloDescribeReport.model_fields) - set(ModeloDescribeResult.model_fields)
    assert dropped == set()


def test_from_report_preserves_every_field_value() -> None:
    """Projection is value-preserving, not merely field-name compatible."""
    report = _report()
    result = ModeloDescribeResult.from_report(report)

    for name in ModeloDescribeReport.model_fields:
        projected = getattr(result, name)
        original = getattr(report, name)
        expected = list(original) if isinstance(original, tuple) else original
        assert projected == expected, name


def test_from_report_carries_legal_and_source_grounding() -> None:
    """Provenance reaches the operator envelope rather than being dropped."""
    result = ModeloDescribeResult.from_report(_report())

    assert result.legal_refs == [_LEGAL_REF]
    assert result.source_refs == [_SOURCE_REF]
    assert result.jurisdiction == "ES"
    assert result.valid_from == date(2025, 1, 1)
    assert result.valid_to == date(2025, 12, 31)
    assert result.filing_period == Period(filing_year=2025, code="0A")


def test_emitted_json_carries_the_grounding_fields() -> None:
    """The serialized envelope body, not just the model, holds the provenance.

    ``OutputSchema`` is ``strict=True`` and emit-only, so this asserts the JSON
    document an operator receives rather than a re-validation round trip.
    """
    emitted = ModeloDescribeResult.from_report(_report()).model_dump(mode="json")

    assert emitted["legal_refs"] == [_LEGAL_REF]
    assert emitted["source_refs"] == [_SOURCE_REF]
    assert emitted["jurisdiction"] == "ES"
    assert emitted["valid_from"] == "2025-01-01"
    assert emitted["valid_to"] == "2025-12-31"
    assert emitted["filing_period"] == {"filing_year": 2025, "code": "0A"}
    assert emitted["manual_casilla_count"] == 5
    assert emitted["bound_casilla_count"] == 4
    assert emitted["computed_casilla_count"] == 3


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("filing_year", -1),
        ("filing_year", 2201),
        ("casilla_count", -2),
        ("manual_casilla_count", -1),
        ("bound_casilla_count", -1),
        ("computed_casilla_count", -1),
        ("binding_count", -1),
        ("formula_count", -1),
    ],
)
def test_canonical_report_refuses_out_of_range_values(field: str, value: int) -> None:
    """A negative count or an out-of-range filing year is refused at the report."""
    with pytest.raises(ValidationError):
        _report(**{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("filing_year", -1),
        ("filing_year", 2201),
        ("casilla_count", -2),
        ("binding_count", -1),
    ],
)
def test_cli_payload_refuses_out_of_range_values(field: str, value: int) -> None:
    """The same bounds hold at the operator envelope, not only in the domain."""
    report = _report()
    fields = {
        name: (list(raw_value) if isinstance(raw_value := getattr(report, name), tuple) else raw_value)
        for name in ModeloDescribeReport.model_fields
    }
    fields[field] = value

    with pytest.raises(ValidationError):
        ModeloDescribeResult.model_validate(fields)


def test_boundary_filing_years_remain_valid() -> None:
    """The bound refuses out-of-range values only, not the legitimate edges."""
    assert _report(filing_year=1980).filing_year == 1980
    assert _report(filing_year=2200).filing_year == 2200
    assert _report(filing_year=None).filing_year is None
