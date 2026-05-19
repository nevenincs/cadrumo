"""Tests for registry-backed filing draft test helpers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

import pytest
from pydantic import ValidationError

from ...domain.filing._schema import ModeloDraft, ModeloDraftStatus, ModeloValueKind
from ._testing_registry import build_registry_filing_draft, build_registry_filing_draft_from_decimals

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _valid_inputs(*, ingresos: Decimal = Decimal("10000")) -> dict[str, Decimal]:
    return {
        "01": ingresos,
        "02": Decimal("4000"),
        "05": Decimal("250"),
        "06": Decimal("100"),
        "08": Decimal("2000"),
        "10": Decimal("10"),
        "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
        "15": Decimal("0"),
        "16": Decimal("0"),
        "18": Decimal("0"),
    }


def test_builds_frozen_draft_through_registry_runtime() -> None:
    draft = build_registry_filing_draft(
        modelo="130",
        period="2026Q1",
        casilla_values=_valid_inputs(),
    )

    assert isinstance(draft, ModeloDraft)
    assert draft.schema_version.startswith("registry:130:")
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        setattr(draft, "status", ModeloDraftStatus.DRAFT)  # noqa: B010 — exercise frozen-model __setattr__


def test_approved_status_uses_application_approval_path() -> None:
    draft = build_registry_filing_draft(
        modelo="130",
        period="1T",
        casilla_values=_valid_inputs(),
    )

    assert draft.status is ModeloDraftStatus.APPROVED
    assert draft.approved_at is not None
    assert draft.approved_by == "registry"
    assert draft.approval_basis is not None
    assert draft.review_checksum is not None


def test_non_approved_status_clears_approval_fields() -> None:
    draft = build_registry_filing_draft(
        modelo="130",
        period="1T",
        casilla_values=_valid_inputs(),
        status=ModeloDraftStatus.DRAFT,
    )

    assert draft.status is ModeloDraftStatus.DRAFT
    assert draft.approved_at is None
    assert draft.approved_by is None
    assert draft.approval_basis is None
    assert draft.review_checksum is None


def test_unsupported_modelo_fails_at_registry_boundary() -> None:
    with pytest.raises(Exception, match="not present in the calculation registry"):
        build_registry_filing_draft(
            modelo="999",
            period="0A",
            casilla_values={"0511": Decimal("5550.00")},
        )


def test_values_are_registry_projected_and_sorted() -> None:
    draft = build_registry_filing_draft(
        modelo="130",
        period="1T",
        casilla_values=_valid_inputs(ingresos=Decimal("12000")),
        status=ModeloDraftStatus.DRAFT,
    )

    values = {value.casilla_id: value for value in draft.values}
    assert tuple(values) == tuple(sorted(values))
    assert values["01"].kind is ModeloValueKind.LITERAL
    assert values["19"].kind is ModeloValueKind.COMPUTED
    assert values["19"].formula_trace == ("17", "18")


def test_draft_id_is_deterministic_for_same_registry_inputs() -> None:
    a = build_registry_filing_draft(
        modelo="130",
        period="1T",
        casilla_values=_valid_inputs(),
    )
    b = build_registry_filing_draft(
        modelo="130",
        period="1T",
        casilla_values=_valid_inputs(),
    )

    assert a.draft_id == b.draft_id


def test_decimal_string_inputs_are_coerced_before_registry_build() -> None:
    draft = build_registry_filing_draft_from_decimals(
        modelo="130",
        period="1T",
        casilla_decimals={key: str(value) for key, value in _valid_inputs().items()},
        status=ModeloDraftStatus.DRAFT,
    )

    values = {value.casilla_id: value for value in draft.values}
    assert values["01"].value == Decimal("10000")


def test_decimal_passthrough() -> None:
    draft = build_registry_filing_draft_from_decimals(
        modelo="130",
        period="1T",
        casilla_decimals=_valid_inputs(ingresos=Decimal("100.50")),
        status=ModeloDraftStatus.DRAFT,
    )

    values = {value.casilla_id: value for value in draft.values}
    assert values["01"].value == Decimal("100.50")


def test_invalid_decimal_string_raises() -> None:
    bad_inputs = {key: str(value) for key, value in _valid_inputs().items()}
    bad_inputs["01"] = "not-a-decimal"

    with pytest.raises(InvalidOperation, match=r"ConversionSyntax|InvalidOperation|conversion"):
        build_registry_filing_draft_from_decimals(
            modelo="130",
            period="1T",
            casilla_decimals=bad_inputs,
        )


def test_spanish_thousands_rejected_at_boundary() -> None:
    bad_inputs = {key: str(value) for key, value in _valid_inputs().items()}
    bad_inputs["01"] = "5.550,00"

    with pytest.raises(InvalidOperation, match=r"ConversionSyntax|InvalidOperation|conversion"):
        build_registry_filing_draft_from_decimals(
            modelo="130",
            period="1T",
            casilla_decimals=bad_inputs,
        )
