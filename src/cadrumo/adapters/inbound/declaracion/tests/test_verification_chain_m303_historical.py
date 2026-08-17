from __future__ import annotations

import pytest

from ._verification_chain_support import (
    _assert_m303_printed_resultado_regimen_general_arithmetic,
    _parse_extracted_declaracion_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


@pytest.mark.parametrize(
    "pdf_stem,year,period",
    [
        ("2021-2T", 2021, "2T"),
        ("2021-3T", 2021, "3T"),
        ("2021-4T", 2021, "4T"),
        ("2022-1T", 2022, "1T"),
        ("2022-2T", 2022, "2T"),
        ("2022-3T", 2022, "3T"),
        ("2022-4T", 2022, "4T"),
    ],
)
def test_verification_chain_m303_historical_printed_resultado_regimen_general_arithmetic(
    pdf_stem: str,
    year: int,
    period: str,
) -> None:
    """The historical declaración's printed arithmetic holds: box 46 == box 27 - box 45.

    GROUNDED authority: Orden EHA/3786/2008 art. 1 - box 46 = box 27 - box 45.
    The 2009-2022 revision covers ejercicios 2009-2022 and uses the same
    formula. Its printed-box extraction profile targets 4 casillas: 27, 29, 45,
    and iva.resultado-regimen-general.

    As with the 2023-onwards specimens this checks the DOCUMENT, not the engine.
    Note the reason is subtler for this revision: boxes 27/29/45 carry no
    formulas here, so they are genuine input casillas and the engine would
    accept them. But resultado-regimen-general is still computed from
    ``iva.cuota-devengada-total`` and ``iva.cuota-deducible-total``, which sum
    the per-rate primitives the printed form does not carry — so feeding the
    printed boxes still leaves the resultado at zero. The engine cannot verify
    this chain from the page in either revision.
    """
    extracted = _parse_extracted_declaracion_values(modelo="303", fixture_stem=pdf_stem, year=year, period=period)

    _assert_m303_printed_resultado_regimen_general_arithmetic(
        pdf_stem=pdf_stem,
        extracted=extracted,
    )
