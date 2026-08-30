"""Strict annual Modelo 210 grouped-renta row contract tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core import M210PayerMode
from ..row_models import (
    Modelo210AgrupacionRentaRow,
    Modelo210AgrupacionRentaRowsError,
    validate_m210_agrupacion_renta_rows,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _lease_row(
    source_id: str,
    *,
    importe: str = "100.00",
    tipo_renta_code: str = "01",
    tipo_gravamen: str = "0.24",
    pagador_mode: M210PayerMode = M210PayerMode.SINGLE_PAYER,
    pagador_id: str | None = "ES-PAGADOR-1",
    bien_derecho_id: str = "ES-INMUEBLE-1",
) -> Modelo210AgrupacionRentaRow:
    return Modelo210AgrupacionRentaRow(
        source_id=source_id,
        tipo_renta_code=tipo_renta_code,
        importe=Decimal(importe),
        tipo_gravamen=Decimal(tipo_gravamen),
        pagador_mode=pagador_mode,
        pagador_id=pagador_id,
        deriva_de_bien_derecho=True,
        bien_derecho_id=bien_derecho_id,
    )


def test_annual_group_accepts_compatible_single_payer_lease_rows() -> None:
    """Two rents with the same official code/rate/payer/property form one 0A group."""
    rows = (
        _lease_row("manual-renta-jan", importe="450.00"),
        _lease_row("manual-renta-feb", importe="550.00"),
    )

    validate_m210_agrupacion_renta_rows(rows)


def test_annual_group_accepts_explicit_code_35_multiple_payer_exception() -> None:
    """Code 35 keeps its multiple-payer meaning without a missing-payer sentinel."""
    rows = (
        _lease_row(
            "manual-renta-jan",
            tipo_renta_code="35",
            pagador_mode=M210PayerMode.MULTIPLE_PAYERS_CODE_35,
            pagador_id=None,
        ),
        _lease_row(
            "manual-renta-feb",
            tipo_renta_code="35",
            pagador_mode=M210PayerMode.MULTIPLE_PAYERS_CODE_35,
            pagador_id=None,
        ),
    )

    validate_m210_agrupacion_renta_rows(rows)


@pytest.mark.parametrize(
    ("rows", "reason"),
    [
        (
            (
                _lease_row("manual-renta-jan"),
                _lease_row(
                    "manual-renta-feb",
                    tipo_renta_code="35",
                    pagador_mode=M210PayerMode.MULTIPLE_PAYERS_CODE_35,
                    pagador_id=None,
                ),
            ),
            "mixed_tipo_renta_code",
        ),
        (
            (
                _lease_row("manual-renta-jan"),
                _lease_row("manual-renta-feb", tipo_gravamen="0.19"),
            ),
            "mixed_tipo_gravamen",
        ),
        (
            (
                _lease_row("manual-renta-jan"),
                _lease_row("manual-renta-feb", bien_derecho_id="ES-INMUEBLE-2"),
            ),
            "mixed_bien_derecho",
        ),
        (
            (
                _lease_row("manual-renta-jan"),
                _lease_row("manual-renta-feb", pagador_id="ES-PAGADOR-2"),
            ),
            "mixed_pagador",
        ),
    ],
)
def test_annual_group_refuses_each_incompatible_statutory_key(
    rows: tuple[Modelo210AgrupacionRentaRow, ...],
    reason: str,
) -> None:
    """The group check fails on the real Article 2 compatibility key that drifts."""
    with pytest.raises(Modelo210AgrupacionRentaRowsError) as exc_info:
        validate_m210_agrupacion_renta_rows(rows)

    assert exc_info.value.reason == reason


def test_row_contract_refuses_negative_offset_and_code_35_without_explicit_mode() -> None:
    """Offsets and an implicit multi-payer exception cannot enter a persisted row."""
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        _lease_row("manual-renta-negative", importe="-0.01")

    with pytest.raises(ValidationError, match="requires the explicit multiple-payers code-35 mode"):
        _lease_row("manual-renta-code-35", tipo_renta_code="35")

    with pytest.raises(ValidationError, match="less than or equal to 1"):
        _lease_row("manual-renta-percent-scale", tipo_gravamen="24")


def test_annual_group_refuses_non_lease_code_and_duplicate_source_identity() -> None:
    """0A is lease/sublease-only and each persisted component has stable identity."""
    with pytest.raises(Modelo210AgrupacionRentaRowsError) as code_exc:
        validate_m210_agrupacion_renta_rows((_lease_row("manual-renta-jan", tipo_renta_code="03"),))
    assert code_exc.value.reason == "annual_code_not_lease_or_sublease"

    with pytest.raises(Modelo210AgrupacionRentaRowsError) as identity_exc:
        validate_m210_agrupacion_renta_rows(
            (
                _lease_row("manual-renta-duplicate"),
                _lease_row("manual-renta-duplicate"),
            )
        )
    assert identity_exc.value.reason == "duplicate_source_id"
