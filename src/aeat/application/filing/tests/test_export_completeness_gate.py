"""The pre-write completeness gate panics on a structurally-thin fichero-BOE.

A fixed-width ``.boe`` always occupies every field's byte slot, so a required
casilla the draft omits renders as a blank slot behind a valid SHA-256 digest.
``assert_export_mirrors_manifest`` runs before the bytes are written and refuses
that thin file with a loud, enumerated ``FilingExportError``. The gate does not
apply to the ``xml_dictionary`` transport, where an absent casilla is a
legitimately-absent optional element rather than a blank slot.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....domain.filing._errors import FilingExportError
from ....domain.filing._schema import ModeloValueKind
from .._export import boe_representable_casilla_ids, export_draft
from ._export_support import (
    _approved_registry_draft,
    _modelo_130_export_headers,
    _schema_provider,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _required_applicable_130(provider, layout, headers) -> set:
    subview = provider.get_subview("130")
    manifest = subview.completeness_manifest
    assert manifest is not None
    representable = boe_representable_casilla_ids(layout, headers=headers, schema_provider=provider)
    return {casilla.casilla_id for casilla in manifest.casillas} & representable


def test_complete_fixed_width_draft_exports_without_panic(tmp_path: Path) -> None:
    provider = _schema_provider()
    draft = _approved_registry_draft()
    output = tmp_path / "modelo-130.txt"

    receipt = export_draft(
        draft, output_path=output, headers=_modelo_130_export_headers(), schema_provider=provider
    )

    assert output.exists()
    assert receipt.file_sha256


def test_thin_fixed_width_draft_panics_before_writing(tmp_path: Path) -> None:
    # Reproduce the REAL production thin state, not an artificial one: build_draft
    # emits a ModeloValue for every declared casilla and marks an unsupplied one
    # EMPTY (value=None), so its id is present in draft.values even though it would
    # render as a blank slot. The gate must key on value presence, not id
    # membership, so setting a required-applicable casilla to EMPTY must panic.
    provider = _schema_provider()
    draft = _approved_registry_draft()
    headers = _modelo_130_export_headers()
    layout = provider.get_subview("130").export_layouts[0]

    required_applicable = _required_applicable_130(provider, layout, headers)
    present_valued = sorted(
        required_applicable & {value.casilla_id for value in draft.values if value.value is not None}
    )
    assert present_valued, "fixture must declare at least one required-applicable casilla with a real value"
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
    output = tmp_path / "modelo-130-thin.txt"

    with pytest.raises(FilingExportError) as exc_info:
        export_draft(thin_draft, output_path=output, headers=headers, schema_provider=provider)

    # The panic names the emptied casilla and never writes the thin file.
    assert emptied in str(exc_info.value)
    assert "structurally-thin" in str(exc_info.value)
    assert not output.exists()
