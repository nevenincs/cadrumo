"""Read and verify bundled manual-part manifests and PDFs."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from ...core.hashing import hash_file
from ...core.logging import get_logger
from ...core.paths import resolve_relative_subpath
from .errors import ManifestError
from .schema import FetchedManualPart

_logger = get_logger(__name__)


def load_manifest(manifest_path: Path) -> FetchedManualPart:
    """Load and validate a manual-part manifest from disk."""
    if not manifest_path.exists():
        raise ManifestError(f"manifest not found: {manifest_path}")
    try:
        return FetchedManualPart.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, ValidationError) as exc:
        raise ManifestError(f"{manifest_path}: invalid manifest ({exc})") from exc


def verify_fetched_pdf(manifest: FetchedManualPart, part_root: Path) -> None:
    """Verify the bundled PDF path, digest, and length declared by a manifest."""
    try:
        pdf_path = resolve_relative_subpath(part_root, manifest.relative_pdf_path, context="manual PDF path")
    except ValueError as exc:
        raise ManifestError(str(exc)) from exc
    if not pdf_path.exists():
        raise ManifestError(f"raw PDF not found at {pdf_path}")
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
