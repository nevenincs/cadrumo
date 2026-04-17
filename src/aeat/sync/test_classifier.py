"""Unit tests for the semantic divergence classifier."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from . import (
    DivergenceClassification,
    DivergenceClassifier,
    DivergenceKind,
    ModeloIdentifier,
    PortalIdentifier,
    WireCasilla,
    WireFilingEntry,
    WireFilingHistory,
    WireModeloDefinition,
    WirePortalLink,
    WirePortalManifest,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


def _casilla(
    id_: str = "C1",
    type_: str = "decimal",
    default: str | None = "0",
    formula: str | None = None,
    label: dict[str, str] | None = None,
) -> WireCasilla:
    return WireCasilla.model_validate(
        {
            "id": id_,
            "label": label or {"es": "Base", "en": "Base", "hu": "Alap"},
            "type": type_,
            "default": default,
            "formula": formula,
        }
    )


def _modelo(
    casillas: tuple[WireCasilla, ...] = (),
    vigencia_end: date = date(2024, 12, 31),
) -> WireModeloDefinition:
    return WireModeloDefinition(
        modelo=ModeloIdentifier("100"),
        vigencia_start=date(2024, 1, 1),
        vigencia_end=vigencia_end,
        casillas=casillas,
    )


def test_no_divergence_baseline() -> None:
    base = _modelo(casillas=(_casilla(),))
    records = DivergenceClassifier().diff_modelo(local=base, live=base)
    assert records == ()


def test_vigencia_extended_is_additive() -> None:
    local = _modelo(casillas=(_casilla(),))
    live = _modelo(casillas=(_casilla(),), vigencia_end=date(2025, 6, 30))
    records = DivergenceClassifier().diff_modelo(local=local, live=live)
    assert len(records) == 1
    assert records[0].payload.kind == DivergenceKind.VIGENCIA_EXTENDED
    assert records[0].classification == DivergenceClassification.ADDITIVE


def test_casilla_added_with_default_is_additive() -> None:
    local = _modelo(casillas=(_casilla("C1"),))
    live = _modelo(casillas=(_casilla("C1"), _casilla("C2", default="1")))
    records = DivergenceClassifier().diff_modelo(local=local, live=live)
    kinds = {r.payload.kind for r in records}
    assert DivergenceKind.CASILLA_ADDED_WITH_DEFAULT in kinds
    record = next(r for r in records if r.payload.kind == DivergenceKind.CASILLA_ADDED_WITH_DEFAULT)
    assert record.classification == DivergenceClassification.ADDITIVE


def test_casilla_added_without_default_is_suspicious() -> None:
    local = _modelo(casillas=(_casilla("C1"),))
    live = _modelo(casillas=(_casilla("C1"), _casilla("C2", default=None)))
    records = DivergenceClassifier().diff_modelo(local=local, live=live)
    record = next(r for r in records if r.payload.kind == DivergenceKind.UNKNOWN_SHAPE)
    assert record.classification == DivergenceClassification.SUSPICIOUS


def test_casilla_removed_is_breaking() -> None:
    local = _modelo(casillas=(_casilla("C1"), _casilla("C2")))
    live = _modelo(casillas=(_casilla("C1"),))
    records = DivergenceClassifier().diff_modelo(local=local, live=live)
    assert len(records) == 1
    assert records[0].payload.kind == DivergenceKind.CASILLA_REMOVED
    assert records[0].classification == DivergenceClassification.BREAKING


def test_casilla_type_changed_is_breaking() -> None:
    local = _modelo(casillas=(_casilla("C1", type_="decimal"),))
    live = _modelo(casillas=(_casilla("C1", type_="text"),))
    records = DivergenceClassifier().diff_modelo(local=local, live=live)
    assert records[0].payload.kind == DivergenceKind.CASILLA_TYPE_CHANGED
    assert records[0].classification == DivergenceClassification.BREAKING


def test_formula_changed_is_breaking() -> None:
    local = _modelo(casillas=(_casilla("C1", formula="A+B"),))
    live = _modelo(casillas=(_casilla("C1", formula="A-B"),))
    records = DivergenceClassifier().diff_modelo(local=local, live=live)
    assert records[0].payload.kind == DivergenceKind.FORMULA_CHANGED
    assert records[0].classification == DivergenceClassification.BREAKING


def test_label_es_changed_is_breaking() -> None:
    local_casilla = _casilla("C1", label={"es": "Base", "en": "Base", "hu": "Alap"})
    live_casilla = _casilla("C1", label={"es": "Importe", "en": "Base", "hu": "Alap"})
    records = DivergenceClassifier().diff_modelo(
        local=_modelo(casillas=(local_casilla,)),
        live=_modelo(casillas=(live_casilla,)),
    )
    assert records[0].payload.kind == DivergenceKind.LABEL_ES_CHANGED
    assert records[0].classification == DivergenceClassification.BREAKING


def test_label_translation_added_is_additive() -> None:
    local_casilla = _casilla("C1", label={"es": "Base"})
    live_casilla = _casilla("C1", label={"es": "Base", "hu": "Alap"})
    records = DivergenceClassifier().diff_modelo(
        local=_modelo(casillas=(local_casilla,)),
        live=_modelo(casillas=(live_casilla,)),
    )
    assert records[0].payload.kind == DivergenceKind.LABEL_TRANSLATION_ADDED
    assert records[0].classification == DivergenceClassification.ADDITIVE


def test_portal_url_changed_is_suspicious() -> None:
    local_link = WirePortalLink.model_validate(
        {"url": "https://sede.agenciatributaria.gob.es/a", "label": {"es": "A", "en": "A", "hu": "A"}, "modelo": "100"}
    )
    live_link = WirePortalLink.model_validate(
        {"url": "https://sede.agenciatributaria.gob.es/b", "label": {"es": "A", "en": "A", "hu": "A"}, "modelo": "100"}
    )
    local = WirePortalManifest(portal=PortalIdentifier("sede"), links=(local_link,))
    live = WirePortalManifest(portal=PortalIdentifier("sede"), links=(live_link,))
    records = DivergenceClassifier().diff_portal_manifest(local=local, live=live)
    assert records[0].payload.kind == DivergenceKind.PORTAL_URL_CHANGED
    assert records[0].classification == DivergenceClassification.SUSPICIOUS


def test_filing_status_changed_is_benign() -> None:
    local_entry = WireFilingEntry(
        modelo=ModeloIdentifier("303"),
        period="2024Q1",
        submitted_at=datetime(2024, 4, 20, 10, 0, 0),
        status="PENDING",
    )
    live_entry = WireFilingEntry(
        modelo=ModeloIdentifier("303"),
        period="2024Q1",
        submitted_at=datetime(2024, 4, 20, 10, 0, 0),
        status="ACCEPTED",
    )
    local = WireFilingHistory(entries=(local_entry,))
    live = WireFilingHistory(entries=(live_entry,))
    records = DivergenceClassifier().diff_filing_history(local=local, live=live)
    assert len(records) == 1
    assert records[0].payload.kind == DivergenceKind.FILING_STATUS_CHANGED
    assert records[0].classification == DivergenceClassification.BENIGN
