"""BOE PDF fetcher for :mod:`aeat.schema`.

Mirrors the sha256-verified streaming-fetch pattern established by
:mod:`aeat.manuals._fetch`. The fetched bytes are written to the
schema cache directory; the returned :class:`FetchedSchemaSource`
record carries the on-disk path plus every provenance scalar a
downstream :class:`~aeat.schema.Extractor` needs.

No manifest sidecar is written: provenance is embedded in the
extractor's output :class:`~aeat.schema.Modelo`, which is itself
persisted as diff-friendly JSON.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx
from pydantic import AnyHttpUrl, AwareDatetime, ConfigDict, Field, TypeAdapter

from ..config import Settings, load_settings
from ..logging import get_logger
from ..models import ModeloCode
from ._errors import SchemaCacheError
from ._models import _StrictFrozenModel

_logger = get_logger(__name__)

_CHUNK_SIZE = 65_536


class BoeOrdenSource(_StrictFrozenModel):
    """One entry in the canonical BOE Orden source table."""

    modelo_code: ModeloCode
    boe_ref: str = Field(min_length=1, max_length=64)
    origin_url: AnyHttpUrl


class FetchedSchemaSource(_StrictFrozenModel):
    """Record of a schema source successfully fetched to disk."""

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        populate_by_name=True,
        arbitrary_types_allowed=False,
    )

    modelo_code: ModeloCode
    boe_ref: str = Field(min_length=1, max_length=64)
    origin_url: AnyHttpUrl
    pdf_path: Path
    sha256: str = Field(min_length=64, max_length=64)
    content_length: int = Field(ge=1)
    fetched_at: AwareDatetime


BOE_ORDEN_SOURCES: tuple[BoeOrdenSource, ...] = (
    BoeOrdenSource(
        modelo_code=ModeloCode.MODELO_130,
        boe_ref="BOE-A-2023-15412",
        origin_url=TypeAdapter(AnyHttpUrl).validate_python(
            "https://www.boe.es/boe/dias/2023/07/13/pdfs/BOE-A-2023-15412.pdf",
        ),
    ),
)
"""Canonical BOE sources covered by the v1 extractor.

Follow-up issues extend this tuple with 303 / 390 entries. Runtime
overrides (used by offline CI and unit tests) go through
:attr:`Settings.aeat_schema_source_urls_override`.
"""


def _resolve_override(settings: Settings) -> dict[str, dict[str, str]]:
    """Parse the override setting into a ``{code: {boe_ref: url}}`` map."""
    raw = settings.aeat_schema_source_urls_override.strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SchemaCacheError(
            f"aeat_schema_source_urls_override is not valid JSON: {exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise SchemaCacheError(
            "aeat_schema_source_urls_override must decode to an object",
        )
    resolved: dict[str, dict[str, str]] = {}
    for code, inner in payload.items():
        if not isinstance(inner, dict):
            raise SchemaCacheError(
                f"aeat_schema_source_urls_override[{code!r}] must be an object",
            )
        resolved[str(code)] = {str(k): str(v) for k, v in inner.items()}
    return resolved


def _lookup_source(modelo_code: ModeloCode, boe_ref: str) -> BoeOrdenSource:
    for entry in BOE_ORDEN_SOURCES:
        if entry.modelo_code is modelo_code and entry.boe_ref == boe_ref:
            return entry
    raise SchemaCacheError(
        f"no BOE source registered for ({modelo_code.value}, {boe_ref}); "
        "add an entry to BOE_ORDEN_SOURCES or set "
        "AEAT_SCHEMA_SOURCE_URLS_OVERRIDE for offline tests",
    )


def _file_url_to_path(url: str) -> Path:
    """Translate a ``file://`` URL into a filesystem :class:`Path`."""
    parsed = urlparse(url)
    if parsed.scheme != "file":
        raise SchemaCacheError(f"not a file URL: {url!r}")
    raw = unquote(parsed.path or "")
    if raw.startswith("/") and len(raw) >= 3 and raw[2] == ":":
        # On Windows, file:///C:/x becomes /C:/x after parsing; strip the leading slash.
        raw = raw[1:]
    return Path(raw)


def _stream_to_file(url: str, destination: Path) -> tuple[str, int]:
    """Stream ``url`` to ``destination`` and return ``(sha256, length)``.

    ``file://`` URLs are read directly from disk (``httpx`` does not
    ship a local-file transport by default) — used by unit tests that
    override the source URL and by offline CI.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256()
    length = 0
    if url.startswith("file://"):
        source = _file_url_to_path(url)
        if not source.exists():
            raise SchemaCacheError(f"file URL source not found: {source}")
        with source.open("rb") as src, destination.open("wb") as dst:
            while True:
                chunk = src.read(_CHUNK_SIZE)
                if not chunk:
                    break
                dst.write(chunk)
                sha.update(chunk)
                length += len(chunk)
        return sha.hexdigest(), length
    with httpx.stream(
        "GET",
        url,
        follow_redirects=True,
        timeout=60.0,
    ) as response:
        response.raise_for_status()
        with destination.open("wb") as handle:
            for chunk in response.iter_bytes(_CHUNK_SIZE):
                if not chunk:
                    continue
                handle.write(chunk)
                sha.update(chunk)
                length += len(chunk)
    return sha.hexdigest(), length


def fetch_boe_pdf(
    modelo_code: ModeloCode,
    boe_ref: str,
    *,
    settings: Settings | None = None,
) -> FetchedSchemaSource:
    """Fetch the BOE PDF backing ``(modelo_code, boe_ref)``.

    Args:
        modelo_code: Target modelo identifier.
        boe_ref: BOE-A identifier, e.g. ``"BOE-A-2023-15412"``.
        settings: Optional :class:`Settings` instance; loaded on
            demand otherwise.

    Returns:
        A :class:`FetchedSchemaSource` record with the on-disk PDF
        path and the provenance scalars needed downstream.

    Raises:
        aeat.schema.SchemaCacheError: On unknown source or transport
            failure.
    """
    resolved = settings or load_settings()
    override = _resolve_override(resolved)
    override_url = override.get(modelo_code.value, {}).get(boe_ref)
    registered = _lookup_source(modelo_code, boe_ref)
    if override_url is None:
        origin_url = registered.origin_url
        url_to_fetch = str(registered.origin_url)
    elif override_url.startswith("file://"):
        # Offline / unit-test path: keep the canonical origin URL for
        # provenance, but read the bytes from the local file URL.
        origin_url = registered.origin_url
        url_to_fetch = override_url
    else:
        origin_url = TypeAdapter(AnyHttpUrl).validate_python(override_url)
        url_to_fetch = override_url
    destination = resolved.aeat_schema_cache_dir / f"modelo_{modelo_code.value}" / f"{boe_ref}.pdf"
    _logger.info(
        "fetching BOE PDF modelo=%s boe_ref=%s url=%s",
        modelo_code.value,
        boe_ref,
        url_to_fetch,
    )
    try:
        sha256, length = _stream_to_file(url_to_fetch, destination)
    except httpx.HTTPError as exc:
        raise SchemaCacheError(
            f"BOE fetch failed for {url_to_fetch}: {exc}",
        ) from exc
    return FetchedSchemaSource(
        modelo_code=modelo_code,
        boe_ref=boe_ref,
        origin_url=origin_url,
        pdf_path=destination,
        sha256=sha256,
        content_length=length,
        fetched_at=datetime.now(tz=UTC),
    )
