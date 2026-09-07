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
        path = subject.unique_declaration_path(tmp_path, row.casilla_id)
        path.write_bytes(subject.render_canonical_declaration(authority, row.casilla_id).encode("utf-8"))
    subject.verify_canonical_declarations(authority, casillas_root=tmp_path)
    target = tmp_path / "c01134.toml"
    original_text = target.read_bytes().decode("utf-8")
    assert "exceso_cuota" in original_text
    tampered_text = original_text.replace("exceso_cuota", "drifted", 1)
    assert tampered_text != original_text
    target.write_bytes(tampered_text.encode("utf-8"))

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


def test_marking_01403_non_authoritative_drifts_the_closed_membership(monkeypatch) -> None:
    """Withholding 01403 through the audit trail, not the closed-id set, is the only sanctioned route.

    ``_require_closed_membership`` derives its "who is withheld" side from the audit rather than
    trusting the closed 36-member id set to say so on its own; flipping 01403 non-authoritative
    without also removing it from the closed set breaks that cross-check.
    """
    audits = list(subject.audit_bundled_restorations())
    row = next(item for item in audits if item.casilla_id == "01403")
    audits[audits.index(row)] = replace(row, cross_revision_status="unique_non_authoritative")
    monkeypatch.setattr(subject, "audit_bundled_restorations", lambda: tuple(audits))

    with pytest.raises(RegistryValidationError, match="source candidate membership drifted"):
        subject.compile_m200_2024_unique_authority()


def test_withheld_01403_cannot_enter_the_unique_receipt() -> None:
    """01403 stays out only while it looks like a live, unresolved candidate.

    This is the guard the closed-membership check above cannot reach: it fires whenever the audit
    row stops backing the deliberate exclusion -- the row vanishes, is already flagged
    non-authoritative through other means, carries no proposed value, or already agrees with the
    current one -- so a change upstream that quietly resolves 01403 is not read as permission to
    admit it.
    """
    audits = tuple(item for item in subject.audit_bundled_restorations() if item.casilla_id != "01403")

    with pytest.raises(RegistryValidationError, match="must remain outside"):
        subject._require_withheld_01403(audits=audits)
