"""BOE PDF fetcher for :mod:`aeat.schema`.

Mirrors the sha256-verified streaming-fetch pattern established by
:mod:`aeat.manuals._fetch`. The fetched bytes are written to the
schema cache directory; the returned :class:`FetchedSchemaSource`
record carries the on-disk path plus every provenance scalar a
downstream :class:`~aeat.schema.Extractor` needs.

No manifest sidecar is written: provenance is embedded in the
extractor's output :class:`~aeat.schema.Modelo`, which is itself
persisted as diff-friendly JSON.

Safety posture (audit-driven):

- Override URLs are constrained to ``https://`` on an allow-listed
  host set (``boe.es`` / ``www.boe.es``) or to ``file://`` URLs that
  resolve under the project tree — no arbitrary-filesystem reads.
- ``boe_ref`` is re-validated at every path-composition site, not
  just at the cache layer.
- Downloads are capped at ``_MAX_PDF_BYTES``; oversized responses
  abort with :class:`SchemaCacheError` before they exhaust disk.
- HTTP redirects are rejected by default; a single-hop follow is
  never implicit.
- The override env var is capped at 64 KiB to prevent a hostile
  ``/proc/PID/environ`` leak from stalling settings load.
- Bytes land in a temporary sibling file and are atomically
  ``os.replace``-d into place so concurrent refresh runs never
  leave a half-written PDF on disk.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx
from pydantic import AnyHttpUrl, AwareDatetime, ConfigDict, Field, TypeAdapter, field_validator

from ..config import PROJECT_ROOT, Settings, load_settings
from ..logging import get_logger
from ..models import ModeloCode
from ._errors import SchemaCacheError
from ._models import _StrictFrozenModel

_logger = get_logger(__name__)

_CHUNK_SIZE = 65_536
_MAX_PDF_BYTES = 64 * 1024 * 1024
"""Hard cap on the byte size of a fetched BOE PDF (64 MiB)."""

_MAX_OVERRIDE_BYTES = 64 * 1024
"""Hard cap on the JSON-encoded override env var (64 KiB)."""

_BOE_REF_RE = re.compile(r"^[A-Z0-9-]+$")
"""Allowed character set for ``boe_ref`` wherever it becomes part of a filesystem path."""

_ALLOWED_HTTPS_HOSTS: frozenset[str] = frozenset({"boe.es", "www.boe.es"})
"""Host allow-list for ``https://`` BOE source URLs.

Extend this set only when a new upstream publisher is added, and
only after security review.
"""


class BoeOrdenSource(_StrictFrozenModel):
    """One entry in the canonical BOE Orden source table."""

    modelo_code: ModeloCode
    boe_ref: str = Field(min_length=1, max_length=64)
    origin_url: AnyHttpUrl

    @field_validator("boe_ref")
    @classmethod
    def _validate_boe_ref(cls, value: str) -> str:
        if not _BOE_REF_RE.fullmatch(value):
            raise ValueError(
                f"boe_ref must match {_BOE_REF_RE.pattern!r}: {value!r}",
            )
        return value


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
    if len(raw) > _MAX_OVERRIDE_BYTES:
        raise SchemaCacheError(
            f"aeat_schema_source_urls_override exceeds {_MAX_OVERRIDE_BYTES} bytes",
        )
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
        if entry.modelo_code == modelo_code and entry.boe_ref == boe_ref:
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


def _allowed_file_roots() -> tuple[Path, ...]:
    """Permitted roots for ``file://`` override URLs.

    Covers the project tree (for committed test fixtures) and the
    OS temp directory (for ``tmp_path``-based unit tests). Both are
    resolved symlink-aware.
    """
    roots: list[Path] = [PROJECT_ROOT.resolve()]
    with contextlib.suppress(OSError):
        roots.append(Path(tempfile.gettempdir()).resolve())
    return tuple(roots)


def _validate_override_url(url: str) -> None:
    """Reject override URLs that escape the supported scheme / host set.

    ``https://`` URLs must point at :data:`_ALLOWED_HTTPS_HOSTS`.
    ``file://`` URLs must resolve under the project tree or the OS
    temp dir (where unit-test fixtures live). Arbitrary-filesystem
    reads are refused.

    Raises:
        SchemaCacheError: For any URL that fails either check.
    """
    parsed = urlparse(url)
    if parsed.scheme == "file":
        resolved = _file_url_to_path(url).resolve(strict=False)
        for root in _allowed_file_roots():
            try:
                resolved.relative_to(root)
            except ValueError:
                continue
            return
        raise SchemaCacheError(
            f"file:// override must resolve under the project tree or the OS temp dir: {resolved}",
        )
    if parsed.scheme != "https":
        raise SchemaCacheError(
            f"override URL must use https:// or a project-local file://: {url!r}",
        )
    host = parsed.hostname
    if host not in _ALLOWED_HTTPS_HOSTS:
        raise SchemaCacheError(
            f"override host {host!r} is not in the allow-list {sorted(_ALLOWED_HTTPS_HOSTS)}",
        )


def _stream_to_file(url: str, destination: Path) -> tuple[str, int]:
    """Stream ``url`` to ``destination`` and return ``(sha256, length)``.

    Writes first to a ``<destination>.part`` sibling, then atomically
    ``os.replace``-s into the final path — guarantees that concurrent
    refresh runs never leave a half-written PDF behind.

    ``file://`` URLs are read directly from disk (``httpx`` does not
    ship a local-file transport by default). Redirects are rejected
    on the ``https://`` path: attackers controlling a 3xx response
    could otherwise pivot to internal endpoints.

    Raises:
        SchemaCacheError: On missing file, oversized content, or an
            HTTP redirect from the upstream server.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(destination.suffix + ".part")
    sha = hashlib.sha256()
    length = 0
    try:
        with tmp.open("wb") as dst:
            if url.startswith("file://"):
                source = _file_url_to_path(url)
                if not source.exists():
                    raise SchemaCacheError(f"file URL source not found: {source}")
                with source.open("rb") as src:
                    while True:
                        chunk = src.read(_CHUNK_SIZE)
                        if not chunk:
                            break
                        length += len(chunk)
                        if length > _MAX_PDF_BYTES:
                            raise SchemaCacheError(
                                f"BOE PDF exceeds {_MAX_PDF_BYTES} bytes: {url!r}",
                            )
                        dst.write(chunk)
                        sha.update(chunk)
            else:
                with httpx.stream(
                    "GET",
                    url,
                    follow_redirects=False,
                    timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0),
                ) as response:
                    if response.is_redirect:
                        raise SchemaCacheError(
                            f"BOE fetch refused to follow redirect from {url!r} to "
                            f"{response.headers.get('location')!r}; reject any "
                            "override that bounces off the canonical host",
                        )
                    response.raise_for_status()
                    for chunk in response.iter_bytes(_CHUNK_SIZE):
                        if not chunk:
                            continue
                        length += len(chunk)
                        if length > _MAX_PDF_BYTES:
                            raise SchemaCacheError(
                                f"BOE PDF exceeds {_MAX_PDF_BYTES} bytes: {url!r}",
                            )
                        dst.write(chunk)
                        sha.update(chunk)
        os.replace(tmp, destination)
    except BaseException:
        # Clean the partial temp file on any failure (including ^C).
        tmp.unlink(missing_ok=True)
        raise
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
        aeat.schema.SchemaCacheError: On unknown source, invalid
            ``boe_ref``, disallowed override URL, oversized response,
            redirected fetch, or transport failure.
    """
    if not _BOE_REF_RE.fullmatch(boe_ref):
        raise SchemaCacheError(
            f"invalid boe_ref {boe_ref!r}; expected {_BOE_REF_RE.pattern!r}",
        )
    resolved = settings or load_settings()
    override = _resolve_override(resolved)
    override_url = override.get(modelo_code.value, {}).get(boe_ref)
    registered = _lookup_source(modelo_code, boe_ref)
    if override_url is None:
        origin_url = registered.origin_url
        url_to_fetch = str(registered.origin_url)
    else:
        _validate_override_url(override_url)
        if override_url.startswith("file://"):
            # Offline / unit-test path: keep the canonical origin URL
            # for provenance, but read the bytes from the local file.
            origin_url = registered.origin_url
        else:
            origin_url = TypeAdapter(AnyHttpUrl).validate_python(override_url)
        url_to_fetch = override_url
    destination = resolved.aeat_schema_cache_dir / f"modelo_{modelo_code.value}" / f"{boe_ref}.pdf"
    _logger.info(
        "fetching BOE PDF modelo=%s boe_ref=%s scheme=%s host=%s",
        modelo_code.value,
        boe_ref,
        urlparse(url_to_fetch).scheme,
        urlparse(url_to_fetch).hostname,
    )
    try:
        sha256, length = _stream_to_file(url_to_fetch, destination)
    except httpx.HTTPError as exc:
        raise SchemaCacheError(f"BOE fetch failed: {exc}") from exc
    return FetchedSchemaSource(
        modelo_code=modelo_code,
        boe_ref=boe_ref,
        origin_url=origin_url,
        pdf_path=destination,
        sha256=sha256,
        content_length=length,
        fetched_at=datetime.now(tz=UTC),
    )
