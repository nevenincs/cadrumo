"""The pre-write completeness gate panics on a structurally-thin fichero-BOE.

A fixed-width ``.boe`` always occupies every field's byte slot, so a required
casilla the draft omits renders as a blank slot behind a valid SHA-256 digest.
``assert_export_mirrors_manifest`` runs before the bytes are written and refuses
that thin file with a loud, enumerated ``FilingExportError``. The gate does not
apply to the ``xml_dictionary`` transport, where an absent casilla is a
legitimately-absent optional element rather than a blank slot.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from ....domain.calculations.registry import CasillaId
from ....domain.filing import FilingExportError, ModeloDraft, ModeloValueKind
from .._export import boe_representable_casilla_ids, export_draft, required_applicable_casilla_ids
from ..runtime import ExportLayoutDefinition, RegistrySchemaAccessor
from ._export_support import (
    _approved_modelo_390_registry_draft,
    _approved_registry_draft,
    _modelo_130_export_headers,
    _modelo_390_export_headers,
    _schema_provider,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@dataclass(frozen=True)
class _CompletenessGateCase:
    modelo: str
    draft_factory: Callable[[], ModeloDraft]
    headers_factory: Callable[[], dict[str, str]]
    provider_factory: Callable[[], RegistrySchemaAccessor]
    output_name: str


def _modelo_130_case() -> _CompletenessGateCase:
    return _CompletenessGateCase(
        modelo="130",
        draft_factory=_approved_registry_draft,
        headers_factory=_modelo_130_export_headers,
        provider_factory=_schema_provider,
        output_name="modelo-130.txt",
    )


def _modelo_390_case() -> _CompletenessGateCase:
    return _CompletenessGateCase(
        modelo="390",
        draft_factory=_approved_modelo_390_registry_draft,
        headers_factory=_modelo_390_export_headers,
        provider_factory=lambda: _schema_provider(filing_year=2025, period="0A", modelos=("390",)),
        output_name="modelo-390.txt",
    )


_COMPLETENESS_GATE_CASES = (
    pytest.param(_modelo_130_case, id="modelo-130"),
    pytest.param(_modelo_390_case, id="modelo-390"),
)


def _required_applicable(
    modelo: str, provider: RegistrySchemaAccessor, layout: ExportLayoutDefinition, headers: dict[str, str]
) -> frozenset[CasillaId]:
    subview = provider.get_subview(modelo)
    manifest = subview.completeness_manifest
    assert manifest is not None
    representable = boe_representable_casilla_ids(layout, headers=headers, schema_provider=provider)
    collection = provider.get_collection(modelo)
    return required_applicable_casilla_ids(manifest, collection=collection, representable=representable)


@pytest.mark.parametrize("case_factory", _COMPLETENESS_GATE_CASES)
def test_complete_fixed_width_draft_exports_without_panic(
    tmp_path: Path,
    case_factory: Callable[[], _CompletenessGateCase],
) -> None:
    case = case_factory()
    provider = case.provider_factory()
    draft = case.draft_factory()
    output = tmp_path / case.output_name

    receipt = export_draft(draft, output_path=output, headers=case.headers_factory(), schema_provider=provider)

    assert output.exists()
    assert receipt.file_sha256


@pytest.mark.parametrize("case_factory", _COMPLETENESS_GATE_CASES)
def test_thin_fixed_width_draft_panics_before_writing(
    tmp_path: Path,
    case_factory: Callable[[], _CompletenessGateCase],
) -> None:
    # Reproduce the REAL production thin state, not an artificial one: build_draft
    # emits a ModeloValue for every declared casilla and marks an unsupplied one
    # EMPTY (value=None), so its id is present in draft.values even though it would
    # render as a blank slot. The gate must key on value presence, not id
    # membership, so setting a required-applicable casilla to EMPTY must panic.
    case = case_factory()
    provider = case.provider_factory()
    draft = case.draft_factory()
    headers = case.headers_factory()
    layout = provider.get_subview(case.modelo).export_layouts[0]

    required_applicable = _required_applicable(case.modelo, provider, layout, headers)
    present_valued = sorted(
        required_applicable & {value.casilla_id for value in draft.values if value.value is not None}
    )
    assert present_valued, f"modelo {case.modelo}: fixture must declare at least one required-applicable casilla"
    emptied = present_valued[0]

    thin_values = tuple(
        value.model_copy(update={"value": None, "kind": ModeloValueKind.EMPTY})
        if value.casilla_id == emptied
        else value
        for value in draft.values
    )
    # The emptied casilla id is STILL present in draft.values (the production
    # failure mode), just with no value.
    thin_draft = draft.model_copy(update={"values": thin_values})
    assert emptied in {value.casilla_id for value in thin_draft.values}
    output = tmp_path / f"{case.modelo}-thin.txt"

    with pytest.raises(FilingExportError) as exc_info:
        export_draft(thin_draft, output_path=output, headers=headers, schema_provider=provider)

    # The panic names the emptied casilla and never writes the thin file.
    assert emptied in str(exc_info.value)
    assert "structurally-thin" in str(exc_info.value)
    assert not output.exists()
