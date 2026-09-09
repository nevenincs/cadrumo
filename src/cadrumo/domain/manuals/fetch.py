"""Read and verify bundled manual-part manifests and PDFs."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from .errors import ManifestError
from .schema import FetchedManualPart


def load_manifest(manifest_path: Path) -> FetchedManualPart:
    """Load and validate a manual-part manifest from disk."""
    if not manifest_path.exists():
        raise ManifestError(f"manifest not found: {manifest_path}")
    try:
        return FetchedManualPart.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, ValidationError) as exc:
        raise ManifestError(f"{manifest_path}: invalid manifest ({exc})") from exc
