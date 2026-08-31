"""Unit tests for the fetch module (offline: table + manifest IO)."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from ....core.directory_scan import scan_directory
from ....core.external_constants import load_external_constants
from ....core.resources._boundary import bundled_path
from ..errors import ManifestError
from ..fetch import PART_SPECS, load_manifest, lookup_spec, verify_fetched_pdf, write_manifest
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


class TestPartSpecs:
    """The PartSpec table covers every supported official PDF triple."""

    def test_part_specs_cover_v1_triples(self) -> None:
        """PART_SPECS contains exactly the currently published official PDF entries."""
        triples = {(spec.manual_id, spec.year, spec.part) for spec in PART_SPECS}
        expected = set()
        for year in [2020, 2021, 2022, 2023, 2024, 2025]:
            expected.add((ManualId.RENTA, year, ManualPart.PARTE_1))
            expected.add((ManualId.IVA, year, ManualPart.SINGLE))
        for year in [2024, 2025]:
            expected.add((ManualId.RENTA, year, ManualPart.PARTE_2_DEDUCCIONES_AUTONOMICAS))
        assert triples == expected

    def test_part_specs_urls_are_aeat(self) -> None:
        """Every URL points at the configured AEAT Sede manuals root."""
        aeat = load_external_constants().aeat
        expected_prefix = f"{aeat.domains.sede}{aeat.help_pages.manual_practicos_root}"
        for spec in PART_SPECS:
            assert spec.source_pdf_url.startswith(expected_prefix)

    def test_lookup_spec_hit(self) -> None:
        """lookup_spec returns the matching entry for a known triple."""
        spec = lookup_spec(ManualId.IVA, 2025, ManualPart.SINGLE)
        assert spec.manual_id is ManualId.IVA
        assert spec.year == 2025
        assert spec.part is ManualPart.SINGLE

    def test_lookup_spec_miss_raises(self) -> None:
        """lookup_spec raises ManifestError for an unregistered triple."""
        with pytest.raises(ManifestError, match=r"IVA|2099|manifest|spec"):
            lookup_spec(ManualId.IVA, 2099, ManualPart.SINGLE)


class TestManifestIO:
    """Manifest round-trips cleanly and rejects tampering."""

    def test_write_then_load_round_trips(self, tmp_path: Path) -> None:
        """A written manifest reloads equal to the original record."""
        manifest = _manifest()
        path = tmp_path / "manifest.json"
        write_manifest(path, manifest)
        reloaded = load_manifest(path)
        assert reloaded == manifest

    def test_write_manifest_wraps_io_failure_as_manifest_error(self, tmp_path: Path) -> None:
        """Manifest persistence failures stay inside the manual error family."""
        manifest = _manifest()
        directory_target = tmp_path / "manifest-dir"
        directory_target.mkdir()

        with pytest.raises(ManifestError, match=r"cannot write manifest"):
            write_manifest(directory_target, manifest)

        assert scan_directory(tmp_path, pattern="*.tmp") == ()

    def test_write_manifest_replaces_the_authoritative_file_atomically(self, tmp_path: Path) -> None:
        """A prior manifest is swapped out, never overwritten in place.

        The manifest is the authoritative record a later verification reads
        to decide whether the downloaded PDF is intact, so a torn write
        behind a trusted name is the failure this pins. A hard link holds a
        durable handle on the prior inode: an in-place write shows through
        that handle, an atomic stage-and-replace does not.
        """
        path = tmp_path / "manifest.json"
        write_manifest(path, _manifest(sha256="a" * 64, length=10))
        prior_content = path.read_text(encoding="utf-8")
        witness = tmp_path / "manifest-witness.json"
        os.link(path, witness)
        assert path.stat().st_ino == witness.stat().st_ino

        write_manifest(path, _manifest(sha256="b" * 64, length=20))

        assert load_manifest(path).sha256 == "b" * 64
        assert witness.read_text(encoding="utf-8") == prior_content
        assert "b" * 64 not in witness.read_text(encoding="utf-8")
        assert path.stat().st_ino != witness.stat().st_ino
        assert scan_directory(tmp_path, pattern="*.tmp") == ()

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
        checked: list[str] = []

        assert manifest_paths
        for manifest_path in manifest_paths:
            manifest = load_manifest(manifest_path)

            assert manifest.synthetic is False, f"{manifest_path} must not be synthetic"
            verify_fetched_pdf(manifest, manifest_path.parent)
            checked.append(f"{manifest.manual_id.value}/{manifest.year}/{manifest.part.value}")

        assert checked == [
            "iva/2020/single",
            "iva/2021/single",
            "iva/2022/single",
            "iva/2023/single",
            "iva/2024/single",
            "iva/2025/single",
            "renta/2020/part1",
            "renta/2021/part1",
            "renta/2022/part1",
            "renta/2023/part1",
            "renta/2024/part1",
            "renta/2024/part2-deducciones-autonomicas",
            "renta/2025/part1",
            "renta/2025/part2-deducciones-autonomicas",
        ]
