"""Tests for TOML/YAML repository quality checks."""

from pathlib import Path

import pytest

from dev.quality.data_files import check, check_file, data_files, fix_file

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_accepts_cloudformation_tags(tmp_path: Path) -> None:
    source = tmp_path / "template.yaml"
    source.write_text("value: !Ref Parameter\n", encoding="utf-8", newline="\n")
    assert check_file(source) == ()


def test_reports_toml_syntax_and_line_endings(tmp_path: Path) -> None:
    source = tmp_path / "broken.toml"
    source.write_bytes(b"key = [1,\r\n")
    findings = check_file(source)
    assert any("CR or CRLF" in finding for finding in findings)
    assert any("invalid TOML" in finding for finding in findings)


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


def test_check_discovers_untracked_files(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("", encoding="utf-8")
    (tmp_path / "new.toml").write_text("invalid = [\n", encoding="utf-8")
    assert any("new.toml" in finding for finding in check(tmp_path))


def test_fix_repairs_only_safe_whitespace(tmp_path: Path) -> None:
    source = tmp_path / "owned.toml"
    source.write_bytes(b"value = 1  \r\n")
    assert fix_file(tmp_path, "owned.toml") == "owned.toml"
    assert source.read_bytes() == b"value = 1\n"


@pytest.mark.parametrize("relative,message", [("src/cadrumo/_data/corpus/evidence.toml", "byte-exact corpus"), ("src/cadrumo/locales/es/common.yml", "locale CLI")])
def test_fix_refuses_protected_paths(tmp_path: Path, relative: str, message: str) -> None:
    source = tmp_path / relative
    source.parent.mkdir(parents=True)
    source.write_text("value = 'test'\n", encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        fix_file(tmp_path, relative)


def test_fix_refuses_outside_repository(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.toml"
    outside.write_text("value = 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="inside the repository"):
        fix_file(tmp_path, str(outside))
