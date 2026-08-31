"""Tests asserting LIRPF art. 85 imputación parameters live in the registry.

The rates and lookback must derive from ``registry/aeat/legal/irpf.toml``
rather than from Python literals on :mod:`cadrumo.domain.fincas.aggregates`.
"""

from __future__ import annotations

import tomllib
from decimal import Decimal
from typing import cast

import pytest
from pydantic import ValidationError

from ....core.resources._boundary import bundled_path
from ...calculations.registry.authority import bundled_authority
from ..errors import FincaValidationError
from ..imputacion_parameters import (
    LirpfArt85ImputacionParameters,
    _parameters_from_catalogue,
    load_imputacion_parameters,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _load_irpf_toml() -> dict[str, dict[str, dict[str, str]]]:
    path = bundled_path("registry", "aeat", "legal", "irpf.toml")
    with path.open("rb") as handle:
        return cast(dict[str, dict[str, dict[str, str]]], tomllib.load(handle))


def test_lirpf_art_85_parameters_match_registry_toml_values() -> None:
    raw = _load_irpf_toml()["parameters"]

    assert load_imputacion_parameters().recent_revision_rate == Decimal(
        raw["lirpf-art-85:imputacion-rate-recent-revision"]["value"],
    )
    assert load_imputacion_parameters().old_or_no_revision_rate == Decimal(
        raw["lirpf-art-85:imputacion-rate-old-or-no-revision"]["value"],
    )
    assert load_imputacion_parameters().catastral_revision_lookback_years == int(
        raw["lirpf-art-85:catastral-revision-lookback-years"]["value"],
    )


def test_load_imputacion_parameters_returns_typed_model() -> None:
    """The accessor returns a strict frozen Pydantic record."""
    result = load_imputacion_parameters()
    assert isinstance(result, LirpfArt85ImputacionParameters)


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
        load_imputacion_parameters().recent_revision_rate = Decimal("0.05")


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


def test_missing_lirpf_art_85_parameter_raises_finca_validation_error() -> None:
    parameters = dict(bundled_authority().catalogues.parameters)
    del parameters["lirpf-art-85:catastral-revision-lookback-years"]

    with pytest.raises(FincaValidationError, match=r"catastral-revision-lookback-years"):
        _parameters_from_catalogue(parameters)
