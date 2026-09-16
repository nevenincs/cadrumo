from __future__ import annotations

import os
from pathlib import Path

import pytest

from dev.registry.compiler.record_design_schema import (
    RecordDesignExtraction,
    RecordDesignSkippedSheet,
)

from ..record_design_cache import (
    RECORD_DESIGN_CACHE_DIR_ENV,
    load_cached_record_design,
    record_design_cache_key,
    store_cached_record_design,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _source(tmp_path: Path) -> Path:
    modelo = tmp_path / "modelo_303" / "files"
    modelo.mkdir(parents=True)
    source = modelo / "design.xlsx"
    source.write_bytes(b"workbook")
    return source


def _fingerprint(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return str(path), stat.st_size, stat.st_mtime_ns


def test_key_follows_the_source_and_its_sidecars(tmp_path: Path) -> None:
    source = _source(tmp_path)
    original = record_design_cache_key(source, _fingerprint(source))
    assert original == record_design_cache_key(source, _fingerprint(source))

    source.write_bytes(b"workbook, revised")
    os.utime(source, ns=(source.stat().st_atime_ns, source.stat().st_mtime_ns + 1_000_000))
    revised = record_design_cache_key(source, _fingerprint(source))
    assert revised != original

    (source.parent / f"{source.name}.record-design-correction.json").write_text('{"corrections": []}', encoding="utf-8")
    assert record_design_cache_key(source, _fingerprint(source)) != revised


def test_round_trip_and_refusal_of_a_corrupt_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(RECORD_DESIGN_CACHE_DIR_ENV, str(tmp_path / "cache"))
    extraction = RecordDesignExtraction(
        source="design.xlsx",
        sheets=(),
        skipped=(RecordDesignSkippedSheet(name="TABLAS", reason="lookup tab", declared_non_record=True),),
    )
    assert load_cached_record_design("key") is None

    store_cached_record_design("key", extraction)
    assert load_cached_record_design("key") == extraction

    entry = next((tmp_path / "cache").glob("record_design_key.json"))
    entry.write_text("{}", encoding="utf-8")
    assert load_cached_record_design("key") is None
    assert not entry.exists()
