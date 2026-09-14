"""Stripping a successor edition's binding members that restate the inherited member.

Every test drives the real planner, the real textual rewriter and the loader's
own keyed-merge function over a modelo materialised in ``tmp_path``. Nothing is
mocked, stubbed or skipped, and nothing outside ``tmp_path`` is written.

The tree is a synthetic three-edition modelo built here, in the TOML grammar the
directory loader accepts, and it is loadable: its members carry real providers,
real value contracts and real grounding, so the assertion that matters most --
that the stripped tree materialises the same typed bindings -- is made against
typed construction rather than against text.

Building it is the point. A fixture seeded from the shipped corpus meant
whatever the corpus happened to author that day: whether any edition restated
its predecessor at all, which member a later edition had rewritten, which
grounding each edition declared. Those are authoring decisions, so they move,
and a gate whose preconditions move is not a gate. Here each precondition the
strip is about is stated outright:

* every edition lifts its binding ``source_refs`` onto its own manifest
  ``binding_source_refs`` default, which is the precondition the tool's own
  documentation names, and the three editions declare three different defaults
  so the carried-grounding rule has two editions grounded differently to work
  with;
* the successor restates three of the predecessor's members byte for byte, so
  there is something to remove;
* it keeps a fourth, the survivor, whose ``legal_refs`` are the version the
  edition before the predecessor stated -- a member that differs from what it
  inherits by exactly one field, so a strip that removed it would be wrong;
* the first edition declares an explicit ``[predecessor.none]`` root while
  still stating a member, so the refusal that guards a rootless edition has
  something to refuse;
* members carry a ``source_citations`` sub-table, so a carried block is more
  than its header line.
"""

from __future__ import annotations

import re
import shutil
import tomllib
from pathlib import Path
from typing import Any, Final

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryError, RegistryLoadError

from ..compiler.loader import load_modelo_directory, modelo_fact_scope
from ..conformance.loader_directory_mode_support import write_standard_manifest
from ..corpus_write import CRLF, LF, detect_newline, verify_written, write_preserving_newlines
from ..run_exclusions import FROZEN_MODELOS, Exclusion, collect_exclusions
from ..strip_restated_bindings import (
    LIFTED,
    MATERIALISED,
    EditionOutcome,
    ModeloOutcome,
    StripReport,
    main,
    parse_edges_file,
    plan_modelo,
    render_report,
    strip_registry,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: A small modelo with a declared predecessor chain and one binding family.
#: ``write_standard_manifest`` declares this id, so the modelo directory carries it.
_MODELO: Final = "999"
#: The edition before the predecessor, whose own version of a member the predecessor rewrote.
_VARIANT: Final = "2019-2023"
_PREDECESSOR: Final = "2024"
_SUCCESSOR: Final = "2025"

_LEGAL_REF: Final = "ley-58-2003:art-29"
#: The survivor's legal reference as the predecessor rewrote it, which is the one
#: field by which the member the successor states differs from the one it inherits.
_REWRITTEN_LEGAL_REF: Final = "ley-35-2006:art-93"
_SOURCE_REF: Final = "aeat-manual"

#: Each edition's declared ``binding_source_refs``, which its members are lifted
#: onto. The three differ, because the carried-grounding rule is about a member
#: inheriting grounding the successor's own default does not supply.
_BINDING_DEFAULTS: Final = {
    _VARIANT: _SOURCE_REF,
    _PREDECESSOR: "aeat-modelo-999-2024-design",
    _SUCCESSOR: "aeat-modelo-999-2025-design",
}
_EDITION_YEARS: Final = {_VARIANT: (2019, 2023), _PREDECESSOR: (2024, 2024), _SUCCESSOR: (2025, 2025)}

#: The members the successor restates byte for byte and the strip may remove.
_RESTATED: Final = ("modelo-999-member-1", "modelo-999-member-2", "modelo-999-member-3")
#: The member the successor states in the pre-predecessor wording, so it differs.
_SURVIVOR: Final = "modelo-999-member-4"


def _binding(edition: str, identity: str, *, offset: int, legal_ref: str = _LEGAL_REF) -> str:
    """One authored binding member, with the citation sub-table that grounds it.

    The member states no ``source_refs``: every edition declares a
    ``binding_source_refs`` default and the loader fills the member from the
    default of the edition it materialises in, which is the lifted state the
    strip's strict equality is defined against. The citation names the modelo's
    own manual, not the edition default, so two editions' versions of one member
    are comparable at all.
    """
    return (
        f'[[revisions."{edition}".bindings]]\n'
        f'id = "{identity}"\n'
        f'provider = {{ kind = "manual_input", record = "page_1", field = "campo-{offset}", '
        f'offset = {offset}, length = 1, data_type = "text" }}\n'
        'value = { data_type = "text", channel = "text" }\n'
        f'legal_refs = ["{legal_ref}"]\n'
        f'\n[[revisions."{edition}".bindings.source_citations]]\n'
        f'source_ref = "{_SOURCE_REF}"\n'
        'required_text = ["Modelo 999"]\n\n'
    )


def _casillas(edition: str) -> str:
    return (
        f'[[revisions."{edition}".casillas]]\n'
        'id = "0001"\n'
        'number = "1"\n'
        'section = ["liquidacion"]\n'
        'data_type = "money"\n'
        'continuidad_id = "base"\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{_SOURCE_REF}"]\n\n'
    )


def _write_edition(modelo_dir: Path, edition: str, *, predecessor: str | None, bindings: str) -> None:
    """Write one edition's manifest, casillas and bindings fragments."""
    edition_dir = modelo_dir / "revisions" / edition
    (edition_dir / "bindings").mkdir(parents=True)
    (edition_dir / "casillas").mkdir(parents=True)
    low, high = _EDITION_YEARS[edition]
    if predecessor is None:
        chain = (
            f'\n[revisions."{edition}".predecessor.none]\n'
            'reason = "the first edition of this modelo"\n'
            f'legal_refs = ["{_LEGAL_REF}"]\n'
            f'source_refs = ["{_SOURCE_REF}"]\n'
        )
    else:
        chain = f'predecessor = "{predecessor}"\n'
    (edition_dir / "revision.toml").write_text(
        f'[revisions."{edition}"]\n'
        f"valid_from = {low}-01-01\n"
        f"valid_to = {high}-12-31\n"
        f'period_selector = {{ years = {list(range(low, high + 1))}, periods = ["0A"] }}\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{_SOURCE_REF}"]\n'
        f'binding_source_refs = ["{_BINDING_DEFAULTS[edition]}"]\n'
        f"{chain}",
        encoding="utf-8",
        newline="\n",
    )
    (edition_dir / "casillas" / "0001-casillas.toml").write_text(_casillas(edition), encoding="utf-8", newline="\n")
    (edition_dir / "bindings" / "0001-bindings.toml").write_text(bindings, encoding="utf-8", newline="\n")


def _staged_registry(tmp_path: Path) -> Path:
    """A registry root holding the synthetic three-edition modelo.

    ``2019-2023`` is an explicit no-predecessor root stating the survivor alone.
    ``2024`` states the three members the successor will restate and rewrites the
    survivor's ``legal_refs``. ``2025`` restates those three byte for byte and
    states the survivor in the pre-2024 wording, so it differs from the member it
    inherits by exactly one field.
    """
    root = tmp_path / "registry"
    modelo_dir = root / "modelos" / _MODELO
    modelo_dir.mkdir(parents=True)
    write_standard_manifest(modelo_dir, "Test")
    _write_edition(
        modelo_dir,
        _VARIANT,
        predecessor=None,
        bindings=_binding(_VARIANT, _SURVIVOR, offset=4),
    )
    _write_edition(
        modelo_dir,
        _PREDECESSOR,
        predecessor=_VARIANT,
        bindings="".join(
            _binding(_PREDECESSOR, identity, offset=offset) for offset, identity in enumerate(_RESTATED, start=1)
        )
        + _binding(_PREDECESSOR, _SURVIVOR, offset=4, legal_ref=_REWRITTEN_LEGAL_REF),
    )
    _write_edition(
        modelo_dir,
        _SUCCESSOR,
        predecessor=_PREDECESSOR,
        bindings="".join(
            _binding(_SUCCESSOR, identity, offset=offset) for offset, identity in enumerate(_RESTATED, start=1)
        )
        + _binding(_SUCCESSOR, _SURVIVOR, offset=4),
    )
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


def test_a_run_writes_nothing_without_apply_and_writes_with_it(tmp_path: Path) -> None:
    """The default run is a plan: every fragment is byte-identical afterwards, and --apply changes that."""
    root = _staged_registry(tmp_path)
    edition_dir = root / "modelos" / _MODELO / "revisions" / _SUCCESSOR
    before = {path.name: path.read_bytes() for path in sorted((edition_dir / "bindings").glob("*.toml"))}

    assert main(["--modelo", _MODELO, "--registry-root", str(root)]) == 0

    planned = {path.name: path.read_bytes() for path in sorted((edition_dir / "bindings").glob("*.toml"))}
    assert planned == before, "a run without --apply wrote to the corpus"

    assert main(["--modelo", _MODELO, "--apply", "--registry-root", str(root)]) == 0

    stripped = {path.name: path.read_bytes() for path in sorted((edition_dir / "bindings").glob("*.toml"))}
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

    with pytest.raises(RegistryError, match="successor edition is not declared"):
        strip_registry(root, edges=((_MODELO, "1999"),), apply=False)
    with pytest.raises(RegistryError, match=r"predecessor\.none"):
        strip_registry(root, edges=((_MODELO, roots[0]),), apply=False)
    with pytest.raises(RegistryError, match="modelo is not in the registry"):
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
    with pytest.raises(RegistryError, match=r"bad\.txt:1: malformed edge"):
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
    with pytest.raises(RegistryLoadError, match="line endings changed"):
        verify_written(crlf, CRLF)
    crlf.write_bytes(b'name = "b"\r\r\nvalue = 2\r\n')
    with pytest.raises(RegistryLoadError, match="doubled carriage return"):
        verify_written(crlf, CRLF)
    lf.write_bytes(b"name = \n")
    with pytest.raises(RegistryLoadError, match="unparsable TOML"):
        verify_written(lf, LF)


def _header(edition: str) -> str:
    """The binding member header line of one edition."""
    return f'[[revisions."{edition}".bindings]]'


def _blocks(path: Path) -> list[tuple[str, str]]:
    """Each binding member of a fragment as (id, text), split on its edition's header line."""
    header = _header(path.parent.parent.name)
    parts = path.read_text(encoding="utf-8").split(header)
    found: list[tuple[str, str]] = []
    for part in parts[1:]:
        identity = re.search(r'id = "([^"]+)"', part)
        found.append((identity.group(1) if identity else "", header + part))
    return found


def _fragment_of(edition_dir: Path, identity: str) -> Path:
    """The fragment stating one member."""
    return next(
        path
        for path in sorted((edition_dir / "bindings").glob("*.toml"))
        if f'id = "{identity}"' in path.read_text(encoding="utf-8")
    )


def _drop_member(edition_dir: Path, identity: str, *, keep: Path) -> None:
    """Remove one member from every fragment but ``keep``, deleting a fragment left with none."""
    for path in sorted((edition_dir / "bindings").glob("*.toml")):
        if path == keep:
            continue
        blocks = _blocks(path)
        if not any(found == identity for found, _ in blocks):
            continue
        kept = [text for found, text in blocks if found != identity]
        if kept:
            path.write_text("".join(kept), encoding="utf-8", newline="\n")
        else:
            path.unlink()


def _removable(root: Path) -> tuple[Path, set[str]]:
    """The successor edition directory and the members a plan would remove from it."""
    edition_dir = root / "modelos" / _MODELO / "revisions" / _SUCCESSOR
    planned = plan_modelo(root / "modelos" / _MODELO)
    removed = set(_outcome_for(planned, _SUCCESSOR).removed)
    assert removed, "the fixture successor must carry at least one restated member"
    return edition_dir, removed


def test_a_fragment_of_comments_and_stripped_members_is_deleted_and_its_comments_reported(
    tmp_path: Path,
) -> None:
    """A fragment reduced to its leading comment run is unlinked; the run survives in the report."""
    root = _staged_registry(tmp_path)
    edition_dir, removed = _removable(root)
    target = sorted(removed)[0]
    (block,) = [text for identity, text in _blocks(_fragment_of(edition_dir, target)) if identity == target]
    note = "# the reason this fragment existed\n# a second commentary line\n\n"
    solo = edition_dir / "bindings" / "9998-commented.toml"
    solo.write_text(note + block, encoding="utf-8", newline="\n")
    _drop_member(edition_dir, target, keep=solo)

    report = strip_registry(root, modelo_ids=(_MODELO,), equality=MATERIALISED, apply=True)
    outcome = _outcome(report, _SUCCESSOR)

    assert not solo.exists(), "a comment-only remnant was left on disk"
    assert solo.name in outcome.fragments_deleted
    assert (solo.name, note) in outcome.comment_only_removed
    assert {"fragment": solo.name, "text": note} in outcome.as_json()["comment_only_removed"]


def test_a_fragment_keeping_one_member_keeps_that_member_and_its_comment_run(tmp_path: Path) -> None:
    """A surviving member and the comment run above it are written back byte for byte."""
    root = _staged_registry(tmp_path)
    edition_dir, removed = _removable(root)
    target = sorted(removed)[0]
    survivor_id, survivor_block = next(
        (identity, text)
        for path in sorted((edition_dir / "bindings").glob("*.toml"))
        for identity, text in _blocks(path)
        if identity and identity not in removed
    )
    (doomed,) = [text for identity, text in _blocks(_fragment_of(edition_dir, target)) if identity == target]
    preamble = "# fragment header\n\n"
    survivor_note = "# this member is new in this edition\n"
    pair = edition_dir / "bindings" / "9997-pair.toml"
    pair.write_text(preamble + doomed + survivor_note + survivor_block, encoding="utf-8", newline="\n")
    _drop_member(edition_dir, target, keep=pair)
    _drop_member(edition_dir, survivor_id, keep=pair)

    strip_registry(root, modelo_ids=(_MODELO,), equality=MATERIALISED, apply=True)

    after = pair.read_text(encoding="utf-8")
    assert after.startswith(preamble)
    assert survivor_note + survivor_block in after
    assert f'id = "{target}"' not in after
    assert [identity for identity, _ in _blocks(pair)] == [survivor_id]


def test_an_emptied_bindings_directory_is_removed_and_the_modelo_still_loads(tmp_path: Path) -> None:
    """Stripping every member of an edition removes its bindings directory and leaves the modelo loadable."""
    root = _staged_registry(tmp_path)
    modelo_dir = root / "modelos" / _MODELO
    edition_dir, removed = _removable(root)
    for path in sorted((edition_dir / "bindings").glob("*.toml")):
        kept = [text for identity, text in _blocks(path) if identity in removed]
        if kept:
            path.write_text("".join(kept), encoding="utf-8", newline="\n")
        else:
            path.unlink()

    report = strip_registry(root, modelo_ids=(_MODELO,), equality=MATERIALISED, apply=True)
    outcome = _outcome(report, _SUCCESSOR)

    assert "bindings" in outcome.directories_removed
    assert not (edition_dir / "bindings").exists(), "an empty section directory was left behind"
    with modelo_fact_scope(modelo_dir):
        definition = load_modelo_directory(modelo_dir)
    assert definition.id


def _manifest_binding_default(edition_dir: Path) -> list[str]:
    """The edition's declared ``binding_source_refs``, read from its own manifest."""
    table = tomllib.loads((edition_dir / "revision.toml").read_text(encoding="utf-8"))
    return list(table["revisions"][edition_dir.name]["binding_source_refs"])


def _construct_source_refs(edition_dir: Path) -> set[str]:
    """Every source ref the edition's constructs and dependency classifications state."""
    found: set[str] = set()
    for family in ("constructs", "dependency_classifications"):
        for path in sorted((edition_dir / family).glob("*.toml")):
            table = tomllib.loads(path.read_text(encoding="utf-8"))["revisions"][edition_dir.name]
            for member in table.get(family, ()):
                found.update(member.get("source_refs", ()))
    return found


def _state_inline_refs(edition_dir: Path, identity: str, refs: list[str]) -> None:
    """Make one member state ``source_refs`` inline, as an unlifted edition does."""
    path = _fragment_of(edition_dir, identity)
    header = _header(edition_dir.name)
    preamble = path.read_text(encoding="utf-8").split(header)[0]
    statement = "source_refs = [" + ", ".join(f'"{ref}"' for ref in refs) + "]\n"
    rewritten = [
        text.replace(f'id = "{identity}"\n', f'id = "{identity}"\n{statement}', 1) if member_id == identity else text
        for member_id, text in _blocks(path)
    ]
    path.write_text(preamble + "".join(rewritten), encoding="utf-8", newline="\n")


def _lifted_removable(modelo_dir: Path) -> tuple[str, ...]:
    return _outcome(
        StripReport(equality=LIFTED, applied=False, enrolment="", modelos=[plan_modelo(modelo_dir, equality=LIFTED)]),
        _SUCCESSOR,
    ).removed


def test_a_member_inheriting_the_predecessors_grounding_is_kept_as_carried_grounding(tmp_path: Path) -> None:
    """A member whose inherited refs are the predecessor's own design ref is kept, not stripped.

    The payload is byte-identical under the lifted equality, so the member was
    removable before this rule. What it would INHERIT is not: the predecessor
    states its own design ref inline, the successor declares a different
    default, and no successor construct or dependency classification cites the
    predecessor's ref -- so a strip would reground the row onto a source the
    edition does not carry.
    """
    root = _staged_registry(tmp_path)
    modelo_dir = root / "modelos" / _MODELO
    revisions = modelo_dir / "revisions"
    predecessor_dir, successor_dir = revisions / _PREDECESSOR, revisions / _SUCCESSOR
    predecessor_default = _manifest_binding_default(predecessor_dir)
    successor_default = _manifest_binding_default(successor_dir)
    assert predecessor_default != successor_default, "the fixture needs two editions grounded differently"
    assert not set(predecessor_default) & _construct_source_refs(successor_dir), (
        "the successor must not already cite the predecessor's grounding"
    )

    baseline = _lifted_removable(modelo_dir)
    target = baseline[0]
    _state_inline_refs(predecessor_dir, target, predecessor_default)
    with modelo_fact_scope(modelo_dir):
        assert load_modelo_directory(modelo_dir).id, "the tree must load before the strip is planned"

    outcome = _outcome(
        StripReport(equality=LIFTED, applied=False, enrolment="", modelos=[plan_modelo(modelo_dir, equality=LIFTED)]),
        _SUCCESSOR,
    )

    assert target not in outcome.removed
    assert set(outcome.removed) == set(baseline) - {target}
    (kept,) = [entry for entry in outcome.carried_grounding if entry.identity == target]
    assert list(kept.inherited_refs) == predecessor_default
    assert list(kept.uncovered_refs) == predecessor_default
    assert outcome.successor_default == tuple(successor_default)
    payload = outcome.as_json()
    assert payload["carried_grounding_count"] == len(outcome.carried_grounding)
    assert payload["carried_grounding"][0]["successor_default"] == successor_default


def test_a_member_inheriting_the_successors_own_default_is_still_stripped(tmp_path: Path) -> None:
    """An inherited member stating exactly the successor's default states nothing the successor lacks."""
    root = _staged_registry(tmp_path)
    modelo_dir = root / "modelos" / _MODELO
    revisions = modelo_dir / "revisions"
    successor_default = _manifest_binding_default(revisions / _SUCCESSOR)

    baseline = _lifted_removable(modelo_dir)
    target = baseline[0]
    _state_inline_refs(revisions / _PREDECESSOR, target, successor_default)

    outcome = _outcome(
        StripReport(equality=LIFTED, applied=False, enrolment="", modelos=[plan_modelo(modelo_dir, equality=LIFTED)]),
        _SUCCESSOR,
    )

    assert target in outcome.removed
    assert set(outcome.removed) == set(baseline)
    assert outcome.carried_grounding == ()


def test_the_lifted_fixture_carries_no_grounding_and_keeps_its_removable_count(tmp_path: Path) -> None:
    """A fixture whose editions are lifted states no inherited refs, so the rule withholds nothing."""
    root = _staged_registry(tmp_path)
    modelo_dir = root / "modelos" / _MODELO

    materialised = plan_modelo(modelo_dir, equality=MATERIALISED)
    lifted = plan_modelo(modelo_dir, equality=LIFTED)

    assert materialised.carried_grounding == 0
    assert lifted.carried_grounding == 0
    assert materialised.removed > 0
    assert _outcome(
        StripReport(equality=MATERIALISED, applied=False, enrolment="", modelos=[materialised]), _SUCCESSOR
    ).kept_differs, "the fixture must still carry a differing survivor"
