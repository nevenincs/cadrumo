"""Contract tests for non-withholding detail-record observations.

Validates pydantic field constraints and deterministic row-builder helpers for
the related-party (232), foreign-asset (720), atribución (184), IVA refund
(360), and donativos (182) detail-record observation surfaces.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast

import pytest
from pydantic import ValidationError

from .....core.foreign_asset_obligation import M720AssetClassCode
from ..detail_record_bindings import (
    AtributionMemberObservation,
    Modelo720RowObservation,
    RefundOperationObservation,
    RelatedPartyOperationObservation,
    _build_related_party_rows,
)
from ..donativo_bindings import DonativoDonorObservation, _build_donativo_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# ---------------------------------------------------------------------------
# RelatedPartyOperationObservation
# ---------------------------------------------------------------------------


def test_related_party_observation_country_code_must_be_uppercase_alphabetic() -> None:
    with pytest.raises(ValidationError, match="country_code must be uppercase alphabetic"):
        RelatedPartyOperationObservation(
            source_id="op1",
            counterparty_tax_id="A12345674",
            country_code="es",
            transaction_date=date(2025, 3, 15),
            operation_kind_code="01",
            amount=Decimal("100"),
        )


def test_related_party_observation_amount_must_be_decimal() -> None:
    with pytest.raises(ValidationError):
        RelatedPartyOperationObservation(
            source_id="op1",
            counterparty_tax_id="A12345674",
            country_code="ES",
            transaction_date=date(2025, 3, 15),
            operation_kind_code="01",
            amount=cast(Decimal, True),
        )


def test_related_party_observation_requires_a_stated_country() -> None:
    """An omitted country must refuse, not resolve to Spain.

    Modelo 232 declares operations with países calificados como paraísos
    fiscales alongside operaciones vinculadas, so a default on this field
    marks a tax-haven counterparty as domestic on the exact axis the
    declaration exists to surface. The positive control is
    ``test_related_party_observation_baseline_validates``: the same payload
    with a country stated must construct.
    """
    with pytest.raises(ValidationError, match="country_code"):
        RelatedPartyOperationObservation.model_validate(
            {
                "source_id": "op1",
                "counterparty_tax_id": "A12345674",
                "transaction_date": date(2025, 3, 15),
                "operation_kind_code": "01",
                "amount": Decimal("100"),
            },
        )


def test_related_party_observation_keeps_a_tax_haven_country() -> None:
    """The declared country survives construction unaltered."""
    obs = _related_party_observation(country_code="KY")

    assert obs.country_code == "KY"


def test_build_related_party_rows_groups_by_party_country_kind_method() -> None:
    es_q1 = Decimal("1000")
    es_q2 = Decimal("500")
    de_amount = Decimal("2000")
    obs = (
        RelatedPartyOperationObservation(
            source_id="op1",
            counterparty_tax_id="A12345674",
            country_code="ES",
            transaction_date=date(2025, 3, 15),
            operation_kind_code="01",
            transfer_pricing_method_code="1A",
            amount=es_q1,
        ),
        RelatedPartyOperationObservation(
            source_id="op2",
            counterparty_tax_id="A12345674",
            country_code="ES",
            transaction_date=date(2025, 6, 15),
            operation_kind_code="01",
            transfer_pricing_method_code="1A",
            amount=es_q2,
        ),
        RelatedPartyOperationObservation(
            source_id="op3",
            counterparty_tax_id="DE12345678",
            country_code="DE",
            transaction_date=date(2025, 4, 1),
            operation_kind_code="02",
            transfer_pricing_method_code="1E",
            amount=de_amount,
        ),
    )

    rows = _build_related_party_rows(obs)

    assert len(rows) == 2
    es_row = next(row for row in rows if row["country_code"] == "ES")
    de_row = next(row for row in rows if row["country_code"] == "DE")
    assert es_row["amount"] == es_q1 + es_q2
    assert de_row["amount"] == de_amount


# ---------------------------------------------------------------------------
# Modelo720RowObservation
# ---------------------------------------------------------------------------


def test_foreign_asset_observation_iso_codes_must_be_uppercase_alphabetic() -> None:
    with pytest.raises(ValidationError, match="ISO code must be uppercase alphabetic"):
        Modelo720RowObservation(
            source_id="a1",
            asset_class_code=M720AssetClassCode.CUENTA,
            country_code="ch",
            currency_code="CHF",
            acquisition_date=date(2024, 1, 1),
            valuation_amount=Decimal("60000"),
        )
    with pytest.raises(ValidationError, match="ISO code must be uppercase alphabetic"):
        Modelo720RowObservation(
            source_id="a1",
            asset_class_code=M720AssetClassCode.CUENTA,
            country_code="CH",
            currency_code="ch1",
            acquisition_date=date(2024, 1, 1),
            valuation_amount=Decimal("60000"),
        )


def test_foreign_asset_observation_valuation_must_be_non_negative() -> None:
    with pytest.raises(ValidationError, match="valuation must be non-negative"):
        Modelo720RowObservation(
            source_id="a1",
            asset_class_code=M720AssetClassCode.CUENTA,
            country_code="CH",
            acquisition_date=date(2024, 1, 1),
            valuation_amount=Decimal("-1"),
        )


# ---------------------------------------------------------------------------
# AtributionMemberObservation
# ---------------------------------------------------------------------------


def test_atribucion_member_share_percentage_must_be_in_range() -> None:
    with pytest.raises(ValidationError, match=r"share_percentage must be within \[0, 100\]"):
        AtributionMemberObservation(
            source_id="m1",
            member_tax_id="12345678A",
            transaction_date=date(2025, 1, 1),
            share_percentage=Decimal("150"),
            base_imponible_assigned=Decimal("0"),
            clave="D",
        )
    with pytest.raises(ValidationError, match=r"share_percentage must be within \[0, 100\]"):
        AtributionMemberObservation(
            source_id="m1",
            member_tax_id="12345678A",
            transaction_date=date(2025, 1, 1),
            share_percentage=Decimal("-1"),
            base_imponible_assigned=Decimal("0"),
            clave="D",
        )


def test_atribucion_member_country_code_must_be_uppercase_alphabetic() -> None:
    with pytest.raises(ValidationError, match="country_code must be uppercase alphabetic"):
        AtributionMemberObservation(
            source_id="m1",
            member_tax_id="12345678A",
            country_code="es",
            transaction_date=date(2025, 1, 1),
            share_percentage=Decimal("50"),
            base_imponible_assigned=Decimal("1000"),
            clave="D",
        )


# ---------------------------------------------------------------------------
# RefundOperationObservation
# ---------------------------------------------------------------------------


def test_refund_operation_member_state_must_be_uppercase_alphabetic() -> None:
    with pytest.raises(ValidationError, match="member_state_code must be uppercase alphabetic"):
        RefundOperationObservation(
            source_id="r1",
            member_state_code="fr",
            operation_kind_code="01",
            operation_date=date(2025, 3, 15),
            supplier_tax_id="FR12345678",
            refund_amount=Decimal("100"),
        )


def test_refund_operation_amount_must_be_non_negative() -> None:
    with pytest.raises(ValidationError, match="refund_amount must be non-negative"):
        RefundOperationObservation(
            source_id="r1",
            member_state_code="FR",
            operation_kind_code="01",
            operation_date=date(2025, 3, 15),
            supplier_tax_id="FR12345678",
            refund_amount=Decimal("-1"),
        )


# ---------------------------------------------------------------------------
# DonativoDonorObservation (modelo 182)
# ---------------------------------------------------------------------------


def test_donativo_donor_amount_must_be_non_negative() -> None:
    with pytest.raises(ValidationError, match="amount_donated must be non-negative"):
        DonativoDonorObservation(
            source_id="d1",
            donor_tax_id="12345678A",
            transaction_date=date(2025, 3, 15),
            amount_donated=Decimal("-1"),
            deduction_percentage=Decimal("80"),
        )


def test_donativo_donor_deduction_percentage_must_be_in_range() -> None:
    with pytest.raises(ValidationError, match=r"deduction_percentage must be within \[0, 100\]"):
        DonativoDonorObservation(
            source_id="d1",
            donor_tax_id="12345678A",
            transaction_date=date(2025, 3, 15),
            amount_donated=Decimal("100"),
            deduction_percentage=Decimal("150"),
        )
    with pytest.raises(ValidationError, match=r"deduction_percentage must be within \[0, 100\]"):
        DonativoDonorObservation(
            source_id="d1",
            donor_tax_id="12345678A",
            transaction_date=date(2025, 3, 15),
            amount_donated=Decimal("100"),
            deduction_percentage=Decimal("-1"),
        )


def test_donativo_donor_country_code_must_be_uppercase_alphabetic() -> None:
    with pytest.raises(ValidationError, match="country_code must be uppercase alphabetic"):
        DonativoDonorObservation(
            source_id="d1",
            donor_tax_id="12345678A",
            country_code="es",
            transaction_date=date(2025, 3, 15),
            amount_donated=Decimal("100"),
            deduction_percentage=Decimal("80"),
        )


def test_donativo_donor_refuses_type_1_declarant_nature() -> None:
    """MUTATION: a protected-estate filer header cannot become donor-row data.

    Modelo 182 type-1 nature ``3`` identifies a protected-estate holder or an
    administrator. It belongs to the still-unshipped declarant/type-2 lifecycle,
    not to a ``DonativoDonorObservation``. Accepting it here would create a
    second, incomplete legal-filer declaration beside the canonical header
    authority and make an eventual export silently narrow the filer population.
    """
    with pytest.raises(ValidationError, match="declarant_nature"):
        DonativoDonorObservation.model_validate(
            {
                "source_id": "d1",
                "donor_tax_id": "12345678A",
                "transaction_date": date(2025, 3, 15),
                "amount_donated": Decimal("100"),
                "deduction_percentage": Decimal("80"),
                "declarant_nature": "3",
            },
        )


def test_build_donativo_rows_sums_per_donor_and_preserves_recurrencia() -> None:
    """A donor who gave twice in the year folds into one row; recurrencia sticks."""
    q1_amount = Decimal("100")
    q3_amount = Decimal("250")
    other_donor_amount = Decimal("500")
    obs = (
        DonativoDonorObservation(
            source_id="d1a",
            donor_tax_id="12345678A",
            donor_legal_name="Donor One",
            transaction_date=date(2025, 2, 1),
            amount_donated=q1_amount,
            deduction_percentage=Decimal("80"),
            is_recurrent=False,
        ),
        DonativoDonorObservation(
            source_id="d1b",
            donor_tax_id="12345678A",
            donor_legal_name="Donor One",
            transaction_date=date(2025, 9, 1),
            amount_donated=q3_amount,
            deduction_percentage=Decimal("80"),
            is_recurrent=True,
        ),
        DonativoDonorObservation(
            source_id="d2",
            donor_tax_id="87654321Z",
            donor_legal_name="Donor Two",
            transaction_date=date(2025, 5, 1),
            amount_donated=other_donor_amount,
            deduction_percentage=Decimal("35"),
            is_recurrent=False,
        ),
    )

    rows = _build_donativo_rows(obs)

    assert len(rows) == 2
    by_nif = {row["donor_tax_id"]: row for row in rows}
    assert by_nif["12345678A"]["amount_donated"] == q1_amount + q3_amount
    assert by_nif["12345678A"]["is_recurrent"] == "1"
    assert by_nif["87654321Z"]["amount_donated"] == other_donor_amount
    assert by_nif["87654321Z"]["is_recurrent"] == "0"


def _related_party_observation(**overrides: object) -> RelatedPartyOperationObservation:
    """Build a valid related-party observation, overriding one field per case.

    Every untouched field is a value the model accepts, so a refusal can only
    have come from the override.
    """
    return RelatedPartyOperationObservation.model_validate(
        {
            "source_id": "detalle:per_related_party_operation:row-0",
            "counterparty_tax_id": "A12345678",
            "counterparty_legal_name": "Entidad Vinculada SL",
            "country_code": "ES",
            "transaction_date": date(2026, 3, 1),
            "operation_kind_code": "01",
            "transfer_pricing_method_code": "1A",
            "amount": Decimal("50000"),
            **overrides,
        },
    )


def test_related_party_observation_baseline_validates() -> None:
    """Anti-tautology guard: the untouched fixture must VALIDATE.

    Without it a typo in an untested field would refuse every case below and
    the catalogue enforcement would be proven by nothing.
    """
    obs = _related_party_observation()
    assert obs.operation_kind_code == "01"
    assert obs.transfer_pricing_method_code == "1A"


def test_related_party_observation_refuses_off_catalogue_codes() -> None:
    """Binding-resolved codes are held to the same DR23200 tables as the CLI row.

    This is the engine-side half of the M232 coded-field contract. The values
    reach it as free-form registry text, so without the catalogue an operation
    kind or valuation method AEAT never published would resolve into a casilla.
    """
    for _case_id, overrides in (
        # DR23200 Tabla C stops at clave 11.
        ("operation-kind-above-catalogue", {"operation_kind_code": "99"}),
        ("operation-kind-unpadded", {"operation_kind_code": "1"}),
        # Tabla B codes are 1A-1E; the OECD abbreviations for the same
        # art. 18.4 methods are not AEAT's codes and do not fit the field.
        ("method-oecd-abbreviation", {"transfer_pricing_method_code": "CUP"}),
        ("method-off-catalogue", {"transfer_pricing_method_code": "ZZ"}),
    ):
        with pytest.raises(ValidationError):
            _related_party_observation(**overrides)


def test_related_party_observation_hydrates_operator_casing() -> None:
    """A lowercase token resolves to the code DR23200 spells in uppercase."""
    assert _related_party_observation(transfer_pricing_method_code="1e").transfer_pricing_method_code == "1E"
