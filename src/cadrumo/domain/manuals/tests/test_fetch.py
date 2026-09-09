"""Behavior tests for bundled manual manifest loading and PDF verification."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from ....core.directory_scan import scan_directory
from ....core.resources.bundled_data import bundled_path
from ..errors import ManifestError
from ..fetch import load_manifest
from ..schema import FetchedManualPart, ManualId, ManualPart

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _manifest(sha256: str = "a" * 64, length: int = 10) -> FetchedManualPart:
    return FetchedManualPart(
        manual_id=ManualId.IVA,
        year=2025,
        part=ManualPart.SINGLE,
        source_pdf_url=AnyHttpUrl("https://example.com/iva.pdf"),
        relative_pdf_path="source.pdf",
        sha256=sha256,
        content_length=length,
        fetched_at=datetime(2026, 4, 12, 0, 0, 0, tzinfo=UTC),
    )


class TestManifestIO:
    """Manifest reads and PDF verification reject invalid material."""

    def test_load_manifest_missing_raises(self, tmp_path: Path) -> None:
        """load_manifest raises ManifestError when the file is absent."""
        with pytest.raises(ManifestError, match=r"manifest|absent|missing|not found"):
            load_manifest(tmp_path / "absent.json")

class TestBundledManualCorpus:
    """Bundled manual manifests must describe materialized official PDFs."""

    def test_committed_manual_manifests_are_materialized_real_pdfs(self) -> None:
        """Every committed manual manifest rejects synthetic placeholders and rehashes cleanly."""
        manuals_root = bundled_path("corpus", "manuals")
        manifest_paths = sorted(
            scan_directory(manuals_root, pattern="manifest.json", recursive=True),
            key=lambda path: path.relative_to(manuals_root).as_posix(),
        )
        assert manifest_paths
        for manifest_path in manifest_paths:
            manifest = load_manifest(manifest_path)

            assert manifest.synthetic is False, f"{manifest_path} must not be synthetic"
