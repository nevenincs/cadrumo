"""Unit tests for :mod:`aeat.models._registry`."""

from __future__ import annotations

import pytest

from ..deadlines import AutonomoProfile, IVARegime
from ._categories import TaxpayerProfile
from ._codes import ModeloCode
from ._errors import RegistryIntegrityError, UnknownModeloError
from ._metadata import ModeloMetadata
from ._registry import (
    MODELO_REGISTRY,
    _check_caps_into,
    get_modelo,
    modelos_for_profile,
    year_plan,
)

pytestmark = pytest.mark.unit


def test_registry_completeness() -> None:
    """Every :class:`ModeloCode` resolves to exactly one entry."""
    assert set(MODELO_REGISTRY.keys()) == set(ModeloCode)


def test_every_entry_matches_its_key() -> None:
    """The ``entry.code`` equals its dict key for every entry."""
    for key, metadata in MODELO_REGISTRY.items():
        assert metadata.code is key


def test_caps_into_resolves_in_registry() -> None:
    """Every non-None ``caps_into`` resolves inside the registry."""
    for metadata in MODELO_REGISTRY.values():
        if metadata.caps_into is not None:
            assert metadata.caps_into in MODELO_REGISTRY


def test_get_modelo_accepts_enum_member() -> None:
    """:func:`get_modelo` accepts a :class:`ModeloCode` member."""
    assert get_modelo(ModeloCode.MODELO_303).code is ModeloCode.MODELO_303


def test_get_modelo_accepts_string_code() -> None:
    """:func:`get_modelo` accepts the canonical string code."""
    assert get_modelo("303").code is ModeloCode.MODELO_303


def test_get_modelo_unknown_string_raises() -> None:
    """An unknown numeric string raises :class:`UnknownModeloError`."""
    with pytest.raises(UnknownModeloError):
        get_modelo("999")


def test_get_modelo_garbage_raises() -> None:
    """Non-numeric garbage raises :class:`UnknownModeloError`."""
    with pytest.raises(UnknownModeloError):
        get_modelo("not-a-code")


def test_modelos_for_autonomo_ed_solo() -> None:
    """``autonomo_ed_solo`` must see IVA + IRPF + censal essentials."""
    matches = modelos_for_profile(TaxpayerProfile.AUTONOMO_ED_SOLO)
    codes = {m.code for m in matches}
    for required in (
        ModeloCode.MODELO_303,
        ModeloCode.MODELO_390,
        ModeloCode.MODELO_130,
        ModeloCode.MODELO_036,
        ModeloCode.MODELO_100,
    ):
        assert required in codes
    for excluded in (ModeloCode.MODELO_037, ModeloCode.MODELO_720, ModeloCode.MODELO_200):
        assert excluded not in codes


def test_modelo_123_caps_into_193() -> None:
    """Modelo 123 resolves to its annual summary counterpart."""
    metadata = get_modelo(ModeloCode.MODELO_123)
    assert metadata.caps_into is ModeloCode.MODELO_193
    assert ModeloCode.MODELO_193 in metadata.related_modelos


def test_check_caps_into_rejects_dangling_reference() -> None:
    """A synthetic mapping with a dangling ``caps_into`` raises."""
    good = MODELO_REGISTRY[ModeloCode.MODELO_130]
    # Build a one-entry mapping whose caps_into target is absent.
    single: dict[ModeloCode, ModeloMetadata] = {ModeloCode.MODELO_130: good}
    with pytest.raises(RegistryIntegrityError):
        _check_caps_into(single)


def test_year_plan_returns_non_empty_schedule() -> None:
    """A GENERAL IVA profile sees at least one obligation for 2026."""
    profile = AutonomoProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )
    schedule = year_plan(2026, profile)
    assert schedule.year == 2026
    assert len(schedule.obligations) > 0
