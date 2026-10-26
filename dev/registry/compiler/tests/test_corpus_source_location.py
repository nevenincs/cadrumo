"""A cited corpus file is found in one fixed order and never outside its root."""

from __future__ import annotations

from pathlib import Path

import pytest

from dev.registry.compiler import corpus_source_location
from dev.registry.compiler.corpus_source_location import (
    PACKAGED_DATA_ROOT,
    CorpusPathEscapeError,
    locate_corpus_file,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CORPUS_PATH = "corpus/manuals/example/source.txt"


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_the_source_root_copy_wins_over_the_packaged_copy(tmp_path: Path) -> None:
    direct = _write(tmp_path / _CORPUS_PATH, "direct")
    _write(tmp_path / PACKAGED_DATA_ROOT / _CORPUS_PATH, "packaged")

    assert locate_corpus_file(tmp_path, _CORPUS_PATH) == direct.resolve()


def test_the_packaged_tree_answers_when_the_source_root_lacks_the_file(tmp_path: Path) -> None:
    packaged = _write(tmp_path / PACKAGED_DATA_ROOT / _CORPUS_PATH, "packaged")

    assert locate_corpus_file(tmp_path, _CORPUS_PATH) == packaged.resolve()


def test_the_companion_namespace_answers_last(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    companion = _write(tmp_path / "companion" / "source.txt", "companion")
    root = tmp_path / "bundle"
    root.mkdir()
    requested: list[tuple[str, ...]] = []

    def resolve(*parts: str) -> Path:
        requested.append(parts)
        return companion

    monkeypatch.setattr(corpus_source_location, "resolve_companion_binary", resolve)

    assert locate_corpus_file(root, _CORPUS_PATH) == companion
    assert requested == [("corpus", "manuals", "example", "source.txt")]


def test_an_absent_file_is_reported_as_none_not_as_a_guessed_path(tmp_path: Path) -> None:
    assert locate_corpus_file(tmp_path, "corpus/manuals/absent/source.txt") is None


@pytest.mark.parametrize("corpus_path", ["../outside.txt", "corpus/../../outside.txt"])
def test_a_path_that_climbs_out_of_the_root_is_refused_even_when_the_target_exists(
    tmp_path: Path, corpus_path: str
) -> None:
    root = tmp_path / "bundle"
    root.mkdir()
    _write(tmp_path / "outside.txt", "secret")

    with pytest.raises(CorpusPathEscapeError):
        locate_corpus_file(root, corpus_path)
