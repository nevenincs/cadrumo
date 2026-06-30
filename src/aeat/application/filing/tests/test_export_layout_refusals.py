"""Registry export-layout refusal and coverage tests."""

from __future__ import annotations

from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from ....domain.filing import FilingExportError
from ....domain.submission import ModeloDraftStatus
from .. import (
    DeclaracionVerifyVerdict,
    ModeloOperatorProfile,
    build_draft,
    export_draft,
    export_layout_renderability_reason,
    verify_export,
)
from ._export_support import (
    _PERIOD,
    _approved_registry_draft,
    _assert_missing_export_layout_refusal,
    _modelo_130_export_headers,
    _modelo_130_export_payload,
    _provider_with_export_layouts,
    _provider_without_export_layout,
    _schema_provider,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@cache
def _approved_modelo_303_registry_draft():
    """An approved modelo-303 draft built from the live registry snapshot."""

    provider = _schema_provider(modelos=("303",))
    draft = build_draft(
        modelo="303",
        period=_PERIOD,
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Export registry test",
        ),
        inputs={
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        },
        schema_provider=provider,
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


def test_export_rejects_modelo_without_registry_export_layout(tmp_path: Path) -> None:
    """A modelo whose registry revision declares no export layout is refused."""

    draft = _approved_modelo_303_registry_draft()
    provider = _provider_without_export_layout(_schema_provider(modelos=("303",)), "303")
    with pytest.raises(FilingExportError) as exc_info:
        export_draft(
            draft,
            output_path=tmp_path / "modelo-303.txt",
            headers={"declaration_type": "I"},
            schema_provider=provider,
        )
    _assert_missing_export_layout_refusal(str(exc_info.value), draft.modelo)


def test_xml_dictionary_layout_is_renderable_for_modelo_100() -> None:
    provider = _schema_provider(filing_year=2024, period="0A", modelos=("100",))
    layout = provider.get_subview("100").export_layouts[0]

    assert layout.format == "xml_dictionary"
    assert export_layout_renderability_reason("100", layout) is None


def test_export_refuses_layout_without_records(tmp_path: Path) -> None:
    draft = _approved_registry_draft()
    provider = _schema_provider()
    layout = provider.get_subview(draft.modelo).export_layouts[0].model_copy(update={"records": ()})
    empty_provider = _provider_with_export_layouts(provider, draft.modelo, (layout,))

    with pytest.raises(FilingExportError, match="declares no export records"):
        export_draft(
            draft,
            output_path=tmp_path / "modelo-130.txt",
            headers=_modelo_130_export_headers(),
            schema_provider=empty_provider,
        )


def test_verify_reports_missing_for_modelo_without_registry_export_layout(tmp_path: Path) -> None:
    """``verify_export`` reports MISSING for a modelo with no export layout."""

    draft = _approved_modelo_303_registry_draft()
    provider = _provider_without_export_layout(_schema_provider(modelos=("303",)), "303")
    verdict = verify_export(
        draft,
        file_path=tmp_path / "modelo-303.txt",
        schema_provider=provider,
    )

    assert verdict.verdict is DeclaracionVerifyVerdict.MISSING
    assert verdict.narrative == "filing.export.missing_registry_layout"
    assert verdict.mismatched_casilla_ids == ()


def test_verify_reports_unchecked_casilla_ids_outside_the_parsed_set(tmp_path: Path) -> None:
    """verify_export surfaces draft casillas the export parser never re-reads."""

    draft = _approved_registry_draft()
    provider = _schema_provider()
    exported = tmp_path / "modelo-130.txt"
    exported.write_bytes(_modelo_130_export_payload())

    verdict = verify_export(draft, file_path=exported, schema_provider=provider)

    draft_casillas = {value.casilla_id for value in draft.values}
    confirmed = {entry.casilla_id for entry in verdict.casilla_provenance}
    unchecked = set(verdict.unchecked_casilla_ids)

    assert verdict.verdict is DeclaracionVerifyVerdict.MATCH
    assert unchecked, "modelo 130 has a non-currency casilla the layout never re-reads"
    assert unchecked <= draft_casillas
    assert unchecked.isdisjoint(confirmed)
    assert unchecked.isdisjoint(set(verdict.mismatched_casilla_ids))
    assert "saldo-negativo-fin-periodo" in unchecked
