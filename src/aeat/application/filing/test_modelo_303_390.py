"""Registry-boundary tests for Modelo 303 and Modelo 390 filing paths."""

from __future__ import annotations

from decimal import Decimal

import pytest

from . import FilingBuilderError, FilingValidator, FilingValue, FilingValueKind, build_draft
from .testing import SyntheticProfile, default_schema_provider, synthesize_filing_draft

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _profile() -> SyntheticProfile:
    return SyntheticProfile(
        tax_id="12345678Z",
        display_name="Registry boundary IVA test",
        applicable_modelos=("303", "390"),
    )


@pytest.mark.parametrize(
    ("modelo", "period", "inputs"),
    [
        ("303", "2025Q1", {"07": Decimal("10000.00"), "29": Decimal("200.00")}),
        ("390", "2025", {"01": 2025}),
    ],
)
def test_modelo_build_draft_requires_registry_snapshot(
    modelo: str,
    period: str,
    inputs: dict[str, object],
) -> None:
    with pytest.raises(FilingBuilderError, match="validated registry snapshot"):
        build_draft(
            modelo=modelo,
            period=period,
            profile=_profile(),
            inputs=inputs,
            schema_provider=default_schema_provider(),
        )


def test_303_formula_validator_still_detects_trace_divergence() -> None:
    draft = synthesize_filing_draft(
        modelo="303",
        period="2025Q1",
        casilla_values={"07": Decimal("10000.00"), "09": Decimal("9999.00")},
        profile_tax_id="12345678Z",
    )
    tampered = draft.model_copy(
        update={
            "values": tuple(
                FilingValue(
                    casilla_id=v.casilla_id,
                    value=v.value,
                    kind=FilingValueKind.LITERAL,
                    source="tampered",
                    formula_trace=None,
                )
                if v.casilla_id == "09"
                else v
                for v in draft.values
            )
        }
    )
    findings = FilingValidator(schema_provider=default_schema_provider()).validate(tampered)
    assert any(f.code == "formula-divergence" and f.casilla_id == "09" for f in findings)


def test_390_quarterly_reconciliation_validator_still_detects_mismatch() -> None:
    annual = synthesize_filing_draft(
        modelo="390",
        period="2025",
        casilla_values={"109": Decimal("42.00")},
        profile_tax_id="12345678Z",
    )
    quarterly = tuple(
        synthesize_filing_draft(
            modelo="303",
            period=f"2025Q{quarter}",
            casilla_values={"09": Decimal("100.00")},
            profile_tax_id="12345678Z",
        )
        for quarter in (1, 2, 3, 4)
    )
    findings = FilingValidator(
        schema_provider=default_schema_provider(),
        quarterly_303_drafts=quarterly,
    ).validate(annual)
    assert any(f.code == "filing-390-303-mismatch" and f.casilla_id == "109" for f in findings)
