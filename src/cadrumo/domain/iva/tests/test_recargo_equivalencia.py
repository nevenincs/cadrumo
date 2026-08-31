"""Tests for the registry-backed LIVA art. 161 recargo substrate.

The suite pins :func:`~domain.iva.load_recargo_rates` and
:func:`~domain.iva.load_recargo_rates` to the bundled legal-parameter catalogue,
its BOE excerpt, and the closed :class:`~domain.iva.IvaRateKind` tier mapping.
It protects the recargo de equivalencia ladder as legal data, not as inline
Python constants.

See Also:
    :mod:`~domain.iva.recargo_equivalencia`
        Registry-backed loader and frozen rate record under test.
    :mod:`~domain.iva.saturation`
        IVA-category saturation policy that surfaces recargo as operator-derived
        rather than silently deriving a domestic rate.
    :mod:`~application.calculations.tests.test_modelo_303_special_case_casilla_routing`
        Ledger aggregation regression proving retailer-side recargo purchases
        are surfaced instead of silently deducted.
"""

from __future__ import annotations

import tomllib
from decimal import Decimal
from typing import cast

import pytest
from pydantic import ValidationError

from ....core.resources._boundary import bundled_path
from ..recargo_equivalencia import LivaArt161RecargoRates, load_recargo_rates

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _load_recargo_toml() -> dict[str, dict[str, dict[str, str]]]:
    path = bundled_path("registry", "aeat", "legal", "iva-recargo-equivalencia.toml")
    with path.open("rb") as handle:
        return cast(dict[str, dict[str, dict[str, str]]], tomllib.load(handle))


@pytest.mark.parametrize(
    ("field_name", "parameter_id", "expected_boe_value"),
    (
        pytest.param("general_rate", "liva-art-161:recargo-rate-general", Decimal("0.052"), id="general"),
        pytest.param("reducido_rate", "liva-art-161:recargo-rate-reducido", Decimal("0.014"), id="reducido"),
        pytest.param(
            "super_reducido_rate",
            "liva-art-161:recargo-rate-super-reducido",
            Decimal("0.005"),
            id="super-reducido",
        ),
        pytest.param("tabaco_rate", "liva-art-161:recargo-rate-tabaco", Decimal("0.0175"), id="tabaco"),
    ),
)
def test_recargo_rate_parameters_match_registry_boe_values_and_liva_ref(
    field_name: str,
    parameter_id: str,
    expected_boe_value: Decimal,
) -> None:
    raw = _load_recargo_toml()["parameters"]
    rates = load_recargo_rates()

    parameter = raw[parameter_id]
    assert getattr(rates, field_name) == Decimal(parameter["value"]) == expected_boe_value
    legal_refs = parameter.get("legal_refs") or []
    assert "ley-37-1992:art-161" in legal_refs, f"{parameter_id} must cite ley-37-1992:art-161"


def test_recargo_legal_section_carries_required_text_from_boe() -> None:
    legal = _load_recargo_toml()["legal"]
    art_161 = legal.get("ley-37-1992:art-161")
    assert art_161 is not None
    required_text: list[str] = list(art_161.get("required_text", []))
    for needle in ("5,2 por ciento", "1,4 por ciento", "0,50 por ciento", "1,75 por ciento"):
        assert any(needle in entry for entry in required_text), f"required_text must mention {needle!r}"


def test_recargo_corpus_excerpt_present_with_boe_quotes() -> None:
    excerpt = bundled_path("corpus", "normatives", "html", "ley-37-1992-art-161.html")
    assert excerpt.exists()
    body = excerpt.read_text(encoding="utf-8")
    assert "Tipos del recargo" in body or "Tipos" in body
    assert "5,2 por ciento" in body
    assert "1,4 por ciento" in body
    assert "0,50 por ciento" in body
    assert "1,75 por ciento" in body


def test_recargo_record_is_frozen() -> None:
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        load_recargo_rates().general_rate = Decimal("0.999")


def test_recargo_record_validates_inputs_in_strict_mode() -> None:
    with pytest.raises(ValidationError, match=r"general_rate|less than"):
        LivaArt161RecargoRates(
            general_rate=Decimal("1.5"),  # > 1 violates Field constraint
            reducido_rate=Decimal("0.014"),
            super_reducido_rate=Decimal("0.005"),
            tabaco_rate=Decimal("0.0175"),
        )
