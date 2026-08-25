"""Anti-tautology proofs for the mandatory-cohort corpus integrity gate.

Two invariants the wheel cohort rests on:

* a corpus binary that is PRESENT stays byte-exact hash-enforced — corrupting a
  present, cited binary still hard-fails (the gate did not go soft), and
* any corpus file that is ABSENT hard-fails, including data owned by either
  mandatory companion distribution.

The tests build real ``SourceReference`` records and a real temporary source
root; no repository file is modified and no behaviour is mocked.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema_references import SourceReference

from .....core.resources import bundled_path
from ..corpus_catalogue import (
    verify_source_catalogue,
    verify_source_file,
)
from ..errors import RegistryValidationError
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _committed_present_companion_binary() -> SourceReference:
    """Return a committed source whose corpus binary is present in the bundled tree."""
    _modelos, catalogues = _committed_registry_tree()
    for source in catalogues.sources.values():
        if not source.corpus_path.lower().endswith((".pdf", ".xls", ".xlsx")):
            continue
        on_disk = bundled_path(*source.corpus_path.split("/"))
        if on_disk.is_file() and on_disk.stat().st_size < 5_000_000:
            return source
    raise AssertionError("no present companion corpus binary found in the committed catalogue")


def _absent_source(*, corpus_path: str, kind: str) -> SourceReference:
    """Build a source reference pointing at an absent corpus path with a plausible hash."""
    template = next(iter(_committed_registry_tree()[1].sources.values()))
    return template.model_copy(
        update={
            "id": "aeat-companion-probe",
            "kind": kind,
            "corpus_path": corpus_path,
            "sha256": "0" * 64,
            "bytes": 1024,
        },
    )


def test_corrupted_present_corpus_binary_still_hard_fails(tmp_path: Path) -> None:
    source = _committed_present_companion_binary()
    real_path = bundled_path(*source.corpus_path.split("/"))
    original = real_path.read_bytes()

    staged = tmp_path / source.corpus_path
    staged.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(real_path, staged)
    # Flip one byte in place: same length, so the byte-count check passes and the
    # SHA-256 check is the one that must fire — proving the hash gate is live.
    corrupted = bytearray(staged.read_bytes())
    corrupted[0] ^= 0xFF
    staged.write_bytes(bytes(corrupted))

    assert staged.read_bytes() != original
    assert len(bytes(corrupted)) == source.bytes

    with pytest.raises(RegistryValidationError, match="sha256 mismatch"):
        verify_source_file(tmp_path, source)


def test_absent_mandatory_companion_binary_hard_fails(tmp_path: Path) -> None:
    corpus_path = "corpus/aeat_official/disenos_registro/modelo_absent_probe/files/absent-companion.xlsx"
    source = _absent_source(corpus_path=corpus_path, kind="record_design")

    with pytest.raises(RegistryValidationError, match="missing corpus file"):
        verify_source_file(tmp_path, source)

    with pytest.raises(RegistryValidationError, match="missing corpus file"):
        verify_source_catalogue(tmp_path, {source.id: source})


def test_absent_non_companion_corpus_file_still_hard_fails(tmp_path: Path) -> None:
    corpus_path = "corpus/normatives/html/absent-probe.html"
    source = _absent_source(corpus_path=corpus_path, kind="form_spec")

    with pytest.raises(RegistryValidationError, match="missing corpus file"):
        verify_source_file(tmp_path, source)

    with pytest.raises(RegistryValidationError, match="missing corpus file"):
        verify_source_catalogue(tmp_path, {source.id: source})
