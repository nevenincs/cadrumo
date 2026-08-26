"""Regression for the Modelo 303 ``verification_source`` snapshot-resolution failure.

A Modelo 303 registry-build failure could surface with the extraction-profile
round-trip gate refusing the profile with *"sets corpus_round_trip_verified =
true but verification_source is not set"*. The root cause was the registry
loader cache serving a **partial** view of a revision fragment while a
concurrent write was in flight: a mid-write ``extraction_profiles`` fragment
could be read with ``corpus_round_trip_verified = true`` already present but
``verification_source`` not yet written, tripping the round-trip gate at
snapshot build.

The registry-tree fingerprint now recursively covers every
``revisions/**/*.toml`` fragment (so an ``extraction_profiles`` fragment edit
invalidates the cache), and a concurrent directory change during
fingerprinting fails loudly with *"retry after concurrent registry writes
settle"* rather than serving a partial.

These tests pin the closed state at the application-facing resolution boundary
(the path the verify flow uses):

* ``test_m303_snapshot_resolves_extraction_profile_verification_source`` proves
  the committed M303 data, resolved through the production
  :class:`~domain.calculations.registry.ValidatedRegistryAuthority` with the
  loader caches cleared, validates cleanly and surfaces a well-formed extraction
  profile — every ``corpus_round_trip_verified`` ``declaracion_pdf`` profile
  carries a non-``None`` ``verification_source``. If a partial or mis-tagged
  profile ever reached the M303 snapshot again, ``validate_modelo`` would raise.

* ``test_m303_round_trip_gate_still_fires_on_the_partial_shape`` is the
  anti-tautology guard: it feeds the round-trip gate the exact partial shape the
  race produced (round-trip verified, ``verification_source = None``) against the
  real justificante corpus and asserts the gate still refuses it. Without this,
  the positive test above could pass vacuously if the gate were ever silenced.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.loader_fingerprints import clear_fingerprint_cache
from cadrumo.domain.calculations.registry.validate import RegistryValidator

from ....core.directory_scan import iter_directory
from ....core.resources import bundled_path
from ....domain.calculations.registry.authority import bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO_303 = "303"

# Mirror ``RegistryValidator.justificante_corpus_root``: bundled_path() resolves
# to src/cadrumo/_data; the fixture tree lives one level up under tests/fixtures.
_JUSTIFICANTE_CORPUS_ROOT = bundled_path().resolve().parents[0] / "tests" / "fixtures" / "justificantes"


def test_m303_snapshot_resolves_extraction_profile_verification_source() -> None:
    """M303 validates and resolves a well-formed extraction profile at HEAD.

    Reproduces the persona's production resolution path with the loader caches
    cleared (the "fresh tmp_path with cleared registry caches" the step calls
    for): ``validate_modelo`` runs the registry validation that includes the
    extraction-profile round-trip gate, and the resolved revisions must carry a
    non-``None`` ``verification_source`` on every ``corpus_round_trip_verified``
    ``declaracion_pdf`` profile. A regressed partial/stale read would make
    ``validate_modelo`` raise ``RegistryValidationError`` here.
    """
    clear_fingerprint_cache()
    authority = bundled_authority()

    # Production validation path — runs the round-trip gate for M303. Must not raise.
    modelo = authority.validate_modelo(_MODELO_303)

    checked: list[str] = []
    for revision_id, revision in modelo.revisions.items():
        for profile in revision.extraction_profiles:
            if profile.surface != "declaracion_pdf" or not profile.corpus_round_trip_verified:
                continue
            checked.append(f"{revision_id}/{profile.id}")
            assert profile.verification_source is not None, (
                f"M303 revision {revision_id!r} extraction profile {profile.id!r} is "
                f"corpus_round_trip_verified but verification_source is None — the exact "
                f"partial-read shape that the pre-688ed6713 loader race surfaced at snapshot build"
            )

    assert checked, (
        "expected at least one corpus_round_trip_verified declaracion_pdf profile on M303; "
        "the regression is dormant if none is present"
    )


def test_m303_public_registry_validation_still_refuses_the_partial_shape() -> None:
    """The public registry validator still refuses a verification-source regression.

    Build the exact historical partial from the live M303 declaration profile,
    then drive it through the supported registry-validation boundary. This proves
    the production validation path—not a private helper—continues to refuse a
    profile which claims corpus round-trip verification without declaring how that
    verification was grounded.
    """
    authority = bundled_authority()
    modelo = authority.validate_modelo(_MODELO_303)
    candidates = [
        (revision_id, revision, profile)
        for revision_id, revision in modelo.revisions.items()
        for profile in revision.extraction_profiles
        if profile.surface == "declaracion_pdf" and profile.corpus_round_trip_verified
    ]
    assert candidates, "M303 must retain a corpus-round-trip-verified declaracion profile for this regression"
    revision_id, revision, profile = candidates[0]
    partial_profile = profile.model_copy(update={"verification_source": None})
    partial_revision = revision.model_copy(
        update={
            "extraction_profiles": tuple(
                partial_profile if candidate.id == profile.id else candidate
                for candidate in revision.extraction_profiles
            )
        }
    )
    partial_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision_id: partial_revision}})

    with pytest.raises(RegistryValidationError, match="verification_source is not set"):
        RegistryValidator(
            authority.catalogues,
            source_root=authority.source_root,
            justificante_corpus_root=_JUSTIFICANTE_CORPUS_ROOT,
        ).validate_modelo(partial_modelo)


def test_justificante_corpus_root_exists_so_the_guard_is_not_dormant() -> None:
    """The M303 justificante corpus must exist, or the guard silently no-ops.

    Public M303 validation only reaches its ``verification_source`` branch when
    a corpus fixture PDF exists for the modelo; without one the anti-tautology
    guard would pass vacuously.
    """
    fixture_dir = _JUSTIFICANTE_CORPUS_ROOT / _MODELO_303
    assert fixture_dir.is_dir() and any(iter_directory(fixture_dir, pattern="*.pdf")), (
        f"no M303 justificante corpus PDF at {fixture_dir}; the round-trip gate guard is dormant"
    )
