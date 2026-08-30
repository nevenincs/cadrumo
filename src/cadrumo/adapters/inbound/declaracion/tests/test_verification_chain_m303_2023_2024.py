"""Modelo 303 2023-2024 verification-chain document-arithmetic tests.

These assert properties of the parsed declaración itself, not of the engine.
The extraction profile targets only printed boxes, and the engine derives boxes
27 and 45 by summing per-rate cuota primitives the form does not print, so the
parse path cannot drive the engine's devengada chain. That coverage lives on the
calculate path; what remains verifiable here is whether the document's own
printed totals agree with each other.
"""

from __future__ import annotations

import pytest

from .....core.casilla_id import validated_casilla_id
from ._verification_chain_support import (
    _M303_2023_ONWARDS_PARAMS,
    _M303_RESULTADO_REGIMEN_GENERAL_CASILLA,
    CasillaId,
    _assert_m303_printed_resultado_regimen_general_arithmetic,
    _extracted_m303_decimal,
    _parse_extracted_declaracion_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


_M303_SUMA_RESULTADOS_CASILLA: CasillaId = validated_casilla_id("64")
_M303_ATRIBUIBLE_ESTADO_CASILLA: CasillaId = validated_casilla_id("66")
_M303_RESULTADO_AUTOLIQUIDACION_CASILLA: CasillaId = validated_casilla_id("iva.resultado")
_M303_RESULTADO_FINAL_CASILLA: CasillaId = validated_casilla_id("71")
_M303_SYNTHETIC_CLOSURE_CASES: tuple[tuple[CasillaId, str, CasillaId, str, str], ...] = (
    (
        _M303_SUMA_RESULTADOS_CASILLA,
        "box 64 (suma de resultados)",
        _M303_RESULTADO_REGIMEN_GENERAL_CASILLA,
        "box 46 (resultado regimen general)",
        "Orden HAC/819/2024 art. 1 §4: box 64 = box 46 + box 58 + box 76; c58=0 and c76=0",
    ),
    (
        _M303_ATRIBUIBLE_ESTADO_CASILLA,
        "box 66 (atribuible Estado)",
        _M303_SUMA_RESULTADOS_CASILLA,
        "box 64 (suma de resultados)",
        "Orden HAC/819/2024 art. 1 §4: box 66 = box 64 x box 65 / 100; box 65=100",
    ),
    (
        _M303_RESULTADO_AUTOLIQUIDACION_CASILLA,
        "box 69 (resultado autoliquidacion)",
        _M303_ATRIBUIBLE_ESTADO_CASILLA,
        "box 66 (atribuible Estado)",
        "Orden HAC/819/2024 art. 1 §5: box 69 = box 66 + box 77 + box 68 - box 78; c77=c68=c78=0",
    ),
    (
        _M303_RESULTADO_FINAL_CASILLA,
        "box 71 (resultado final)",
        _M303_RESULTADO_AUTOLIQUIDACION_CASILLA,
        "box 69 (resultado autoliquidacion)",
        "Orden HAC/819/2024 art. 1 §6: box 71 = box 69 - box 70 + box 109; c70=0 and c109=0",
    ),
)


@pytest.mark.parametrize(
    "pdf_stem,year,period",
    _M303_2023_ONWARDS_PARAMS,
)
def test_verification_chain_m303_printed_resultado_regimen_general_arithmetic(
    pdf_stem: str,
    year: int,
    period: str,
) -> None:
    """The parsed declaración's own printed arithmetic holds: box 46 == box 27 - box 45.

    GROUNDED authority: Orden EHA/3786/2008 art. 1 — box 46 = box 27 − box 45.
      box 27 = Total cuota devengada (LIVA art. 88)
      box 45 = Total a deducir (LIVA arts. 92-94)
      box 46 = Resultado régimen general

    This asserts a property of the DOCUMENT across three independently printed
    amounts, so a render whose own totals disagree fails here.

    It does not run the engine, and that is the deliberate consequence of the
    profile targeting only printed boxes: the per-rate cuota primitives the
    engine sums into boxes 27 and 45 are not printed on the form, and the
    printed totals cannot be substituted for them because the engine refuses
    computed casillas as inputs. Engine coverage of those summation formulas is
    exercised on the calculate path instead.
    """
    extracted = _parse_extracted_declaracion_values(
        modelo="303",
        fixture_stem=pdf_stem,
        year=year,
        period=period,
    )

    _assert_m303_printed_resultado_regimen_general_arithmetic(
        pdf_stem=pdf_stem,
        extracted=extracted,
    )


@pytest.mark.parametrize("pdf_stem,year,period", _M303_2023_ONWARDS_PARAMS)
def test_verification_chain_m303_printed_closure_box_arithmetic(
    pdf_stem: str,
    year: int,
    period: str,
) -> None:
    """The printed closure chain is internally consistent down boxes 64, 66, 69, 71.

    GROUNDED authority: Orden HAC/819/2024 art. 1 closure formulas for boxes
    64, 66, 69, and 71.

    SCOPE LIMIT, stated because it is not universal: these corpus PDFs set every
    non-base term in those formulas to zero (c58, c76, c77, c68, c78, c70, c109),
    and box 65 to 100, so each target box collapses to its immediate base box.
    That collapse is a property of THIS corpus shape, not of the AEAT form — a
    real render carrying a non-zero régimen simplificado result or a
    compensación would legitimately break the equality. The relation asserted
    here is therefore a check that the corpus renders a self-consistent chain,
    not a general claim about M303. The general closure formulas are the
    engine's, and they are exercised on the calculate path.
    """
    extracted = _parse_extracted_declaracion_values(
        modelo="303",
        fixture_stem=pdf_stem,
        year=year,
        period=period,
    )

    for target_casilla, target_label, base_casilla, base_label, formula_context in _M303_SYNTHETIC_CLOSURE_CASES:
        target_value = _extracted_m303_decimal(
            pdf_stem=pdf_stem,
            extracted=extracted,
            casilla_id=target_casilla,
            label=target_label,
        )
        base_value = _extracted_m303_decimal(
            pdf_stem=pdf_stem,
            extracted=extracted,
            casilla_id=base_casilla,
            label=base_label,
        )
        assert target_value == base_value, (
            f"DOCUMENT-INCONSISTENT [{pdf_stem}]: printed {target_label} {target_value!r} != "
            f"printed {base_label} {base_value!r}\n"
            f"  ({formula_context} in corpus PDFs)"
        )
