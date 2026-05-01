"""Unit tests for :class:`aeat.models._metadata.ModeloMetadata`."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ._applicability import ModeloApplicability
from ._categories import (
    LegalCitationSource,
    ModeloCadence,
    ModeloCategory,
    TaxpayerProfile,
)
from ._citations import LegalCitation
from ._codes import ModeloCode
from ._metadata import ModeloMetadata

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_ALL: frozenset[TaxpayerProfile] = frozenset(TaxpayerProfile)


def _make_citation() -> LegalCitation:
    return LegalCitation(
        source=LegalCitationSource.LEY,
        article="29",
        url=None,
        quoted_text_es="Enumera las obligaciones tributarias formales.",
        retrieval_date=date(2026, 4, 13),
        is_curated_summary=True,
    )


def _make_applicability() -> ModeloApplicability:
    return ModeloApplicability(
        mandatory_profiles=frozenset({TaxpayerProfile.AUTONOMO_ED_SOLO}),
        optional_profiles=frozenset(),
        exempt_profiles=_ALL - frozenset({TaxpayerProfile.AUTONOMO_ED_SOLO}),
        trigger_notes_es="smoke",
    )


def _make(**overrides: object) -> ModeloMetadata:
    base: dict[str, object] = {
        "code": ModeloCode.MODELO_303,
        "official_name_es": "Autoliquidación del IVA",
        "display_label": {"es": "IVA", "en": "VAT", "hu": "IVA"},
        "category": ModeloCategory.IVA,
        "cadence": ModeloCadence.QUARTERLY,
        "legal_basis": (_make_citation(),),
        "applicability": _make_applicability(),
        "caps_into": ModeloCode.MODELO_390,
        "related_modelos": (ModeloCode.MODELO_349,),
        "submission_portal": None,
        "known_gotchas": ("SII exoneración",),
    }
    base.update(overrides)
    return ModeloMetadata.model_validate(base)


def test_happy_path() -> None:
    """A valid metadata record constructs and exposes its fields."""
    record = _make()
    assert record.code is ModeloCode.MODELO_303
    assert record.caps_into is ModeloCode.MODELO_390


def test_frozen_rejects_assignment() -> None:
    """``frozen=True`` prevents post-construction field assignment."""
    record = _make()
    with pytest.raises(ValidationError):
        record.code = ModeloCode.MODELO_100  # type: ignore[misc]


def test_extra_forbid() -> None:
    """Unknown keys are rejected."""
    with pytest.raises(ValidationError):
        _make(unexpected="boom")


@pytest.mark.parametrize("missing_key", ["es", "en", "hu"])
def test_display_label_requires_all_three_languages(missing_key: str) -> None:
    """A display label missing any of ``es``/``en``/``hu`` raises."""
    label = {"es": "IVA", "en": "VAT", "hu": "IVA"}
    del label[missing_key]
    with pytest.raises(ValidationError):
        _make(display_label=label)


def test_display_label_rejects_blank_value() -> None:
    """Blank language values in ``display_label`` are rejected."""
    with pytest.raises(ValidationError):
        _make(display_label={"es": "IVA", "en": " ", "hu": "IVA"})


def test_legal_basis_non_empty() -> None:
    """An empty ``legal_basis`` tuple is rejected by ``min_length=1``."""
    with pytest.raises(ValidationError):
        _make(legal_basis=())


def test_blank_official_name_es_rejected() -> None:
    """Whitespace-only ``official_name_es`` is rejected."""
    with pytest.raises(ValidationError):
        _make(official_name_es="   ")
