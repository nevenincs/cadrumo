"""Legal/source evidence and source-citation validation helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from functools import lru_cache
from pathlib import Path

from ._schema import LegalReference, SourceCitation, SourceReference
from ._text import normalise_corpus_text

_SourceTextCacheKey = tuple[str, str, int, int]
_SourceTextCacheValue = tuple[Path, str]
_NORMALISED_SOURCE_TEXT_CACHE: dict[_SourceTextCacheKey, _SourceTextCacheValue] = {}


@lru_cache(maxsize=4096)
def _normalise_required_text(text: str) -> str:
    return normalise_corpus_text(text)


def _extract_pdf_text(path: Path) -> str:
    stat = path.stat()
    return _extract_pdf_text_cached(str(path.expanduser().resolve()), stat.st_size, stat.st_mtime_ns)


@lru_cache(maxsize=256)
def _extract_pdf_text_cached(path: str, byte_count: int, modified_ns: int) -> str:
    del byte_count, modified_ns
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
        stat = source_path.stat()
        source_key = (source.kind, str(source_path.expanduser().resolve()), stat.st_size, stat.st_mtime_ns)
        global_cached = _NORMALISED_SOURCE_TEXT_CACHE.get(source_key)
        if global_cached is not None and global_cached[0] == source_path:
            self._source_text_cache[source.id] = global_cached[1]
            return global_cached[1]
        if source.kind == "manual_pdf":
            text = _extract_pdf_text(source_path)
        else:
            text = source_path.read_text(encoding="utf-8", errors="replace")
        normalised = normalise_corpus_text(text)
        _NORMALISED_SOURCE_TEXT_CACHE[source_key] = (source_path, normalised)
        self._source_text_cache[source.id] = normalised
        return normalised
