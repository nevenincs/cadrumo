"""Behaviour of the family-wide edition-token collapse in the identifier rename tool.

Every case builds an isolated temporary registry tree and writes only inside it,
so the contributor's working tree is never touched and the detector teeth are
proven against real fragments rather than against a patched module. The
fragments are authored here rather than copied wholesale, because what is under
test is the rule -- which identifiers carry an edition token, which collapse,
which are refused -- and an authored fixture states each case in one place a
reader can check against the assertion.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..analysis.edition_delta_status import edition_token_in_identifier
from ..rename_formula_binding_identifiers import (
    FamilyWithoutIdentityError,
    apply_family_collapse,
    data_keyed_families,
    family_data_fields,
    id_keyed_families,
    is_filing_coordinate_annotation,
    plan_family_collapse,
    strip_identifier_token,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

MODELO = "131"
EDITION = "2024"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.lstrip("\n"), encoding="utf-8")


def _seed(root: Path) -> Path:
    """Build a one-edition modelo carrying a mix of stable and edition-keyed ids."""
    edition_dir = root / MODELO / "revisions" / EDITION
    _write(
        edition_dir / "revision.toml",
        f"""
[revisions."{EDITION}"]
valid_from = 2024-01-01
authority_grade = "filing"
""",
    )
    _write(
        edition_dir / "parameters" / "0001-parameters.toml",
        f"""
[[revisions."{EDITION}".parameters]]
id = "modelo-{MODELO}-{EDITION}-modulo-personal"
value = "1.00"

[[revisions."{EDITION}".parameters]]
id = "modelo-{MODELO}-reduccion-general"
value = "0.05"
""",
    )
    _write(
        edition_dir / "constructs" / "0001-constructs.toml",
        f"""
[[revisions."{EDITION}".constructs]]
id = "modelo-{MODELO}-{EDITION}-modulos"
parameters = ["modelo-{MODELO}-{EDITION}-modulo-personal", "modelo-{MODELO}-reduccion-general"]
""",
    )
    _write(
        edition_dir / "dependency_classifications" / "0001-dependencies.toml",
        f"""
[[revisions."{EDITION}".dependency_classifications]]
id = "modelo-{MODELO}-{EDITION}-dep"
target_constructs = ["modelo-{MODELO}-{EDITION}-modulos"]
""",
    )
    return edition_dir


def test_keyed_members_collapse_and_stable_members_are_untouched(tmp_path: Path) -> None:
    """A mixed family loses the edition token from the keyed id and keeps the stable one."""
    _seed(tmp_path)

    plan = plan_family_collapse(MODELO, ("parameters",), modelos_root=tmp_path)

    assert plan.rename_map == {f"modelo-{MODELO}-{EDITION}-modulo-personal": f"modelo-{MODELO}-modulo-personal"}
    assert plan.per_family() == {"parameters": 1}
    assert not plan.collisions
    assert not plan.refusals


def test_references_in_other_families_are_rewritten_in_the_same_pass(tmp_path: Path) -> None:
    """A construct member list and a dependency classification follow the rename."""
    edition_dir = _seed(tmp_path)

    plan = plan_family_collapse(MODELO, ("parameters", "constructs"), modelos_root=tmp_path)
    touched, hits = apply_family_collapse(plan, modelos_root=tmp_path, mappings_root=tmp_path / "absent", code_files=())

    construct_text = (edition_dir / "constructs" / "0001-constructs.toml").read_text(encoding="utf-8")
    dependency_text = (edition_dir / "dependency_classifications" / "0001-dependencies.toml").read_text(
        encoding="utf-8"
    )
    assert f"modelo-{MODELO}-{EDITION}-modulo-personal" not in construct_text
    assert f'"modelo-{MODELO}-modulo-personal"' in construct_text
    assert f'"modelo-{MODELO}-reduccion-general"' in construct_text
    # The construct's own id collapsed too, and the classification that names it
    # followed in the same pass rather than being left pointing at a dead id.
    assert f'target_constructs = ["modelo-{MODELO}-modulos"]' in dependency_text
    assert hits >= 4
    assert len(touched) == 3


def test_a_collapse_onto_an_existing_id_is_refused_as_a_collision(tmp_path: Path) -> None:
    """Two members of one edition that collapse onto one name are both refused."""
    edition_dir = _seed(tmp_path)
    _write(
        edition_dir / "verification_expectations" / "0001-expectations.toml",
        f"""
[[revisions."{EDITION}".verification_expectations]]
id = "modelo-{MODELO}-{EDITION}-cuota-chain"

[[revisions."{EDITION}".verification_expectations]]
id = "modelo-{MODELO}-cuota-chain"
""",
    )

    plan = plan_family_collapse(MODELO, ("verification_expectations",), modelos_root=tmp_path)

    assert not plan.renames
    assert len(plan.collisions) == 1
    collision = plan.collisions[0]
    assert f"modelo-{MODELO}-{EDITION}-cuota-chain" in collision
    assert f"modelo-{MODELO}-cuota-chain" in collision
    assert "verification_expectations" in collision
    assert EDITION in collision


def test_generated_export_layout_ids_are_skipped_and_listed(tmp_path: Path) -> None:
    """The generator's own layout id is reported apart and never renamed."""
    edition_dir = _seed(tmp_path)
    _write(
        edition_dir / "export_layouts" / "0001-authored.toml",
        f"""
[[revisions."{EDITION}".export_layouts]]
id = "modelo-{MODELO}-{EDITION}-fichero-boe"
""",
    )
    _write(
        edition_dir / "export" / "0001-generated.toml",
        f"""
[[revisions."{EDITION}".export_layouts]]
id = "generated-modelo-{MODELO}-{EDITION}-fichero"
""",
    )

    plan = plan_family_collapse(MODELO, ("export_layouts",), modelos_root=tmp_path)

    assert plan.rename_map == {f"modelo-{MODELO}-{EDITION}-fichero-boe": f"modelo-{MODELO}-fichero-boe"}
    assert plan.generated_skipped == [f"{MODELO} {EDITION} export_layouts generated-modelo-{MODELO}-{EDITION}-fichero"]


def test_a_qualified_edition_id_collapses_as_one_whole_token(tmp_path: Path) -> None:
    """Modelo 303's two 2024 editions both lose their whole qualifier, not just the year."""
    modelo = "303"
    for edition, suffix in (("2024-hasta-08-y-2t", "hasta"), ("2024-desde-09-y-3t", "desde")):
        edition_dir = tmp_path / modelo / "revisions" / edition
        _write(
            edition_dir / "revision.toml",
            f'[revisions."{edition}"]\nvalid_from = 2024-01-01\n',
        )
        _write(
            edition_dir / "verification_expectations" / f"0001-{suffix}.toml",
            f"""
[[revisions."{edition}".verification_expectations]]
id = "modelo-{modelo}-{edition}-reconcile-when-present"
""",
        )

    plans = [plan_family_collapse(modelo, ("verification_expectations",), modelos_root=tmp_path)]

    collapsed = {new for plan in plans for new in plan.rename_map.values()}
    assert collapsed == {f"modelo-{modelo}-reconcile-when-present"}
    assert all(not plan.collisions and not plan.refusals for plan in plans)


def test_a_year_range_is_not_an_edition_token(tmp_path: Path) -> None:
    """A ``NNNN-NNNN`` validity range carried by a box does not fire the collapse.

    The tokeniser and the removal must agree on this, so both are asserted: a
    removal that read the range as a token would cut it in half, and a tokeniser
    that reported one would make every ranged box a finding.
    """
    edition = "2016-2017"
    identifier = "modelo-232-page_02.2001-2017"

    assert edition_token_in_identifier(identifier, edition) is None

    # The edition's own id, spelled whole, still collapses even though it is
    # itself a four-digit range.
    whole = f"modelo-232-{edition}-vinculada"
    assert edition_token_in_identifier(whole, edition) == edition
    assert strip_identifier_token(whole, edition) == "modelo-232-vinculada"


def test_every_enrolled_family_is_read_off_the_schema_and_others_are_refused() -> None:
    """The family roster comes from the revision model, and a family without an id is refused."""
    enrolled = id_keyed_families()

    assert "casillas" not in enrolled
    assert {"parameters", "bindings", "formulas", "constructs", "deadline_windows"} <= set(enrolled)
    # Declared on ModeloRevision as a SCHEMA_FAMILY, but its member model carries
    # no id, so it cannot join a collapse that keys on one.
    with pytest.raises(FamilyWithoutIdentityError):
        plan_family_collapse(MODELO, ("projection_endpoints",))


def test_a_year_the_member_states_as_its_own_datum_is_never_collapsed(tmp_path: Path) -> None:
    """A deadline window's ``filing_year`` is the row's subject, not the edition restating itself.

    Modelo 763's ``2013-2014`` edition declares one window per quarter per
    filing year. Both years are edition years, so the token test alone would
    collapse ``modelo-763-2013-1t`` and ``modelo-763-2014-1t`` onto one name and
    lose a filing year. The typed ``filing_year`` field is what tells them apart,
    and the exemption is read off that field rather than guessed from the id.
    """
    modelo = "763"
    edition = "2013-2014"
    edition_dir = tmp_path / modelo / "revisions" / edition
    _write(edition_dir / "revision.toml", f'[revisions."{edition}"]\nvalid_from = 2013-01-01\n')
    _write(
        edition_dir / "deadline_windows" / "0001-windows.toml",
        f"""
[[revisions."{edition}".deadline_windows]]
id = "modelo-{modelo}-2013-1t"
filing_year = 2013

[[revisions."{edition}".deadline_windows]]
id = "modelo-{modelo}-2014-1t"
filing_year = 2014

[[revisions."{edition}".deadline_windows]]
id = "modelo-{modelo}-2013-resumen"
""",
    )

    plan = plan_family_collapse(modelo, ("deadline_windows",), modelos_root=tmp_path)

    assert not plan.collisions
    assert plan.rename_map == {}
    assert plan.refusals == [
        f"{modelo} deadline_windows: members are identified by the filing coordinate they state "
        "(filing_year, period), so no id in this family is a rename candidate"
    ]


def test_a_family_identified_by_a_filing_coordinate_is_withheld_whole() -> None:
    """Deadline windows are a ``(filing_year, period)`` cell, so no window id is a candidate.

    The exemption is structural rather than per member: modelo 763's edition
    ``2018-4t`` IS the fourth quarter of 2018, so its window's edition token and
    its filing coordinate are the same characters, and a rule that protected
    only the four-digit-year match would still collapse the qualified edition id
    and lose the cell.
    """
    assert family_data_fields("deadline_windows") == ("filing_year", "period")
    assert family_data_fields("parameters") == ()
    assert data_keyed_families() == ("deadline_windows",)


def test_two_keyed_members_of_sibling_editions_that_share_a_spelling_are_refused(tmp_path: Path) -> None:
    """A rename is withdrawn when the modelo's post-image would give two members one name.

    Modelo 210 spells ``modelo-210-procedure-2025`` and
    ``modelo-210-procedure-2026`` in BOTH of its editions. Each edition carries
    a token only for its own year, so a per-edition gate sees one rename and no
    conflict -- but the rewrite is textual and corpus-wide, so applying both
    editions' plans lands the two ids on one name in each edition. Only the
    whole post-image shows it.
    """
    modelo = "210"
    for edition in ("2025", "2026-y-siguientes"):
        edition_dir = tmp_path / modelo / "revisions" / edition
        _write(edition_dir / "revision.toml", f'[revisions."{edition}"]\nvalid_from = 2025-01-01\n')
        _write(
            edition_dir / "workbook_parity_refs" / "0001-refs.toml",
            f"""
[[revisions."{edition}".workbook_parity_refs]]
id = "modelo-{modelo}-procedure-2025"

[[revisions."{edition}".workbook_parity_refs]]
id = "modelo-{modelo}-procedure-2026"
""",
        )

    plan = plan_family_collapse(modelo, ("workbook_parity_refs",), modelos_root=tmp_path)

    assert plan.rename_map == {}
    assert plan.collisions
    assert all(f"modelo-{modelo}-procedure" in collision for collision in plan.collisions)


def test_the_data_keyed_exemption_is_decided_by_type_and_not_by_field_name() -> None:
    """A coordinate is a coordinate because of its TYPE, whatever it is called.

    The exemption used to match the names ``year`` and ``period`` and any field
    ending in ``_year``/``_period``. That reads the author's spelling instead of
    the schema's guarantee, in both directions: a Spanish-named ``ejercicio``
    coordinate is a filing year and would have been collapsed, while a
    ``grace_period`` duration is a number of days and would have been exempted.
    Both are decided correctly here off the declared type.
    """
    from datetime import timedelta

    from cadrumo.core.filing_year import FilingYear
    from cadrumo.core.period import Period, RegistrySelectorPeriodCode
    from cadrumo.domain.calculations.registry.schema_scalars import PeriodCode

    assert is_filing_coordinate_annotation(FilingYear)
    assert is_filing_coordinate_annotation(Period)
    assert is_filing_coordinate_annotation(PeriodCode)
    assert is_filing_coordinate_annotation(RegistrySelectorPeriodCode)
    # An optional coordinate is still a coordinate.
    assert is_filing_coordinate_annotation(FilingYear | None)
    # A bare int is not: the constraint is what makes it a filing year.
    assert not is_filing_coordinate_annotation(int)
    assert not is_filing_coordinate_annotation(str)
    assert not is_filing_coordinate_annotation(timedelta)
    # A COLLECTION of period codes is the coverage of a row, not its identity.
    assert not is_filing_coordinate_annotation(tuple[RegistrySelectorPeriodCode, ...])


def test_the_typed_rule_keeps_deadline_windows_withheld_and_schedules_in_scope() -> None:
    """The structural rule reaches the same classification the shipped corpus needs.

    ``deadline_windows`` stays withheld: its ``filing_year`` is a ``FilingYear``
    and its ``period`` is a ``Period``, so a window IS a filing cell. Filing
    schedules stay IN scope: a schedule declares ``periods`` -- the tuple of
    periods it covers -- and covering a period is not being identified by one,
    which is why ``modelo-303-trimestral`` names no period at all.
    """
    assert family_data_fields("deadline_windows") == ("filing_year", "period")
    assert family_data_fields("filing_schedules") == ()
    assert data_keyed_families() == ("deadline_windows",)
