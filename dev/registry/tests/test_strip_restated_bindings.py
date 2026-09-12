"""Stripping a successor edition's binding members that restate the inherited member.

Every test drives the real planner, the real textual rewriter and the loader's
own keyed-merge function over a modelo materialised in ``tmp_path``. Nothing is
mocked, stubbed or skipped, and nothing outside ``tmp_path`` is written.

The tree is a copy of a shipped multi-edition modelo with the per-edition
``source_refs`` lifted off its binding members onto the manifest default each
edition already declares. That lift is the precondition the tool's own
documentation names, and performing it in the fixture is what makes the
inherited member and the stated member comparable at all: a hand-built modelo
would not carry the providers, value contracts and grounding typed construction
checks, so the assertion that matters most -- that the stripped tree
materialises the same typed bindings -- could not be made against one.
"""

from __future__ import annotations

import re
import shutil
import tomllib
from pathlib import Path
from typing import Any, Final

import pytest

from ..corpus_write import CRLF, LF, ReadBackFailedError, detect_newline, verify_written, write_preserving_newlines
from ..run_exclusions import FROZEN_MODELOS, Exclusion, collect_exclusions
from ..strip_restated_bindings import (
    MATERIALISED,
    EditionOutcome,
    ModeloOutcome,
    StripRefusedError,
    StripReport,
    main,
    parse_edges_file,
    plan_modelo,
    render_report,
    strip_registry,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: A small modelo with a declared predecessor chain and one binding family.
_MODELO: Final = "131"
_PREDECESSOR: Final = "2024"
_SUCCESSOR: Final = "2025"
_SOURCE_REFS_LINE: Final = re.compile(r"^source_refs = \[.*\]$")


def _registry_root() -> Path:
    from cadrumo.core.resources.bundled_data import bundled_path

    return Path(bundled_path("registry", "aeat")).resolve()


def _lift_source_refs(edition_dir: Path) -> None:
    """Drop each binding member's ``source_refs``, leaving the manifest default to fill it."""
    for path in sorted((edition_dir / "bindings").glob("*.toml")):
        kept = [line for line in path.read_text(encoding="utf-8").splitlines() if not _SOURCE_REFS_LINE.match(line)]
        path.write_text("\n".join(kept) + "\n", encoding="utf-8", newline="\n")


def _staged_registry(tmp_path: Path) -> Path:
    """A registry root holding one modelo, with every edition's binding references lifted."""
    root = tmp_path / "registry"
    modelo_dir = root / "modelos" / _MODELO
    shutil.copytree(_registry_root() / "modelos" / _MODELO, modelo_dir)
    for edition_dir in sorted((modelo_dir / "revisions").iterdir()):
        if edition_dir.is_dir():
            _lift_source_refs(edition_dir)
    return root


def _members(edition_dir: Path) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for path in sorted((edition_dir / "bindings").glob("*.toml")):
        table = tomllib.loads(path.read_text(encoding="utf-8"))["revisions"][edition_dir.name]
        found.extend(member for member in table.get("bindings", ()) if isinstance(member, dict))
    return found


def _outcome(report: StripReport, edition: str) -> EditionOutcome:
    (found,) = [item for modelo in report.modelos for item in modelo.editions if item.edition == edition]
    return found


def test_restated_members_are_removed_and_the_typed_binding_set_is_unchanged(tmp_path: Path) -> None:
    """A member identical to the inherited one is dropped, and the edition materialises the same bindings."""
    root = _staged_registry(tmp_path)
    edition_dir = root / "modelos" / _MODELO / "revisions" / _SUCCESSOR
    before = {str(member["id"]) for member in _members(edition_dir)}

    report = strip_registry(root, modelo_ids=(_MODELO,), equality=MATERIALISED, apply=True)
    outcome = _outcome(report, _SUCCESSOR)

    assert outcome.predecessor == _PREDECESSOR
    assert outcome.removed, "no restated member was found in a lifted successor edition"
    assert outcome.proof.startswith("byte-identical")
    after = {str(member["id"]) for member in _members(edition_dir)}
    assert after == before - set(outcome.removed)


def test_a_member_differing_in_one_field_is_kept_and_the_field_is_named(tmp_path: Path) -> None:
    """Changing one field of an otherwise restated member moves it from removed to kept."""
    root = _staged_registry(tmp_path)
    edition_dir = root / "modelos" / _MODELO / "revisions" / _SUCCESSOR
    planned = plan_modelo(root / "modelos" / _MODELO)
    target = _outcome_for(planned, _SUCCESSOR).removed[0]

    fragment = next(
        path
        for path in sorted((edition_dir / "bindings").glob("*.toml"))
        if f'id = "{target}"' in path.read_text(encoding="utf-8")
    )
    text = fragment.read_text(encoding="utf-8")
    head, _, tail = text.partition(f'id = "{target}"')
    changed = re.sub(r"legal_refs = \[[^\]]*\]", 'legal_refs = ["rd-439-2007:art-110"]', tail, count=1)
    fragment.write_text(head + f'id = "{target}"' + changed, encoding="utf-8", newline="\n")

    report = strip_registry(root, modelo_ids=(_MODELO,), equality=MATERIALISED, apply=True)
    outcome = _outcome(report, _SUCCESSOR)

    assert target not in outcome.removed
    assert ("legal_refs",) in {fields for identity, fields in outcome.kept_differs if identity == target}
    assert target in {str(member["id"]) for member in _members(edition_dir)}


def test_a_fragment_left_with_no_member_is_deleted(tmp_path: Path) -> None:
    """A fragment whose every member is restated is removed rather than left as an empty file."""
    root = _staged_registry(tmp_path)
    edition_dir = root / "modelos" / _MODELO / "revisions" / _SUCCESSOR
    planned = plan_modelo(root / "modelos" / _MODELO)
    target = _outcome_for(planned, _SUCCESSOR).removed[0]

    fragment = next(
        path
        for path in sorted((edition_dir / "bindings").glob("*.toml"))
        if f'id = "{target}"' in path.read_text(encoding="utf-8")
    )
    text = fragment.read_text(encoding="utf-8")
    blocks = text.split('[[revisions."2025".bindings]]')
    (block,) = [item for item in blocks if f'id = "{target}"' in item]
    solo = edition_dir / "bindings" / "9999-solo.toml"
    solo.write_text('[[revisions."2025".bindings]]' + block, encoding="utf-8", newline="\n")
    fragment.write_text(
        '[[revisions."2025".bindings]]'.join(item for item in blocks if item is not block),
        encoding="utf-8",
        newline="\n",
    )

    report = strip_registry(root, modelo_ids=(_MODELO,), equality=MATERIALISED, apply=True)
    outcome = _outcome(report, _SUCCESSOR)

    assert solo.name in outcome.fragments_deleted
    assert not solo.exists()
    assert fragment.exists(), "a sibling fragment was deleted with its neighbour"


def test_sibling_members_and_their_comments_survive_a_strip(tmp_path: Path) -> None:
    """Removing one member leaves every other member's text, comments included, byte for byte."""
    root = _staged_registry(tmp_path)
    edition_dir = root / "modelos" / _MODELO / "revisions" / _SUCCESSOR
    planned = plan_modelo(root / "modelos" / _MODELO)
    removed = set(_outcome_for(planned, _SUCCESSOR).removed)
    fragment = next(
        path
        for path in sorted((edition_dir / "bindings").glob("*.toml"))
        if any(f'id = "{identity}"' in path.read_text(encoding="utf-8") for identity in removed)
    )
    text = fragment.read_text(encoding="utf-8")
    marked = text.replace('[[revisions."2025".bindings]]', '# a reviewer\'s note\n[[revisions."2025".bindings]]', 1)
    fragment.write_text(marked, encoding="utf-8", newline="\n")
    survivors = {str(member["id"]): member for member in _members(edition_dir) if str(member["id"]) not in removed}

    strip_registry(root, modelo_ids=(_MODELO,), equality=MATERIALISED, apply=True)

    after = {str(member["id"]): member for member in _members(edition_dir)}
    assert after == survivors
    if fragment.exists():
        first = fragment.read_text(encoding="utf-8").splitlines()[0]
        assert first.startswith("#") or first.startswith("[[revisions")


def test_a_root_edition_is_refused_rather_than_stripped(tmp_path: Path) -> None:
    """An edition declaring an explicit no-predecessor inherits nothing and is refused."""
    root = _staged_registry(tmp_path)
    report = strip_registry(root, modelo_ids=(_MODELO,), equality=MATERIALISED, apply=False)
    refusals = {
        edition.edition: edition.refusal for modelo in report.modelos for edition in modelo.editions if edition.refusal
    }
    assert any("predecessor_none_root" in reason for reason in refusals.values())
    assert all(not edition.removed for modelo in report.modelos for edition in modelo.editions if edition.refusal)


def test_apply_refuses_while_the_enrolment_is_simulated(tmp_path: Path) -> None:
    """``--apply`` needs the operator to accept the simulated enrolment explicitly."""
    root = _staged_registry(tmp_path)
    edition_dir = root / "modelos" / _MODELO / "revisions" / _SUCCESSOR
    before = {path.name: path.read_text(encoding="utf-8") for path in sorted((edition_dir / "bindings").glob("*.toml"))}

    with pytest.raises(SystemExit) as refused:
        main(["--modelo", _MODELO, "--apply", "--registry-root", str(root)])

    assert refused.value.code == 2
    after = {path.name: path.read_text(encoding="utf-8") for path in sorted((edition_dir / "bindings").glob("*.toml"))}
    assert after == before

    assert main(["--modelo", _MODELO, "--apply", "--enrolment-simulated", "--registry-root", str(root)]) == 0
    stripped = {
        path.name: path.read_text(encoding="utf-8") for path in sorted((edition_dir / "bindings").glob("*.toml"))
    }
    assert stripped != before


def test_an_edge_selection_restricts_the_plan_to_that_successor(tmp_path: Path) -> None:
    """Naming one edge plans that successor and leaves the modelo's other editions unexamined."""
    root = _staged_registry(tmp_path)
    sweep = strip_registry(root, modelo_ids=(_MODELO,), equality=MATERIALISED, apply=False)
    swept = {edition.edition for modelo in sweep.modelos for edition in modelo.editions}
    assert len(swept) > 1, "the fixture modelo must carry more than one binding-stating edition"

    report = strip_registry(root, edges=((_MODELO, _SUCCESSOR),), equality=MATERIALISED, apply=False)

    assert report.edges == ((_MODELO, _SUCCESSOR),)
    assert {edition.edition for modelo in report.modelos for edition in modelo.editions} == {_SUCCESSOR}
    assert _outcome(report, _SUCCESSOR).removed == _outcome(sweep, _SUCCESSOR).removed


def test_an_edge_whose_successor_is_undeclared_or_rootless_is_refused(tmp_path: Path) -> None:
    """An edge naming a missing successor, or one declaring [predecessor.none], refuses the run."""
    root = _staged_registry(tmp_path)
    roots = [
        edition.edition
        for modelo in strip_registry(root, modelo_ids=(_MODELO,), apply=False).modelos
        for edition in modelo.editions
        if "predecessor_none_root" in edition.refusal
    ]
    assert roots, "the fixture modelo must carry an explicit no-predecessor root"

    with pytest.raises(StripRefusedError, match="successor edition is not declared"):
        strip_registry(root, edges=((_MODELO, "1999"),), apply=False)
    with pytest.raises(StripRefusedError, match=r"predecessor\.none"):
        strip_registry(root, edges=((_MODELO, roots[0]),), apply=False)
    with pytest.raises(StripRefusedError, match="modelo is not in the registry"):
        strip_registry(root, edges=(("000", _SUCCESSOR),), apply=False)


def test_an_edges_file_ignores_comments_and_blank_lines(tmp_path: Path) -> None:
    """The edges file parses one 'modelo/edition' per line, dropping comments, blanks and duplicates."""
    path = tmp_path / "edges.txt"
    path.write_text(
        "# the enrolling lane's edges\n"
        f"{_MODELO}/{_SUCCESSOR}\n"
        "\n"
        "   303/2023   # trailing comment\n"
        f"{_MODELO}/{_SUCCESSOR}\n",
        encoding="utf-8",
    )

    assert parse_edges_file(path) == ((_MODELO, _SUCCESSOR), ("303", "2023"))

    (tmp_path / "bad.txt").write_text("390\n", encoding="utf-8")
    with pytest.raises(StripRefusedError, match=r"bad\.txt:1: malformed edge"):
        parse_edges_file(tmp_path / "bad.txt")


def test_the_cli_plans_the_edges_named_in_a_file(tmp_path: Path) -> None:
    """``--edges-file`` reaches the planner and refuses to be combined with a modelo sweep."""
    root = _staged_registry(tmp_path)
    path = tmp_path / "edges.txt"
    path.write_text(f"# one edge\n{_MODELO}/{_SUCCESSOR}\n", encoding="utf-8")

    assert main(["--edges-file", str(path), "--registry-root", str(root)]) == 0
    with pytest.raises(SystemExit) as refused:
        main(["--edges-file", str(path), "--all", "--registry-root", str(root)])
    assert refused.value.code == 2


def _outcome_for(outcome: ModeloOutcome, edition: str) -> EditionOutcome:
    (found,) = [item for item in outcome.editions if item.edition == edition]
    return found


def test_an_excluded_edition_plans_nothing_and_is_listed_with_its_reason(tmp_path: Path) -> None:
    """``--exclude-edition`` withholds an edition whole, and the report states it and the reason.

    Exclusion answers a judgement the strip cannot make for itself -- an edition
    whose grounding a later adjudication owns -- so what is proved here is that
    the withheld edition is not planned, not proved and not written, and that
    the run says so rather than quietly examining less than it was asked to.
    """
    root = _staged_registry(tmp_path)
    sweep = strip_registry(root, modelo_ids=(_MODELO,), equality=MATERIALISED, apply=False)
    assert _SUCCESSOR in {edition.edition for modelo in sweep.modelos for edition in modelo.editions}, (
        "the fixture never examines the edition this test withholds"
    )

    reason = "forward grounding belongs to the banked adjudication wave"
    report = strip_registry(
        root,
        modelo_ids=(_MODELO,),
        exclusions=collect_exclusions(editions=(f"{_MODELO}/{_SUCCESSOR}",), reason=reason),
        equality=MATERIALISED,
        apply=False,
    )

    planned = {edition.edition for modelo in report.modelos for edition in modelo.editions}
    assert _SUCCESSOR not in planned, "the excluded edition was still planned"
    assert Exclusion(_MODELO, _SUCCESSOR, reason) in report.exclusions.exclusions
    assert f"excluded: {_MODELO}/{_SUCCESSOR} reason={reason}" in render_report(report)
    assert {"target": f"{_MODELO}/{_SUCCESSOR}", "reason": reason} in report.as_json()["exclusions"]


def test_an_exclusion_outranks_an_edge_that_names_the_same_edition(tmp_path: Path) -> None:
    """Excluding the only named edge withholds the run rather than widening it to a sweep.

    An empty selection must never read as "no selection": that would turn a
    withheld single-edge run into a corpus-wide one, which is the opposite of
    what the operator asked for.
    """
    root = _staged_registry(tmp_path)

    report = strip_registry(
        root,
        edges=((_MODELO, _SUCCESSOR),),
        exclusions=collect_exclusions(editions=(f"{_MODELO}/{_SUCCESSOR}",), reason="withheld"),
        apply=False,
    )

    assert report.modelos == [], "an excluded edge run widened into a sweep"
    assert Exclusion(_MODELO, _SUCCESSOR, "withheld") in report.exclusions.exclusions


def test_a_corpus_run_plans_nothing_under_a_frozen_modelo(tmp_path: Path) -> None:
    """The frozen modelos are withheld from a sweep that names no exclusion at all.

    A freeze that depended on the operator remembering a flag would not be a
    freeze: the run that forgets it is exactly the run that writes another
    lane's adjudication surface.
    """
    root = _staged_registry(tmp_path)
    # The frozen ids are staged with a real, plannable modelo tree, so the only
    # reason the run can leave them alone is that they are frozen.
    for name in FROZEN_MODELOS:
        shutil.copytree(root / "modelos" / _MODELO, root / "modelos" / name)
    frozen_present = list(FROZEN_MODELOS)
    assert strip_registry(root, modelo_ids=(_MODELO,), apply=False).modelos, (
        "the staged tree plans nothing even unfrozen, so this test could not detect a freeze failure"
    )

    report = strip_registry(root, modelo_ids=(), equality=MATERIALISED, apply=False)

    assert {modelo.modelo for modelo in report.modelos}.isdisjoint(frozen_present), (
        "a frozen modelo was planned by a run that named no exclusion"
    )
    rendered = render_report(report)
    for name in frozen_present:
        assert f"excluded: {name} reason=frozen:" in rendered


def test_a_write_keeps_the_file_line_ending_style_and_is_read_back_on_raw_bytes(tmp_path: Path) -> None:
    """A CRLF file stays CRLF and an LF file stays LF, and the read-back proves it on the bytes.

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

    # The read-back reports rather than accepts: a file rewritten in the other
    # style, doubled, or left unparsable fails its own assertion.
    crlf.write_bytes(b'name = "b"\nvalue = 2\n')
    with pytest.raises(ReadBackFailedError, match="line endings changed"):
        verify_written(crlf, CRLF)
    crlf.write_bytes(b'name = "b"\r\r\nvalue = 2\r\n')
    with pytest.raises(ReadBackFailedError, match="doubled carriage return"):
        verify_written(crlf, CRLF)
    lf.write_bytes(b"name = \n")
    with pytest.raises(ReadBackFailedError, match="unparsable TOML"):
        verify_written(lf, LF)
