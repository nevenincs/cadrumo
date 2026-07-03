"""Anti-tautology proofs for the companion-aware corpus integrity gate.

Two invariants the wheel split rests on:

* a corpus binary that is PRESENT stays byte-exact hash-enforced — corrupting a
  present, cited binary still hard-fails (the gate did not go soft), and
* a companion corpus binary that is ABSENT surfaces a loud advisory naming the
  file and the ``aeat[corpus-sources]`` install hint and is never silently
  accepted, while an absent NON-companion corpus file (extracted text, HTML)
  still hard-fails exactly as before.

The tests build real ``SourceReference`` records and a real temporary source
root; no repository file is modified and no behaviour is mocked.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from .....core.resources import bundled_path
from .._corpus_catalogue import (
    is_companion_corpus_binary,
    verify_source_file,
)
from .._errors import RegistryValidationError
from .._schema import SourceReference
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _committed_present_companion_binary() -> SourceReference:
    """Return a committed source whose corpus binary is present in the bundled tree."""
    _modelos, catalogues = _committed_registry_tree()
    for source in catalogues.sources.values():
        if not is_companion_corpus_binary(source):
            continue
        on_disk = bundled_path(*source.corpus_path.split("/"))
        if on_disk.is_file() and on_disk.stat().st_size < 5_000_000:
            return source
    raise AssertionError("no present companion corpus binary found in the committed catalogue")


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
