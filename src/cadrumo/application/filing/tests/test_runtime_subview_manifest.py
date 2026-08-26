"""The export subview projects the revision calculation-completeness manifest.

The fichero-BOE export parity gate reads ``subview.completeness_manifest`` at the
render choke point to assert the rendered ``.boe`` mirrors the official
modelo-revision structure. This gate proves the projection carries the exact
manifest the registry snapshot declares, so the export path sees the real
authority rather than a dropped field.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from .. import build_runtime_schema_provider
from ..runtime import RegistryModeloSubview, _subview_from_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_subview_projects_revision_completeness_manifest() -> None:
    # Modelo 130 1T/2025 declares a completeness manifest (it is a covered
    # modelo in the workbook parity gate), so its subview must carry it intact.
    snapshot = bundled_authority().snapshot("130", filing_year=2025, period="1T", on=date(2025, 4, 1))
    assert snapshot.revision.completeness_manifest is not None

    subview = _subview_from_snapshot(snapshot)

    assert subview.has_completeness_manifest()
    assert subview.completeness_manifest == snapshot.revision.completeness_manifest


def test_build_runtime_schema_provider_subview_carries_manifest() -> None:
    provider = build_runtime_schema_provider(modelos=("130",))

    subview = provider.get_subview("130")

    assert subview.has_completeness_manifest()
    manifest = subview.completeness_manifest
    assert manifest is not None
    assert manifest.casillas


def test_subview_without_manifest_reports_absence() -> None:
    # A revision with no completeness manifest projects ``None`` and the
    # accessor reports its absence, so the export path routes to a coverage
    # advisory rather than asserting parity against nothing.
    bare = RegistryModeloSubview(
        modelo_id="000",
        revision_id="rev",
        schema_version="registry:000:rev",
        cadence="anual",
        period_selector_periods=("0A",),
        legal_ref_ids=(),
        source_ref_ids=(),
        extraction_profile_ids=(),
        verification_expectation_ids=(),
        reconciliation_total_casilla_ids={},
        export_layout_ids=(),
        export_layouts=(),
        application_link_ids=(),
        deadline_window_ids=(),
        completeness_manifest=None,
    )

    assert bare.completeness_manifest is None
    assert not bare.has_completeness_manifest()
