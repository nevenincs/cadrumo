"""A broadly read shard is parsed once; only per-Modelo schema shards stream a single key."""

from __future__ import annotations

from pathlib import Path
from typing import IO

import pytest

from .. import _lazy_catalogue
from .._lazy_catalogue import LazyLocaleCatalogue

pytestmark = [pytest.mark.hex_core]

_SHARD_TEXT = """\
cli:
  root:
    app_help: Raíz
    app_app_help: Aplicación
  late:
    title: Tarde
"""


def _catalogue_with_parse_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[LazyLocaleCatalogue, list[str]]:
    shard = tmp_path / "es" / "cli.yml"
    shard.parent.mkdir(parents=True)
    shard.write_text(_SHARD_TEXT, encoding="utf-8")
    parses: list[str] = []
    real_scan = _lazy_catalogue._scan_shard_for_key
    real_load = _lazy_catalogue.load_yaml_handle

    def counting_scan(handle: IO[str], key: str) -> str | None:
        parses.append("scan")
        return real_scan(handle, key)

    def counting_load(handle: IO[str]) -> object:
        parses.append("load")
        return real_load(handle)

    monkeypatch.setattr(_lazy_catalogue, "_scan_shard_for_key", counting_scan)
    monkeypatch.setattr(_lazy_catalogue, "load_yaml_handle", counting_load)
    return LazyLocaleCatalogue("es", shard_dir=tmp_path / "es"), parses


@pytest.mark.unit
def test_a_domain_shard_is_parsed_once_across_many_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    catalogue, parses = _catalogue_with_parse_log(tmp_path, monkeypatch)

    assert catalogue["cli.root.app_help"] == "Raíz"
    assert catalogue["cli.root.app_app_help"] == "Aplicación"
    assert catalogue["cli.late.title"] == "Tarde"
    assert parses == ["load"]


@pytest.mark.unit
def test_missing_keys_still_raise_after_a_single_parse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    catalogue, parses = _catalogue_with_parse_log(tmp_path, monkeypatch)

    with pytest.raises(KeyError):
        catalogue["cli.root.absent"]
    assert "cli.root.absent" not in catalogue
    assert catalogue.get("cli.root.app_help") == "Raíz"
    assert parses == ["load"]
