"""Cross-process cache of parsed record-design sources for the development compiler.

Reading an official record design means parsing a workbook or a PDF, which
costs a cold process well over ten seconds across the bundled registry. The
parse is a pure function of the source bytes, its hand-authored sidecars and
the extractor code, so its typed result is persisted once per such input
state and served to every later process, following the corpus-text cache
convention: an explicit ``CADRUMO_RECORD_DESIGN_CACHE_DIR`` wins, otherwise
the checkout's own ``.cache`` holds it, outside the application's storage root.
"""

from __future__ import annotations

import logging
import os
from functools import cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from cadrumo.core.atomic_write import atomic_write_best_effort_text
from cadrumo.core.hashing import content_hash_hex, sha256_hex
from dev.cache_root import dev_cache_dir
from dev.registry.compiler import record_design_schema
from dev.registry.compiler.record_design_schema import RecordDesignExtraction

from . import record_design_sources

RECORD_DESIGN_CACHE_DIR_ENV: Final = "CADRUMO_RECORD_DESIGN_CACHE_DIR"
_CACHE_SCHEMA: Final = "record-design-extraction-cache/v1"
_EXTRACTOR_MODULE_GLOB: Final = "record_design*.py"
_EXTRACTOR_PACKAGES: Final = ("openpyxl", "pdfplumber", "pypdfium2", "xlrd")
_LOGGER = logging.getLogger(__name__)


def record_design_cache_dir() -> Path:
    """Resolve the runner-local record-design extraction cache directory."""
    override = os.environ.get(RECORD_DESIGN_CACHE_DIR_ENV)
    if override:
        return Path(override)
    return dev_cache_dir("record-design")


@cache
def _extractor_code_fingerprint() -> str:
    """Hash the extractor sources and reader libraries, once per process.

    Every module of the record-design extractor, the typed result schema and
    the shared cell-text coercion contribute their bytes; the parsing
    libraries contribute their versions. Any change yields a new key, so a
    result parsed by earlier code is never served to the current code.
    """
    compiler_root = Path(__file__).resolve().parent
    sources = sorted(compiler_root.glob(_EXTRACTOR_MODULE_GLOB))
    sources.append(Path(record_design_schema.__file__).resolve())
    sources.append(Path(record_design_sources.__file__).resolve().parent.parent.parent / "core" / "tabular.py")
    digests: dict[str, str] = {}
    for source in sources:
        try:
            digests[source.name] = sha256_hex(source.read_bytes().replace(b"\r\n", b"\n"))
        except OSError:
            digests[source.name] = "unreadable"
    libraries: dict[str, str] = {}
    for name in _EXTRACTOR_PACKAGES:
        try:
            libraries[name] = version(name)
        except PackageNotFoundError:
            libraries[name] = "absent"
    return content_hash_hex({"schema": _CACHE_SCHEMA, "sources": digests, "libraries": libraries})


def _stat_row(path: Path | None) -> tuple[str, int, int] | None:
    if path is None:
        return None
    try:
        stat = path.stat()
    except OSError:
        return None
    return str(path), stat.st_size, stat.st_mtime_ns


def record_design_cache_key(source_path: Path, fingerprint: tuple[str, int, int]) -> str:
    """Return the cache key for one source at its observed stat fingerprint.

    The key binds the source file, both hand-authored sidecars that steer its
    reading (the per-binary correction sidecar and the per-modelo declared
    non-record sheets) and the extractor fingerprint.
    """
    sidecars = (
        record_design_sources.correction_sidecar_path(source_path),
        record_design_sources.declared_non_record_sheets_path(source_path),
    )
    return content_hash_hex(
        {
            "schema": _CACHE_SCHEMA,
            "extractor": _extractor_code_fingerprint(),
            "source": list(fingerprint),
            "sidecars": [list(row) if (row := _stat_row(sidecar)) is not None else None for sidecar in sidecars],
        }
    )


def _cache_path(key: str) -> Path:
    return record_design_cache_dir() / f"record_design_{key}.json"


def load_cached_record_design(key: str) -> RecordDesignExtraction | None:
    """Return the persisted extraction for ``key``, or ``None`` to re-extract."""
    path = _cache_path(key)
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    try:
        return RecordDesignExtraction.model_validate_json(raw)
    except (ValidationError, ValueError):
        _LOGGER.warning("Ignoring unreadable record-design cache entry at %s; re-extracting", path, exc_info=True)
        try:
            path.unlink()
        except OSError:
            _LOGGER.debug("Could not remove record-design cache entry at %s", path, exc_info=True)
        return None


def store_cached_record_design(key: str, extraction: RecordDesignExtraction) -> None:
    """Persist one extraction under ``key``; a failed write only costs the next process a parse."""
    path = _cache_path(key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_best_effort_text(path, extraction.model_dump_json(), encoding="utf-8")
    except Exception:
        _LOGGER.warning("Could not write record-design cache entry at %s", path, exc_info=True)


__all__ = [
    "RECORD_DESIGN_CACHE_DIR_ENV",
    "load_cached_record_design",
    "record_design_cache_dir",
    "record_design_cache_key",
    "store_cached_record_design",
]
