from __future__ import annotations

from dataclasses import replace

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..analysis import m200_2024_template_adjudications as subject
from ..analysis.m200_restored_semantic_audit import AuditDisposition

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_compiles_closed_target_only_same_template_cohort() -> None:
    authority = subject.compile_m200_2024_same_template_authority()

    assert tuple(item.casilla_id for item in authority.adjudications) == ("00942", "02239", "01603", "02412")
    assert authority.source_sha256 == subject.TARGET_SOURCE_SHA256
    assert authority.manual_source_sha256 == subject.MANUAL_SOURCE_SHA256
    assert "pending independent review" in authority.reviewed_by
    assert all(
        "2025" not in render
        for render in (
            subject.render_canonical_declaration(authority, item.casilla_id) for item in authority.adjudications
        )
    )
    subject.verify_canonical_declarations(authority)


def test_refuses_cross_revision_only_or_unreviewed_cohort_member(monkeypatch) -> None:
    audits = list(subject.audit_bundled_restorations())
    target = next(row for row in audits if row.casilla_id == "00942")
    audits[audits.index(target)] = replace(target, disposition=AuditDisposition.UNRESOLVED)
    monkeypatch.setattr(subject, "audit_bundled_restorations", lambda: tuple(audits))

    with pytest.raises(RegistryValidationError, match="not a repairable same-year template"):
        subject.compile_m200_2024_same_template_authority()


def test_refuses_target_label_drift(monkeypatch) -> None:
    audits = list(subject.audit_bundled_restorations())
    target = next(row for row in audits if row.casilla_id == "02239")
    audits[audits.index(target)] = replace(target, official_description="drifted official label")
    monkeypatch.setattr(subject, "audit_bundled_restorations", lambda: tuple(audits))

    with pytest.raises(RegistryValidationError, match="official label drifted"):
        subject.compile_m200_2024_same_template_authority()


def test_refuses_hand_authored_canonical_declaration_drift(monkeypatch, tmp_path) -> None:
    authority = subject.compile_m200_2024_same_template_authority()
    generated = subject.render_canonical_declaration(authority, "00942")
    target = tmp_path / "c00942.toml"
    target.write_text(generated.replace("is_deduccion_donativos_prioritarias", "drifted"), encoding="utf-8")
    monkeypatch.setattr(subject, "bundled_path", lambda *_parts: tmp_path)

    with pytest.raises(RegistryValidationError, match="not compiler-identical"):
        subject.verify_canonical_declarations(authority)


def test_promoted_candidate_ids_refuses_a_preconstructed_compiler_receipt() -> None:
    authority = subject.compile_m200_2024_same_template_authority()

    with pytest.raises(RegistryValidationError, match="compiler receipt/provenance drifted"):
        subject.promoted_candidate_ids(replace(authority, reviewed_by="forged"))
