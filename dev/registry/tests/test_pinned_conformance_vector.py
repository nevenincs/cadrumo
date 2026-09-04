"""Detector teeth for the pinned public conformance-vector contract.

The pinning design exists to make a regenerated export tree fail closed rather
than be silently absorbed: the vector's evidence is committed data, so a tree
whose generation manifest no longer matches the pin must be refused. These
tests prove that refusal actually fires, and that a corrupt pin surfaces as a
typed registry refusal rather than an unhandled crash with no owner.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cadrumo.application.registry.tree import _bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..filing_export_proof import (
    build_pinned_conformance_evidence,
    canonical_filing_export_conformance_vectors,
    derive_filing_export_conformance_enrollment,
    load_pinned_conformance_document,
    load_pinned_conformance_inputs,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PINNED = Path(__file__).resolve().parents[1] / "conformance_vectors" / "modelo_200_2025_y_siguientes.toml"
_REGISTRY_ROOT = _bundled_path("registry", "aeat")


def test_the_shipped_pin_materializes_against_the_current_generated_tree() -> None:
    """The committed pin admits the tree as generated today."""
    vectors = canonical_filing_export_conformance_vectors(
        registry_root=_REGISTRY_ROOT,
        source_root=_bundled_path(),
    )
    assert len(vectors) == 1
    coordinate = vectors[0].evidence.coordinate
    assert (str(coordinate.modelo), str(coordinate.revision)) == ("200", "2025-y-siguientes")

    authority = ValidatedRegistryAuthority.load(_REGISTRY_ROOT, source_root=_bundled_path())
    enrollment = derive_filing_export_conformance_enrollment(
        workspace_root=Path.cwd(),
        registry_root=_REGISTRY_ROOT,
        source_root=_bundled_path(),
        authority=authority,
        vectors=vectors,
    )
    materialized = {
        (str(vector.evidence.coordinate.modelo), str(vector.evidence.coordinate.revision))
        for vector in enrollment.materializable_vectors
    }
    assert ("200", "2025-y-siguientes") in materialized
    assert not [residue for residue in enrollment.residues if str(residue.modelo) == "200"]


def test_a_manifest_digest_that_drifts_from_the_pin_is_refused(tmp_path: Path) -> None:
    """A regenerated tree must fail closed, never be silently absorbed."""
    drifted = tmp_path / "drifted.toml"
    text = _PINNED.read_text(encoding="utf-8")
    document = load_pinned_conformance_document(_PINNED)
    drifted.write_text(
        text.replace(document.generation_manifest_sha256, "0" * 64),
        encoding="utf-8",
    )
    manifest_path = (
        _REGISTRY_ROOT
        / "modelos"
        / "200"
        / "revisions"
        / "2025-y-siguientes"
        / "export"
        / "_generation.provenance.json"
    )
    manifest_raw = manifest_path.read_bytes()

    from ..pipeline._provenance_manifest import load_export_fragment_provenance_manifest

    with pytest.raises(RegistryValidationError, match="does not match the pinned conformance vector"):
        build_pinned_conformance_evidence(
            load_pinned_conformance_document(drifted),
            manifest_raw=manifest_raw,
            manifest=load_export_fragment_provenance_manifest(manifest_raw),
        )


def test_a_corrupt_pin_refuses_as_a_typed_registry_error(tmp_path: Path) -> None:
    """A truncated or malformed pin must not escape as an unowned crash."""
    truncated = tmp_path / "truncated.toml"
    shutil.copy(_PINNED, truncated)
    truncated.write_text('authority_id = "only-this"\n', encoding="utf-8")
    with pytest.raises(RegistryValidationError, match="pinned-vector contract"):
        load_pinned_conformance_document(truncated)

    unparseable = tmp_path / "unparseable.toml"
    unparseable.write_text("this is = = not toml\n", encoding="utf-8")
    with pytest.raises(RegistryValidationError, match="unreadable"):
        load_pinned_conformance_document(unparseable)

    absent = tmp_path / "absent.toml"
    with pytest.raises(RegistryValidationError, match="unreadable"):
        load_pinned_conformance_document(absent)


def test_one_id_declared_on_both_input_channels_is_refused(tmp_path: Path) -> None:
    """An ambiguous declaration is refused rather than resolved by ordering."""
    colliding = tmp_path / "colliding.toml"
    text = _PINNED.read_text(encoding="utf-8")
    colliding.write_text(
        text.replace(
            "[inputs.enum]",
            '[inputs.enum]\n"00501" = "sl"',
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(RegistryValidationError, match="both the decimal and enum channels"):
        load_pinned_conformance_inputs(load_pinned_conformance_document(colliding))
