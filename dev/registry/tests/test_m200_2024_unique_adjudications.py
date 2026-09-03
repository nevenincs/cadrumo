from __future__ import annotations

from dataclasses import replace

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..analysis import m200_2024_unique_adjudications as subject

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_compiles_the_closed_36_member_target_evidence_cohort() -> None:
    authority = subject.compile_m200_2024_unique_authority()

    assert len(authority.adjudications) == 36
    assert "00942" not in {row.casilla_id for row in authority.adjudications}
    assert {"01134", "01135", "01136", "01469"} <= {row.casilla_id for row in authority.adjudications}
    assert all(
        len(row.official_label_sha256) == 64 and len(row.semantic_payload_sha256) == 64
        for row in authority.adjudications
    )
    subject.verify_canonical_declarations(authority)
    assert subject.promoted_candidate_ids(authority) == {row.casilla_id for row in authority.adjudications}


def test_column_distinctions_are_part_of_the_target_receipt() -> None:
    authority = subject.compile_m200_2024_unique_authority()
    rows = {row.casilla_id: row for row in authority.adjudications}

    assert len({rows[identifier].official_column for identifier in ("01134", "01135", "01136", "01469")}) == 4
    assert (
        rows["01134"].semantic_role
        == rows["01135"].semantic_role
        == rows["01136"].semantic_role
        == rows["01469"].semantic_role
    )


def test_receipt_refuses_tampered_canonical_bytes(tmp_path) -> None:
    authority = subject.compile_m200_2024_unique_authority()
    for row in authority.adjudications:
        path = tmp_path / f"c{row.casilla_id.replace(':', '+')}.toml"
        path.write_text(subject.render_canonical_declaration(authority, row.casilla_id), encoding="utf-8")
    subject.verify_canonical_declarations(authority, casillas_root=tmp_path)
    target = tmp_path / "c01134.toml"
    target.write_text(target.read_text(encoding="utf-8").replace("exceso_cuota", "drifted", 1), encoding="utf-8")

    with pytest.raises(RegistryValidationError, match="not compiler-identical"):
        subject.verify_canonical_declarations(authority, casillas_root=tmp_path)


def test_refuses_a_preconstructed_receipt_and_a_missing_manual_anchor(monkeypatch) -> None:
    authority = subject.compile_m200_2024_unique_authority()
    with pytest.raises(RegistryValidationError, match="receipt/provenance drifted"):
        subject.promoted_candidate_ids(replace(authority, reviewed_by="forged"))

    fields, maps, _manual = subject._target_fields_and_map()
    monkeypatch.setattr(subject, "_target_fields_and_map", lambda: (fields, maps, ""))
    with pytest.raises(RegistryValidationError, match="manual evidence drifted"):
        subject.compile_m200_2024_unique_authority()


def test_withheld_01403_cannot_enter_the_unique_receipt(monkeypatch) -> None:
    audits = list(subject.audit_bundled_restorations())
    row = next(item for item in audits if item.casilla_id == "01403")
    audits[audits.index(row)] = replace(row, cross_revision_status="unique_non_authoritative")
    monkeypatch.setattr(subject, "audit_bundled_restorations", lambda: tuple(audits))

    with pytest.raises(RegistryValidationError, match=r"source candidate membership drifted|must remain outside"):
        subject.compile_m200_2024_unique_authority()
