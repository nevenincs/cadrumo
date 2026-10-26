"""Tests for TOML/YAML repository quality checks."""

from pathlib import Path

import pytest

from dev.quality.data_files import check, check_file, data_files

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_accepts_cloudformation_tags(tmp_path: Path) -> None:
    source = tmp_path / "template.yaml"
    source.write_text("value: !Ref Parameter\n", encoding="utf-8", newline="\n")
    assert check_file(source) == ()


def test_reports_toml_syntax(tmp_path: Path) -> None:
    source = tmp_path / "broken.toml"
    source.write_bytes(b"key = [1,\r\n")
    findings = check_file(source)
    assert any("invalid TOML" in finding for finding in findings)


def test_toml_syntax_check_accepts_platform_line_endings(tmp_path: Path) -> None:
    source = tmp_path / "valid.toml"
    source.write_bytes(b"value = 1\r\r\n")
    assert check_file(source) == ()


def test_yaml_check_is_read_only(tmp_path: Path) -> None:
    source = tmp_path / "broken.yml"
    original = b"key:\tvalue\n"
    source.write_bytes(original)
    assert check_file(source)
    assert source.read_bytes() == original


def test_discovery_excludes_byte_exact_corpus(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("", encoding="utf-8")
    governed = tmp_path / "registry" / "facts.toml"
    governed.parent.mkdir(parents=True)
    governed.write_text("value = 1\n", encoding="utf-8")
    corpus = tmp_path / "src/cadrumo/_data/corpus/capture.toml"
    corpus.parent.mkdir(parents=True)
    corpus.write_text("not = [valid\n", encoding="utf-8")
    assert data_files(tmp_path) == ("registry/facts.toml",)


def test_discovery_keeps_data_siblings_beside_excluded_corpus(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("", encoding="utf-8")
    sibling = tmp_path / "src/cadrumo/_data/registry/facts.toml"
    sibling.parent.mkdir(parents=True)
    sibling.write_text("value = 1\n", encoding="utf-8")
    assert data_files(tmp_path) == ("src/cadrumo/_data/registry/facts.toml",)


def test_check_discovers_untracked_files(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("", encoding="utf-8")
    (tmp_path / "new.toml").write_text("invalid = [\n", encoding="utf-8")
    assert any("new.toml" in finding for finding in check(tmp_path))
