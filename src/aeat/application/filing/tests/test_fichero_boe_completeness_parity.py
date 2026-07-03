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

from datetime import date
from pathlib import Path

import pytest

from ....core.resources import resources
from ....domain.calculations.registry import CasillaFieldKind
from .._export import boe_representable_casilla_ids, export_draft, rendered_casilla_ids
from ._export_support import (
    _approved_modelo_111_registry_draft,
    _approved_modelo_115_registry_draft,
    _approved_modelo_123_registry_draft,
    _approved_modelo_131_registry_draft,
    _approved_modelo_200_registry_draft,
    _approved_modelo_390_registry_draft,
    _approved_registry_draft,
    _modelo_111_export_headers,
    _modelo_115_export_headers,
    _modelo_123_export_headers,
    _modelo_130_export_headers,
    _modelo_200_export_headers,
    _modelo_390_export_headers,
    _schema_provider,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _m131_headers() -> dict[str, str]:
    return {"declaration_type": "I"}


# (modelo, draft builder, headers builder, filing_year, period) — fixed-width
# covered modelos that declare a completeness manifest and have a reusable complete
# approved draft. filing_year/period pin the schema provider to the same revision
# the draft was built against (None = the builder's default period). Modelo 131
# (binding-derived) is covered: with the truth-grounded gate (required = calculation
# results + schema-required, not optional inputs), its computed result casillas are
# populated and reach disk, while its optional inputs (02/08/09/12/14) are excluded.
# Modelo 200 (sociedades) is covered with its 2024/0A provider. Modelo 390 (IVA
# resumen anual) is covered with its 2025/0A provider: the required-applicable
# set is the three computed annual totals (cuota devengada/deducible/resultado),
# each of which carries a real DR390 box (34/64/65) via export_refs.
_COVERED = [
    ("130", _approved_registry_draft, _modelo_130_export_headers, None, None),
    ("111", _approved_modelo_111_registry_draft, _modelo_111_export_headers, None, None),
    ("115", _approved_modelo_115_registry_draft, _modelo_115_export_headers, None, None),
    ("123", _approved_modelo_123_registry_draft, _modelo_123_export_headers, None, None),
    ("131", _approved_modelo_131_registry_draft, _m131_headers, None, None),
    ("200", _approved_modelo_200_registry_draft, _modelo_200_export_headers, 2024, "0A"),
    ("390", _approved_modelo_390_registry_draft, _modelo_390_export_headers, 2025, "0A"),
]

# Broader fixed-width, manifest-bearing set for the structural dormancy lock
# below (no complete draft needed — the check is layout-vs-manifest only).
_DORMANCY_MODELOS = [
    ("130", 2025, "1T"),
    ("111", 2025, "1T"),
    ("115", 2025, "1T"),
    ("123", 2025, "1T"),
    ("131", 2025, "1T"),
    ("303", 2025, "1T"),
    ("200", 2025, "0A"),
    ("390", 2025, "0A"),
]


@pytest.mark.parametrize(("modelo", "build_draft_fn", "headers_fn", "filing_year", "period"), _COVERED)
def test_complete_draft_reaches_disk_for_every_required_casilla(
    modelo: str, build_draft_fn, headers_fn, filing_year, period, tmp_path: Path
) -> None:
    provider = _schema_provider(filing_year=filing_year, period=period, modelos=(modelo,))
    draft = build_draft_fn()
    headers = headers_fn()
    subview = provider.get_subview(modelo)
    layout = subview.export_layouts[0]
    manifest = subview.completeness_manifest
    assert manifest is not None, f"modelo {modelo} must declare a completeness manifest to ground the parity gate"

    representable = boe_representable_casilla_ids(layout, headers=headers, schema_provider=provider)
    rendered = rendered_casilla_ids(layout, draft=draft, headers=headers, schema_provider=provider)
    # Mirror the gate's required set: calculation RESULTS (formula) and
    # schema-required casillas that are representable. Optional inputs are excluded
    # (a blank optional input is a valid zero, not a thin file).
    collection = provider.get_collection(modelo)
    required_applicable = {
        casilla.casilla_id
        for casilla in manifest.casillas
        if (schema := collection.get(casilla.casilla_id)) is not None
        and (schema.formula is not None or schema.required)
    } & representable

    # Non-vacuous: the gate is genuinely active for this modelo.
    assert required_applicable, f"modelo {modelo} has an empty required-applicable set; the gate would pass trivially"
    # Parity: every required computed/schema-required casilla reaches disk for a complete draft.
    missing = sorted(required_applicable - rendered)
    assert not missing, f"modelo {modelo} complete draft omits required casillas: {missing}"


@pytest.mark.parametrize(("modelo", "build_draft_fn", "headers_fn", "filing_year", "period"), _COVERED)
def test_complete_draft_exports_without_panic(
    modelo: str, build_draft_fn, headers_fn, filing_year, period, tmp_path: Path
) -> None:
    provider = _schema_provider(filing_year=filing_year, period=period, modelos=(modelo,))
    draft = build_draft_fn()
    output = tmp_path / f"modelo-{modelo}.txt"

    receipt = export_draft(draft, output_path=output, headers=headers_fn(), schema_provider=provider)

    assert output.exists()
    assert receipt.file_sha256


@pytest.mark.parametrize(("modelo", "year", "period"), _DORMANCY_MODELOS)
def test_no_manifest_casilla_is_representable_only_via_binding_rows(modelo: str, year: int, period: str) -> None:
    # Dormancy lock for the row_field_casilla_ids false-panic vector: the rendered
    # set is derived from draft.values, so a manifest-required casilla whose only
    # representable route is a binding-row (row_field_casilla_ids) mapping -- never
    # a direct CASILLA field -- would show permanently missing and false-panic on
    # every export. No shipped registry revision does this today; this test fails
    # the moment a future TOML author introduces the collision, which is the signal
    # to teach rendered_casilla_ids about binding-materialised row casillas (or add
    # a registry-build validator forbidding a manifest-required row_field-only
    # casilla).
    snapshot = resources().modelos.authority.snapshot(modelo, filing_year=year, period=period, on=date(year, 6, 1))
    revision = snapshot.revision
    manifest = revision.completeness_manifest
    assert manifest is not None
    layout = sorted(revision.export_layouts, key=lambda item: item.id)[0]
    assert layout.format == "fixed_width"

    casilla_field_ids = {
        field.casilla_id
        for record in layout.records
        for field in record.fields
        if field.kind == CasillaFieldKind.CASILLA and field.casilla_id is not None
    }
    row_field_ids: set = set()
    for record in layout.records:
        row_field_ids.update(record.row_field_casilla_ids.values())

    manifest_ids = {casilla.casilla_id for casilla in manifest.casillas}
    row_field_only_required = (manifest_ids & row_field_ids) - casilla_field_ids
    assert not row_field_only_required, (
        f"modelo {modelo}: manifest-required casillas representable only via binding rows "
        f"(would false-panic): {sorted(row_field_only_required)}"
    )
