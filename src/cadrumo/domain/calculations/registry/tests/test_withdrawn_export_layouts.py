"""Withdrawn export layouts remain absent and explicitly grounded."""

import pytest

from .. import bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REMOVED_LAYOUTS = {
    "modelo-111-fichero-boe",
    "modelo-115-fichero-boe",
    "modelo-123-2019-fichero-boe",
    "modelo-123-fichero-boe",
    "modelo-130-fichero-boe",
    "modelo-200-fichero-boe",
    "modelo-202-2019-2022-fichero-boe",
    "modelo-202-2023-2024-fichero-boe",
    "modelo-202-fichero-boe",
    "modelo-232-2016-fichero-aeat",
    "modelo-232-2018-fichero-aeat",
}
_WITHDRAWN_MODELOS = {"111", "115", "123", "130", "200", "202", "232", "303", "390"}
_REMOVED_EXPORT_PROFILES = {
    "modelo-111-export-record",
    "modelo-115-export-record",
    "modelo-123-2019-export-record",
    "modelo-123-export-record",
}


def test_withdrawn_layouts_have_no_active_registry_capability() -> None:
    authority = bundled_authority()

    for modelo_id in _WITHDRAWN_MODELOS:
        for revision in authority.modelo(modelo_id).revisions.values():
            assert not revision.export_layouts, f"{modelo_id}:{revision.id} resurrected export support"


def test_each_construct_owned_layout_withdrawal_has_one_grounded_decision() -> None:
    authority = bundled_authority()
    decisions = {
        decision.subject_id: decision
        for modelo_id in _WITHDRAWN_MODELOS
        for revision in authority.modelo(modelo_id).revisions.values()
        for decision in revision.support_removal_decisions
        if decision.subject_type == "export_layout"
    }

    assert set(decisions) == _REMOVED_LAYOUTS
    for layout_id, decision in decisions.items():
        assert decision.id == f"{layout_id}-support-removal"
        assert decision.decision == "remove_from_filing_grade"
        assert decision.legal_refs
        assert decision.source_refs


def test_export_record_profiles_removed_without_deleting_pdf_authority() -> None:
    authority = bundled_authority()
    profiles = {
        profile.id: profile.surface
        for modelo_id in {"111", "115", "123"}
        for revision in authority.modelo(modelo_id).revisions.values()
        for profile in revision.extraction_profiles
    }

    assert _REMOVED_EXPORT_PROFILES.isdisjoint(profiles)
    assert profiles == {
        "modelo-111-declaracion-pdf": "declaracion_pdf",
        "modelo-115-declaracion-pdf": "declaracion_pdf",
        "modelo-123-2019-declaracion-pdf": "declaracion_pdf",
        "modelo-123-declaracion-pdf": "declaracion_pdf",
    }
