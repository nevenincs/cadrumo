"""Legal/source evidence and source-citation validation helpers."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping
from functools import lru_cache
from pathlib import Path

from pydantic import ConfigDict, TypeAdapter, ValidationError

from cadrumo.domain.calculations.registry.schema import SourceCitation
from cadrumo.domain.calculations.registry.schema_references import LegalReference, SourceReference

from ....core import (
    MANUAL_CORPUS_TEXT_CORPUS_PATH_PREFIX,
    MANUAL_CORPUS_TEXT_SIDECAR_SUFFIX,
    ManualCorpusTextSidecar,
    StorageCategory,
    normalise_corpus_text,
    storage_location,
    storage_path,
)
from ....core.atomic_write import atomic_write_best_effort_text
from ....core.hashing import sha256_hex
from ....core.resources import packaged_data, resolve_companion_binary

_SourceTextCacheKey = tuple[str, str, int, int]
_NORMALISED_SOURCE_TEXT_CACHE: dict[_SourceTextCacheKey, str] = {}
_LOGGER = logging.getLogger(__name__)

# Bare filename, read off the taxonomy rather than an untethered string
# literal. Still joined onto ``cadrumo_corpus_text_cache_dir`` exactly as
# before -- the member carries no ``settings_field`` and is not safe to
# resolve directly, because ``CORPUS_TEXT_CACHE`` is operator-overridable
# (see the member's declaration in ``core._storage_taxonomy``).
_CORPUS_TEXT_CACHE_FILENAME = Path(storage_location(StorageCategory.CORPUS_TEXT_CACHE_FILE).subpath).name

# Shipped sidecar constants (written by the corpus extraction tooling).
# Sidecars live at _data/manual_corpus_text/<path-relative-to-corpus>.corpus_text.json
# where the path is source.corpus_path with the leading "corpus/" prefix stripped.
# The payload shape itself is the shared ManualCorpusTextSidecar contract in core.
_MANUAL_CORPUS_TEXT_DIR = "manual_corpus_text"


def _validated_sidecar_text(raw: str, corpus_path: str, actual_sha256: str) -> str | None:
    """Return the sidecar's text when it satisfies the shared contract, else ``None``.

    The whole admission decision for a manual-PDF sidecar lives here: the
    payload must validate against :class:`ManualCorpusTextSidecar` (pinned
    schema version, prefixed corpus path, hex-64 content key, stamped
    extraction platform, non-empty text), must claim the very
    ``corpus_path`` it was addressed under, and must carry the content key of
    the deployed PDF bytes. Any refusal is logged and returns ``None``, which
    the caller answers by re-extracting from the real bytes -- so a tampered,
    truncated, foreign, or older-schema sidecar costs a slow path, never a
    wrong ``required_text`` verdict.

    Args:
        raw: The sidecar file's decoded JSON text.
        corpus_path: The :attr:`SourceReference.corpus_path` the sidecar was
            addressed under.
        actual_sha256: Hex SHA-256 of the deployed source PDF's bytes.
    """
    try:
        sidecar = ManualCorpusTextSidecar.model_validate_json(raw)
    except ValidationError:
        _LOGGER.warning(
            "Manual PDF sidecar for %s does not satisfy the sidecar contract; falling back to on-demand extraction",
            corpus_path,
            exc_info=True,
        )
        return None
    if not sidecar.addresses(corpus_path):
        _LOGGER.warning(
            "Manual PDF sidecar for %s claims corpus_path %r; falling back to on-demand extraction",
            corpus_path,
            sidecar.corpus_path,
        )
        return None
    if sidecar.source_sha256 != actual_sha256:
        _LOGGER.warning(
            "Manual PDF sidecar sha256 mismatch for %s; falling back to on-demand extraction",
            corpus_path,
        )
        return None
    return sidecar.normalised_text


def _read_manual_pdf_sidecar(corpus_path: str, source_path: Path) -> str | None:
    """Return the shipped normalised text for a manual-PDF source, or ``None``.

    Locates the content-keyed sidecar committed under
    ``_data/manual_corpus_text/`` that was built by
    the corpus extraction tooling, then hands the payload to
    :func:`_validated_sidecar_text`, which owns the whole admission decision
    against the shared :class:`ManualCorpusTextSidecar` contract the extractor
    writes through.

    Returns ``None`` when the sidecar is absent (not yet generated or path
    unexpected), unreadable, or refused by that contract. The caller falls
    back to on-demand pypdfium2 extraction on ``None``. End-user machines
    should never reach that path: the shipped sidecar covers every
    ``manual_pdf`` source the registry declares.

    Args:
        corpus_path: The source's :attr:`SourceReference.corpus_path`,
            e.g. ``"corpus/manuals/renta/2020/part1/source.pdf"``.
        source_path: Resolved on-disk path to the source PDF bytes.
    """
    if not corpus_path.startswith(MANUAL_CORPUS_TEXT_CORPUS_PATH_PREFIX):
        return None
    relative = corpus_path[len(MANUAL_CORPUS_TEXT_CORPUS_PATH_PREFIX) :]
    # Build the sidecar Traversable under the bundled _data tree.
    sidecar_parts = relative.split("/")
    sidecar_parts[-1] = sidecar_parts[-1] + MANUAL_CORPUS_TEXT_SIDECAR_SUFFIX
    try:
        node = packaged_data(_MANUAL_CORPUS_TEXT_DIR, *sidecar_parts)
        raw = node.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return _validated_sidecar_text(raw, corpus_path, sha256_hex(source_path.read_bytes()))


@lru_cache(maxsize=4096)
def _normalise_required_text(text: str) -> str:
    return normalise_corpus_text(text)


_disk_cache: dict[str, str] | None = None
_disk_cache_dirty: bool = False
# Disk-cache writes since reset; observability for the validation-verdict pin.
_disk_cache_write_count: int = 0
_DISK_CACHE_ADAPTER: TypeAdapter[dict[str, str]] = TypeAdapter(dict[str, str], config=ConfigDict(strict=True))


def _corpus_text_cache_path() -> Path:
    """Return the settings-derived corpus-text cache file location.

    Resolved through the taxonomy accessor rather than by reading
    ``cadrumo_corpus_text_cache_dir`` here. Both answer the same today, because
    the settings field is what the accessor consults first -- but only one of
    them stays correct if the member's resolution ever gains a case. Defaults
    under ``<cadrumo_local_storage_root>/cache/corpus-text`` (scoped per user by
    the storage root), replacing the former shared OS-temp-dir location that
    any two users or CI containers on one host could clobber.
    """
    return storage_path(StorageCategory.CORPUS_TEXT_CACHE) / _CORPUS_TEXT_CACHE_FILENAME


def reset_corpus_text_cache() -> None:
    """Drop the in-process corpus-text cache memos (test isolation only)."""
    global _disk_cache, _disk_cache_dirty, _disk_cache_write_count
    _disk_cache = None
    _disk_cache_dirty = False
    _disk_cache_write_count = 0
    _NORMALISED_SOURCE_TEXT_CACHE.clear()


def flush_corpus_text_cache() -> None:
    """Persist accumulated corpus-text entries in one write.

    Cache misses only mutate the in-process mapping and mark it dirty; the
    validation entry points flush once when they finish. Writing per miss was
    accidentally quadratic: every miss re-read and fully rewrote a JSON file
    that grows to tens of megabytes, which alone cost ~13 seconds of the
    first-touch registry validation on an end-user machine.
    """
    global _disk_cache_dirty
    if not _disk_cache_dirty or _disk_cache is None:
        return
    _write_disk_cache(_disk_cache)
    _disk_cache_dirty = False


def _load_disk_cache() -> dict[str, str]:
    global _disk_cache
    if _disk_cache is not None:
        return _disk_cache
    cache_path = _corpus_text_cache_path()
    if not cache_path.is_file():
        _disk_cache = {}
        return _disk_cache
    try:
        with open(cache_path, encoding="utf-8") as f:
            loaded = _DISK_CACHE_ADAPTER.validate_python(json.load(f))
            _disk_cache = loaded
            return loaded
    except Exception:
        # Degrade to a cache miss (the entries recompute deterministically),
        # but surface the anomaly rather than swallowing it silently.
        _LOGGER.warning("Ignoring unreadable corpus text cache at %s; recomputing", cache_path, exc_info=True)
        _disk_cache = {}
        return _disk_cache


def _write_disk_cache(data: dict[str, str]) -> None:
    global _disk_cache_write_count
    _disk_cache_write_count += 1
    cache_path = _corpus_text_cache_path()
    try:
        # Read-merge-before-write narrows the multi-process last-writer-wins
        # window that the atomic replace alone does not close: fold in any
        # entries a concurrent writer committed since our in-memory copy
        # loaded, so a parallel writer's new key is not dropped. The residual
        # race (two writers merging the same pre-image) can only cost a
        # recompute, never a wrong value, because every key embeds the source
        # file's size and mtime -- a stale entry cannot match a changed file.
        merged: dict[str, str] = {}
        if cache_path.is_file():
            try:
                with open(cache_path, encoding="utf-8") as f:
                    on_disk = _DISK_CACHE_ADAPTER.validate_python(json.load(f))
                merged.update(on_disk)
            except Exception:
                _LOGGER.debug("Ignoring unreadable corpus text cache while merging at %s", cache_path, exc_info=True)
        merged.update(data)
        # Compact separators: this is a machine cache that reaches tens of
        # megabytes; indentation only inflates every read and write.
        atomic_write_best_effort_text(
            cache_path,
            json.dumps(merged, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    except Exception:
        _LOGGER.warning("Could not write corpus text cache at %s", cache_path, exc_info=True)


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

    def source_text(self, source: SourceReference) -> str | None:
        """Return ``source``'s normalised bundled text, or ``None`` when unreachable.

        Public wrapper around :meth:`_source_text` for content-shape checks that
        need the same PDF-sidecar-aware, disk-cached text resolution this class
        already owns -- e.g. a vocabulary probe over a deadline window's
        ``official_source_guidance`` sources -- without duplicating the manual-PDF
        sidecar lookup, the on-disk cache, or the companion-binary fallback path.
        Swallows the read failures :meth:`validate_source_citations` reports as
        failures itself; a caller with no per-citation failure slot to put that in
        treats an unreadable source the same way :func:`validate_layout_authority_content`
        does -- skipped rather than silently accepted.
        """
        if self._source_root is None:
            return None
        try:
            return self._source_text(source)
        except OSError:
            return None

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
            # Try the shipped content-keyed sidecar first; verify sha256 before
            # using it so a modified source PDF never serves stale text.  The
            # sidecar is generated once at build time by
            # the corpus extraction tooling and shipped with the
            # cadrumo wheel — end-user machines should never reach the fallback.
            sidecar_text = _read_manual_pdf_sidecar(source.corpus_path, source_path)
            if sidecar_text is not None:
                normalised = sidecar_text
            else:
                normalised = normalise_corpus_text(_extract_pdf_text_impl(str(source_path)))
        else:
            normalised = normalise_corpus_text(source_path.read_text(encoding="utf-8", errors="replace"))

        _NORMALISED_SOURCE_TEXT_CACHE[source_key] = normalised
        self._source_text_cache[source.id] = normalised
        disk_cache[cache_key_str] = normalised
        global _disk_cache_dirty
        _disk_cache_dirty = True
        return normalised
