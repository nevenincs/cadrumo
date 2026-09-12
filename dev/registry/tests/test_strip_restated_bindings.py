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

from ..strip_restated_bindings import (
    MATERIALISED,
    EditionOutcome,
    ModeloOutcome,
    StripReport,
    main,
    plan_modelo,
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


def _outcome_for(outcome: ModeloOutcome, edition: str) -> EditionOutcome:
    (found,) = [item for item in outcome.editions if item.edition == edition]
    return found
