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
from cadrumo.domain.calculations.registry.errors import RegistryLoadError

from ..compiler.loader import load_modelo_directory
from ..corpus_write import CRLF, LF, detect_newline, verify_written, write_preserving_newlines
from ..lift_family_source_defaults import (
    FAMILIES,
    FAMILY_DEFAULT_KEY,
    REGISTRY_MODELOS_ROOT,
    EditionLift,
    ModeloLiftFailedError,
    _cap_refusal,
    _live_inherited_ids,
    _member_ids,
    _revision_model,
    _unreproducible_statements,
    apply_plan,
    iter_modelo_dirs,
    lifted_fragment_text,
    load_outcome,
    main,
    plan_modelo,
    render_plan,
)
from ..run_exclusions import FROZEN_MODELOS, collect_exclusions, excluded_editions, parse_exclusions_file

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

#: A modelo whose latest edition inherits this family from its predecessor
#: rather than restating it. Lifting the predecessor without carrying the
#: default is exactly what broke this edition's load.
_INHERITING_MODELO: Final = "303"
_INHERITING_FAMILY: Final = "filing_schedules"


def _restate_members(edition_dir: Path, family: str, default: tuple[str, ...]) -> None:
    """Put ``default`` back into every member of ``family`` as its own ``source_refs``.

    The inverse of the member-side lift, and the reason this fixture does not
    depend on what the shipped corpus happens to state today: a modelo that has
    already been lifted states nothing per member, and a fixture reading that
    shape would exercise the "states no source_refs" branch of the rule no
    matter which branch the test meant to reach. Restating from the manifest
    default the fixture is about to remove reconstructs the full-copy authoring
    shape deterministically, and a member carrying a tail is folded back into
    one statement, which is exactly the shape the tail rule reduces again.
    """
    header = re.compile(
        rf"""^\[\[revisions\.(?:"{re.escape(edition_dir.name)}"|{re.escape(edition_dir.name)})\.{family}\]\]\s*$"""
    )
    for path in sorted(edition_dir.rglob("*.toml")):
        lines = path.read_text(encoding="utf-8").splitlines()
        rebuilt: list[str] = []
        in_member = False
        for line in lines:
            if line.startswith("["):
                in_member = bool(header.match(line))
                rebuilt.append(line)
                if in_member:
                    rebuilt.append(_refs_line("source_refs", default))
                continue
            if in_member and line.startswith("additional_source_refs = ["):
                tail = tuple(re.findall(r'"([^"]*)"', line))
                rebuilt[-1] = _refs_line("source_refs", (*default, *tail))
                continue
            if in_member and line.startswith("source_refs = ["):
                continue
            rebuilt.append(line)
        path.write_text("\n".join(rebuilt) + "\n", encoding="utf-8", newline="\n")


def _refs_line(key: str, refs: tuple[str, ...]) -> str:
    return f"{key} = [" + ", ".join(f'"{ref}"' for ref in refs) + "]"


def _unlifted_modelo(tmp_path: Path) -> Path:
    """Copy the shipped modelo into ``tmp_path``, restate its members, and undeclare its family defaults.

    The copy is a real modelo rather than a hand-built minimal one because the
    assertion that matters most -- that the lifted tree still compiles -- needs
    the binding providers, construct enrolments and legal grounding the loader
    checks. What the copy must NOT inherit is the shipped tree's current lift
    STATE, so the members are restated into the full-copy authoring shape this
    tool exists to fix before the manifest defaults are removed.
    """
    modelo_dir = tmp_path / "modelos" / _MODELO
    shutil.copytree(REGISTRY_MODELOS_ROOT / _MODELO, modelo_dir)
    edition_dir = modelo_dir / "revisions" / _EDITION
    for family in _UNDER_TEST:
        _restate_members(edition_dir, family, _DEFAULT)
    manifest = edition_dir / "revision.toml"
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


def _unlifted_inheriting_modelo(tmp_path: Path) -> Path:
    """Copy the inheriting modelo and put its family back into the pre-lift authoring shape.

    The shipped corpus has already been lifted for this family, so a plain copy
    admits no lift and would make every test below vacuous. The undo is the
    lift's own inverse: drop the manifest declaration (and any carried-marker
    comment above it) and restate the default on every member that no longer
    states references of its own.
    """
    modelo_dir = tmp_path / "modelos" / _INHERITING_MODELO
    shutil.copytree(REGISTRY_MODELOS_ROOT / _INHERITING_MODELO, modelo_dir)
    key = FAMILY_DEFAULT_KEY[_INHERITING_FAMILY]
    declaration = re.compile(rf"^{re.escape(key)}\s*=\s*\[(?P<items>[^\]]*)\]\s*$")
    carried = re.compile(rf"^#\s*{re.escape(key)}: carried from predecessor edition ")

    for edition_dir in sorted(p for p in (modelo_dir / "revisions").iterdir() if p.is_dir()):
        manifest = edition_dir / "revision.toml"
        declared: str | None = None
        kept: list[str] = []
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if carried.match(line):
                continue
            match = declaration.match(line)
            if match is not None:
                declared = str(match.group("items"))
                continue
            kept.append(line)
        if declared is None:
            continue
        manifest.write_text("\n".join(kept) + "\n", encoding="utf-8", newline="\n")

        edition = re.escape(edition_dir.name)
        header = re.compile(rf'^\[\[revisions\.(?:"{edition}"|{edition})\.{_INHERITING_FAMILY}\]\]\s*$')
        for fragment in sorted((edition_dir / _INHERITING_FAMILY).glob("*.toml")):
            restored: list[str] = []
            for line in fragment.read_text(encoding="utf-8").splitlines():
                restored.append(line)
                if header.match(line):
                    restored.append(f"source_refs = [{declared}]")
            fragment.write_text("\n".join(restored) + "\n", encoding="utf-8", newline="\n")
    return modelo_dir


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


def test_a_multi_line_statement_lifts_rather_than_refusing_the_edition(tmp_path: Path) -> None:
    """A wrapped array is read and rewritten like the one-line spelling, not refused.

    The layout is an authoring accident rather than a statement about grounding,
    so a member that happens to wrap must not survive a lift that rewrites the
    identical one-line member beside it.
    """
    modelo_dir = _unlifted_modelo(tmp_path)
    fragment = sorted((modelo_dir / "revisions" / _EDITION / "bindings").glob("*.toml"))[0]
    fragment.write_text(
        fragment.read_text(encoding="utf-8").replace(
            'source_refs = ["aeat-dr-111-2019-v18", "aeat-modelo-111-instructions"]',
            'source_refs = [\n  "aeat-dr-111-2019-v18",\n  "aeat-modelo-111-instructions",\n]',
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )

    plan = plan_modelo(modelo_dir, ("bindings",))
    apply_plan(plan, modelo_dir.parent)

    assert plan.refusals == []
    assert "source_refs" not in fragment.read_text(encoding="utf-8")
    assert load_outcome(modelo_dir) == "loads"


def test_a_statement_carrying_a_comment_still_refuses_the_whole_edition(tmp_path: Path) -> None:
    """A wrapped array the rewrite cannot reproduce exactly is refused rather than partially applied.

    Rewriting it would silently drop an authored comment, so the refusal is the
    honest outcome: the tool declines the edition rather than deciding for the
    author which half of the statement mattered.
    """
    modelo_dir = _unlifted_modelo(tmp_path)
    fragment = sorted((modelo_dir / "revisions" / _EDITION / "bindings").glob("*.toml"))[0]
    fragment.write_text(
        fragment.read_text(encoding="utf-8").replace(
            'source_refs = ["aeat-dr-111-2019-v18", "aeat-modelo-111-instructions"]',
            'source_refs = [\n  "aeat-dr-111-2019-v18",  # the design, not the procedure\n'
            '  "aeat-modelo-111-instructions",\n]',
            1,
        ),
        encoding="utf-8",
        newline="\n",
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


def test_an_inheriting_successor_materialises_the_same_references_after_the_lift(tmp_path: Path) -> None:
    """The lift moves no grounding: every inherited row resolves to what it resolved to before.

    Carrying the predecessor's default onto an edition that inherits its rows
    exists for exactly one reason -- the successor's materialised rows must not
    change. This drives the real loader over a real inheriting modelo and
    compares every member's materialised ``source_refs`` before and after, so a
    lift that regrounded an inherited row fails here rather than in the corpus.
    """
    modelo_dir = _unlifted_inheriting_modelo(tmp_path)

    def materialised() -> dict[tuple[str, str], tuple[str, ...]]:
        modelo = load_modelo_directory(modelo_dir)
        return {
            (revision_id, str(member.id)): tuple(member.source_refs)
            for revision_id, revision in modelo.revisions.items()
            for member in getattr(revision, _INHERITING_FAMILY)
        }

    before = materialised()
    assert before, "the fixture materialises no members of the family under test"

    plan = plan_modelo(modelo_dir, (_INHERITING_FAMILY,))
    assert plan.liftable, "the fixture admits no lift, so it proves nothing"
    assert any(lift.inherited_from for lift in plan.liftable), (
        "the fixture has no inheriting successor, so the carry is never exercised"
    )
    apply_plan(plan, modelo_dir.parent)

    assert materialised() == before


def test_a_carried_declaration_names_the_predecessor_it_came_from(tmp_path: Path) -> None:
    """An inheriting successor's declaration is marked as carried, not as its own grounding."""
    modelo_dir = _unlifted_inheriting_modelo(tmp_path)
    plan = plan_modelo(modelo_dir, (_INHERITING_FAMILY,))
    carried = [lift for lift in plan.liftable if lift.inherited_from]
    assert carried, "no carried declaration to check"
    apply_plan(plan, modelo_dir.parent)

    key = FAMILY_DEFAULT_KEY[_INHERITING_FAMILY]
    for lift in carried:
        manifest = modelo_dir / "revisions" / lift.edition / "revision.toml"
        lines = manifest.read_text(encoding="utf-8").splitlines()
        declaration = next(index for index, line in enumerate(lines) if line.startswith(f"{key} ="))
        assert lines[declaration - 1] == (
            f'# {key}: carried from predecessor edition "{lift.inherited_from}"; '
            "not re-grounded on this edition's own design"
        )


def test_a_successor_regrounding_a_live_inherited_member_refuses_the_lift(tmp_path: Path) -> None:
    """A default that would move a live inherited row onto other grounding is refused, and says so.

    The successor is given a different declared default while it still inherits
    the lifted edition's members live. Nothing fails to load in that state, so
    only this check stands between the corpus and a silent regrounding.
    """
    modelo_dir = _unlifted_inheriting_modelo(tmp_path)
    plan = plan_modelo(modelo_dir, (_INHERITING_FAMILY,))
    successor = next(lift.edition for lift in plan.liftable if lift.inherited_from)
    key = FAMILY_DEFAULT_KEY[_INHERITING_FAMILY]
    manifest = modelo_dir / "revisions" / successor / "revision.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            f"[revisions.{successor}]", f'[revisions.{successor}]\n{key} = ["aeat-something-else"]', 1
        ),
        encoding="utf-8",
        newline="\n",
    )

    refused = plan_modelo(modelo_dir, (_INHERITING_FAMILY,))
    regrounding = [lift for lift in refused.refusals if lift.refusal.startswith("live_regrounding: ")]
    assert regrounding, f"no live_regrounding refusal among {[lift.refusal for lift in refused.refusals]}"
    reason = regrounding[0].refusal
    assert successor in reason
    assert "aeat-something-else" in reason
    assert not any(lift.inherited_from for lift in refused.liftable), "a carried declaration survived a refused family"


def test_a_superseded_inherited_member_does_not_refuse_the_lift(tmp_path: Path) -> None:
    """A differing successor default is harmless where nothing of the lift survives into it.

    The refusal exists to protect rows that materialise in the successor
    carrying the predecessor's grounding. Where the successor states its own
    row under every inherited identity, no such row exists, and refusing would
    withhold a lift that changes nothing.
    """
    modelo_dir = _unlifted_inheriting_modelo(tmp_path)
    plan = plan_modelo(modelo_dir, (_INHERITING_FAMILY,))
    lifted = next(lift for lift in plan.liftable if not lift.inherited_from)
    successor = next(lift.edition for lift in plan.liftable if lift.inherited_from)

    live = _live_inherited_ids(modelo_dir, successor, _INHERITING_FAMILY)
    assert live, "the fixture's successor inherits nothing live, so this proves nothing"
    assert live & _member_ids(modelo_dir / "revisions" / lifted.edition, _INHERITING_FAMILY)


def test_an_over_cap_reference_refuses_before_anything_is_written(tmp_path: Path) -> None:
    """A value the schema would reject stops the lift before the first byte, not after.

    The cap is the schema's own: ``SourceRefId`` constrains the id, so a
    reference longer than it allows must never reach the tree. Proven by making
    the derived default itself over-cap and asserting both that the lift raises
    and that every file is byte-identical afterwards -- a refusal that wrote
    first and rolled back would pass a weaker assertion.
    """
    modelo_dir = _unlifted_modelo(tmp_path)
    over_cap = "a" * 512
    for fragment in sorted((modelo_dir / "revisions" / _EDITION / "bindings").glob("*.toml")):
        fragment.write_bytes(
            fragment.read_text(encoding="utf-8").replace(f'"{_DEFAULT[0]}"', f'"{over_cap}"').encode("utf-8")
        )
    before = {path: path.read_bytes() for path in sorted(modelo_dir.rglob("*.toml"))}

    plan = plan_modelo(modelo_dir, ("bindings",))
    if not plan.liftable:
        pytest.skip("the over-cap corpus admits no lift, so the cap gate is not reached")
    with pytest.raises(ModeloLiftFailedError) as raised:
        apply_plan(plan, modelo_dir.parent)

    assert "would not validate" in str(raised.value)
    assert {path: path.read_bytes() for path in sorted(modelo_dir.rglob("*.toml"))} == before, (
        "the cap refusal wrote to the tree before refusing"
    )


def test_the_cap_gate_reads_its_limits_from_the_schema(tmp_path: Path) -> None:
    """Every cap enforced is one the typed model declares, never a number restated here.

    If the schema's own constraint is what runs, a value the model accepts must
    pass the gate and a value it rejects must fail it. Both directions are
    driven through the real model rather than against a copied bound.
    """
    from pydantic import TypeAdapter, ValidationError

    revision = _revision_model()
    key = FAMILY_DEFAULT_KEY["bindings"]
    adapter = TypeAdapter(revision.model_fields[key].annotation)

    adapter.validate_python(list(_DEFAULT))
    with pytest.raises(ValidationError):
        adapter.validate_python(["a" * 512])
    with pytest.raises(ValidationError):
        adapter.validate_python([])

    lift = EditionLift(modelo=_MODELO, edition=_EDITION, family="bindings", default=("a" * 512,))
    modelo_dir = _unlifted_modelo(tmp_path)
    assert _cap_refusal(modelo_dir / "revisions" / _EDITION, lift), "an over-cap default was not refused"
    accepted = EditionLift(modelo=_MODELO, edition=_EDITION, family="bindings", default=_DEFAULT)
    assert _cap_refusal(modelo_dir / "revisions" / _EDITION, accepted) == ""


def test_a_file_under_a_live_edit_is_skipped_whole_and_named(tmp_path: Path) -> None:
    """A lift whose file another writer just touched is withheld entirely, and reported.

    Writing over an edit this tool never saw would destroy it. The withholding
    is per lift rather than per file because the halves of a lift are not
    separable: members stripped without their manifest declaration materialise
    with no grounding at all.
    """
    modelo_dir = _unlifted_modelo(tmp_path)
    plan = plan_modelo(modelo_dir, _UNDER_TEST)
    assert plan.liftable, "the fixture admits no lift"
    fragment = sorted((modelo_dir / "revisions" / _EDITION / "bindings").glob("*.toml"))[0]
    fragment.touch()
    before = {path: path.read_bytes() for path in sorted(modelo_dir.rglob("*.toml"))}

    touched = apply_plan(plan, modelo_dir.parent, skip_recent_minutes=10)

    skipped_families = {lift.family for lift, _recent in plan.skipped}
    assert "bindings" in skipped_families, "the live-edited family was not withheld"
    assert all(path != fragment for path in touched), "the live-edited file was written"
    assert fragment.read_bytes() == before[fragment], "the live-edited file was modified"

    skipped_paths = {path for _lift, recent in plan.skipped for path, _age in recent}
    assert fragment in skipped_paths, "the skip did not name the file that caused it"
    rendered = render_plan([plan], applied=True, written={plan.modelo: touched})
    assert f"path={fragment.as_posix()}" in rendered
    assert "skip modelo=111 edition=" in rendered


def test_the_skip_window_is_off_by_default(tmp_path: Path) -> None:
    """A freshly written fixture still lifts when no window is asked for.

    Every file a test fixture creates is seconds old, so a guard that defaulted
    to on would silently withhold every lift in this module and make the whole
    suite vacuous.
    """
    modelo_dir = _unlifted_modelo(tmp_path)
    plan = plan_modelo(modelo_dir, _UNDER_TEST)
    touched = apply_plan(plan, modelo_dir.parent)
    assert touched, "the default window withheld a lift"
    assert plan.skipped == []


def test_an_excluded_edition_plans_nothing_and_is_listed_with_its_reason(tmp_path: Path) -> None:
    """``--exclude-edition`` withholds an edition whole, and the report says so and why.

    The exclusion is a campaign judgement the tool cannot derive -- an edition
    whose grounding a later adjudication owns -- so the proof that matters is
    that the withheld edition contributes no lift at all, not merely that it is
    mentioned. It is reported because a run that silently looked at less than it
    was asked to would be indistinguishable from one that found nothing.
    """
    modelo_dir = _unlifted_modelo(tmp_path)
    # The teeth are that the edition is not looked at, so the baseline must show
    # it being looked at. Whether that examination ends in a lift or a refusal is
    # the derivation rule's business and not what this test pins.
    examined = [lift.edition for lift in plan_modelo(modelo_dir, _UNDER_TEST).lifts]
    assert _EDITION in examined, "the fixture never examines the edition this test withholds"

    reason = "grounding belongs to the banked adjudication wave"
    excluded = collect_exclusions(editions=(f"{_MODELO}/{_EDITION}",), reason=reason)
    plan = plan_modelo(modelo_dir, _UNDER_TEST, excluded=excluded_editions(excluded, _MODELO))

    assert plan.lifts == [], "the excluded edition was still planned"
    assert plan.exclusions == [(_EDITION, reason)]
    rendered = render_plan([plan], applied=False)
    assert f"excluded: {_MODELO}/{_EDITION} reason={reason}" in rendered
    assert "planned=0" in rendered
    assert "excluded=1" in rendered

    before = {path: path.read_bytes() for path in sorted(modelo_dir.rglob("*.toml"))}
    assert (
        main(
            [
                "--modelo",
                _MODELO,
                "--apply",
                "--exclude-edition",
                f"{_MODELO}/{_EDITION}",
                "--exclude-reason",
                reason,
                "--modelos-root",
                str(modelo_dir.parent),
            ]
        )
        == 0
    )
    assert {path: path.read_bytes() for path in sorted(modelo_dir.rglob("*.toml"))} == before, (
        "an excluded edition was written"
    )


def test_a_malformed_exclusion_refuses_the_run(tmp_path: Path) -> None:
    """A '<modelo>/' with no edition is refused rather than widened to the whole modelo.

    Widening on a typo is safe for the corpus and silently drops work the
    operator meant to plan, which is the failure that looks like success.
    """
    modelo_dir = _unlifted_modelo(tmp_path)
    assert (
        main(["--modelo", _MODELO, "--exclude-edition", f"{_MODELO}/", "--modelos-root", str(modelo_dir.parent)])
    ) == 2


def test_a_whole_modelo_exclusion_plans_nothing_under_it(tmp_path: Path) -> None:
    """``--exclude <modelo>`` withholds every edition of that modelo, named or not."""
    modelo_dir = _unlifted_modelo(tmp_path)
    before = {path: path.read_bytes() for path in sorted(modelo_dir.rglob("*.toml"))}

    assert (
        main(
            [
                "--modelo",
                _MODELO,
                "--apply",
                "--exclude",
                _MODELO,
                "--exclude-reason",
                "the whole modelo is another lane's",
                "--modelos-root",
                str(modelo_dir.parent),
            ]
        )
        == 0
    )

    assert {path: path.read_bytes() for path in sorted(modelo_dir.rglob("*.toml"))} == before, (
        "an excluded modelo was written"
    )


def test_a_corpus_run_plans_nothing_under_a_frozen_modelo(tmp_path: Path) -> None:
    """The frozen modelos are withheld from a sweep that names no exclusion at all.

    A freeze that depended on the operator remembering a flag would not be a
    freeze: the run that forgets it is the run that writes another lane's
    adjudication surface.
    """
    modelo_dir = _unlifted_modelo(tmp_path)
    for name in FROZEN_MODELOS:
        shutil.copytree(modelo_dir, modelo_dir.parent / name)
    assert plan_modelo(modelo_dir.parent / FROZEN_MODELOS[0], _UNDER_TEST).lifts, (
        "the staged frozen tree is examined by nobody, so this test could not detect a freeze failure"
    )

    exclusions = collect_exclusions()
    plans = [
        plan_modelo(directory, _UNDER_TEST)
        for directory in iter_modelo_dirs(modelo_dir.parent)
        if not exclusions.excludes_modelo(directory.name)
    ]

    assert {plan.modelo for plan in plans}.isdisjoint(FROZEN_MODELOS), (
        "a frozen modelo was planned by a run that named no exclusion"
    )
    rendered = render_plan(plans, applied=False, withheld_modelos=exclusions.exclusions)
    for name in FROZEN_MODELOS:
        assert f"excluded: {name} reason=frozen:" in rendered


def test_an_exclusions_file_carries_a_reason_per_group(tmp_path: Path) -> None:
    """A '#' comment states the reason for the entries beneath it, up to the next comment."""
    path = tmp_path / "exclusions.txt"
    path.write_text(
        "# reason: another lane owns these\n100\n190/2022\n\n# reason: forward grounding\n190/2024\n",
        encoding="utf-8",
    )

    found = parse_exclusions_file(path)

    assert [(item.target, item.reason) for item in found] == [
        ("100", "another lane owns these"),
        ("190/2022", "another lane owns these"),
        ("190/2024", "forward grounding"),
    ]


def test_a_write_keeps_the_file_line_ending_style_and_is_read_back_on_raw_bytes(tmp_path: Path) -> None:
    """A CRLF fragment stays CRLF and an LF fragment stays LF, proved on the bytes read back.

    The failure this guards is silent: a translating write flips every line of a
    file the run meant to touch on one, and translating text that already
    carries CRLF produces the doubled carriage return no reader repairs.
    """
    lf = tmp_path / "lf.toml"
    lf.write_bytes(b'name = "a"\nvalue = 1\n')
    crlf = tmp_path / "crlf.toml"
    crlf.write_bytes(b'name = "a"\r\nvalue = 1\r\n')

    assert detect_newline(lf.read_bytes()) == LF
    assert detect_newline(crlf.read_bytes()) == CRLF
    assert write_preserving_newlines(lf, 'name = "b"\nvalue = 2\n') == LF
    assert write_preserving_newlines(crlf, 'name = "b"\nvalue = 2\n') == CRLF
    verify_written(lf, LF)
    verify_written(crlf, CRLF)

    assert lf.read_bytes() == b'name = "b"\nvalue = 2\n'
    assert crlf.read_bytes() == b'name = "b"\r\nvalue = 2\r\n'
    assert b"\r\r\n" not in crlf.read_bytes()

    crlf.write_bytes(b'name = "b"\nvalue = 2\n')
    with pytest.raises(RegistryLoadError, match="line endings changed"):
        verify_written(crlf, CRLF)
    crlf.write_bytes(b'name = "b"\r\r\nvalue = 2\r\n')
    with pytest.raises(RegistryLoadError, match="doubled carriage return"):
        verify_written(crlf, CRLF)
    lf.write_bytes(b"name = \n")
    with pytest.raises(RegistryLoadError, match="unparsable TOML"):
        verify_written(lf, LF)


def test_a_crlf_fragment_survives_a_real_lift_unflipped(tmp_path: Path) -> None:
    """A lift over a CRLF-authored corpus file leaves every untouched line in CRLF."""
    modelo_dir = _unlifted_modelo(tmp_path)
    for path in sorted(modelo_dir.rglob("*.toml")):
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))

    plan = plan_modelo(modelo_dir, _UNDER_TEST)
    apply_plan(plan, modelo_dir.parent)

    for path in sorted(modelo_dir.rglob("*.toml")):
        raw = path.read_bytes()
        assert b"\r\r\n" not in raw, f"{path} read back with a doubled carriage return"
        assert detect_newline(raw) == CRLF, f"{path} was flipped to LF"


_MIXED_FRAGMENT: Final = """[[revisions."2019-y-siguientes".bindings]]
casilla = "01"
source_refs = ["a", "b"]

[[revisions."2019-y-siguientes".bindings]]
casilla = "02"
source_refs = [
    "a",
    "b",
]

[[revisions."2019-y-siguientes".bindings]]
casilla = "03"
source_refs = [
    "a",
    "b",
    "c",
]

[[revisions."2019-y-siguientes".bindings.providers]]
source_refs = [
    "nested-and-untouched",
]

[[revisions."2019-y-siguientes".bindings]]
casilla = "04"
source_refs = [
    "z",
]
"""


def test_a_multi_line_source_refs_array_lifts_like_the_one_line_spelling() -> None:
    """Both spellings answer to one member-side rule: equal drops, opening keeps its tail, else kept.

    The layout is an authoring accident, not a statement about grounding, so a
    member that happens to wrap its array must not survive a lift that would
    have rewritten the identical one-line member beside it.
    """
    lifted = lifted_fragment_text(_MIXED_FRAGMENT, "2019-y-siguientes", "bindings", ("a", "b"))

    # Equal to the default, in either spelling: the statement goes entirely.
    assert "source_refs" not in lifted.split('casilla = "01"')[1].split("[[")[0]
    assert "source_refs" not in lifted.split('casilla = "02"')[1].split("[[")[0]
    # Opening with the default: only the tail survives, in the one-line spelling.
    assert 'additional_source_refs = ["c"]' in lifted
    assert '"a",\n    "b",\n    "c",' not in lifted
    # Irreducible, and a nested provider table, are both kept exactly as authored.
    assert '    "z",\n' in lifted
    assert '    "nested-and-untouched",\n' in lifted
    assert lifted.count("additional_source_refs") == 1


def test_a_no_op_lift_reproduces_a_mixed_spelling_file_byte_for_byte() -> None:
    """A default that rewrites nothing returns the file unchanged, wrapped arrays and all.

    A textual pass that reflowed the statements it decided to keep would dirty
    every file it merely looked at, which is how a run's real diff becomes
    unreviewable.
    """
    unchanged = lifted_fragment_text(_MIXED_FRAGMENT, "2019-y-siguientes", "bindings", ("no", "such", "default"))

    assert unchanged == _MIXED_FRAGMENT


def test_a_statement_the_rewrite_cannot_reproduce_is_still_refused(tmp_path: Path) -> None:
    """A wrapped array carrying a comment or a non-quoted value is kept whole and reported.

    Rewriting it would silently drop something an author wrote, so the tool
    refuses the edition instead of guessing which half mattered.
    """
    path = tmp_path / "0001-bindings.toml"
    text = (
        '[[revisions."2019-y-siguientes".bindings]]\n'
        'casilla = "01"\n'
        "source_refs = [\n"
        '    "a",  # the procedure, not the design\n'
        '    "b",\n'
        "]\n"
    )
    path.write_text(text, encoding="utf-8", newline="\n")

    assert _unreproducible_statements((path,), "2019-y-siguientes", "bindings") == (f"{path.name}: source_refs = [",)
    assert lifted_fragment_text(text, "2019-y-siguientes", "bindings", ("a", "b")) == text


def test_a_member_stating_no_source_refs_refuses_the_lift(tmp_path: Path) -> None:
    """A family where one row states nothing is refused: a default would ADD references to it.

    The sibling branch to the shared-leading-run refusal, and the one a fixture
    that read an already-lifted tree would hit by accident whichever branch it
    meant to reach. Declaring a default here would ground a row on a document
    its author never cited, which is an under-declaration the loader cannot see.
    """
    modelo_dir = _unlifted_modelo(tmp_path)
    edition_dir = modelo_dir / "revisions" / _EDITION
    fragment = sorted((edition_dir / "bindings").glob("*.toml"))[0]
    text = fragment.read_text(encoding="utf-8")
    silenced = text.replace(_refs_line("source_refs", _DEFAULT) + "\n", "", 1)
    assert silenced != text, "the fixture states no member references to remove"
    fragment.write_text(silenced, encoding="utf-8", newline="\n")
    before = {path: path.read_bytes() for path in sorted(modelo_dir.rglob("*.toml"))}

    plan = plan_modelo(modelo_dir, ("bindings",))

    assert plan.liftable == []
    assert [lift.refusal for lift in plan.refusals] == [
        "a row or constraints table states no source_refs, so a default would add references to it"
    ]
    assert apply_plan(plan, modelo_dir.parent) == []
    assert {path: path.read_bytes() for path in sorted(modelo_dir.rglob("*.toml"))} == before
