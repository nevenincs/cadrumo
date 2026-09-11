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

import hashlib
import shutil
from datetime import date
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.artifact_catalogue import ArtifactRole, registry_source_identity
from dev.registry.compiler.corpus_catalogue import (
    compile_record_design_manifest_catalogue,
    verify_catalogue_identity_bindings,
    verify_source_catalogue,
    verify_source_file,
)
from cadrumo.domain.calculations.registry.provenance import NormativeCorpusProvenance
from dev.registry.compiler.corpus_provenance import classify_normative_corpus_provenance
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_references import SourceReference
from dev.registry.tests._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_registry_cited_record_design_boundary_is_exhaustively_catalogued() -> None:
    """The registry's record-design evidence boundary has one official role per source.

    This is deliberately the registry publication consumer's bounded manifest
    projection, rather than a taxonomy of all bundled data.  The registry
    supplies its cited sources; the independently acquired manifests supply
    their payload identities.
    """
    _modelos, catalogues = _committed_registry_tree()

    compiled = compile_record_design_manifest_catalogue(bundled_path(), catalogues.sources)

    assert compiled is not None
    catalogue, record_design_sources = compiled
    expected_paths = {registry_source_identity(source).path for source in record_design_sources.values()}

    assert expected_paths
    assert catalogue.diagnostics == ()
    assert set(catalogue.roles) == expected_paths
    assert set(catalogue.identities) == expected_paths
    assert all(catalogue.roles[path] is ArtifactRole.OFFICIAL_ARTIFACT for path in expected_paths)
    for source in record_design_sources.values():
        registry_identity = registry_source_identity(source)
        catalog_identity = catalogue.identities[registry_identity.path]
        assert catalog_identity.sha256 == registry_identity.sha256
        assert catalog_identity.bytes == registry_identity.bytes
        assert catalog_identity.source_url == registry_identity.source_url
    verify_catalogue_identity_bindings(catalogue, record_design_sources)


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


def test_changed_provenance_shaped_normative_source_still_fails_hash_validation(tmp_path: Path) -> None:
    """A provenance-shaped normative file cannot bypass its recorded source hash."""
    corpus_path = "corpus/normatives/html/provenance-probe.html"
    target = tmp_path / corpus_path
    target.parent.mkdir(parents=True)
    original = b"<!-- Official BOE consolidated source excerpt -->\n<p>original</p>\n"
    target.write_bytes(original)
    source = SourceReference.model_validate(
        {
            "id": "provenance-probe",
            "evidence_tier": "official_source_guidance",
            "authority": "boe",
            "kind": "form_spec",
            "corpus_path": corpus_path,
            "sha256": hashlib.sha256(original).hexdigest(),
            "bytes": len(original),
            "retrieved_at": date(2026, 9, 10),
            "source_url": "https://www.boe.es/",
            "review_status": "pending_review",
        }
    )
    verify_source_file(tmp_path, source)
    assert classify_normative_corpus_provenance(tmp_path, corpus_path) is NormativeCorpusProvenance.BOE_ATTESTED
    target.write_bytes(b"<!-- Official BOE consolidated source excerpt -->\n<p>changed!</p>\n")

    with pytest.raises(RegistryValidationError, match="sha256 mismatch"):
        verify_source_file(tmp_path, source)
