"""Tests asserting LIRPF art. 85 imputación parameters live in the registry.

The rates and lookback must derive from ``registry/aeat/legal/irpf.toml``
rather than from Python literals on :mod:`aeat.domain.rental._aggregates`.
"""

from __future__ import annotations

import tomllib
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from aeat.core.resources import bundled_path
from aeat.domain.rental._aggregates import (
    CATASTRAL_REVISION_LOOKBACK_YEARS,
    IMPUTACION_RATE_OLD_OR_NO_REVISION,
    IMPUTACION_RATE_RECENT_REVISION,
)
from aeat.domain.rental._imputacion_parameters import (
    LIRPF_ART_85_IMPUTACION,
    LirpfArt85ImputacionParameters,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _load_irpf_toml() -> dict[str, dict[str, dict[str, str]]]:
    path = bundled_path("registry", "aeat", "legal", "irpf.toml")
    with path.open("rb") as handle:
        return tomllib.load(handle)


def test_lirpf_art_85_parameters_match_registry_toml_values() -> None:
    raw = _load_irpf_toml()["parameters"]

    assert LIRPF_ART_85_IMPUTACION.recent_revision_rate == Decimal(
        raw["lirpf-art-85:imputacion-rate-recent-revision"]["value"]
    )
    assert LIRPF_ART_85_IMPUTACION.old_or_no_revision_rate == Decimal(
        raw["lirpf-art-85:imputacion-rate-old-or-no-revision"]["value"]
    )
    assert LIRPF_ART_85_IMPUTACION.catastral_revision_lookback_years == int(
        raw["lirpf-art-85:catastral-revision-lookback-years"]["value"]
    )


def test_rental_aggregate_constants_now_route_through_registry() -> None:
    assert IMPUTACION_RATE_RECENT_REVISION is LIRPF_ART_85_IMPUTACION.recent_revision_rate
    assert IMPUTACION_RATE_OLD_OR_NO_REVISION is LIRPF_ART_85_IMPUTACION.old_or_no_revision_rate
    assert CATASTRAL_REVISION_LOOKBACK_YEARS is LIRPF_ART_85_IMPUTACION.catastral_revision_lookback_years


def test_lirpf_art_85_parameters_each_cite_the_boe_authority() -> None:
    raw = _load_irpf_toml()["parameters"]

    for parameter_id in (
        "lirpf-art-85:imputacion-rate-recent-revision",
        "lirpf-art-85:imputacion-rate-old-or-no-revision",
        "lirpf-art-85:catastral-revision-lookback-years",
    ):
        legal_refs = raw[parameter_id].get("legal_refs") or []
        assert "ley-35-2006:art-85" in legal_refs, (
            f"{parameter_id} must cite ley-35-2006:art-85 to remain registry-grounded"
        )


def test_legal_section_carries_lirpf_art_85_citation_with_required_text() -> None:
    legal = _load_irpf_toml()["legal"]
    art_85 = legal.get("ley-35-2006:art-85")
    assert art_85 is not None, "registry/aeat/legal/irpf.toml must declare ley-35-2006:art-85"

    required_text: list[str] = list(art_85.get("required_text", []))
    expected_substrings = (
        "Imputación de rentas inmobiliarias",
        "2 por ciento al valor catastral",
        "diez períodos impositivos anteriores",
        "1,1 por ciento",
    )
    for needle in expected_substrings:
        assert any(needle in entry for entry in required_text), (
            f"required_text for ley-35-2006:art-85 must mention {needle!r}"
        )


def test_lirpf_art_85_parameter_record_is_frozen() -> None:
    with pytest.raises(ValidationError):
        LIRPF_ART_85_IMPUTACION.recent_revision_rate = Decimal("0.05")


def test_lirpf_art_85_corpus_excerpt_is_present() -> None:
    excerpt = bundled_path("corpus", "normatives", "html", "ley-35-2006-art-85.html")
    assert excerpt.exists(), "the LIRPF art. 85 BOE excerpt must be present in the bundled normatives corpus"
    body = excerpt.read_text(encoding="utf-8")
    assert "Imputación de rentas inmobiliarias" in body
    assert "1,1 por ciento" in body
    assert "diez períodos impositivos anteriores" in body


def test_loader_record_validates_inputs_in_pydantic_strict_mode() -> None:
    with pytest.raises(ValidationError):
        LirpfArt85ImputacionParameters(
            recent_revision_rate=Decimal("1.5"),
            old_or_no_revision_rate=Decimal("0.02"),
            catastral_revision_lookback_years=10,
        )
