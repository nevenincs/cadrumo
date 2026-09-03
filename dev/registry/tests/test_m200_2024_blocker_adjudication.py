"""Focused contract tests for the target-only M200/2024 blocker worklist."""

from __future__ import annotations

import pytest

from ..analysis import m200_2024_blocker_adjudication as subject

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture(scope="module")
def worklist() -> dict[str, object]:
    return subject.build_worklist()


def test_worklist_is_closed_non_authoritative_and_target_only(worklist: dict[str, object]) -> None:
    assert worklist["authority_status"] == "proposal_only_non_authoritative"
    assert worklist["policy"] == {
        "target_first": True,
        "sibling_semantics_used_as_authority": False,
        "canonical_write_path": False,
        "geometry_source": "parsed_pinned_official_record_design",
    }
    assert worklist["counts"] == {
        "conflicting_non_authoritative": 17,
        "no_applicable_match": 102,
        "safely_compilable": 119,
        "unresolved_refusal": 0,
    }


def test_every_member_has_exact_target_design_and_manual_evidence(worklist: dict[str, object]) -> None:
    members = worklist["member"]
    assert isinstance(members, list)
    assert len(members) == 119
    assert len({row["export_field_id"] for row in members}) == 119
    for row in members:
        assert row["adjudication"] == "safely_compilable_from_target_2024"
        assert row["refusal"] is None
        design = row["record_design_locator"]
        assert design["source_ref"] == subject.TARGET_SOURCE_REF
        assert design["sha256"] == subject.TARGET_SOURCE_SHA256
        assert design["sheet"] == design["record_identity"]
        assert isinstance(design["source_row"], int)
        assert design["source_cell"]
        assert design["ordinal"]
        assert isinstance(design["offset"], int)
        assert isinstance(design["length"], int)
        assert design["aeat_type"] == "Num"
        manual = row["manual_locator"]
        assert manual["source_ref"] == subject.MANUAL_SOURCE_REF
        assert manual["sha256"] == subject.MANUAL_SOURCE_SHA256
        assert manual["pages"]
        assert row["legal_locator"]["provision"]


def test_high_risk_families_carry_target_year_provisions(worklist: dict[str, object]) -> None:
    by_id = {row["casilla_id"]: row for row in worklist["member"]}
    expected = {
        "00093": "artículo 1.7 Ley 38/2022",
        "02971": "artículo 2.6 Ley 38/2022",
        "02365": "disposición adicional tercera del Real Decreto-ley 17/2020",
        "00948": "artículo 22 Ley 49/2002",
        "01982": "artículo 16.2 LIS",
        "02239": "artículo 105 LIS",
        "00923": "artículo 27 Ley 19/1994",
        "01708": "disposición adicional 70.Cuatro Ley 31/2022",
        "03250": "artículo 36.2 LIS y disposición adicional 14 Ley 19/1994",
    }
    assert {identifier: by_id[identifier]["legal_locator"]["provision"] for identifier in expected} == expected


def test_module_exposes_no_apply_path() -> None:
    assert not hasattr(subject, "apply")
    assert not hasattr(subject, "render_apply_patch")
