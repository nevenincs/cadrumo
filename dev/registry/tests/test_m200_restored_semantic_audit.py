from __future__ import annotations

import pytest

from ..analysis import m200_restored_semantic_audit as subject

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_live_restoration_audit_catches_four_review_findings() -> None:
    audits = subject.audit_bundled_restorations()
    by_id = {item.casilla_id: item for item in audits}

    assert len(audits) == 156
    for casilla_id in ("01683", "01684", "01685"):
        finding = by_id[casilla_id]
        assert finding.disposition is subject.AuditDisposition.UNRESOLVED
        assert "exceptional-public-interest" in finding.reason
        assert "innovation semantic role" in finding.reason

    nivelacion = by_id["02239"]
    assert nivelacion.disposition is subject.AuditDisposition.REPAIRABLE
    assert nivelacion.proposed is not None
    assert nivelacion.proposed.semantic_role == "is_reserva_nivelacion_adicion_realizada"
    assert "ley-27-2014:art-105" in nivelacion.proposed.legal_refs
    assert "capitalizacion" in nivelacion.reason


def test_patch_emitter_omits_unresolved_and_emits_only_proved_repair() -> None:
    payload = subject.SemanticPayload(
        section=("unsafe",),
        semantic_role="unsafe",
        data_type="money",
        required=False,
        input_kind="manual",
        legal_refs=(),
        source_refs=("aeat-dr-200-2024",),
    )
    unresolved = subject.RestoredSemanticAudit(
        casilla_id="01683",
        export_field_id="m200-2024.dp200018.f0165",
        official_description="Otras deducciones [01683]",
        template="Otras deducciones [#]",
        path="c01683.toml",
        disposition=subject.AuditDisposition.UNRESOLVED,
        reason="no exact template authority",
        current=payload,
    )

    proposed = subject.SemanticPayload(
        section=("liquidacion_iii", "base_imponible"),
        semantic_role="is_reserva_nivelacion_adicion_realizada",
        data_type="money",
        required=False,
        input_kind="manual",
        legal_refs=("ley-27-2014:art-105",),
        source_refs=("aeat-dr-200-2024",),
    )
    repair = subject.RestoredSemanticAudit(
        casilla_id="02239",
        export_field_id="m200-2024.dp200020b.f0034",
        official_description="Reserva de nivelación [02239]",
        template="Reserva de nivelación [#]",
        path="src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/casillas/c02239.toml",
        disposition=subject.AuditDisposition.REPAIRABLE,
        reason="unique peer",
        current=payload,
        proposed=proposed,
    )

    patch = subject.render_apply_patch((unresolved, repair))

    assert "c02239.toml" in patch
    assert "c01683.toml" not in patch
    assert 'semantic_role = "is_reserva_nivelacion_adicion_realizada"' in patch
    assert 'legal_refs = ["ley-27-2014:art-105"]' in patch
