"""Contract tests for the reviewed, disjoint M200/2024 S14/S15 compiler."""

from __future__ import annotations

from dataclasses import replace

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..analysis import m200_2024_blocker_adjudications as subject

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_compiles_the_closed_disjoint_s14_s15_cohort_and_live_bytes() -> None:
    authority = subject.compile_m200_2024_blocker_authority()
    assert len(authority.adjudications) == 116
    assert {row.source_cohort for row in authority.adjudications} == {
        "conflicting_non_authoritative",
        "no_applicable_match",
    }
    assert not {row.casilla_id for row in authority.adjudications} & subject.S12_MEMBERS
    subject.verify_canonical_declarations(authority)


def test_refuses_a_target_label_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    worklist = subject.build_worklist()
    target = next(row for row in worklist["member"] if row["casilla_id"] == "00093")
    target["official_description"] = "drifted"
    monkeypatch.setattr(subject, "build_worklist", lambda: worklist)
    with pytest.raises(RegistryValidationError, match="official label drifted"):
        subject.compile_m200_2024_blocker_authority()


def test_refuses_hand_authored_declaration_drift(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    authority = subject.compile_m200_2024_blocker_authority()
    target = tmp_path / "registry" / "aeat" / "modelos" / "200" / "revisions" / "2024" / "casillas"
    target.mkdir(parents=True)
    for row in authority.adjudications:
        body = subject.render_canonical_declaration(authority, row.casilla_id)
        if row.casilla_id == "00093":
            body = body.replace("required = false", "required = true")
        (target / f"c{row.casilla_id}.toml").write_text(body, encoding="utf-8")
    monkeypatch.setattr(subject, "bundled_path", lambda *_parts: tmp_path / "registry" / "aeat")
    with pytest.raises(RegistryValidationError, match="not compiler-identical"):
        subject.verify_canonical_declarations(authority)


def test_refuses_a_hand_constructed_receipt_even_when_its_ids_are_plausible() -> None:
    authority = subject.compile_m200_2024_blocker_authority()
    forged = replace(authority, reviewed_by="forged")
    with pytest.raises(RegistryValidationError, match="receipt/provenance drifted"):
        subject.promoted_candidate_ids(forged)
