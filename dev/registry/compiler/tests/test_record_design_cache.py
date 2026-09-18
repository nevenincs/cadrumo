from __future__ import annotations

import os
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from dev.registry.compiler.record_design_schema import (
    RecordDesignExtraction,
    RecordDesignSkippedSheet,
)

from ..record_design import extract_record_design
from ..record_design_cache import (
    RECORD_DESIGN_CACHE_DIR_ENV,
    load_cached_record_design,
    load_cached_record_design_refusal,
    record_design_cache_key,
    store_cached_record_design,
    store_cached_record_design_refusal,
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


def test_a_refusal_round_trips_and_a_corrupt_entry_re_extracts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A refusal is served back verbatim, and an unreadable one falls back to a parse.

    The message is replayed rather than summarised: a caller must read the same
    refusal whether or not a cache served it.
    """
    monkeypatch.setenv(RECORD_DESIGN_CACHE_DIR_ENV, str(tmp_path / "cache"))
    assert load_cached_record_design_refusal("key") is None

    store_cached_record_design_refusal("key", "design.xlsx: no record-design sheets found; skipped sheets: none")
    assert load_cached_record_design_refusal("key") == (
        "design.xlsx: no record-design sheets found; skipped sheets: none"
    )

    entry = next((tmp_path / "cache").glob("record_design_refusal_key.json"))
    entry.write_text("not json", encoding="utf-8")
    assert load_cached_record_design_refusal("key") is None


def test_a_refusal_and_a_reading_do_not_occupy_the_same_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The two stores are keyed apart, so one cannot be read as the other."""
    monkeypatch.setenv(RECORD_DESIGN_CACHE_DIR_ENV, str(tmp_path / "cache"))
    extraction = RecordDesignExtraction(source="design.xlsx", sheets=(), skipped=())

    store_cached_record_design("key", extraction)
    assert load_cached_record_design_refusal("key") is None

    store_cached_record_design_refusal("key", "unreadable")
    assert load_cached_record_design("key") == extraction


def test_an_unreadable_source_is_refused_once_and_replayed_thereafter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The extractor runs for the first refusal only; later processes replay it.

    ``lru_cache`` records only returns, so before the refusal was persisted an
    unreadable source re-parsed on every call in every process. The in-process
    memo is cleared here so the second call reaches the disk store, which is the
    boundary a fresh process would see.
    """
    monkeypatch.setenv(RECORD_DESIGN_CACHE_DIR_ENV, str(tmp_path / "cache"))
    source = _source(tmp_path)
    parses = 0

    def refusing_extractor(path: Path) -> RecordDesignExtraction:
        nonlocal parses
        parses += 1
        raise RegistryValidationError(f"{path}: no record-design sheets found; skipped sheets: none")

    monkeypatch.setattr("dev.registry.compiler.record_design.extract_record_design_workbook", refusing_extractor)
    extract_record_design.__globals__["_extract_record_design_cached"].cache_clear()

    with pytest.raises(RegistryValidationError, match="no record-design sheets found"):
        extract_record_design(source)
    extract_record_design.__globals__["_extract_record_design_cached"].cache_clear()
    with pytest.raises(RegistryValidationError, match="no record-design sheets found"):
        extract_record_design(source)

    assert parses == 1
