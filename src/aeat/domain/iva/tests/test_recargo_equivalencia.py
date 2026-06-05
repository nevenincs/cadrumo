"""Tests for the registry-backed LIVA art. 161 recargo de equivalencia substrate."""

from __future__ import annotations

import tomllib
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.resources import bundled_path
from .. import (
    IvaRateKind,
    LivaArt161RecargoRates,
    load_recargo_rates,
    recargo_rate_for,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _load_recargo_toml() -> dict[str, dict[str, dict[str, str]]]:
    path = bundled_path("registry", "aeat", "legal", "iva-recargo-equivalencia.toml")
    with path.open("rb") as handle:
        return tomllib.load(handle)


def test_recargo_rates_match_registry_toml_values() -> None:
    raw = _load_recargo_toml()["parameters"]
    assert load_recargo_rates().general_rate == Decimal(raw["liva-art-161:recargo-rate-general"]["value"])
    assert load_recargo_rates().reducido_rate == Decimal(raw["liva-art-161:recargo-rate-reducido"]["value"])
    assert load_recargo_rates().super_reducido_rate == Decimal(raw["liva-art-161:recargo-rate-super-reducido"]["value"])
    assert load_recargo_rates().tabaco_rate == Decimal(raw["liva-art-161:recargo-rate-tabaco"]["value"])


def test_recargo_rates_match_liva_art_161_boe_text() -> None:
    """Sanity check: the loaded values match the BOE-cited percentages."""
    assert load_recargo_rates().general_rate == Decimal("0.052")  # 5.2 %
    assert load_recargo_rates().reducido_rate == Decimal("0.014")  # 1.4 %
    assert load_recargo_rates().super_reducido_rate == Decimal("0.005")  # 0.5 %
    assert load_recargo_rates().tabaco_rate == Decimal("0.0175")  # 1.75 %


def test_recargo_parameters_each_cite_liva_art_161() -> None:
    raw = _load_recargo_toml()["parameters"]
    for parameter_id in (
        "liva-art-161:recargo-rate-general",
        "liva-art-161:recargo-rate-reducido",
        "liva-art-161:recargo-rate-super-reducido",
        "liva-art-161:recargo-rate-tabaco",
    ):
        legal_refs = raw[parameter_id].get("legal_refs") or []
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


def test_recargo_rate_for_general_returns_5_2_percent() -> None:
    assert recargo_rate_for(IvaRateKind.GENERAL) == Decimal("0.052")


def test_recargo_rate_for_reduced_returns_1_4_percent() -> None:
    assert recargo_rate_for(IvaRateKind.REDUCED) == Decimal("0.014")


def test_recargo_rate_for_super_reduced_returns_0_5_percent() -> None:
    assert recargo_rate_for(IvaRateKind.SUPER_REDUCED) == Decimal("0.005")


def test_recargo_rate_for_zero_returns_none() -> None:
    """Recargo de equivalencia does not apply to zero-rated operations."""
    assert recargo_rate_for(IvaRateKind.ZERO) is None


def test_recargo_rate_for_exempt_returns_none() -> None:
    """Recargo de equivalencia does not apply to exempt operations."""
    assert recargo_rate_for(IvaRateKind.EXEMPT) is None


def test_recargo_record_validates_inputs_in_strict_mode() -> None:
    with pytest.raises(ValidationError, match=r"general_rate|less than"):
        LivaArt161RecargoRates(
            general_rate=Decimal("1.5"),  # > 1 violates Field constraint
            reducido_rate=Decimal("0.014"),
            super_reducido_rate=Decimal("0.005"),
            tabaco_rate=Decimal("0.0175"),
        )
