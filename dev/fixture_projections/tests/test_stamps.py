"""A stamp says fresh only while every input and output still has the content it recorded."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ..registry import Command, FixtureFamily, InputGroup
from ..stamps import FixtureState, InputDigests, family_inputs, family_status, stamp_path, write_stamp

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_AUTHORITY = {"database_sha256": "a" * 64, "logical_generation": "b" * 64}


def _family(*, committed: bool = True) -> FixtureFamily:
    return FixtureFamily(
        name="sample",
        summary="A sample projection.",
        inputs=(InputGroup("producer", ("tools/produce.py",)), InputGroup("personas", ("personas",))),
        check=(Command(("{python}", "tools/produce.py", "--check")),),
        producer=Command(("{python}", "tools/produce.py")),
        output_root="out",
        outputs=("*.json",),
        committed=committed,
    )


def _tree(root: Path) -> None:
    (root / "tools").mkdir()
    (root / "tools" / "produce.py").write_text("print('produce')\n", encoding="utf-8")
    (root / "personas" / "one").mkdir(parents=True)
    (root / "personas" / "one" / "persona.toml").write_text("id = 'one'\n", encoding="utf-8")
    (root / "out").mkdir()
    (root / "out" / "fixture.json").write_text("{}\n", encoding="utf-8")


def _status(root: Path, cache: Path, *, authority: dict[str, str] = _AUTHORITY, committed: bool = True):
    family = _family(committed=committed)
    inputs = family_inputs(family, InputDigests(root), authority)
    return family_status(family, root, inputs, cache_directory=cache)


def _stamp(root: Path, cache: Path, *, committed: bool = True) -> Path:
    family = _family(committed=committed)
    return write_stamp(family, root, family_inputs(family, InputDigests(root), _AUTHORITY), cache_directory=cache)


def test_a_family_with_no_stamp_is_missing(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _tree(root)

    result = _status(root, tmp_path / "cache")

    assert result.state is FixtureState.MISSING
    assert result.reasons == ("no stamp",)


def test_a_family_with_no_outputs_is_missing_even_when_stamped(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _tree(root)
    _stamp(root, tmp_path / "cache")
    (root / "out" / "fixture.json").unlink()

    assert _status(root, tmp_path / "cache").state is FixtureState.MISSING


def test_a_stamp_over_unchanged_content_is_fresh_whatever_the_modification_times(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _tree(root)
    _stamp(root, tmp_path / "cache")
    for path in (root / "tools" / "produce.py", root / "out" / "fixture.json"):
        os.utime(path, (1, 1))

    assert _status(root, tmp_path / "cache").state is FixtureState.FRESH


def test_a_changed_input_is_stale_and_named(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _tree(root)
    _stamp(root, tmp_path / "cache")
    (root / "personas" / "one" / "persona.toml").write_text("id = 'two'\n", encoding="utf-8")
    (root / "personas" / "one" / "ledger.csv").write_text("date,amount\n", encoding="utf-8")

    result = _status(root, tmp_path / "cache")

    assert result.state is FixtureState.STALE
    assert result.reasons == (
        "personas: personas/one/persona.toml changed",
        "personas: personas/one/ledger.csv added",
    )


def test_a_line_ending_change_alone_is_not_a_changed_input(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _tree(root)
    (root / ".gitattributes").write_text("* text=auto eol=lf\n", encoding="utf-8")
    _stamp(root, tmp_path / "cache")
    (root / "tools" / "produce.py").write_bytes(b"print('produce')\r\n")

    assert _status(root, tmp_path / "cache").state is FixtureState.FRESH


def test_a_republished_authority_is_stale(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _tree(root)
    _stamp(root, tmp_path / "cache")

    result = _status(root, tmp_path / "cache", authority={**_AUTHORITY, "database_sha256": "c" * 64})

    assert result.state is FixtureState.STALE
    assert result.reasons == ("authority: database_sha256 changed",)


def test_an_edited_or_extra_output_is_stale(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _tree(root)
    _stamp(root, tmp_path / "cache")
    (root / "out" / "fixture.json").write_text('{"edited": true}\n', encoding="utf-8")
    (root / "out" / "extra.json").write_text("{}\n", encoding="utf-8")

    result = _status(root, tmp_path / "cache")

    assert result.reasons == ("output: fixture.json changed", "output: extra.json added")


def test_a_generated_family_keeps_its_stamp_beside_its_outputs(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _tree(root)

    path = _stamp(root, tmp_path / "cache", committed=False)

    assert path == stamp_path(_family(committed=False), root) == root / "out" / ".sample.fixture-stamp.json"
    assert _status(root, tmp_path / "cache", committed=False).state is FixtureState.FRESH
    assert _stamp(root, tmp_path / "cache").parent == tmp_path / "cache"
