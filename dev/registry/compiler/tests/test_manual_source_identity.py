"""PDF source identity is independent of authored manual structure coverage."""

from hashlib import sha256
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_base import RegistrySourceKind
from cadrumo.domain.calculations.registry.static_inspection import StaticGeneratedArtifactSource

from ..corpus_catalogue import verify_source_file

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _source(payload: bytes) -> StaticGeneratedArtifactSource:
    return StaticGeneratedArtifactSource(
        id="manual-iva-2024",
        kind=RegistrySourceKind.MANUAL_PDF,
        corpus_path="corpus/manuals/iva/2024/source.pdf",
        sha256=sha256(payload).hexdigest(),
        bytes=len(payload),
        applies_from=None,
        applies_to=None,
        record_design_epoch=None,
        corpus_tier=None,
    )


def test_corrupt_optional_structure_does_not_change_source_identity(tmp_path: Path) -> None:
    payload = b"%PDF-1.4 source identity fixture"
    source = _source(payload)
    path = tmp_path / source.corpus_path
    path.parent.mkdir(parents=True)
    path.write_bytes(payload)
    structure = path.parent / "structure"
    structure.mkdir()
    (structure / "manual.json").write_text("{invalid", encoding="utf-8")
    assert verify_source_file(tmp_path, source) == path


@pytest.mark.parametrize("replacement", [b"short", b"%PDF-1.4 source identity fixturE"])
def test_manual_source_still_requires_exact_bytes(tmp_path: Path, replacement: bytes) -> None:
    source = _source(b"%PDF-1.4 source identity fixture")
    path = tmp_path / source.corpus_path
    path.parent.mkdir(parents=True)
    path.write_bytes(replacement)
    with pytest.raises(RegistryValidationError, match=r"byte count mismatch|sha256 mismatch"):
        verify_source_file(tmp_path, source)
