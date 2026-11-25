"""Pension, reserve and ledger-coverage refusals carry catalogue words in every supported locale.

Each refusal is raised by the real domain code and rendered through the error
renderer. The ledger-coverage refusal is checked beside its validator tests.
"""

from __future__ import annotations

import ast
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.errors.error_codes import resolve_error_message
from ....core.i18n.render import tr
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ..dt12_reduccion import compute_dt12_reduccion_plan_pensiones, dt12_regime_window_eligibility
from ..errors import PensionReduccionError
from ..modelo_fact_context import ModeloFactResolutionContext
from ..sal_reserva_especial import compute_sal_reserva_especial_dotacion

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LOCALES = ("en", "es", "ca", "hu")
_DOMAIN_DIR = Path(__file__).resolve().parents[1]
_WORDED_MODULES = ("dt12_reduccion.py", "sal_reserva_especial.py")
_PLACEHOLDER = re.compile(r"%\{(\w+)\}")
_YEAR = filing_year_envelope().horizon


def _context(operation: PinnedAuthorityOperation) -> ModeloFactResolutionContext:
    coordinate = date(_YEAR, 12, 31)
    return ModeloFactResolutionContext(authority=operation, filing_period=coordinate, devengo_date=coordinate)


def _assert_words(error: BaseException, key: str, *mentions: str) -> None:
    assert getattr(error, "translated_message", None) == key
    for locale in _LOCALES:
        words = resolve_error_message(error, locale=locale)
        assert words, (locale, key)
        assert words != key, (locale, key)
        assert "%{" not in words, (locale, words)
        assert not words.startswith("errors."), (locale, words)
        for mention in mentions:
            assert mention in words, (locale, mention, words)


def _pension(operation: PinnedAuthorityOperation, **amounts: str) -> PensionReduccionError:
    values = {"gross_rescate": "100", "aportaciones_pre_2007": "10", "aportaciones_totales": "20"} | amounts
    with pytest.raises(PensionReduccionError) as raised:
        compute_dt12_reduccion_plan_pensiones(
            gross_rescate=Decimal(values["gross_rescate"]),
            aportaciones_pre_2007=Decimal(values["aportaciones_pre_2007"]),
            aportaciones_totales=Decimal(values["aportaciones_totales"]),
            context=_context(operation),
        )
    return raised.value


def test_total_contributions_that_are_not_positive_name_the_amount(operation: PinnedAuthorityOperation) -> None:
    _assert_words(
        _pension(operation, aportaciones_totales="0"),
        "errors.refused.pension_reduccion_total_contributions_not_positive",
        "0",
    )


def test_a_negative_rescue_names_the_amount(operation: PinnedAuthorityOperation) -> None:
    _assert_words(_pension(operation, gross_rescate="-5"), "errors.refused.pension_reduccion_rescate_negative", "-5")


def test_negative_early_contributions_name_the_amount(operation: PinnedAuthorityOperation) -> None:
    _assert_words(
        _pension(operation, aportaciones_pre_2007="-3"),
        "errors.refused.pension_reduccion_early_contributions_negative",
        "-3",
    )


def test_early_contributions_above_the_total_name_both_amounts(operation: PinnedAuthorityOperation) -> None:
    _assert_words(
        _pension(operation, aportaciones_pre_2007="30", aportaciones_totales="20"),
        "errors.refused.pension_reduccion_early_contributions_exceed_total",
        "30",
        "20",
    )


@pytest.mark.parametrize(
    ("contingencia", "rescate", "key"),
    [
        (99, 2020, "errors.refused.pension_reduccion_contingencia_year_not_four_digits"),
        (2010, 21, "errors.refused.pension_reduccion_rescate_year_not_four_digits"),
    ],
)
def test_a_year_without_four_digits_names_which_year(
    operation: PinnedAuthorityOperation, contingencia: int, rescate: int, key: str
) -> None:
    with pytest.raises(PensionReduccionError) as raised:
        dt12_regime_window_eligibility(
            contingencia_year=contingencia, rescate_year=rescate, context=_context(operation)
        )
    _assert_words(raised.value, key, str(min(contingencia, rescate)))


@pytest.mark.parametrize(
    ("amounts", "key", "mention"),
    [
        (
            {"capital_social": "0", "beneficio_neto": "1", "reserva_dotada": "1"},
            "errors.refused.sal_reserva_capital_social_not_positive",
            "0",
        ),
        (
            {"capital_social": "5", "beneficio_neto": "-7", "reserva_dotada": "1"},
            "errors.refused.sal_reserva_beneficio_negative",
            "-7",
        ),
        (
            {"capital_social": "5", "beneficio_neto": "1", "reserva_dotada": "-9"},
            "errors.refused.sal_reserva_dotada_negative",
            "-9",
        ),
    ],
)
def test_a_reserve_input_out_of_range_names_the_amount(
    operation: PinnedAuthorityOperation, amounts: dict[str, str], key: str, mention: str
) -> None:
    with pytest.raises(PensionReduccionError) as raised:
        compute_sal_reserva_especial_dotacion(
            beneficio_neto=Decimal(amounts["beneficio_neto"]),
            reserva_dotada=Decimal(amounts["reserva_dotada"]),
            capital_social=Decimal(amounts["capital_social"]),
            context=_context(operation),
        )
    _assert_words(raised.value, key, mention)


@pytest.mark.parametrize("module_name", _WORDED_MODULES)
def test_every_key_a_worded_module_names_renders_words_in_all_locales(module_name: str) -> None:
    tree = ast.parse((_DOMAIN_DIR / module_name).read_text(encoding="utf-8"))
    keys = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.startswith(("errors.refused.", "errors.integrity."))
    }
    assert keys, module_name
    for key in sorted(keys):
        english = tr(key, locale="en")
        assert english != key, key
        fill = {name: "x" for name in _PLACEHOLDER.findall(english)}
        for locale in _LOCALES:
            words = tr(key, locale=locale, **fill)
            assert words and words != key, (locale, key)
            assert "%{" not in words, (locale, key, words)
