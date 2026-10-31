"""A content-keyed TOML build answers per distinct bytes, never per path or stat identity."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryLoadError

from ..loader_cache import TomlContentCache

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _counting_cache() -> tuple[TomlContentCache[tuple[str, int]], list[Path]]:
    built: list[Path] = []

    def build(path: Path, document: dict[str, object]) -> tuple[str, int]:
        built.append(path)
        value = document["value"]
        if not isinstance(value, int):
            raise RegistryLoadError(f"{path}: value must be an integer")
        return ("value", value)

    return TomlContentCache(build, error_factory=RegistryLoadError), built


def _write(path: Path, text: str) -> Path:
    path.write_bytes(text.encode("utf-8"))
    return path


def test_identical_bytes_at_different_paths_build_once(tmp_path: Path) -> None:
    cache, built = _counting_cache()
    first = _write(tmp_path / "a.toml", "value = 1\n")
    second = _write(tmp_path / "b.toml", "value = 1\n")

    assert cache.load(first) is cache.load(second)
    assert built == [first]
    assert len(cache) == 1


def test_a_stat_preserving_rewrite_builds_afresh(tmp_path: Path) -> None:
    cache, built = _counting_cache()
    path = _write(tmp_path / "a.toml", "value = 1\n")
    assert cache.load(path) == ("value", 1)
    before = path.stat()

    _write(path, "value = 2\n")
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    after = path.stat()

    assert (after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns)
    assert cache.load(path) == ("value", 2)
    assert built == [path, path]


def test_a_refusal_is_raised_on_every_call_naming_the_path_asked_about(tmp_path: Path) -> None:
    cache, built = _counting_cache()
    first = _write(tmp_path / "a.toml", 'value = "one"\n')
    second = _write(tmp_path / "b.toml", 'value = "one"\n')

    for path in (first, first, second):
        with pytest.raises(RegistryLoadError, match=f"{path.name}: value must be an integer"):
            cache.load(path)

    assert built == [first, first, second]
    assert len(cache) == 0


@pytest.mark.parametrize(
    ("payload", "message"),
    [(b"value = [", "invalid TOML"), (b"\xff\xfe", "invalid TOML")],
)
def test_unparseable_bytes_refuse_in_read_toml_wording(tmp_path: Path, payload: bytes, message: str) -> None:
    cache, built = _counting_cache()
    path = tmp_path / "a.toml"
    path.write_bytes(payload)

    with pytest.raises(RegistryLoadError, match=f"{path.name}: {message}"):
        cache.load(path)
    assert built == []


def test_an_unreadable_path_refuses_in_read_toml_wording(tmp_path: Path) -> None:
    cache, _built = _counting_cache()

    with pytest.raises(RegistryLoadError, match="cannot read TOML"):
        cache.load(tmp_path / "absent.toml")
