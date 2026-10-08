"""Incomplete source and data corpora cannot produce a reachability verdict."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..unreachable_code import scan_unreachable_code
from ..unreachable_memo import parse_module
from ..unreachable_models import Confidence, UnreachableCodeOutcome
from ..unreachable_reporting import filter_by_confidence, result_as_json
from ..unreachable_tree import EntryPoint, OutsideCorpus, ShippedTreeSpec

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _spec(root: Path) -> ShippedTreeSpec:
    package = root / "src" / "pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "cli.py").write_text("def main(): pass\n", encoding="utf-8")
    (root / "dev").mkdir()
    return ShippedTreeSpec(
        repo_root=root,
        src_root=root / "src",
        package="pkg",
        entry_points=(EntryPoint("pkg.cli", "main"),),
        outside=(OutsideCorpus("dev", root / "dev"),),
        data_globs=("_data/**/*.json",),
    )


@pytest.mark.parametrize("source", [b"def (: \n", b"\xff\xfe"])
def test_broken_reference_source_is_unavailable_with_its_reason(tmp_path: Path, source: bytes) -> None:
    spec = _spec(tmp_path)
    path = tmp_path / "dev" / "broken.py"
    path.write_bytes(source)

    result = scan_unreachable_code(spec)

    assert result.outcome is UnreachableCodeOutcome.ERROR
    assert "broken.py" in result.reason
    assert "SyntaxError" in result.reason
    assert not result.is_green
    assert filter_by_confidence(result, Confidence.EXACT).outcome is UnreachableCodeOutcome.ERROR
    assert "broken.py" in result_as_json(result)


@pytest.mark.parametrize("source", [b"{broken", b"\xff\xfe"])
def test_broken_data_is_unavailable_instead_of_unused_members(tmp_path: Path, source: bytes) -> None:
    spec = _spec(tmp_path)
    data = tmp_path / "src" / "pkg" / "_data"
    data.mkdir()
    (data / "broken.json").write_bytes(source)

    result = scan_unreachable_code(spec)

    assert result.outcome is UnreachableCodeOutcome.ERROR
    assert "broken.json" in result.reason
    assert "coverage is unproven" in result.reason
    assert result.symbols == ()


def test_missing_reference_corpus_cannot_look_empty(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    (tmp_path / "dev").rmdir()

    result = scan_unreachable_code(spec)

    assert result.outcome is UnreachableCodeOutcome.ERROR
    assert "does not exist" in result.reason


@pytest.mark.parametrize("source", [b"\xef\xbb\xbfVALUE = 1\n", b"# coding: latin-1\nVALUE = 'caf\xe9'\n"])
def test_source_parsing_honours_python_encoding_rules(tmp_path: Path, source: bytes) -> None:
    path = tmp_path / "encoded.py"
    path.write_bytes(source)

    assert parse_module(path).body


def test_a_same_named_function_in_another_module_is_not_a_console_entrypoint(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    package = tmp_path / "src" / "pkg"
    (package / "cli.py").write_text("from . import work\ndef main(): pass\n", encoding="utf-8")
    (package / "work.py").write_text("def main(): pass\n", encoding="utf-8")

    result = scan_unreachable_code(spec)

    assert result.outcome is UnreachableCodeOutcome.FINDINGS
    assert {(finding.module, finding.name) for finding in result.symbols} == {("pkg.work", "main")}
