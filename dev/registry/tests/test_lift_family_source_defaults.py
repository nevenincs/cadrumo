"""Lifting a family's shared ``source_refs`` onto the edition manifest.

Every test drives the real planner and writer over a modelo materialised in
``tmp_path``, and the positive cases run the real loader gate the writer itself
consults, so a lift that produced a tree the registry refuses fails here rather
than in the corpus. Nothing is mocked, stubbed, or skipped.

The tree is a copy of a shipped modelo with its family defaults REMOVED from
the manifest, which is exactly the authoring shape this tool exists to fix: a
hand-built minimal modelo would not carry the binding providers, construct
enrolments, and legal grounding the loader checks, so the one assertion that
matters most -- that the lifted tree still compiles -- could not be made
against it. The copy is read once and written only inside ``tmp_path``.
"""

from __future__ import annotations

import re
import shutil
import tomllib
from pathlib import Path
from typing import Final

import pytest

from cadrumo.domain.calculations.registry.reference_sections import FAMILY_SOURCE_DEFAULT_FIELDS

from ..compiler.loader import load_modelo_directory
from ..lift_family_source_defaults import (
    FAMILIES,
    FAMILY_DEFAULT_KEY,
    REGISTRY_MODELOS_ROOT,
    ModeloLiftFailedError,
    apply_plan,
    lifted_fragment_text,
    load_outcome,
    main,
    plan_modelo,
    render_plan,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: A one-edition modelo whose bindings and formulas all cite the same two
#: documents, so the rule derives a two-reference default from it.
_MODELO: Final = "111"
_EDITION: Final = "2019-y-siguientes"
_DEFAULT: Final = ("aeat-dr-111-2019-v18", "aeat-modelo-111-instructions")
_FAMILY_KEYS: Final = ("binding_source_refs", "formula_source_refs")

#: The families the shared fixture undeclares, and so the only ones these tests
#: plan. Which families are liftable at all is pinned separately, against the
#: domain pairing, by the derivation test at the end of this module.
_UNDER_TEST: Final = ("bindings", "formulas")


def _unlifted_modelo(tmp_path: Path) -> Path:
    """Copy the shipped modelo into ``tmp_path`` and undeclare its family defaults."""
    modelo_dir = tmp_path / "modelos" / _MODELO
    shutil.copytree(REGISTRY_MODELOS_ROOT / _MODELO, modelo_dir)
    manifest = modelo_dir / "revisions" / _EDITION / "revision.toml"
    kept = [
        line
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if not any(line.startswith(f"{key} =") for key in _FAMILY_KEYS)
    ]
    manifest.write_text("\n".join(kept) + "\n", encoding="utf-8", newline="\n")
    return modelo_dir


def _manifest_table(modelo_dir: Path) -> dict[str, object]:
    manifest = modelo_dir / "revisions" / _EDITION / "revision.toml"
    revisions: object = tomllib.loads(manifest.read_text(encoding="utf-8"))["revisions"]
    assert isinstance(revisions, dict)
    table: object = revisions[_EDITION]
    assert isinstance(table, dict)
    return {str(key): value for key, value in table.items()}


def _members(modelo_dir: Path, family: str) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for path in sorted((modelo_dir / "revisions" / _EDITION / family).glob("*.toml")):
        table = tomllib.loads(path.read_text(encoding="utf-8"))["revisions"][_EDITION]
        found.extend(row for row in table.get(family, ()) if isinstance(row, dict))
    return found


def test_undeclared_family_default_is_lifted_and_members_drop_the_restatement(tmp_path: Path) -> None:
    """The derived default lands on the manifest and every member that restated it states none."""
    modelo_dir = _unlifted_modelo(tmp_path)
    plan = plan_modelo(modelo_dir, _UNDER_TEST)
    lifted = {(lift.family, lift.default) for lift in plan.liftable}
    assert lifted == {("bindings", _DEFAULT), ("formulas", _DEFAULT)}

    touched = apply_plan(plan, modelo_dir.parent)
    assert touched, "a planned lift wrote no file"

    table = _manifest_table(modelo_dir)
    assert table["binding_source_refs"] == list(_DEFAULT)
    assert table["formula_source_refs"] == list(_DEFAULT)
    for family in ("bindings", "formulas"):
        restating = [member for member in _members(modelo_dir, family) if "source_refs" in member]
        assert restating == [], f"{family} still restates the lifted default"

    # The lift is only correct if the registry still compiles it, and the
    # members must materialise with exactly the references they stated before.
    revision = load_modelo_directory(modelo_dir).revisions[_EDITION]
    assert revision.binding_source_refs == _DEFAULT
    assert all(binding.source_refs == _DEFAULT for binding in revision.bindings)
    assert all(formula.source_refs == _DEFAULT for formula in revision.formulas)


def test_manifest_default_is_declared_beside_the_casilla_default(tmp_path: Path) -> None:
    """The three grounding keys are one statement and are written together."""
    modelo_dir = _unlifted_modelo(tmp_path)
    apply_plan(plan_modelo(modelo_dir, _UNDER_TEST), modelo_dir.parent)
    lines = (modelo_dir / "revisions" / _EDITION / "revision.toml").read_text(encoding="utf-8").splitlines()
    grounding = [
        index for index, line in enumerate(lines) if re.match(r"^(casilla|binding|formula)_source_refs =", line)
    ]
    assert grounding == list(range(min(grounding), min(grounding) + 3)), "the grounding keys were split apart"


def test_a_member_opening_with_the_default_keeps_only_its_tail(tmp_path: Path) -> None:
    """A longer statement is reduced to its additions rather than dropped or kept whole."""
    modelo_dir = _unlifted_modelo(tmp_path)
    fragment = sorted((modelo_dir / "revisions" / _EDITION / "formulas").glob("*.toml"))[0]
    text = fragment.read_text(encoding="utf-8")
    extended = text.replace(
        'source_refs = ["aeat-dr-111-2019-v18", "aeat-modelo-111-instructions"]',
        'source_refs = ["aeat-dr-111-2019-v18", "aeat-modelo-111-instructions", "aeat-modelo-111-instructions-anexo"]',
        1,
    )
    assert extended != text
    fragment.write_text(extended, encoding="utf-8")

    plan = plan_modelo(modelo_dir, ("formulas",))
    apply_plan(plan, modelo_dir.parent)
    additions = [member.get("additional_source_refs") for member in _members(modelo_dir, "formulas")]
    assert ["aeat-modelo-111-instructions-anexo"] in additions
    assert additions.count(None) == len(additions) - 1


def test_members_that_disagree_refuse_the_lift(tmp_path: Path) -> None:
    """A family with no shared leading run is refused with the rule's own reason, and nothing is written."""
    modelo_dir = _unlifted_modelo(tmp_path)
    # Every member is given its OWN references, so no run of any length opens
    # two of them and the rule has nothing to derive.
    distinct = iter(range(1000))
    pattern = re.compile(r"^(\s*)source_refs = \[.*\]$", re.MULTILINE)
    for fragment in sorted((modelo_dir / "revisions" / _EDITION / "bindings").glob("*.toml")):
        fragment.write_text(
            pattern.sub(
                lambda match: f'{match.group(1)}source_refs = ["aeat-unique-{next(distinct)}"]',
                fragment.read_text(encoding="utf-8"),
            ),
            encoding="utf-8",
        )
    before = (modelo_dir / "revisions" / _EDITION / "revision.toml").read_text(encoding="utf-8")

    plan = plan_modelo(modelo_dir, ("bindings",))
    assert plan.liftable == []
    assert [lift.refusal for lift in plan.refusals] == ["no leading source_refs run is shared by two rows"]
    assert apply_plan(plan, modelo_dir.parent) == []
    assert (modelo_dir / "revisions" / _EDITION / "revision.toml").read_text(encoding="utf-8") == before


def test_a_conflicting_declared_default_is_never_overwritten(tmp_path: Path) -> None:
    """A manifest already declaring a different default outranks the derivation."""
    modelo_dir = _unlifted_modelo(tmp_path)
    manifest = modelo_dir / "revisions" / _EDITION / "revision.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "casilla_source_refs = [", 'binding_source_refs = ["aeat-something-else"]\ncasilla_source_refs = [', 1
        ),
        encoding="utf-8",
    )
    plan = plan_modelo(modelo_dir, ("bindings",))
    assert plan.liftable == []
    assert plan.refusals[0].refusal == (
        "binding_source_refs already declares ['aeat-something-else']; "
        "the rule derives ['aeat-dr-111-2019-v18', 'aeat-modelo-111-instructions']"
    )
    assert _manifest_table(modelo_dir)["binding_source_refs"] == ["aeat-something-else"]


def test_a_second_run_finds_nothing_left_to_lift(tmp_path: Path) -> None:
    """The lift is idempotent: the tree it produces is one it plans no further change to."""
    modelo_dir = _unlifted_modelo(tmp_path)
    apply_plan(plan_modelo(modelo_dir, _UNDER_TEST), modelo_dir.parent)
    after_first = {path: path.read_text(encoding="utf-8") for path in sorted(modelo_dir.rglob("*.toml"))}

    second = plan_modelo(modelo_dir, _UNDER_TEST)
    assert second.liftable == []
    assert second.refusals == []
    assert apply_plan(second, modelo_dir.parent) == []
    assert {path: path.read_text(encoding="utf-8") for path in sorted(modelo_dir.rglob("*.toml"))} == after_first


def test_a_textually_unrewritable_statement_refuses_the_whole_edition(tmp_path: Path) -> None:
    """A multi-line array is refused rather than partially rewritten."""
    modelo_dir = _unlifted_modelo(tmp_path)
    fragment = sorted((modelo_dir / "revisions" / _EDITION / "bindings").glob("*.toml"))[0]
    fragment.write_text(
        fragment.read_text(encoding="utf-8").replace(
            'source_refs = ["aeat-dr-111-2019-v18", "aeat-modelo-111-instructions"]',
            'source_refs = [\n  "aeat-dr-111-2019-v18",\n  "aeat-modelo-111-instructions",\n]',
            1,
        ),
        encoding="utf-8",
    )
    plan = plan_modelo(modelo_dir, ("bindings",))
    assert plan.liftable == []
    assert "not textually rewritable" in plan.refusals[0].refusal


def test_a_write_that_does_not_reparse_is_rolled_back(tmp_path: Path) -> None:
    """The validation gate has teeth: a tree the parser refuses is restored whole and reported.

    The defect is planted rather than simulated -- the manifest already carries
    the edition table twice, so declaring a default into it produces a duplicate
    key -- and the gate is reached through a real parse failure.
    """
    modelo_dir = _unlifted_modelo(tmp_path)
    plan = plan_modelo(modelo_dir, ("formulas",))
    assert plan.liftable, "the fixture planned no lift, so the rollback is unproven"
    manifest = modelo_dir / "revisions" / _EDITION / "revision.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8") + f'\n[revisions."{_EDITION}"]\nformula_source_refs = ["x"]\n',
        encoding="utf-8",
        newline="\n",
    )
    planted = {path: path.read_bytes() for path in sorted(modelo_dir.rglob("*.toml"))}

    with pytest.raises(ModeloLiftFailedError) as raised:
        apply_plan(plan, modelo_dir.parent)
    assert raised.value.modelo == _MODELO
    # Every file this run touched is back, byte for byte; the planted defect remains.
    assert {path: path.read_bytes() for path in sorted(modelo_dir.rglob("*.toml"))} == planted


def test_a_modelo_already_failing_to_load_is_still_lifted(tmp_path: Path) -> None:
    """A defect that is not this tool's does not make a modelo permanently unliftable.

    The corpus is edited by several hands. The gate compares the load outcome
    across the write rather than demanding an absolute pass, so a modelo already
    failing in some way keeps its lift while that way is unchanged.
    """
    modelo_dir = _unlifted_modelo(tmp_path)
    casilla_fragment = sorted((modelo_dir / "revisions" / _EDITION / "casillas").glob("*.toml"))[0]
    casilla_fragment.write_text(
        casilla_fragment.read_text(encoding="utf-8") + f'\n[[revisions."{_EDITION}".casillas]]\nid = "no-such-shape"\n',
        encoding="utf-8",
        newline="\n",
    )
    assert load_outcome(modelo_dir) != "loads", "the planted defect did not break the load, so nothing is proven"

    touched = apply_plan(plan_modelo(modelo_dir, ("formulas",)), modelo_dir.parent)
    assert touched, "a modelo failing for someone else's reason was refused its lift"
    assert _manifest_table(modelo_dir)["formula_source_refs"] == list(_DEFAULT)


def test_lifted_fragment_text_leaves_other_families_and_nested_tables_alone() -> None:
    """Only a member's own top-level statement is rewritten."""
    text = (
        '[[revisions."2025".formulas]]\n'
        'id = "f1"\n'
        'source_refs = ["a", "b"]\n'
        '[[revisions."2025".formulas.source_citations]]\n'
        'source_refs = ["a", "b"]\n'
        '[[revisions."2025".bindings]]\n'
        'id = "b1"\n'
        'source_refs = ["a", "b"]\n'
    )
    rewritten = lifted_fragment_text(text, "2025", "formulas", ("a", "b"))
    assert rewritten.count('source_refs = ["a", "b"]') == 2
    assert '[[revisions."2025".formulas]]\nid = "f1"\n[[revisions."2025".formulas.source_citations]]' in rewritten


def test_render_plan_reports_a_manifest_line_per_edition_it_writes(tmp_path: Path) -> None:
    """Each edition whose manifest the run declares on is named with the fields it gained."""
    modelo_dir = _unlifted_modelo(tmp_path)
    rendered = render_plan([plan_modelo(modelo_dir, _UNDER_TEST)], applied=False)
    assert f"manifest {_MODELO}/{_EDITION} fields=binding_source_refs,formula_source_refs" in rendered
    assert "total planned=2 bindings=1 formulas=1 refusals=0" in rendered


def test_the_lift_changes_only_the_lines_it_means_to(tmp_path: Path) -> None:
    """Every file the run writes keeps its LF line endings and its untouched bytes.

    A write that translated line endings would report a change on every line of
    a file the run meant to touch on one, and would leave the tree dirty even
    after a rollback. Asserted on bytes, since text reads hide the difference.
    """
    modelo_dir = _unlifted_modelo(tmp_path)
    before = {path: path.read_bytes() for path in sorted(modelo_dir.rglob("*.toml"))}
    assert all(b"\r\n" not in data for data in before.values()), "the fixture is not LF-authored"

    touched = apply_plan(plan_modelo(modelo_dir, _UNDER_TEST), modelo_dir.parent)
    for path in touched:
        data = path.read_bytes()
        assert b"\r\n" not in data, f"{path.name} was rewritten with CRLF line endings"
        was, now = before[path].split(b"\n"), data.split(b"\n")
        removed = [line for line in was if line not in now]
        added = [line for line in now if line not in was]
        assert all(line.strip().startswith(b"source_refs =") for line in removed), (
            f"{path.name} dropped a line that is not a lifted source_refs statement: {removed}"
        )
        assert all(
            line.strip().startswith((b"additional_source_refs =", b"binding_source_refs =", b"formula_source_refs ="))
            for line in added
        ), f"{path.name} gained a line the lift does not state: {added}"
    for path, data in before.items():
        if path not in touched:
            assert path.read_bytes() == data, f"{path.name} was rewritten by a lift that does not name it"


def test_a_declared_equal_default_rewrites_the_members_under_it(tmp_path: Path) -> None:
    """An edition that declared the default but never lifted its members is still work.

    Declaring the default and dropping it from the members are two halves of
    one lift. An edition holding only the first half has the restatement the
    tool exists to remove, sitting under a manifest that already states it, so
    the members are rewritten and the correct declaration is left exactly as
    authored rather than overwritten or duplicated.
    """
    modelo_dir = _unlifted_modelo(tmp_path)
    manifest = modelo_dir / "revisions" / _EDITION / "revision.toml"
    declaration = 'binding_source_refs = ["' + '", "'.join(_DEFAULT) + '"]'
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "casilla_source_refs = [", f"{declaration}\ncasilla_source_refs = [", 1
        ),
        encoding="utf-8",
        newline="\n",
    )
    assert [member for member in _members(modelo_dir, "bindings") if "source_refs" in member], (
        "the fixture's members do not restate the declared default"
    )

    plan = plan_modelo(modelo_dir, ("bindings",))
    assert plan.refusals == []
    lifted = plan.liftable
    assert [(lift.family, lift.default, lift.manifest_declared) for lift in lifted] == [("bindings", _DEFAULT, True)]
    assert plan.manifests == {}, "an already-correct declaration was queued for rewriting"

    touched = apply_plan(plan, modelo_dir.parent)
    assert touched, "the planned member rewrite wrote no file"
    assert manifest not in touched, "the manifest was rewritten although it already declared the default"
    assert manifest.read_text(encoding="utf-8").count("binding_source_refs =") == 1

    restating = [member for member in _members(modelo_dir, "bindings") if "source_refs" in member]
    assert restating == [], "the members still restate the declared default"
    revision = load_modelo_directory(modelo_dir).revisions[_EDITION]
    assert all(binding.source_refs == _DEFAULT for binding in revision.bindings)

    second = plan_modelo(modelo_dir, ("bindings",))
    assert second.liftable == [] and second.refusals == []


def test_the_applied_total_counts_the_files_the_run_actually_wrote(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The summary reports writes, not plan rows, and names them per edition.

    A planned lift and a written file are different facts, so the applied
    total is read back off the tree: it must equal the number of files whose
    bytes the run actually changed.
    """
    modelo_dir = _unlifted_modelo(tmp_path)
    before = {path: path.read_bytes() for path in sorted(modelo_dir.rglob("*.toml"))}

    assert (
        main(
            [
                "--modelo",
                _MODELO,
                "--modelos-root",
                str(modelo_dir.parent),
                "--apply",
                *[arg for family in _UNDER_TEST for arg in ("--family", family)],
            ]
        )
        == 0
    )
    rendered = capsys.readouterr().out

    changed = [path for path, data in before.items() if path.read_bytes() != data]
    assert changed, "the run wrote nothing to count"
    assert f"total applied={len(changed)} " in rendered
    assert f"wrote modelo={_MODELO} edition={_EDITION} files={len(changed)}" in rendered


def test_the_liftable_families_are_read_from_the_domain_pairing() -> None:
    """The family surfaces follow the domain's pairing rather than a list restated here.

    The loader fills a member's default by walking
    ``FAMILY_SOURCE_DEFAULT_FIELDS``, so a tool that carried its own list of
    families could only ever disagree with it. Every paired family must be an
    offered choice, must map to the domain's own manifest key, and must be one
    whose members this tool rewrites; the casilla family is the single
    declare-only exception, because another pass owns its member statements.
    """
    paired = dict(FAMILY_SOURCE_DEFAULT_FIELDS)
    assert paired, "the domain declares no family source defaults"
    for family, key in paired.items():
        assert family in FAMILIES, f"{family} is paired by the domain but is not an offered choice"
        assert FAMILY_DEFAULT_KEY[family] == key, f"{family} maps to a key the domain does not pair it with"

    assert set(FAMILIES) == set(paired) | {"casillas"}
    assert FAMILY_DEFAULT_KEY["casillas"] == "casilla_source_refs"
    assert "casillas" not in paired, "the casilla family's members are owned by another pass"
