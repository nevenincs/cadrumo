"""Contract tests for the six detail-record observation types.

Validates pydantic field constraints, validator semantics, and the
deterministic row-builder helpers for the observation surfaces feeding
the per-record tipo-2 row-producer bindings on the IRPF retencion
modelos (190 / 193 perceptors), the IS related-party operations modelo
(232), the foreign-asset informative modelo (720), the régimen de
atribución de rentas modelo (184), the IVA refund operations modelo
(360), and the donativos/donaciones/aportaciones informativa modelo
(182).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast

import pytest
from pydantic import ValidationError

from .....core.aggregation import RetencionClave
from .._bindings import (
    AtributionMemberObservation,
    DonativoDonorObservation,
    Modelo720RowObservation,
    RefundOperationObservation,
    RelatedPartyOperationObservation,
)
from .._detail_record_bindings import _build_related_party_rows
from .._donativo_bindings import _build_donativo_rows
from .._withholding_bindings import (
    WithholdingObservation,
    _build_withholding_rows,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


# ---------------------------------------------------------------------------
# WithholdingObservation
# ---------------------------------------------------------------------------


def test_withholding_observation_country_code_must_be_uppercase_alphabetic() -> None:
    with pytest.raises(ValidationError, match="country_code must be uppercase alphabetic"):
        WithholdingObservation(
            source_id="p1",
            perceptor_tax_id="12345678A",
            country_code="es",
            transaction_date=date(2025, 3, 15),
            clave=RetencionClave.A,
        )
    with pytest.raises(ValidationError, match="country_code must be uppercase alphabetic"):
        WithholdingObservation(
            source_id="p1",
            perceptor_tax_id="12345678A",
            country_code="E1",
            transaction_date=date(2025, 3, 15),
            clave=RetencionClave.A,
        )


def test_withholding_observation_clave_must_be_a_valid_retencion_clave() -> None:
    """A lowercase / out-of-set clave is refused: ``clave`` is the typed
    :class:`RetencionClave` (Modelo 190/193 A-L), so ``"a"`` (lowercase) is not a
    member.
    """
    with pytest.raises(ValidationError, match="not a valid RetencionClave"):
        WithholdingObservation.model_validate(
            {
                "source_id": "p1",
                "perceptor_tax_id": "12345678A",
                "transaction_date": date(2025, 3, 15),
                "clave": "a",
            }
        )


def test_withholding_observation_amounts_reject_negative() -> None:
    with pytest.raises(ValidationError, match="amounts must be non-negative"):
        WithholdingObservation(
            source_id="p1",
            perceptor_tax_id="12345678A",
            transaction_date=date(2025, 3, 15),
            clave=RetencionClave.A,
            retencion_practicada=Decimal("-1"),
        )


def test_withholding_observation_amounts_must_be_decimal_not_bool() -> None:
    with pytest.raises(ValidationError):
        WithholdingObservation(
            source_id="p1",
            perceptor_tax_id="12345678A",
            transaction_date=date(2025, 3, 15),
            clave=RetencionClave.A,
            retencion_practicada=cast(Decimal, True),
        )


def test_build_withholding_rows_per_perceptor_sums_amounts() -> None:
    a_dinerario_q1 = Decimal("10000")
    a_dinerario_q2 = Decimal("5000")
    a_retencion_q1 = Decimal("1500")
    a_retencion_q2 = Decimal("750")
    z_dinerario = Decimal("30000")
    obs = (
        WithholdingObservation(
            source_id="p1a",
            perceptor_tax_id="12345678A",
            perceptor_legal_name="P One",
            transaction_date=date(2025, 3, 15),
            clave=RetencionClave.A,
            percibido_dinerario=a_dinerario_q1,
            retencion_practicada=a_retencion_q1,
        ),
        WithholdingObservation(
            source_id="p1b",
            perceptor_tax_id="12345678A",
            perceptor_legal_name="P One",
            transaction_date=date(2025, 6, 15),
            clave=RetencionClave.A,
            percibido_dinerario=a_dinerario_q2,
            retencion_practicada=a_retencion_q2,
        ),
        WithholdingObservation(
            source_id="p2",
            perceptor_tax_id="87654321Z",
            perceptor_legal_name="P Two",
            transaction_date=date(2025, 4, 1),
            clave=RetencionClave.G,
            percibido_dinerario=z_dinerario,
            retencion_practicada=Decimal("5500"),
        ),
    )

    rows = _build_withholding_rows("per_perceptor", obs)

    assert len(rows) == 2
    by_nif = {row["perceptor_tax_id"]: row for row in rows}
    assert by_nif["12345678A"]["percibido_dinerario"] == a_dinerario_q1 + a_dinerario_q2
    assert by_nif["12345678A"]["retencion_practicada"] == a_retencion_q1 + a_retencion_q2
    assert by_nif["87654321Z"]["percibido_dinerario"] == z_dinerario


def test_build_withholding_rows_per_perceptor_clave_distinguishes_clave_tuples() -> None:
    obs = (
        WithholdingObservation(
            source_id="p1a",
            perceptor_tax_id="12345678A",
            transaction_date=date(2025, 3, 15),
            clave=RetencionClave.A,
            percibido_dinerario=Decimal("100"),
        ),
        WithholdingObservation(
            source_id="p1b",
            perceptor_tax_id="12345678A",
            transaction_date=date(2025, 4, 15),
            clave=RetencionClave.G,
            percibido_dinerario=Decimal("200"),
        ),
    )

    rows = _build_withholding_rows("per_perceptor_clave", obs)

    assert len(rows) == 2
    keys = {(row["perceptor_tax_id"], row["clave"]) for row in rows}
    assert keys == {("12345678A", "A"), ("12345678A", "G")}


# ---------------------------------------------------------------------------
# RelatedPartyOperationObservation
# ---------------------------------------------------------------------------


def test_related_party_observation_country_code_must_be_uppercase_alphabetic() -> None:
    with pytest.raises(ValidationError, match="country_code must be uppercase alphabetic"):
        RelatedPartyOperationObservation(
            source_id="op1",
            counterparty_tax_id="A12345678",
            country_code="es",
            transaction_date=date(2025, 3, 15),
            operation_kind_code="01",
            amount=Decimal("100"),
        )


def test_related_party_observation_amount_must_be_decimal() -> None:
    with pytest.raises(ValidationError):
        RelatedPartyOperationObservation(
            source_id="op1",
            counterparty_tax_id="A12345678",
            transaction_date=date(2025, 3, 15),
            operation_kind_code="01",
            amount=cast(Decimal, True),
        )


def test_build_related_party_rows_groups_by_party_country_kind_method() -> None:
    es_q1 = Decimal("1000")
    es_q2 = Decimal("500")
    de_amount = Decimal("2000")
    obs = (
        RelatedPartyOperationObservation(
            source_id="op1",
            counterparty_tax_id="A12345678",
            country_code="ES",
            transaction_date=date(2025, 3, 15),
            operation_kind_code="01",
            transfer_pricing_method_code="CUP",
            amount=es_q1,
        ),
        RelatedPartyOperationObservation(
            source_id="op2",
            counterparty_tax_id="A12345678",
            country_code="ES",
            transaction_date=date(2025, 6, 15),
            operation_kind_code="01",
            transfer_pricing_method_code="CUP",
            amount=es_q2,
        ),
        RelatedPartyOperationObservation(
            source_id="op3",
            counterparty_tax_id="DE12345678",
            country_code="DE",
            transaction_date=date(2025, 4, 1),
            operation_kind_code="02",
            transfer_pricing_method_code="TNMM",
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
            asset_class_code="C",
            country_code="ch",
            currency_code="CHF",
            acquisition_date=date(2024, 1, 1),
            valuation_amount=Decimal("60000"),
        )
    with pytest.raises(ValidationError, match="ISO code must be uppercase alphabetic"):
        Modelo720RowObservation(
            source_id="a1",
            asset_class_code="C",
            country_code="CH",
            currency_code="ch1",
            acquisition_date=date(2024, 1, 1),
            valuation_amount=Decimal("60000"),
        )


def test_foreign_asset_observation_valuation_must_be_non_negative() -> None:
    with pytest.raises(ValidationError, match="valuation must be non-negative"):
        Modelo720RowObservation(
            source_id="a1",
            asset_class_code="C",
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
        )
    with pytest.raises(ValidationError, match=r"share_percentage must be within \[0, 100\]"):
        AtributionMemberObservation(
            source_id="m1",
            member_tax_id="12345678A",
            transaction_date=date(2025, 1, 1),
            share_percentage=Decimal("-1"),
            base_imponible_assigned=Decimal("0"),
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
