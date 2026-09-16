"""A single-key lookup streams its shard only as far as the key, with full-load parity.

A modelo listing asks each large schema shard for one title, and a full load
constructs every entry to answer it. The catalogue streams the shard up to the
requested key and falls back to the full load for anything the stream cannot
read the same way. Every answer must equal what the full load gives.
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path
from typing import IO

import pytest

from ...product_identity import PRODUCT_IDENTITY
from .. import _lazy_catalogue
from .._lazy_catalogue import (
    LazyLocaleCatalogue,
    _flatten_dict,
    _load_yaml_handle,
    _scan_shard_for_key,
    _UnscannableShardError,
)

pytestmark = [pytest.mark.hex_core]

_SHARD = "modelo/schema/900.yml"
_TITLE = "modelo.schema.900.title"

_TYPED_SHARD = """\
modelo:
  schema:
    '900':
      listed:
        - title: from a sequence member
      field:
        title: Declaración informativa
        count: 12
        ratio: 1.50
        enabled: yes
        cleared: ~
        empty: ''
        quoted_number: '0012'
        dated: 2024-01-31
        folded: >
          folded
          text
        literal: |
          line one
          line two
        list_value: [a, b]
        7: integer key
        true: boolean key
        dotted.key: dotted segment
        empty_mapping: {}
        nested:
          deep:
            leaf: deepest
      after: final
"""


def _full_load(path: Path) -> dict[str, str | None]:
    with path.open(encoding="utf-8") as handle:
        return _flatten_dict(_load_yaml_handle(handle))


def _scan(path: Path, key: str) -> str | None:
    with path.open(encoding="utf-8") as handle:
        return _scan_shard_for_key(handle, key)


def _write_shard(root: Path, text: str) -> Path:
    shard = root / "es" / _SHARD
    shard.parent.mkdir(parents=True)
    shard.write_text(text, encoding="utf-8")
    return shard


@pytest.mark.unit
def test_every_key_of_a_typed_shard_reads_as_the_full_load_reads_it(tmp_path: Path) -> None:
    shard = _write_shard(tmp_path, _TYPED_SHARD)
    full = _full_load(shard)
    assert full["modelo.schema.900.field.count"] == "12"
    assert full["modelo.schema.900.field.enabled"] == "True"
    assert full["modelo.schema.900.field.cleared"] is None
    assert full["modelo.schema.900.field.True"] == "boolean key"

    for key, expected in full.items():
        catalogue = LazyLocaleCatalogue("es", shard_dir=tmp_path / "es")
        assert catalogue[key] == expected, key


@pytest.mark.unit
def test_scalar_keys_are_answered_without_a_full_load(tmp_path: Path) -> None:
    shard = _write_shard(tmp_path, _TYPED_SHARD)
    catalogue = LazyLocaleCatalogue("es", shard_dir=tmp_path / "es")

    assert catalogue["modelo.schema.900.field.title"] == "Declaración informativa"
    assert _scan(shard, "modelo.schema.900.field.nested.deep.leaf") == "deepest"
    assert _scan(shard, "modelo.schema.900.after") == "final"
    assert Path(_SHARD) not in catalogue._loaded_shards
    assert set(catalogue._key_cache) == {"modelo.schema.900.field.title"}


@pytest.mark.unit
def test_a_shard_asked_many_keys_is_streamed_once_then_loaded_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shard = _write_shard(tmp_path, _TYPED_SHARD)
    full = _full_load(shard)
    calls: list[str] = []
    real_scan = _lazy_catalogue._scan_shard_for_key
    real_load = _lazy_catalogue._load_yaml_handle

    def counting_scan(handle: IO[str], key: str) -> str | None:
        calls.append("scan")
        return real_scan(handle, key)

    def counting_load(handle: IO[str]) -> object:
        calls.append("load")
        return real_load(handle)

    monkeypatch.setattr(_lazy_catalogue, "_scan_shard_for_key", counting_scan)
    monkeypatch.setattr(_lazy_catalogue, "_load_yaml_handle", counting_load)
    catalogue = LazyLocaleCatalogue("es", shard_dir=tmp_path / "es")

    answers = {key: catalogue.get(key) for key in full}

    assert answers == full
    assert calls == ["scan", "load"]


@pytest.mark.unit
@pytest.mark.parametrize(
    "key",
    [
        pytest.param("modelo.schema.900.field.list_value", id="sequence-value"),
        pytest.param("modelo.schema.900.listed.title", id="key-inside-a-sequence"),
        pytest.param("modelo.schema.900.field.empty_mapping", id="empty-mapping"),
        pytest.param("modelo.schema.900.field", id="mapping-value"),
        pytest.param("modelo.schema.900.field.absent", id="absent-key"),
    ],
)
def test_keys_the_stream_cannot_answer_fall_back_to_the_full_load(tmp_path: Path, key: str) -> None:
    shard = _write_shard(tmp_path, _TYPED_SHARD)
    catalogue = LazyLocaleCatalogue("es", shard_dir=tmp_path / "es")

    with pytest.raises(_UnscannableShardError):
        _scan(shard, key)
    assert catalogue.get(key) == _full_load(shard).get(key)
    assert Path(_SHARD) in catalogue._loaded_shards


@pytest.mark.unit
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param("base: &b\n  title: anchored\nmodelo:\n  schema:\n    '900':\n      title: x\n", "x", id="anchor"),
        pytest.param("modelo:\n  schema:\n    '900':\n      <<: {title: merged}\n", "merged", id="merge"),
        # A full load refuses an unhashable key, which leaves the whole shard unread.
        pytest.param("? [complex]\n: v\nmodelo:\n  schema:\n    '900':\n      title: x\n", None, id="complex-key"),
    ],
)
def test_constructs_only_a_full_load_interprets_fall_back(tmp_path: Path, text: str, expected: str | None) -> None:
    shard = _write_shard(tmp_path, text)
    catalogue = LazyLocaleCatalogue("es", shard_dir=tmp_path / "es")

    with pytest.raises(_UnscannableShardError):
        _scan(shard, _TITLE)
    assert catalogue.get(_TITLE) == expected


@pytest.mark.unit
def test_a_second_document_falls_back_to_the_full_load_refusal(tmp_path: Path) -> None:
    shard = _write_shard(tmp_path, "other: 1\n---\nmodelo:\n  schema:\n    '900':\n      title: second\n")
    catalogue = LazyLocaleCatalogue("es", shard_dir=tmp_path / "es")

    with pytest.raises(_UnscannableShardError):
        _scan(shard, _TITLE)
    assert catalogue.get(_TITLE) is None


def _packaged_schema_shards() -> list[Path]:
    root = Path(str(importlib.resources.files(PRODUCT_IDENTITY.python_package).joinpath("locales")))
    return sorted(root.glob("*/modelo/schema/*.yml"))


@pytest.mark.integration
def test_every_packaged_modelo_title_streams_to_its_full_load_value() -> None:
    shards = _packaged_schema_shards()
    assert len({shard.parents[2].name for shard in shards}) > 1
    streamed_titles = 0

    for shard in shards:
        full = _full_load(shard)
        keys = list(full)
        titles = [key for key in keys if key.startswith(f"modelo.schema.{shard.stem}.") and key.endswith(".title")]
        # Titles, both ends, and a stride through the middle exercise path tracking across the shard.
        for key in {*titles[:5], *keys[:3], *keys[-3:], *keys[:: max(1, len(keys) // 20)]}:
            try:
                streamed = _scan(shard, key)
            except _UnscannableShardError:
                # Only a value the stream cannot hold as one scalar may fall back.
                assert (full[key] or "").startswith("["), (shard, key)
                continue
            assert streamed == full[key], (shard, key)
            streamed_titles += key in titles

    assert streamed_titles > len(shards)
