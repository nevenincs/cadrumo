"""Unit tests for the strict wire payload schemas."""

from __future__ import annotations

from datetime import datetime

import pytest

from aeat.sync import (
    ModeloIdentifier,
    PortalIdentifier,
    WireCasilla,
    WireFilingEntry,
    WireFilingHistory,
    WireModeloDefinition,
    WirePortalLink,
    WirePortalManifest,
    WireValidationError,
    WireValidator,
)


def _modelo_json() -> str:
    return (
        '{"modelo": "100",'
        ' "vigencia_start": "2024-01-01",'
        ' "vigencia_end": "2024-12-31",'
        ' "casillas": ['
        '  {"id": "C1", "label": {"es": "Base", "en": "Base", "hu": "Alap"},'
        '   "type": "decimal", "default": "0", "formula": null}'
        " ]}"
    )


@pytest.mark.unit
def test_modelo_roundtrip() -> None:
    payload = WireModeloDefinition.model_validate_json(_modelo_json())
    assert payload.modelo == "100"
    assert len(payload.casillas) == 1
    restored = WireModeloDefinition.model_validate_json(payload.model_dump_json(by_alias=True))
    assert restored == payload


@pytest.mark.unit
def test_modelo_rejects_extra_keys() -> None:
    bad = '{"modelo": "100", "vigencia_start": "2024-01-01", "vigencia_end": "2024-12-31", "casillas": [], "extra": 1}'
    with pytest.raises(WireValidationError):
        WireValidator().validate(bad, WireModeloDefinition)


@pytest.mark.unit
def test_modelo_rejects_bad_identifier() -> None:
    bad = '{"modelo": "not-a-modelo", "vigencia_start": "2024-01-01", "vigencia_end": "2024-12-31", "casillas": []}'
    with pytest.raises(WireValidationError):
        WireValidator().validate(bad, WireModeloDefinition)


@pytest.mark.unit
def test_filing_history_roundtrip() -> None:
    entry = WireFilingEntry(
        modelo=ModeloIdentifier("303"),
        period="2024Q1",
        submitted_at=datetime(2024, 4, 20, 10, 0, 0),
        status="ACCEPTED",
    )
    history = WireFilingHistory(entries=(entry,))
    restored = WireFilingHistory.model_validate_json(history.model_dump_json())
    assert restored == history


@pytest.mark.unit
def test_portal_manifest_roundtrip() -> None:
    link = WirePortalLink.model_validate(
        {
            "url": "https://sede.agenciatributaria.gob.es/a",
            "label": {"es": "A", "en": "A", "hu": "A"},
            "modelo": None,
        }
    )
    manifest = WirePortalManifest(portal=PortalIdentifier("sede"), links=(link,))
    restored = WirePortalManifest.model_validate_json(manifest.model_dump_json())
    assert restored == manifest


@pytest.mark.unit
def test_casilla_requires_label_and_type() -> None:
    with pytest.raises(WireValidationError):
        WireValidator().validate('{"id": "C1"}', WireCasilla)
