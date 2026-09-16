"""A source path is resolved once per path, not once per ingested row.

Provenance keeps the resolved source's basename, so resolution decides the
stored name whenever the given path is a link or differs in spelling.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from ..providers import base as provider_base
from ..providers.base import FinancialProvider, _resolved_absolute_source_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


@pytest.fixture(autouse=True)
def _forget_resolved_paths() -> Iterator[None]:
    provider_base._clear_resolved_source_paths()
    yield
    provider_base._clear_resolved_source_paths()


@pytest.fixture
def resolutions(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    resolved: list[Path] = []
    original = Path.resolve

    def counting(self: Path, *args: Any, **kwargs: Any) -> Path:
        resolved.append(self)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", counting)
    return resolved


def _provider() -> FinancialProvider:
    from ..providers.csv import CsvProvider

    return CsvProvider()


def test_every_row_of_one_source_resolves_its_path_once(tmp_path: Path, resolutions: list[Path]) -> None:
    source = tmp_path / "statement.csv"
    source.write_text("x", encoding="utf-8")
    provider = _provider()

    stamped = [
        provider.build_provenance(path=source, source_sha256="a" * 64, source_row_index=index) for index in range(1, 26)
    ]

    resolved_by_provider = resolutions.count(source)

    assert resolved_by_provider == 1
    assert [record.source_path for record in stamped] == [Path(source.resolve().name)] * 25


def test_a_second_source_resolves_its_own_path(tmp_path: Path, resolutions: list[Path]) -> None:
    """TEETH: the answer is kept per path, never shared between paths."""
    first = tmp_path / "one.csv"
    second = tmp_path / "nested" / "two.csv"
    second.parent.mkdir()
    for path in (first, second):
        path.write_text("x", encoding="utf-8")
    provider = _provider()

    stamped_first = provider.build_provenance(path=first, source_sha256="a" * 64, source_row_index=1)
    stamped_second = provider.build_provenance(path=second, source_sha256="b" * 64, source_row_index=1)
    resolved_by_provider = (resolutions.count(first), resolutions.count(second))

    assert stamped_first.source_path == Path(first.resolve().name)
    assert stamped_second.source_path == Path(second.resolve().name)
    assert stamped_first.source_path != stamped_second.source_path
    assert resolved_by_provider == (1, 1)


def test_a_relative_path_is_stamped_with_its_resolved_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "relative.csv"
    source.write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    stamped = _provider().build_provenance(path=Path("relative.csv"), source_sha256="a" * 64, source_row_index=1)

    assert stamped.source_path == Path(source.resolve().name)


def test_the_resolution_cache_stays_bounded(tmp_path: Path) -> None:
    bound = _resolved_absolute_source_path.cache_info().maxsize
    assert bound is not None, "an unbounded resolution cache would retain every path a host ever imported"
    for index in range(bound + 5):
        _resolved_absolute_source_path(str(tmp_path / f"{index}.csv"))

    assert _resolved_absolute_source_path.cache_info().currsize == bound


def test_a_relative_path_follows_a_change_of_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """STALE KEY: the same relative spelling in another directory names another file."""
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    for directory in (first_dir, second_dir):
        directory.mkdir()
    (first_dir / "real-one.csv").write_text("x", encoding="utf-8")
    (second_dir / "real-two.csv").write_text("x", encoding="utf-8")
    for directory, target in ((first_dir, "real-one.csv"), (second_dir, "real-two.csv")):
        try:
            (directory / "statement.csv").symlink_to(directory / target)
        except OSError:
            pytest.skip("this platform refuses unprivileged symbolic links")
    provider = _provider()

    monkeypatch.chdir(first_dir)
    in_first = provider.build_provenance(path=Path("statement.csv"), source_sha256="a" * 64, source_row_index=1)
    monkeypatch.chdir(second_dir)
    in_second = provider.build_provenance(path=Path("statement.csv"), source_sha256="a" * 64, source_row_index=1)

    assert in_first.source_path == Path("real-one.csv")
    assert in_second.source_path == Path("real-two.csv")
