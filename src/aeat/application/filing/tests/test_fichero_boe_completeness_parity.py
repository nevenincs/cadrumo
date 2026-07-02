"""Multi-modelo fichero-BOE completeness parity regression lock.

For every export-capable, fixed-width covered modelo that declares a
calculation-completeness manifest, a complete approved draft must export clean and
every manifest-required, representable casilla must actually reach disk. This is
the fichero-BOE analogue of the workbook parity gate (``test_modelo_export_parity``):
it pins the pre-write completeness gate against regression -- both against
weakening (a required casilla silently dropping out) and against a vacuous gate (a
modelo whose required-applicable set is empty, so the gate passes trivially).

The disposition-suppression case is covered by ``test_export_completeness_sets``
(Modelo 303 DID page) and the anti-tautology drift case -- a thin draft must panic
-- by ``test_export_completeness_gate``; they are not duplicated here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .._export import boe_representable_casilla_ids, export_draft, rendered_casilla_ids
from ._export_support import (
    _approved_modelo_111_registry_draft,
    _approved_modelo_115_registry_draft,
    _approved_modelo_123_registry_draft,
    _approved_registry_draft,
    _modelo_111_export_headers,
    _modelo_115_export_headers,
    _modelo_123_export_headers,
    _modelo_130_export_headers,
    _schema_provider,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# (modelo, draft builder, headers builder) — fixed-width covered modelos that
# declare a completeness manifest and have a reusable complete approved draft.
_COVERED = [
    ("130", _approved_registry_draft, _modelo_130_export_headers),
    ("111", _approved_modelo_111_registry_draft, _modelo_111_export_headers),
    ("115", _approved_modelo_115_registry_draft, _modelo_115_export_headers),
    ("123", _approved_modelo_123_registry_draft, _modelo_123_export_headers),
]


@pytest.mark.parametrize(("modelo", "build_draft_fn", "headers_fn"), _COVERED)
def test_complete_draft_reaches_disk_for_every_required_casilla(
    modelo: str, build_draft_fn, headers_fn, tmp_path: Path
) -> None:
    provider = _schema_provider(modelos=(modelo,))
    draft = build_draft_fn()
    headers = headers_fn()
    subview = provider.get_subview(modelo)
    layout = subview.export_layouts[0]
    manifest = subview.completeness_manifest
    assert manifest is not None, f"modelo {modelo} must declare a completeness manifest to ground the parity gate"

    representable = boe_representable_casilla_ids(layout, headers=headers, schema_provider=provider)
    required_applicable = {casilla.casilla_id for casilla in manifest.casillas} & representable
    rendered = rendered_casilla_ids(layout, draft=draft, headers=headers, schema_provider=provider)

    # Non-vacuous: the gate is genuinely active for this modelo.
    assert required_applicable, f"modelo {modelo} has an empty required-applicable set; the gate would pass trivially"
    # Parity: every required, representable casilla reaches disk for a complete draft.
    missing = sorted(required_applicable - rendered)
    assert not missing, f"modelo {modelo} complete draft omits required casillas: {missing}"


@pytest.mark.parametrize(("modelo", "build_draft_fn", "headers_fn"), _COVERED)
def test_complete_draft_exports_without_panic(modelo: str, build_draft_fn, headers_fn, tmp_path: Path) -> None:
    provider = _schema_provider(modelos=(modelo,))
    draft = build_draft_fn()
    output = tmp_path / f"modelo-{modelo}.txt"

    receipt = export_draft(draft, output_path=output, headers=headers_fn(), schema_provider=provider)

    assert output.exists()
    assert receipt.file_sha256
