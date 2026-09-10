"""Catalog diagnostics for the AEAT corpus coverage boundary.

This gate used to admit a payload through any of three locally reconstructed
signals: a registry path, a manifest location, or a filename mentioned in
``PROVENANCE.md``. Those are different kinds of evidence, not interchangeable
proof of a bundled artifact's immutable identity. The artifact catalog is now
the one place that decides whether independently declared identities classify
the bounded paths supplied by this consumer.

Registry semantics remain outside this test: a ``SourceReference`` is
projected to an immutable identity by the registry verifier, which retains
applicability, evidence tier, and review authority. The tests below exercise
only the catalog's coverage diagnostics with declarations assembled
independently, so a matching path alone cannot become an origin claim.
"""

from __future__ import annotations

from datetime import date
from pathlib import PurePosixPath

import pytest

from cadrumo.domain.calculations.registry.artifact_catalogue import (
    ArtifactDiagnosticKind,
    ArtifactIdentity,
    ArtifactRole,
    compile_artifact_catalogue,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PAYLOAD = PurePosixPath("corpus/aeat_official/instructions/modelo_999/files/payload.html")
_RETRIEVED_AT = date(2026, 9, 10)


def _identity(
    *,
    path: PurePosixPath = _PAYLOAD,
    sha256: str = "a" * 64,
    bytes: int = 7,
    source_url: str = "https://www.agenciatributaria.gob.es/payload.html",
) -> ArtifactIdentity:
    """Return one independently-declarable immutable artifact identity."""
    return ArtifactIdentity(
        path=path,
        sha256=sha256,
        bytes=bytes,
        source_url=source_url,
        publisher="AEAT",
        retrieved_at=_RETRIEVED_AT,
    )


def _diagnostic_kinds(
    *,
    known_paths: tuple[PurePosixPath, ...],
    official_identities: tuple[ArtifactIdentity, ...] = (),
    registry_identities: tuple[ArtifactIdentity, ...] = (),
) -> set[ArtifactDiagnosticKind]:
    """Compile a bounded catalog and expose its typed findings to each proof."""
    catalogue = compile_artifact_catalogue(
        known_paths=known_paths,
        official_identities=official_identities,
        registry_identities=registry_identities,
    )
    return {diagnostic.kind for diagnostic in catalogue.diagnostics}


def test_unclassified_bundled_payload_is_an_unknown_catalog_file() -> None:
    """DETECTOR TEETH: a file with no identity claim fails visibly.

    The bounded file list comes from the consumer's corpus traversal; it is
    deliberately separate from the (empty) acquisition declarations. Passing
    the same collection for both would make the compiler's unknown-file branch
    untestable and recreate the old vacuous coverage sweep.
    """
    findings = _diagnostic_kinds(known_paths=(_PAYLOAD,))

    assert findings == {ArtifactDiagnosticKind.UNKNOWN_FILE}


def test_independent_official_declarations_for_one_path_conflict() -> None:
    """DETECTOR TEETH: path equality cannot hide divergent acquisition proof.

    These stand in for two independent declarations (for example, a manifest
    and a separately supplied source inventory). They intentionally name the
    same bundled path but disagree on the content digest, so this is not a
    test that manufactures both sides from a single catalog record.
    """
    manifest_identity = _identity()
    independently_declared_identity = _identity(sha256="b" * 64)

    findings = _diagnostic_kinds(
        known_paths=(_PAYLOAD,),
        official_identities=(manifest_identity, independently_declared_identity),
    )

    assert findings == {ArtifactDiagnosticKind.CONFLICTING_IDENTITY}


def test_registry_projection_must_bind_the_independent_official_identity() -> None:
    """Registry authority cannot be weakened to an enrolled path assertion.

    The official identity and registry projection are created separately. The
    path and digest match, but the independently declared acquisition URL does
    not, which must report a broken registry binding instead of accepting the
    common path as sufficient evidence.
    """
    manifest_identity = _identity()
    registry_projection = _identity(source_url="https://www.agenciatributaria.gob.es/other-payload.html")

    findings = _diagnostic_kinds(
        known_paths=(_PAYLOAD,),
        official_identities=(manifest_identity,),
        registry_identities=(registry_projection,),
    )

    assert findings == {ArtifactDiagnosticKind.BROKEN_REGISTRY_BINDING}


def test_matching_independent_identity_assigns_the_official_role() -> None:
    """A complete identity claim classifies the bounded payload exactly once."""
    manifest_identity = _identity()
    registry_projection = _identity()

    catalogue = compile_artifact_catalogue(
        known_paths=(_PAYLOAD,),
        official_identities=(manifest_identity,),
        registry_identities=(registry_projection,),
    )

    assert catalogue.diagnostics == ()
    assert catalogue.roles == {_PAYLOAD: ArtifactRole.OFFICIAL_ARTIFACT}
