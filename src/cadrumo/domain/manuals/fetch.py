"""Raw manual-part downloader and manifest writer.

The fetcher speaks :mod:`httpx` directly: the :class:`PartSpec` table
below hard-codes the verified canonical AEAT URLs for every
``(manual_id, year, part)`` triple the subpackage supports. The
``fetch`` CLI looks up a triple in the table, streams the PDF to
disk, computes its sha256 on the fly, and writes a
:class:`~cadrumo.domain.manuals.FetchedManualPart` manifest next to the
raw binary.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Protocol

import httpx
from pydantic import AnyHttpUrl, BaseModel, ValidationError

from ...core.models import STRICT_FROZEN_CONFIG
from ...core.atomic_write import atomic_write_stream, atomic_write_text
from ...core.config import Settings, load_settings
from ...core.hashing import hash_file
from ...core.logging import get_logger
from ...core.paths import resolve_relative_subpath
from ...core.time import now
from .errors import ManifestError
from .loader import resolve_part_root
from .schema import FetchedManualPart, ManualId, ManualPart

_logger = get_logger(__name__)

_CHUNK_SIZE = 65_536
_PDF_FILENAME = "source.pdf"
_MANIFEST_FILENAME = "manifest.json"


class _ChunkHasher(Protocol):
    """Minimal hash interface needed while staging a streamed download."""

    def update(self, data: bytes, /) -> object: ...


class PartSpec(BaseModel):
    """Canonical source URL for a ``(manual_id, year, part)`` triple.

    Strict and frozen so the public surface stays on pydantic v2 per
    the project mandate; held as a static tuple in :data:`PART_SPECS`
    and never constructed from untrusted input.

    Attributes:
        manual_id: Handbook identifier.
        year: Tax year.
        part: Volume split within the year.
        source_pdf_url: Canonical AEAT URL the PDF is fetched from.
    """

    model_config = STRICT_FROZEN_CONFIG

    manual_id: ManualId
    year: int
    part: ManualPart
    source_pdf_url: str


_EXTERNAL = Settings.external_constants().aeat
_MANUAL_BIBLIOTECA_ROOT = f"{_EXTERNAL.domains.sede}{_EXTERNAL.help_pages.manual_practicos_root}"

PART_SPECS: tuple[PartSpec, ...] = (
    # 2020
    PartSpec(
        manual_id=ManualId.RENTA,
        year=2020,
        part=ManualPart.PARTE_1,
        source_pdf_url=f"{_MANUAL_BIBLIOTECA_ROOT}/IRPF/IRPF-2020/ManualRenta2020_es_es.pdf",
    ),
    # 2021
    PartSpec(
        manual_id=ManualId.RENTA,
        year=2021,
        part=ManualPart.PARTE_1,
        source_pdf_url=f"{_MANUAL_BIBLIOTECA_ROOT}/IRPF/IRPF-2021/ManualRenta2021_es_es.pdf",
    ),
    # 2022
    PartSpec(
        manual_id=ManualId.RENTA,
        year=2022,
        part=ManualPart.PARTE_1,
        source_pdf_url=f"{_MANUAL_BIBLIOTECA_ROOT}/IRPF/IRPF-2022/ManualRenta2022_es_es.pdf",
    ),
    # 2023
    PartSpec(
        manual_id=ManualId.RENTA,
        year=2023,
        part=ManualPart.PARTE_1,
        source_pdf_url=f"{_MANUAL_BIBLIOTECA_ROOT}/IRPF/IRPF-2023/ManualRenta2023_es_es.pdf",
    ),
    # 2024
    PartSpec(
        manual_id=ManualId.RENTA,
        year=2024,
        part=ManualPart.PARTE_1,
        source_pdf_url=f"{_MANUAL_BIBLIOTECA_ROOT}/IRPF/IRPF-2024/ManualRenta2024Tomo1_es_es.pdf",
    ),
    PartSpec(
        manual_id=ManualId.RENTA,
        year=2024,
        part=ManualPart.PARTE_2_DEDUCCIONES_AUTONOMICAS,
        source_pdf_url=(
            f"{_MANUAL_BIBLIOTECA_ROOT}/IRPF/IRPF-2024-Deducciones-autonomicas/ManualRenta2024Tomo2_es_es.pdf"
        ),
    ),
    # 2025
    PartSpec(
        manual_id=ManualId.RENTA,
        year=2025,
        part=ManualPart.PARTE_1,
        source_pdf_url=f"{_MANUAL_BIBLIOTECA_ROOT}/IRPF/IRPF-2025/ManualRenta2025Parte1_es_es.pdf",
    ),
    PartSpec(
        manual_id=ManualId.RENTA,
        year=2025,
        part=ManualPart.PARTE_2_DEDUCCIONES_AUTONOMICAS,
        source_pdf_url=(
            f"{_MANUAL_BIBLIOTECA_ROOT}/IRPF/IRPF-2025-Deducciones-autonomicas/ManualRenta2025Parte2_es_es.pdf"
        ),
    ),
    PartSpec(
        manual_id=ManualId.IVA,
        year=2020,
        part=ManualPart.SINGLE,
        source_pdf_url=f"{_MANUAL_BIBLIOTECA_ROOT}/IVA/Manual_IVA_2020.pdf",
    ),
    PartSpec(
        manual_id=ManualId.IVA,
        year=2021,
        part=ManualPart.SINGLE,
        source_pdf_url=f"{_MANUAL_BIBLIOTECA_ROOT}/IVA/ManualIVA2021.pdf",
    ),
    PartSpec(
        manual_id=ManualId.IVA,
        year=2022,
        part=ManualPart.SINGLE,
        source_pdf_url=f"{_MANUAL_BIBLIOTECA_ROOT}/IVA/Manual_IVA_2022.pdf",
    ),
    PartSpec(
        manual_id=ManualId.IVA,
        year=2023,
        part=ManualPart.SINGLE,
        source_pdf_url=f"{_MANUAL_BIBLIOTECA_ROOT}/IVA/Manual_IVA_2023.pdf",
    ),
    PartSpec(
        manual_id=ManualId.IVA,
        year=2024,
        part=ManualPart.SINGLE,
        source_pdf_url=f"{_MANUAL_BIBLIOTECA_ROOT}/IVA/Manual_IVA_2024.pdf",
    ),
    PartSpec(
        manual_id=ManualId.IVA,
        year=2025,
        part=ManualPart.SINGLE,
        source_pdf_url=f"{_MANUAL_BIBLIOTECA_ROOT}/IVA/Manual_IVA_2025.pdf",
    ),
)


class FetchResult(BaseModel):
    """Thin wrapper returned by :func:`fetch_manual_part` to the CLI.

    Attributes:
        manifest: The :class:`~cadrumo.domain.manuals.FetchedManualPart`
            record written next to the raw PDF.
        part_root: Resolved directory root for the manual part.
        pdf_path: Absolute path to the freshly downloaded PDF.
        manifest_path: Absolute path to the JSON manifest on disk.
    """

    model_config = STRICT_FROZEN_CONFIG

    manifest: FetchedManualPart
    part_root: Path
    pdf_path: Path
    manifest_path: Path


def lookup_spec(manual_id: ManualId, year: int, part: ManualPart) -> PartSpec:
    """Look up a canonical source URL for a ``(manual_id, year, part)`` triple.

    Args:
        manual_id: Handbook identifier.
        year: Tax year.
        part: Volume split within the year.

    Returns:
        The matching :class:`PartSpec`.

    Raises:
        ManifestError: If no entry exists in :data:`PART_SPECS`.
    """
    for spec in PART_SPECS:
        if spec.manual_id is manual_id and spec.year == year and spec.part is part:
            return spec
    raise ManifestError(
        f"no canonical URL registered for {manual_id.value}/{year}/{part.value}; "
        "add a PartSpec entry to cadrumo.domain.manuals.fetch.PART_SPECS",
    )


def _stream_to_file(url: str, destination: Path) -> tuple[str, int]:
    """Download ``url`` to ``destination`` and return ``(sha256, length)``.

    Streams the response body in 64 KiB chunks while updating the
    sha256 hash in flight so the caller never needs to re-read the
    file from disk to verify it.
    """
    sha = hashlib.sha256()
    with httpx.stream(
        "GET",
        url,
        follow_redirects=True,
        timeout=load_settings().cadrumo_manuals_http_timeout_s,
    ) as response:
        response.raise_for_status()
        length = atomic_write_stream(destination, _hashing_chunks(response.iter_bytes(_CHUNK_SIZE), sha))
    return sha.hexdigest(), length


def _hashing_chunks(chunks: Iterable[bytes], sha: _ChunkHasher) -> Iterator[bytes]:
    """Yield non-empty source chunks while recording their content hash."""
    for chunk in chunks:
        if not chunk:
            continue
        sha.update(chunk)
        yield chunk


def write_manifest(manifest_path: Path, manifest: FetchedManualPart) -> None:
    """Serialise a :class:`~cadrumo.domain.manuals.FetchedManualPart` as indented JSON on disk.

    Args:
        manifest_path: Destination path for the JSON manifest.
        manifest: Manifest record to serialise.

    Raises:
        ManifestError: If the file cannot be written due to an OS error.
    """
    try:
        payload = manifest.model_dump(mode="json")
        atomic_write_text(
            manifest_path,
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise ManifestError(f"{manifest_path}: cannot write manifest ({exc})") from exc


def load_manifest(manifest_path: Path) -> FetchedManualPart:
    """Load and validate a manifest from disk.

    Args:
        manifest_path: Path to a ``manifest.json`` file.

    Returns:
        The parsed :class:`FetchedManualPart` record.

    Raises:
        ManifestError: If the file is missing, malformed, or fails
            schema validation.
    """
    if not manifest_path.exists():
        raise ManifestError(f"manifest not found: {manifest_path}")
    try:
        return FetchedManualPart.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, ValidationError) as exc:
        raise ManifestError(f"{manifest_path}: invalid manifest ({exc})") from exc


def fetch_manual_part(
    *,
    manual_id: ManualId,
    year: int,
    part: ManualPart,
    settings: Settings | None = None,
) -> FetchResult:
    """Download a manual part and write its sha256-verified manifest.

    Args:
        manual_id: Handbook identifier.
        year: Tax year.
        part: Volume split within the year.
        settings: Optional settings instance; loaded on demand otherwise.

    Returns:
        A :class:`FetchResult` containing the manifest and the resolved
        paths for the raw PDF and the manifest JSON.

    Raises:
        ManifestError: If the canonical URL is unknown or the download
            fails.
    """
    resolved = settings or load_settings()
    spec = lookup_spec(manual_id, year, part)
    part_root = resolve_part_root(manual_id=manual_id, year=year, part=part, settings=resolved)
    pdf_path = part_root / _PDF_FILENAME
    manifest_path = part_root / _MANIFEST_FILENAME

    _logger.info("fetching %s/%s/%s from %s", manual_id.value, year, part.value, spec.source_pdf_url)
    try:
        sha256, length = _stream_to_file(spec.source_pdf_url, pdf_path)
    except (OSError, httpx.HTTPError) as exc:
        _logger.warning("manual fetch failed %s/%s/%s", manual_id.value, year, part.value, exc_info=True)
        raise ManifestError(f"download failed for {spec.source_pdf_url}: {exc}") from exc

    manifest = FetchedManualPart(
        manual_id=manual_id,
        year=year,
        part=part,
        source_pdf_url=AnyHttpUrl(spec.source_pdf_url),
        relative_pdf_path=_PDF_FILENAME,
        sha256=sha256,
        content_length=length,
        fetched_at=now(),
        synthetic=False,
    )
    write_manifest(manifest_path, manifest)
    _logger.info("wrote manifest %s (%d bytes, sha256=%s)", manifest_path, length, sha256)
    return FetchResult(
        manifest=manifest,
        part_root=part_root,
        pdf_path=pdf_path,
        manifest_path=manifest_path,
    )


def verify_fetched_pdf(manifest: FetchedManualPart, part_root: Path) -> None:
    """Re-hash the on-disk PDF and compare against the manifest sha256.

    Args:
        manifest: The manifest record to verify against.
        part_root: Directory containing the raw PDF.

    Raises:
        ManifestError: If the PDF is missing or its sha256 diverges.
    """
    try:
        pdf_path = resolve_relative_subpath(part_root, manifest.relative_pdf_path, context="manual PDF path")
    except ValueError as exc:
        raise ManifestError(str(exc)) from exc
    if not pdf_path.exists():
        raise ManifestError(f"raw PDF not found at {pdf_path}; run 'aeat manual fetch' to materialise it")
    try:
        sha256, length = hash_file(pdf_path)
    except OSError as exc:
        raise ManifestError(f"{pdf_path}: cannot read raw PDF ({exc})") from exc
    if sha256 != manifest.sha256:
        _logger.error(
            "manual pdf sha256 mismatch %s: computed=%s manifest=%s",
            pdf_path,
            sha256,
            manifest.sha256,
        )
        raise ManifestError(f"{pdf_path}: sha256 mismatch (got {sha256}, manifest {manifest.sha256})")
    if length != manifest.content_length:
        _logger.error(
            "manual pdf length mismatch %s: computed=%d manifest=%d",
            pdf_path,
            length,
            manifest.content_length,
        )
        raise ManifestError(f"{pdf_path}: content_length mismatch (got {length}, manifest {manifest.content_length})")
