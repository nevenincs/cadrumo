"""Top-level orchestrator for :mod:`dev.sanitizer`.

Implements the canonical sanitiser pipeline:

1. Open source bytes; refuse if signed; refuse if already sanitised.
2. Strip dynamic surfaces (attachments, JS, OpenAction/AA,
   annotations, OCG, AcroForm).
3. Drop page thumbnails.
4. Drop outlines + page labels.
5. Drop ``Root.StructTreeRoot`` (lossy).
6. Rewrite content streams against the :class:`TokenMap`.
7. Scrub static metadata (DocInfo + XMP).
8. Save with deterministic flags.

Order matters: dynamic surfaces precede the content rewrite so a
JS action cannot re-inject PII the rewriter just stripped. The
content rewrite precedes the metadata scrub because some XMP-write
paths in :mod:`pikepdf` re-stamp metadata if they detect a content
change. The deterministic save runs last so byte-stable output
captures every prior mutation.

The library function is a pure transformer over ``bytes | Path`` plus a
declarative token map. It returns sanitised bytes and an audit record; CLI or
workflow code decides whether to write those bytes to disk.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Literal

import pikepdf
from pikepdf import PdfError as PikepdfError

from cadrumo.core.hashing import hash_file, sha256_hex
from cadrumo.core.logging import get_logger

from . import fixtures as _fixtures
from ._determinism import save_with_deterministic_flags
from ._dynamic import (
    strip_acroform,
    strip_annotations,
    strip_attachments,
    strip_javascript,
    strip_optional_content_groups,
    strip_outlines,
    strip_page_labels,
    strip_thumbnails,
)
from ._metadata import scrub_docinfo, scrub_xmp
from ._records import (
    Replacement,
    SanitizationResult,
    SanitizationWarning,
    ScrubbedSurface,
    TokenMap,
)
from ._streams import apply_token_map_to_pdf
from ._structtree import drop_struct_tree as _drop_struct_tree_helper
from .errors import (
    AlreadySanitizedError,
    SanitizerSourceParseError,
    SignaturePresentError,
)

_LOG = get_logger(__name__)
SANITIZER_VERSION = "0.1.0"


def sanitize_pdf(
    source: bytes | Path,
    mapping: TokenMap,
    *,
    drop_attachments: bool = True,
    drop_javascript: bool = True,
    drop_annotations: bool = True,
    drop_outlines: bool = True,
    drop_optional_content_groups: bool = True,
    drop_struct_tree: bool = True,
    drop_acroform: bool = False,
    scrub_docinfo_dict: bool = True,
    scrub_xmp_packet: bool = True,
    scrub_xmp_strategy: Literal["delete", "rewrite"] = "delete",
    refuse_if_already_sanitized: bool = True,
) -> SanitizationResult:
    """Strip PII from ``source`` against ``mapping``.

    Args:
        source: Raw bytes of the source PDF, or a :class:`Path`
            pointing to it. Path inputs are read once at the top
            of the function.
        mapping: Declarative cleartext-to-synthetic
            :class:`TokenMap`. Real values are consumed in memory through
            ``SecretStr`` fields; callers must keep any serialized mapping
            files outside git.
        drop_attachments: When True, removes every embedded file.
        drop_javascript: When True, removes embedded JavaScript
            and document-level actions (OpenAction, AA).
        drop_annotations: When True, drops every page annotation.
        drop_outlines: When True, drops the outline tree.
        drop_optional_content_groups: When True, removes
            ``Root.OCProperties``.
        drop_struct_tree: When True, drops ``Root.StructTreeRoot``
            (and emits ``structtree_dropped_lossy`` warning when
            the tree was present).
        drop_acroform: When True, deletes ``Root.AcroForm``
            entirely; otherwise clears field values in place.
        scrub_docinfo_dict: When True, deletes the legacy DocInfo
            dictionary.
        scrub_xmp_packet: When True, scrubs the XMP packet via the
            ``scrub_xmp_strategy`` policy.
        scrub_xmp_strategy: ``"delete"`` (default) drops the
            entire XMP packet; ``"rewrite"`` clears only the
            PII-bearing keys.
        refuse_if_already_sanitized: When True, raises
            :class:`AlreadySanitizedError` if ``source`` SHA-256
            is in :data:`fixtures.SANITIZED_SHAS`. Pass False to
            opt out (useful when intentionally re-sanitising an
            existing fixture against an extended TokenMap).

    Returns:
        A :class:`SanitizationResult` carrying the sanitised
        bytes, audit log, and warnings. The function itself does not write the
        PDF or audit record to disk.

    Raises:
        SanitizerSourceParseError: If the source bytes cannot be opened by :mod:`pikepdf`.
        AlreadySanitizedError: If ``refuse_if_already_sanitized`` is True and the source
            SHA-256 is in :data:`fixtures.SANITIZED_SHAS`.
    """
    source_sha, source_size_bytes = _digest_source(source)

    if refuse_if_already_sanitized and source_sha in _fixtures.SANITIZED_SHAS:
        raise AlreadySanitizedError(source_sha256=source_sha)

    pdf = _open_source_pdf(source)

    _refuse_if_signed(pdf)

    surfaces: list[ScrubbedSurface] = []
    warnings: list[SanitizationWarning] = []

    if drop_attachments:
        surfaces.append(strip_attachments(pdf))
    if drop_javascript:
        js, oa, aa = strip_javascript(pdf)
        surfaces.extend((js, oa, aa))
    if drop_annotations:
        surfaces.append(strip_annotations(pdf))
    if drop_optional_content_groups:
        surfaces.append(strip_optional_content_groups(pdf))
    acroform_scrubbed, acroform_warnings = strip_acroform(pdf, drop_entirely=drop_acroform)
    surfaces.append(acroform_scrubbed)
    warnings.extend(acroform_warnings)
    surfaces.append(strip_thumbnails(pdf))
    if drop_outlines:
        surfaces.append(strip_outlines(pdf))
        surfaces.append(strip_page_labels(pdf))
    if drop_struct_tree:
        struct, struct_warnings = _drop_struct_tree_helper(pdf)
        surfaces.append(struct)
        warnings.extend(struct_warnings)

    replacements: tuple[Replacement, ...] = apply_token_map_to_pdf(pdf, mapping)

    if scrub_docinfo_dict:
        surfaces.append(scrub_docinfo(pdf))
    if scrub_xmp_packet:
        scrubbed, xmp_warnings = scrub_xmp(pdf, strategy=scrub_xmp_strategy)
        surfaces.append(scrubbed)
        warnings.extend(xmp_warnings)

    output_bytes, flags = save_with_deterministic_flags(pdf)
    output_sha = sha256_hex(output_bytes)
    _LOG.info(
        "sanitize_pdf: completed source_sha=%s output_sha=%s replacements=%d surfaces=%d warnings=%d",
        source_sha[:16],
        output_sha[:16],
        len(replacements),
        len(surfaces),
        len(warnings),
    )

    return SanitizationResult(
        output_bytes=output_bytes,
        source_sha256=source_sha,
        output_sha256=output_sha,
        source_size_bytes=source_size_bytes,
        output_size_bytes=len(output_bytes),
        sanitizer_version=SANITIZER_VERSION,
        determinism_flags=flags,
        replacements_applied=replacements,
        surfaces_scrubbed=tuple(surfaces),
        warnings=tuple(warnings),
    )


def _open_source_pdf(source: bytes | Path) -> pikepdf.Pdf:
    """Open the source with pikepdf, refusing under a redacted label.

    Path inputs feed pikepdf directly so QPDF's memory-mapping path can avoid a
    full in-memory copy of the source bytes. bytes inputs (uncommon - used by
    tests and by library consumers with the bytes already in hand) take the
    BytesIO path.

    The refusal is raised OUTSIDE the ``except`` block, matching
    :func:`_digest_source`. ``raise ... from None`` is not sufficient here: it
    clears ``__cause__`` and suppresses the chained traceback from DISPLAY, but
    ``__context__`` still holds the pikepdf error, and that error's message
    embeds the source - a filesystem path for a Path input. Anything that reads
    ``__context__`` rather than the rendered traceback (a handler logging with
    ``exc_info``, a crash reporter, a structured serializer) would carry the
    unredacted source out with it. Leaving the handler is what drops it.
    """
    failure: str | None = None
    try:
        return pikepdf.Pdf.open(io.BytesIO(source) if isinstance(source, bytes) else source)
    except PikepdfError as exc:
        _LOG.debug(
            "sanitize_pdf: source=<input-pdf> failure=%s",
            type(exc).__name__,
        )
        failure = type(exc).__name__
    raise SanitizerSourceParseError(failure=failure)


def _digest_source(source: bytes | Path) -> tuple[str, int]:
    """Returns ``(sha256_hex, size_bytes)`` for ``source``.

    ``Path`` inputs delegate to the canonical chunked file digest so a
    multi-hundred-megabyte capture never has to be fully resident in memory,
    wrapping the ``OSError`` on an unreadable artefact in the sanitizer source
    error. ``bytes`` inputs (rare — used by library consumers with the bytes
    already in hand) hash directly through the canonical in-memory digest.

    Args:
        source: Raw bytes of the source PDF, or a :class:`Path`.

    Returns:
        Tuple of (lowercase hex SHA-256 digest, byte count).
    """
    if isinstance(source, bytes):
        return sha256_hex(source), len(source)
    digest = ""
    size = 0
    source_parse_error: SanitizerSourceParseError | None = None
    try:
        digest, size = hash_file(source)
    except OSError as exc:
        _LOG.debug(
            "sanitize_pdf: source=<input-pdf> failure=%s",
            type(exc).__name__,
        )
        source_parse_error = SanitizerSourceParseError(failure=type(exc).__name__)
    if source_parse_error is not None:
        # Raise outside the ``except`` block so neither ``__cause__`` nor
        # ``__context__`` carries the OSError (which leaks the source path).
        raise source_parse_error
    return digest, size


def _refuse_if_signed(pdf: pikepdf.Pdf) -> None:
    """Raises :class:`SignaturePresentError` if ``pdf`` is signed.

    AEAT justificantes are not signed at the capture step; if a
    future modelo's PDF carries a signature, the sanitiser must
    refuse rather than silently invalidate the signature.
    """
    acroform = pdf.Root.get("/AcroForm")
    if acroform is not None:
        sig_flags = acroform.get("/SigFlags")
        if sig_flags is not None and int(sig_flags) != 0:
            raise SignaturePresentError(
                "Source PDF carries a digital signature (SigFlags set); "
                "the sanitiser refuses to modify signed documents.",
            )
        fields = acroform.get("/Fields")
        if fields is not None:
            for index in range(len(fields)):
                field = fields[index]
                ft = field.get("/FT")
                if ft is not None and ft == pikepdf.Name.Sig:
                    raise SignaturePresentError(
                        "Source PDF contains a signature field; the sanitiser refuses to modify signed documents.",
                    )
