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

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from ....core.resources import resources
from ....domain.calculations.registry import CasillaFieldKind
from ....domain.filing import FilingExportError
from .._export import (
    _assert_casilla_metadata_fidelity,
    _assert_record_order_fidelity,
    boe_representable_casilla_ids,
    export_draft,
    rendered_casilla_ids,
    required_applicable_casilla_ids,
)
from ..runtime import CasillaRecordMetadata
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


_CoveredCase = tuple[str, Callable[[], Any], Callable[[], dict[str, str]], int | None, str | None]

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
_COVERED: tuple[_CoveredCase, ...] = (
    ("130", _approved_registry_draft, _modelo_130_export_headers, None, None),
    ("111", _approved_modelo_111_registry_draft, _modelo_111_export_headers, None, None),
    ("115", _approved_modelo_115_registry_draft, _modelo_115_export_headers, None, None),
    ("123", _approved_modelo_123_registry_draft, _modelo_123_export_headers, None, None),
    ("131", _approved_modelo_131_registry_draft, _m131_headers, None, None),
    ("200", _approved_modelo_200_registry_draft, _modelo_200_export_headers, 2024, "0A"),
    ("390", _approved_modelo_390_registry_draft, _modelo_390_export_headers, 2025, "0A"),
)

# Broader fixed-width, manifest-bearing set for the structural dormancy lock
# below (no complete draft needed — the check is layout-vs-manifest only).
_DORMANCY_MODELOS = (
    ("130", 2025, "1T"),
    ("111", 2025, "1T"),
    ("115", 2025, "1T"),
    ("123", 2025, "1T"),
    ("131", 2025, "1T"),
    ("303", 2025, "1T"),
    ("200", 2025, "0A"),
    ("390", 2025, "0A"),
)


def test_complete_draft_reaches_disk_for_every_required_casilla() -> None:
    for modelo, build_draft_fn, headers_fn, filing_year, period in _COVERED:
        provider = _schema_provider(filing_year=filing_year, period=period, modelos=(modelo,))
        draft = build_draft_fn()
        headers = headers_fn()
        subview = provider.get_subview(modelo)
        layout = subview.export_layouts[0]
        manifest = subview.completeness_manifest
        assert manifest is not None, f"modelo {modelo} must declare a completeness manifest to ground the parity gate"

        representable = boe_representable_casilla_ids(layout, headers=headers, schema_provider=provider)
        rendered = rendered_casilla_ids(layout, draft=draft, headers=headers, schema_provider=provider)
        required_applicable = required_applicable_casilla_ids(
            manifest,
            collection=provider.get_collection(modelo),
            representable=representable,
        )

        # Non-vacuous: the gate is genuinely active for this modelo.
        assert required_applicable, (
            f"modelo {modelo} has an empty required-applicable set; the gate would pass trivially"
        )
        # Parity: every required computed/schema-required casilla reaches disk for a complete draft.
        missing = sorted(required_applicable - rendered)
        assert not missing, f"modelo {modelo} complete draft omits required casillas: {missing}"


def test_complete_draft_exports_without_panic(tmp_path: Path) -> None:
    for modelo, build_draft_fn, headers_fn, filing_year, period in _COVERED:
        provider = _schema_provider(filing_year=filing_year, period=period, modelos=(modelo,))
        draft = build_draft_fn()
        output = tmp_path / f"modelo-{modelo}.txt"

        receipt = export_draft(draft, output_path=output, headers=headers_fn(), schema_provider=provider)

        assert output.exists(), modelo
        assert receipt.file_sha256, modelo


def test_no_manifest_casilla_is_representable_only_via_binding_rows() -> None:
    # Dormancy lock for the row_field_casilla_ids false-panic vector: the rendered
    # set is derived from draft.values, so a manifest-required casilla whose only
    # representable route is a binding-row (row_field_casilla_ids) mapping -- never
    # a direct CASILLA field -- would show permanently missing and false-panic on
    # every export. No shipped registry revision does this today; this test fails
    # the moment a future TOML author introduces the collision, which is the signal
    # to teach rendered_casilla_ids about binding-materialised row casillas (or add
    # a registry-build validator forbidding a manifest-required row_field-only
    # casilla).
    for modelo, year, period in _DORMANCY_MODELOS:
        snapshot = resources().modelos.authority.snapshot(modelo, filing_year=year, period=period, on=date(year, 6, 1))
        revision = snapshot.revision
        manifest = revision.completeness_manifest
        assert manifest is not None, modelo
        layout = sorted(revision.export_layouts, key=lambda item: item.id)[0]
        assert layout.format == "fixed_width", modelo

        casilla_field_ids = {
            field.casilla_id
            for record in layout.records
            for field in record.fields
            if field.kind == CasillaFieldKind.CASILLA and field.casilla_id is not None
        }
        row_field_ids: set[str] = set()
        for record in layout.records:
            row_field_ids.update(record.row_field_casilla_ids.values())

        manifest_ids = {casilla.casilla_id for casilla in manifest.casillas}
        row_field_only_required = (manifest_ids & row_field_ids) - casilla_field_ids
        assert not row_field_only_required, (
            f"modelo {modelo}: manifest-required casillas representable only via binding rows "
            f"(would false-panic): {sorted(row_field_only_required)}"
        )


def test_structural_fidelity_holds_for_every_covered_modelo() -> None:
    # The parity gate asserts more than casilla presence: the rendered casilla
    # numbering/segmento must mirror the registry CasillaDefinition, and the
    # rendered record order must follow the registry export-layout declaration
    # order. Both must hold for the real shipped structure of every covered
    # modelo (including the multi-segment M200 and the annual M390), so the
    # fidelity gate is grounded rather than false-firing on legitimate layouts.
    for modelo, _build_draft_fn, headers_fn, filing_year, period in _COVERED:
        provider = _schema_provider(filing_year=filing_year, period=period, modelos=(modelo,))
        subview = provider.get_subview(modelo)
        layout = subview.export_layouts[0]
        manifest = subview.completeness_manifest
        assert manifest is not None, modelo
        headers = headers_fn()
        representable = boe_representable_casilla_ids(layout, headers=headers, schema_provider=provider)

        _assert_record_order_fidelity(modelo=modelo, layout=layout, headers=headers)
        _assert_casilla_metadata_fidelity(
            modelo=modelo,
            manifest=manifest,
            representable=representable,
            casilla_metadata=subview.casilla_record_metadata,
        )

        # Non-vacuous: the metadata fidelity check actually cross-checked at least one
        # representable manifest casilla against the registry declaration.
        cross_checked = [casilla.casilla_id for casilla in manifest.casillas if casilla.casilla_id in representable]
        assert cross_checked, f"modelo {modelo}: metadata fidelity check is vacuous (no representable manifest casilla)"


def test_rendered_casilla_number_drift_panics() -> None:
    # Anti-tautology: mutate a rendered casilla's registry-declared number so it
    # diverges from the manifest copy the gate keys on. The gate must panic,
    # naming the drifted casilla — proving the numbering fidelity assertion bites.
    provider = _schema_provider(modelos=("130",))
    subview = provider.get_subview("130")
    layout = subview.export_layouts[0]
    manifest = subview.completeness_manifest
    assert manifest is not None
    headers = _modelo_130_export_headers()
    representable = boe_representable_casilla_ids(layout, headers=headers, schema_provider=provider)
    target = next(casilla.casilla_id for casilla in manifest.casillas if casilla.casilla_id in representable)

    drifted_metadata = tuple(
        CasillaRecordMetadata(casilla_id=meta.casilla_id, number=f"{meta.number}9", segmento=meta.segmento)
        if meta.casilla_id == target
        else meta
        for meta in subview.casilla_record_metadata
    )

    with pytest.raises(FilingExportError) as exc_info:
        _assert_casilla_metadata_fidelity(
            modelo="130",
            manifest=manifest,
            representable=representable,
            casilla_metadata=drifted_metadata,
        )

    assert target in str(exc_info.value)
    assert "structural-fidelity" in str(exc_info.value)


def test_rendered_casilla_segmento_drift_panics() -> None:
    # Anti-tautology: mutate a rendered casilla's registry-declared segmento so it
    # diverges from the manifest copy. A segmento drift must panic too.
    provider = _schema_provider(modelos=("130",))
    subview = provider.get_subview("130")
    layout = subview.export_layouts[0]
    manifest = subview.completeness_manifest
    assert manifest is not None
    headers = _modelo_130_export_headers()
    representable = boe_representable_casilla_ids(layout, headers=headers, schema_provider=provider)
    target = next(casilla.casilla_id for casilla in manifest.casillas if casilla.casilla_id in representable)

    drifted_metadata = tuple(
        CasillaRecordMetadata(casilla_id=meta.casilla_id, number=meta.number, segmento="DP999999")
        if meta.casilla_id == target
        else meta
        for meta in subview.casilla_record_metadata
    )

    with pytest.raises(FilingExportError) as exc_info:
        _assert_casilla_metadata_fidelity(
            modelo="130",
            manifest=manifest,
            representable=representable,
            casilla_metadata=drifted_metadata,
        )

    assert target in str(exc_info.value)
    assert "DP999999" in str(exc_info.value)


def test_rendered_record_order_permutation_panics() -> None:
    # Anti-tautology: reverse the records' emit orders so the rendered sequence no
    # longer follows the registry declaration order. The record-order fidelity
    # assertion must panic, enumerating the drifted position.
    provider = _schema_provider(modelos=("130",))
    layout = provider.get_subview("130").export_layouts[0]
    headers = _modelo_130_export_headers()
    reversed_orders = list(reversed([record.order for record in layout.records]))
    permuted = layout.model_copy(
        update={
            "records": tuple(
                record.model_copy(update={"order": order})
                for record, order in zip(layout.records, reversed_orders, strict=True)
            )
        }
    )

    with pytest.raises(FilingExportError) as exc_info:
        _assert_record_order_fidelity(modelo="130", layout=permuted, headers=headers)

    assert "record order" in str(exc_info.value)
    assert "structural-fidelity" in str(exc_info.value)


def test_ambiguous_duplicate_record_order_panics() -> None:
    # Anti-tautology: collapse every record onto the same emit order so the
    # rendered sequence is ambiguous. The record-order fidelity assertion must
    # panic rather than emit a non-deterministic record sequence.
    provider = _schema_provider(modelos=("130",))
    layout = provider.get_subview("130").export_layouts[0]
    headers = _modelo_130_export_headers()
    collided = layout.model_copy(
        update={"records": tuple(record.model_copy(update={"order": 0}) for record in layout.records)}
    )

    with pytest.raises(FilingExportError) as exc_info:
        _assert_record_order_fidelity(modelo="130", layout=collided, headers=headers)

    assert "ambiguous" in str(exc_info.value)
