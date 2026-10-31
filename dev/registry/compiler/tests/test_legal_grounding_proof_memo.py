"""A catalogue pass proves each legal reference once per content of its evidence.

Every staged export candidate re-parses the legal catalogue and grounds it
against the same corpus, so each pass re-proved roughly a thousand references
from unchanged bytes. The proof is now remembered under the reference, the
SHA-256 of every file the proof reads and the grounding code. These gates hold
the reuse and, above all, that a stat-preserving rewrite of the evidence --
which the stat-keyed digest memo could not see, and which is why that memo is
dropped every pass -- reaches the full proof and its refusal.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Final

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_references import LegalReference

from .. import legal_grounding
from ..legal_grounding import verify_legal_catalogue_grounding
from ..loader import load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REFERENCE_ID: Final = "ley-49-2002:art-10"
_REQUIRED: Final = "positiva"
_FORGED: Final = "negativo"


def _bundled_reference() -> LegalReference:
    reference = load_shared_catalogues(bundled_path("registry", "aeat")).legal[_REFERENCE_ID]
    assert any(_REQUIRED in text for text in reference.required_text), "fixture reference changed its clause"
    return reference


def _isolated_corpus(tmp_path: Path, reference: LegalReference) -> tuple[Path, Path]:
    """Copy the reference's document and sidecar into a fresh root, so edits never reach the bundle."""
    path_text = reference.corpus_ref.partition("#")[0]
    root = tmp_path / "source"
    document = root / path_text
    document.parent.mkdir(parents=True)
    bundled_document = bundled_path() / path_text
    shutil.copy2(bundled_document, document)
    sidecar = document.with_name(f"{document.name}.extracted.json")
    shutil.copy2(bundled_document.with_name(sidecar.name), sidecar)
    return root, sidecar


def _forge_preserving_stat(path: Path, old: bytes, new: bytes) -> None:
    """Rewrite ``path`` with ``old`` replaced by same-length ``new``, restoring size and mtime."""
    assert len(old) == len(new)
    before = path.stat()
    payload = path.read_bytes()
    assert old in payload, "the forged text must occur in the evidence"
    path.write_bytes(payload.replace(old, new))
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    after = path.stat()
    assert (after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns), "stat identity not forged"


def _counting_proofs(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record each full proof the catalogue pass runs, still running the real proof."""
    proven: list[str] = []
    real: Callable[..., None] = legal_grounding.verify_legal_reference_grounding

    def counting(reference: LegalReference, *, source_root: Path) -> None:
        proven.append(reference.id)
        real(reference, source_root=source_root)

    monkeypatch.setattr(legal_grounding, "verify_legal_reference_grounding", counting)
    return proven


def test_unchanged_evidence_is_proven_once_across_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reference = _bundled_reference()
    root, _sidecar = _isolated_corpus(tmp_path, reference)
    proven = _counting_proofs(monkeypatch)

    for _ in range(3):
        verify_legal_catalogue_grounding({reference.id: reference}, source_root=root)

    assert proven == [reference.id], "an unchanged reference over unchanged bytes must be proven exactly once"


def test_a_stat_preserving_rewrite_of_the_evidence_reaches_the_refusal(tmp_path: Path) -> None:
    reference = _bundled_reference()
    root, sidecar = _isolated_corpus(tmp_path, reference)
    verify_legal_catalogue_grounding({reference.id: reference}, source_root=root)

    _forge_preserving_stat(sidecar, _REQUIRED.encode(), _FORGED.encode())

    with pytest.raises(RegistryValidationError, match="missing required text"):
        verify_legal_catalogue_grounding({reference.id: reference}, source_root=root)


def test_a_refusal_is_raised_by_the_full_proof_on_every_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reference = _bundled_reference()
    root, sidecar = _isolated_corpus(tmp_path, reference)
    original = sidecar.read_bytes()
    _forge_preserving_stat(sidecar, _REQUIRED.encode(), _FORGED.encode())
    proven = _counting_proofs(monkeypatch)

    messages = []
    for _ in range(2):
        with pytest.raises(RegistryValidationError) as refused:
            verify_legal_catalogue_grounding({reference.id: reference}, source_root=root)
        messages.append(str(refused.value))

    assert proven == [reference.id, reference.id], "a refusal must never be answered from memory"
    assert messages[0] == messages[1]
    sidecar.write_bytes(original)
    verify_legal_catalogue_grounding({reference.id: reference}, source_root=root)


def test_a_changed_reference_is_proven_afresh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reference = _bundled_reference()
    root, _sidecar = _isolated_corpus(tmp_path, reference)
    verify_legal_catalogue_grounding({reference.id: reference}, source_root=root)
    proven = _counting_proofs(monkeypatch)
    narrowed = reference.model_copy(update={"required_text": reference.required_text[:1]})
    assert narrowed != reference, "the fixture needs a second clause to drop"

    verify_legal_catalogue_grounding({narrowed.id: narrowed}, source_root=root)

    assert proven == [reference.id]
