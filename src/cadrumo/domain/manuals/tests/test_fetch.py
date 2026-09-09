"""Behavior tests for bundled manual manifest loading and PDF verification."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from ....core.directory_scan import scan_directory
from ....core.resources.bundled_data import bundled_path
from ..errors import ManifestError
from ..fetch import load_manifest, verify_fetched_pdf
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

    def test_verify_fetched_pdf_success(self, tmp_path: Path) -> None:
        """Matching sha256 and length pass verification silently."""
        part_root = tmp_path
        pdf = part_root / "source.pdf"
        pdf.write_bytes(b"hello pdf\n")
        # sha256 of "hello pdf\n"
        import hashlib

        sha256 = hashlib.sha256(b"hello pdf\n").hexdigest()
        manifest = _manifest(sha256=sha256, length=len(b"hello pdf\n"))
        assert manifest.sha256 == sha256
        result = verify_fetched_pdf(manifest, part_root)
        assert result is None

    def test_verify_fetched_pdf_sha_mismatch(self, tmp_path: Path) -> None:
        """A sha256 mismatch raises ManifestError."""
        part_root = tmp_path
        pdf = part_root / "source.pdf"
        pdf.write_bytes(b"hello pdf\n")
        manifest = _manifest(sha256="b" * 64, length=len(b"hello pdf\n"))
        with pytest.raises(ManifestError, match="sha256 mismatch"):
            verify_fetched_pdf(manifest, part_root)

    def test_verify_fetched_pdf_missing_file(self, tmp_path: Path) -> None:
        """A missing raw PDF raises a clear ManifestError."""
        manifest = _manifest()
        with pytest.raises(ManifestError, match="raw PDF not found"):
            verify_fetched_pdf(manifest, tmp_path)

    def test_verify_fetched_pdf_rejects_traversal_path(self, tmp_path: Path) -> None:
        """A tampered relative_pdf_path must not escape the part root."""
        manifest = _manifest().model_copy(update={"relative_pdf_path": "../outside.pdf"})
        with pytest.raises(ManifestError, match="must stay within the owning root"):
            verify_fetched_pdf(manifest, tmp_path)


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
            verify_fetched_pdf(manifest, manifest_path.parent)
