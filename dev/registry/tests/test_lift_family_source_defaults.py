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

from ..compiler.loader import load_modelo_directory
from ..lift_family_source_defaults import (
    REGISTRY_MODELOS_ROOT,
    ModeloLiftFailedError,
    apply_plan,
    lifted_fragment_text,
    load_outcome,
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
    plan = plan_modelo(modelo_dir)
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
    apply_plan(plan_modelo(modelo_dir), modelo_dir.parent)
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
    apply_plan(plan_modelo(modelo_dir), modelo_dir.parent)
    after_first = {path: path.read_text(encoding="utf-8") for path in sorted(modelo_dir.rglob("*.toml"))}

    second = plan_modelo(modelo_dir)
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
    rendered = render_plan([plan_modelo(modelo_dir)], applied=False)
    assert f"manifest {_MODELO}/{_EDITION} fields=binding_source_refs,formula_source_refs" in rendered
    assert "total planned=2 bindings=1 formulas=1 casillas=0 refusals=0" in rendered


def test_the_lift_changes_only_the_lines_it_means_to(tmp_path: Path) -> None:
    """Every file the run writes keeps its LF line endings and its untouched bytes.

    A write that translated line endings would report a change on every line of
    a file the run meant to touch on one, and would leave the tree dirty even
    after a rollback. Asserted on bytes, since text reads hide the difference.
    """
    modelo_dir = _unlifted_modelo(tmp_path)
    before = {path: path.read_bytes() for path in sorted(modelo_dir.rglob("*.toml"))}
    assert all(b"\r\n" not in data for data in before.values()), "the fixture is not LF-authored"

    touched = apply_plan(plan_modelo(modelo_dir), modelo_dir.parent)
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
