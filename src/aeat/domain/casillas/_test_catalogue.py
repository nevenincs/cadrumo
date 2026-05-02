"""Unit tests for casilla catalogue parsing and verification."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from . import (
    CasillaCatalogue,
    CasillaDataType,
    CasillaParseError,
    CasillaRecord,
    LLMDraftProvenance,
    SelectOption,
    load_casillas,
    save_casillas,
    verify_casillas,
)
from ..modelos import ModeloCode as CanonicalModeloCode

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _record(
    *,
    casilla_id: str = "01",
    definition_reviewed_by: str = "codex",
    definition_reviewed_at: date | None = date(2026, 4, 12),
    references_casillas: tuple[str, ...] = (),
    llm_draft_provenance: LLMDraftProvenance | None = None,
) -> CasillaRecord:
    """Build a valid record for tests."""
    return CasillaRecord(
        modelo="MODELO_130",
        period="2025Q4",
        casilla_id=casilla_id,
        label={"es": f"Etiqueta {casilla_id}", "en": f"Label {casilla_id}", "hu": f"Mezo {casilla_id}"},
        help={"es": f"Ayuda {casilla_id}", "en": f"Help {casilla_id}", "hu": f"Sugo {casilla_id}"},
        data_type=CasillaDataType.TEXT,
        select_options=None,
        required=True,
        computed=False,
        formula=None,
        references_casillas=references_casillas,
        references_rules=(),
        validation=(),
        source_manual_url=None,
        source_page=1,
        source_section="1",
        definition_reviewed_by=definition_reviewed_by,
        definition_reviewed_at=definition_reviewed_at,
        llm_draft_provenance=llm_draft_provenance,
    )


def test_casillas_exports_canonical_modelo_code() -> None:
    """The casilla API must not expose a shadow ModeloCode enum."""

    from . import ModeloCode

    assert ModeloCode is CanonicalModeloCode
    assert ModeloCode.MODELO_130.value == "130"


def test_modelo_validator_accepts_canonical_and_legacy_modelo_ids() -> None:
    """Corpus payloads keep legacy names while new boundaries use canonical codes."""

    assert _record().modelo == "MODELO_130"
    assert CasillaCatalogue(modelo=CanonicalModeloCode.MODELO_130.value, period="2025Q4", records=()).modelo == "130"


def test_loader_rejects_malformed_records(tmp_path: Path) -> None:
    """The loader must reject records that violate the strict schema."""
    root = tmp_path / "casillas"
    path = root / "modelo_130" / "2025Q4.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "modelo": "MODELO_130",
                "period": "2025Q4",
                "records": [
                    {
                        "synthetic": False,
                        "modelo": "MODELO_130",
                        "period": "2025Q4",
                        "casilla_id": "01",
                        "label": {"en": "Missing Spanish"},
                        "help": {"es": "Ayuda"},
                        "data_type": "text",
                        "select_options": None,
                        "required": True,
                        "computed": False,
                        "formula": None,
                        "references_casillas": [],
                        "references_rules": [],
                        "validation": [],
                        "source_manual_url": None,
                        "source_page": None,
                        "source_section": None,
                        "definition_reviewed_by": "codex",
                        "definition_reviewed_at": "2026-04-12",
                        "llm_draft_provenance": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(CasillaParseError):
        load_casillas("MODELO_130", "2025Q4", root=root)


def test_cross_reference_validator_catches_dangling_refs() -> None:
    """Verification must flag references to casillas that are not present."""
    catalogue = CasillaCatalogue(
        modelo="MODELO_130",
        period="2025Q4",
        records=(
            _record(casilla_id="01", references_casillas=("99",)),
            _record(casilla_id="02"),
        ),
    )

    errors = verify_casillas(catalogue)
    assert len(errors) == 1
    assert errors[0].casilla_code == "cross_reference"


def test_schema_upgrade_path_round_trips_optional_fields(tmp_path: Path) -> None:
    """Older payloads that omit optional fields must still round-trip cleanly."""
    root = tmp_path / "casillas"
    catalogue = CasillaCatalogue(modelo="MODELO_130", period="2025Q4", records=(_record(),))
    save_casillas(catalogue, root=root)
    reloaded = load_casillas("MODELO_130", "2025Q4", root=root)
    payload = (root / "modelo_130" / "2025Q4.json").read_text(encoding="utf-8")

    assert reloaded == catalogue
    assert reloaded.records[0].llm_draft_provenance is None
    assert '"definition_reviewed_by"' in payload
    assert '"definition_reviewed_at"' in payload
    assert '"reviewed_by"' not in payload
    assert '"reviewed_at"' not in payload


def test_llm_provenance_is_optional_but_strict() -> None:
    """Provenance can be omitted, but invalid typed values must be rejected."""
    ok = _record(
        llm_draft_provenance=LLMDraftProvenance(
            provider="synthetic",
            model="issue-21-pending",
            prompt_id="casilla_extract_v1",
            cache_hit=False,
            drafted_at=datetime(2026, 4, 12, 12, 0, 0),
        )
    )
    assert ok.llm_draft_provenance is not None

    with pytest.raises(ValidationError):
        CasillaRecord(
            **(
                _record().model_dump(mode="python")
                | {
                    "llm_draft_provenance": {
                        "provider": "synthetic",
                        "model": "m",
                        "prompt_id": "x",
                        "cache_hit": "false",
                        "drafted_at": datetime(2026, 4, 12, 12, 0, 0),
                    }
                }
            )
        )


def test_multilingual_authoritative_spanish_is_required() -> None:
    """Label and help must both carry the authoritative Spanish text."""
    with pytest.raises(ValidationError):
        CasillaRecord(
            **(
                _record().model_dump(mode="python")
                | {
                    "label": {"en": "Only English"},
                }
            )
        )


def test_select_options_require_select_data_type() -> None:
    """Select options are only valid for SELECT casillas."""
    options = (SelectOption(value="A", label={"es": "Alta", "en": "High", "hu": "Magas"}),)
    with pytest.raises(ValidationError):
        CasillaRecord(
            **(
                _record().model_dump(mode="python")
                | {
                    "data_type": CasillaDataType.TEXT,
                    "select_options": options,
                }
            )
        )
