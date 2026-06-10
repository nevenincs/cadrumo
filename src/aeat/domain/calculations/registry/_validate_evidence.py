"""Legal/source evidence and source-citation validation helpers."""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from collections.abc import Iterable, Mapping
from functools import lru_cache
from pathlib import Path

from ._schema import LegalReference, SourceCitation, SourceReference
from ._text import normalise_corpus_text

_SourceTextCacheKey = tuple[str, str, int]
_NORMALISED_SOURCE_TEXT_CACHE: dict[_SourceTextCacheKey, str] = {}


@lru_cache(maxsize=4096)
def _normalise_required_text(text: str) -> str:
    return normalise_corpus_text(text)


_STAT_CACHE: dict[Path, os.stat_result] = {}
_DISK_CACHE: dict[str, str] | None = None


def _cached_stat(path: Path) -> os.stat_result:
    stat = _STAT_CACHE.get(path)
    if stat is None:
        stat = path.stat()
        _STAT_CACHE[path] = stat
    return stat


def _load_disk_cache() -> dict[str, str]:
    global _DISK_CACHE
    if _DISK_CACHE is not None:
        return _DISK_CACHE
    cache_path = Path(tempfile.gettempdir()) / "aeat_corpus_text_cache.json"
    if not cache_path.is_file():
        _DISK_CACHE = {}
        return _DISK_CACHE
    try:
        with open(cache_path, encoding="utf-8") as f:
            loaded: dict[str, str] = json.load(f)
            _DISK_CACHE = loaded
            return loaded
    except Exception:
        _DISK_CACHE = {}
        return _DISK_CACHE


def _write_disk_cache(data: dict[str, str]) -> None:
    cache_path = Path(tempfile.gettempdir()) / "aeat_corpus_text_cache.json"
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=cache_path.parent, delete=False, encoding="utf-8") as tf:
            json.dump(data, tf, ensure_ascii=False, indent=2)
            temp_name = tf.name
        os.replace(temp_name, cache_path)
    except Exception:
        if temp_name is not None:
            with contextlib.suppress(Exception):
                os.unlink(temp_name)


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

    def require_legal_authority_refs(self, scope: str, owner: str, refs: Iterable[str]) -> list[str]:
        failures: list[str] = []
        for ref in refs:
            legal = self._legal.get(ref)
            if legal is not None and legal.evidence_tier != "legal_authority":
                failures.append(f"{scope}: {owner} legal ref {ref!r} is not legal authority")
        return failures

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
                    f"{scope}: {owner} source citation {citation.source_ref!r} is not listed in source_refs"
                )
                continue
            source = self._sources.get(citation.source_ref)
            if source is None:
                continue
            if source.evidence_tier != required_tier:
                failures.append(
                    f"{scope}: {owner} source citation {citation.source_ref!r} is not {required_tier} evidence"
                )
                continue
            if self._source_root is None:
                continue
            try:
                source_text = self._source_text(source)
            except OSError as exc:
                failures.append(f"{scope}: {owner} source citation {citation.source_ref!r} cannot be read: {exc}")
                continue
            for required in citation.required_text:
                if _normalise_required_text(required) not in source_text:
                    failures.append(
                        f"{scope}: {owner} source citation {citation.source_ref!r} missing text {required!r}"
                    )
        return failures

    def _source_text(self, source: SourceReference) -> str:
        cached = self._source_text_cache.get(source.id)
        if cached is not None:
            return cached
        if self._source_root is None:
            return ""
        source_path = self._source_root / source.corpus_path
        stat = _cached_stat(source_path)
        source_key = (source.kind, source_path.name, stat.st_size)
        global_cached = _NORMALISED_SOURCE_TEXT_CACHE.get(source_key)
        if global_cached is not None:
            self._source_text_cache[source.id] = global_cached
            return global_cached

        # Check disk cache
        cache_key_str = f"{source_path.name}:{stat.st_size}:{int(stat.st_mtime)}"
        disk_cache = _load_disk_cache()
        if cache_key_str in disk_cache:
            normalised = disk_cache[cache_key_str]
            _NORMALISED_SOURCE_TEXT_CACHE[source_key] = normalised
            self._source_text_cache[source.id] = normalised
            return normalised

        if source.kind == "manual_pdf":
            text = _extract_pdf_text_impl(str(source_path.expanduser().resolve()))
        else:
            text = source_path.read_text(encoding="utf-8", errors="replace")
        normalised = normalise_corpus_text(text)

        _NORMALISED_SOURCE_TEXT_CACHE[source_key] = normalised
        self._source_text_cache[source.id] = normalised
        disk_cache[cache_key_str] = normalised
        _write_disk_cache(disk_cache)
        return normalised
