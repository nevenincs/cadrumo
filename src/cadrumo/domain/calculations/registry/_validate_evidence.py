"""Legal/source evidence and source-citation validation helpers."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from collections.abc import Iterable, Mapping
from functools import lru_cache
from pathlib import Path

from ....core.config import load_settings
from ....core.resources import resolve_companion_binary
from ._schema import LegalReference, SourceCitation, SourceReference
from ._text import normalise_corpus_text

_SourceTextCacheKey = tuple[str, str, int, int]
_NORMALISED_SOURCE_TEXT_CACHE: dict[_SourceTextCacheKey, str] = {}
_LOGGER = logging.getLogger(__name__)

_CORPUS_TEXT_CACHE_FILENAME = "cadrumo_corpus_text_cache.json"


@lru_cache(maxsize=4096)
def _normalise_required_text(text: str) -> str:
    return normalise_corpus_text(text)


_DISK_CACHE: dict[str, str] | None = None
_DISK_CACHE_DIRTY: bool = False


def _corpus_text_cache_path() -> Path:
    """Return the settings-derived corpus-text cache file location.

    Defaults under ``<cadrumo_local_storage_root>/cache/corpus-text`` (scoped
    per user by the storage root), replacing the former shared OS-temp-dir
    location that any two users or CI containers on one host could clobber.
    """
    return load_settings().cadrumo_corpus_text_cache_dir / _CORPUS_TEXT_CACHE_FILENAME


def reset_corpus_text_cache() -> None:
    """Drop the in-process corpus-text cache memos (test isolation only)."""
    global _DISK_CACHE, _DISK_CACHE_DIRTY
    _DISK_CACHE = None
    _DISK_CACHE_DIRTY = False
    _NORMALISED_SOURCE_TEXT_CACHE.clear()


def flush_corpus_text_cache() -> None:
    """Persist accumulated corpus-text entries in one write.

    Cache misses only mutate the in-process mapping and mark it dirty; the
    validation entry points flush once when they finish. Writing per miss was
    accidentally quadratic: every miss re-read and fully rewrote a JSON file
    that grows to tens of megabytes, which alone cost ~13 seconds of the
    first-touch registry validation on an end-user machine.
    """
    global _DISK_CACHE_DIRTY
    if not _DISK_CACHE_DIRTY or _DISK_CACHE is None:
        return
    _write_disk_cache(_DISK_CACHE)
    _DISK_CACHE_DIRTY = False


def _load_disk_cache() -> dict[str, str]:
    global _DISK_CACHE
    if _DISK_CACHE is not None:
        return _DISK_CACHE
    cache_path = _corpus_text_cache_path()
    if not cache_path.is_file():
        _DISK_CACHE = {}
        return _DISK_CACHE
    try:
        with open(cache_path, encoding="utf-8") as f:
            loaded: dict[str, str] = json.load(f)
            _DISK_CACHE = loaded
            return loaded
    except Exception:
        # Degrade to a cache miss (the entries recompute deterministically),
        # but surface the anomaly rather than swallowing it silently.
        _LOGGER.warning("Ignoring unreadable corpus text cache at %s; recomputing", cache_path, exc_info=True)
        _DISK_CACHE = {}
        return _DISK_CACHE


def _write_disk_cache(data: dict[str, str]) -> None:
    cache_path = _corpus_text_cache_path()
    temp_name = None
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        # Read-merge-before-write narrows the multi-process last-writer-wins
        # window that the atomic ``os.replace`` alone does not close: fold in
        # any entries a concurrent writer committed since our in-memory copy
        # loaded, so a parallel writer's new key is not dropped. The residual
        # race (two writers merging the same pre-image) can only cost a
        # recompute, never a wrong value, because every key embeds the source
        # file's size and mtime -- a stale entry cannot match a changed file.
        merged: dict[str, str] = {}
        if cache_path.is_file():
            try:
                with open(cache_path, encoding="utf-8") as f:
                    on_disk = json.load(f)
                if isinstance(on_disk, dict):
                    merged.update(on_disk)
            except Exception:
                _LOGGER.debug("Ignoring unreadable corpus text cache while merging at %s", cache_path, exc_info=True)
        merged.update(data)
        with tempfile.NamedTemporaryFile("w", dir=cache_path.parent, delete=False, encoding="utf-8") as tf:
            # Compact separators: this is a machine cache that reaches tens of
            # megabytes; indentation only inflates every read and write.
            json.dump(merged, tf, ensure_ascii=False, separators=(",", ":"))
            temp_name = tf.name
        os.replace(temp_name, cache_path)
    except Exception:
        _LOGGER.warning("Could not write corpus text cache at %s", cache_path, exc_info=True)
        if temp_name is not None:
            try:
                os.unlink(temp_name)
            except Exception:
                _LOGGER.debug("Could not remove temporary corpus text cache file %s", temp_name, exc_info=True)


def _extract_pdf_text_impl(path: str) -> str:
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:  # pragma: no cover - dependency is required by pyproject.
        raise OSError("pypdfium2 is required to validate manual PDF citations") from exc
    try:
        pdf = pdfium.PdfDocument(path)
        pages: list[str] = []
        try:
            for index in range(len(pdf)):
                page = pdf[index]
                try:
                    text_page = page.get_textpage()
                    try:
                        pages.append(text_page.get_text_range())
                    finally:
                        text_page.close()
                finally:
                    page.close()
        finally:
            pdf.close()
        return "\n".join(pages)
    except Exception as exc:
        raise OSError(f"could not extract text from manual PDF {path}") from exc


class EvidenceValidator:
    """Validate legal authority, source tiers, and source-citation text evidence."""

    def __init__(
        self,
        *,
        legal_refs: Mapping[str, LegalReference],
        source_refs: Mapping[str, SourceReference],
        source_root: Path | None,
    ) -> None:
        self._legal = legal_refs
        self._sources = source_refs
        self._source_root = source_root
        self._source_text_cache: dict[str, str] = {}

    def require_source_tier(
        self,
        scope: str,
        owner: str,
        refs: Iterable[str],
        required_tier: str,
    ) -> list[str]:
        if any(
            (source := self._sources.get(ref)) is not None and source.evidence_tier == required_tier for ref in refs
        ):
            return []
        return [f"{scope}: {owner} requires {required_tier} source evidence"]

    def require_any_source_tier(
        self,
        scope: str,
        owner: str,
        refs: Iterable[str],
        allowed_tiers: Iterable[str],
    ) -> list[str]:
        allowed = tuple(allowed_tiers)
        if any((source := self._sources.get(ref)) is not None and source.evidence_tier in allowed for ref in refs):
            return []
        if len(allowed) == 1:
            requirement = f"{allowed[0]} source evidence"
        else:
            requirement = f"one of {', '.join(allowed)} source evidence"
        return [f"{scope}: {owner} requires {requirement}"]

    def validate_source_citations(
        self,
        scope: str,
        owner: str,
        refs: Iterable[str],
        citations: Iterable[SourceCitation],
        required_tier: str,
    ) -> list[str]:
        failures: list[str] = []
        refs_set = set(refs)
        citations_tuple = tuple(citations)
        if not citations_tuple:
            return [f"{scope}: {owner} requires source citations"]
        for citation in citations_tuple:
            if citation.source_ref not in refs_set:
                failures.append(
                    f"{scope}: {owner} source citation {citation.source_ref!r} is not listed in source_refs",
                )
                continue
            source = self._sources.get(citation.source_ref)
            if source is None:
                continue
            if source.evidence_tier != required_tier:
                failures.append(
                    f"{scope}: {owner} source citation {citation.source_ref!r} is not {required_tier} evidence",
                )
                continue
            if self._source_root is None:
                continue
            try:
                source_text = self._source_text(source)
            except FileNotFoundError as exc:
                failures.append(f"{scope}: {owner} source citation {citation.source_ref!r} cannot be read: {exc}")
                continue
            except OSError as exc:
                failures.append(f"{scope}: {owner} source citation {citation.source_ref!r} cannot be read: {exc}")
                continue
            for required in citation.required_text:
                if _normalise_required_text(required) not in source_text:
                    failures.append(
                        f"{scope}: {owner} source citation {citation.source_ref!r} missing text {required!r}",
                    )
        return failures

    def _source_text(self, source: SourceReference) -> str:
        cached = self._source_text_cache.get(source.id)
        if cached is not None:
            return cached
        if self._source_root is None:
            return ""
        source_root = self._source_root.expanduser().resolve()
        source_path = (source_root / source.corpus_path).expanduser().resolve()
        if source_root not in source_path.parents and source_path != source_root:
            raise OSError(f"source {source.id!r} escapes source root")
        if not source_path.is_file():
            # The command-bearing wheel sheds corpus source binaries; the
            # mandatory cadrumo_data namespace supplies the same bytes at the
            # mirrored relative path, keeping required_text verification
            # byte-identical to a full checkout.
            companion_path = resolve_companion_binary(*source.corpus_path.split("/"))
            if companion_path is not None:
                source_path = companion_path
        stat = source_path.stat()
        source_key = (source.kind, str(source_path), stat.st_size, stat.st_mtime_ns)
        global_cached = _NORMALISED_SOURCE_TEXT_CACHE.get(source_key)
        if global_cached is not None:
            self._source_text_cache[source.id] = global_cached
            return global_cached

        # Check disk cache
        cache_key_str = f"{source.kind}:{source_path}:{stat.st_size}:{stat.st_mtime_ns}"
        disk_cache = _load_disk_cache()
        if cache_key_str in disk_cache:
            normalised = disk_cache[cache_key_str]
            _NORMALISED_SOURCE_TEXT_CACHE[source_key] = normalised
            self._source_text_cache[source.id] = normalised
            return normalised

        if source.kind == "manual_pdf":
            text = _extract_pdf_text_impl(str(source_path))
        else:
            text = source_path.read_text(encoding="utf-8", errors="replace")
        normalised = normalise_corpus_text(text)

        _NORMALISED_SOURCE_TEXT_CACHE[source_key] = normalised
        self._source_text_cache[source.id] = normalised
        disk_cache[cache_key_str] = normalised
        global _DISK_CACHE_DIRTY
        _DISK_CACHE_DIRTY = True
        return normalised
