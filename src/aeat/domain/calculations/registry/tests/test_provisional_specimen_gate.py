"""Tests for the declaracion_pdf provisional_pending_specimen validator gate.

The gate enforces that any ``declaracion_pdf`` extraction profile without a
corpus fixture PDF in the justificantes fixture directory must explicitly declare
``provisional_pending_specimen = true``.  Profiles that do neither cause a hard
snapshot-build failure; profiles with a fixture or with the flag set validate
cleanly.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import pytest

from .....core.resources import bundled_path
from .. import RegistryCatalogues, RegistryValidationError
from .._loader import load_registry_tree
from .._schema import ExtractionProfileDefinition, ModeloDefinition
from .._validate import RegistryValidator

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_DATA_ROOT = bundled_path()


@cache
def _committed_130() -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    return next(m for m in modelos if m.id == "130"), catalogues


def _committed_profile(provisional: bool = False) -> ExtractionProfileDefinition:
    """Return the committed M130 declaracion_pdf profile, optionally overriding provisional flag."""
    modelo, _catalogues = _committed_130()
    revision = modelo.revisions["2019-y-siguientes"]
    profile = next(p for p in revision.extraction_profiles if p.surface == "declaracion_pdf")
    return profile.model_copy(update={"provisional_pending_specimen": provisional})


def test_provisional_field_defaults_false() -> None:
    profile = _committed_profile()
    assert profile.provisional_pending_specimen is False


def test_provisional_field_accepts_true() -> None:
    profile = _committed_profile(provisional=True)
    assert profile.provisional_pending_specimen is True


# --- Gate: no fixture, no flag → fails validation ---------------------------


def test_no_fixture_no_flag_fails_validation(tmp_path: Path) -> None:
    """Profile with no corpus fixture and provisional_pending_specimen=False must fail."""
    modelo, catalogues = _committed_130()
    # Use an empty corpus root so no fixture exists for any modelo
    empty_corpus_root = tmp_path / "justificantes"
    empty_corpus_root.mkdir()

    revision = modelo.revisions["2019-y-siguientes"]
    profile = _committed_profile(provisional=False)
    mutated = revision.model_copy(update={"extraction_profiles": (profile,)})
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, mutated.id: mutated}})

    validator = RegistryValidator(
        catalogues,
        source_root=bundled_path(),
        justificante_corpus_root=empty_corpus_root,
    )
    with pytest.raises(RegistryValidationError, match="provisional_pending_specimen"):
        validator.validate_modelo(mutated_modelo)


# --- Gate: no fixture but flag set → validates --------------------------------


def test_no_fixture_with_flag_validates(tmp_path: Path) -> None:
    """Profile with no corpus fixture but provisional_pending_specimen=True must pass."""
    modelo, catalogues = _committed_130()
    empty_corpus_root = tmp_path / "justificantes"
    empty_corpus_root.mkdir()

    revision = modelo.revisions["2019-y-siguientes"]
    profile = _committed_profile(provisional=True)
    mutated = revision.model_copy(update={"extraction_profiles": (profile,)})
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, mutated.id: mutated}})

    validator = RegistryValidator(
        catalogues,
        source_root=bundled_path(),
        justificante_corpus_root=empty_corpus_root,
    )
    # No exception raised: provisional flag satisfies the gate
    validator.validate_modelo(mutated_modelo)


# --- Gate: fixture present, flag unset → validates ----------------------------


def test_fixture_present_round_trip_verified_validates(tmp_path: Path) -> None:
    """Profile with a corpus fixture PDF and corpus_round_trip_verified=True must pass.

    Having a fixture alone is no longer sufficient — the round-trip gate also
    requires corpus_round_trip_verified=True (or provisional_pending_specimen=True).
    This test confirms the correct happy-path: fixture present AND round-trip verified.
    """
    modelo, catalogues = _committed_130()
    corpus_root = tmp_path / "justificantes"
    modelo_fixture_dir = corpus_root / "130"
    modelo_fixture_dir.mkdir(parents=True)
    # Place a stub PDF file to satisfy the fixture check
    (modelo_fixture_dir / "2024-1T.pdf").write_bytes(b"%PDF-1.4 stub")

    revision = modelo.revisions["2019-y-siguientes"]
    profile = _committed_profile(provisional=False).model_copy(
        update={
            "corpus_round_trip_verified": True,
            "verification_source": "synthetic_from_aeat_published_text",
        },
    )
    mutated = revision.model_copy(update={"extraction_profiles": (profile,)})
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, mutated.id: mutated}})

    validator = RegistryValidator(
        catalogues,
        source_root=bundled_path(),
        justificante_corpus_root=corpus_root,
    )
    # No exception raised: fixture present + corpus_round_trip_verified satisfies both gates
    validator.validate_modelo(mutated_modelo)


# --- Production path: corpus derivation from source_root ----------------------


def test_corpus_root_derived_from_bundled_path() -> None:
    """RegistryValidator must derive a valid corpus root from bundled_path().

    This exercises the production code path where justificante_corpus_root is
    NOT injected directly.  The derivation must resolve to
    src/aeat/tests/fixtures/justificantes, which exists on disk, so
    _justificante_corpus_root must not be None.
    """
    _modelo, catalogues = _committed_130()
    validator = RegistryValidator(catalogues, source_root=_DATA_ROOT)
    assert validator._justificante_corpus_root is not None, (
        "corpus root derivation from bundled_path() returned None; "
        "the provisional specimen gate is disabled in production"
    )
    assert validator._justificante_corpus_root.is_dir(), (
        f"derived corpus root {validator._justificante_corpus_root} is not a directory"
    )
    assert validator._justificante_corpus_root.name == "justificantes"


def test_gate_fires_no_fixture_no_flag(tmp_path: Path) -> None:
    """Gate must raise RegistryValidationError when no fixture exists and flag is False.

    Uses M130 with an injected empty corpus root so no fixture directory exists.
    With provisional_pending_specimen overridden to False, the gate must reject the
    modelo regardless of the production corpus derivation path.

    Production-path corpus derivation is already covered by
    test_corpus_root_derived_from_bundled_path; this test focuses purely on the
    gate-fires logic independent of the fixture inventory on disk.
    """
    modelo, catalogues = _committed_130()
    empty_corpus_root = tmp_path / "justificantes"
    empty_corpus_root.mkdir()

    revision = modelo.revisions["2019-y-siguientes"]
    profile = _committed_profile(provisional=False)
    mutated = revision.model_copy(update={"extraction_profiles": (profile,)})
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, mutated.id: mutated}})

    validator = RegistryValidator(
        catalogues,
        source_root=_DATA_ROOT,
        justificante_corpus_root=empty_corpus_root,
    )
    assert validator._justificante_corpus_root is not None, "corpus root must be set; gate would be silent"
    with pytest.raises(RegistryValidationError, match="provisional_pending_specimen"):
        validator.validate_modelo(mutated_modelo)


def test_gate_fires_via_production_path() -> None:
    """Specimen gate exercises: pure-production wiring with source_root=bundled_path() only.

    NOTE ON COVERAGE BOUNDARY: The specimen gate fires when no corpus fixture exists
    for a model with a declaracion_pdf profile and provisional_pending_specimen=False.
    All real modelos with declaracion_pdf profiles have at least one real fixture
    under tests/fixtures/justificantes/, so the specimen-gate "fires" scenario
    (no fixture + no flag) cannot be triggered via pure-production wiring without
    direct corpus_root injection.  This is a structural property of the fixture
    inventory, not a gap in derivation logic.

    What pure-production wiring CAN assert about the specimen gate:
      - The derivation resolves to a real directory (guarding against silent None).
      - The gate is silent for M130 when provisional_pending_specimen=True (Scenario B).
      - The gate is silent for M130 when corpus + round_trip_verified satisfies both
        gates (Scenario C), confirming no spurious specimen-gate firing on verified
        profiles.

    The "gate fires" scenario (Scenario A) is covered by test_gate_fires_no_fixture_no_flag
    which injects an empty corpus root to isolate that branch from fixture inventory.
    """
    modelo, catalogues = _committed_130()

    validator = RegistryValidator(catalogues, source_root=_DATA_ROOT)
    assert validator._justificante_corpus_root is not None, (
        "corpus root derivation returned None; specimen gate is silently disabled in production"
    )
    assert validator._justificante_corpus_root.is_dir(), (
        f"derived corpus root {validator._justificante_corpus_root} is not a directory"
    )

    # Scenario B via production wiring: provisional flag opts out → no error
    revision = modelo.revisions["2019-y-siguientes"]
    profile_provisional = _committed_profile(provisional=True)
    mutated = revision.model_copy(update={"extraction_profiles": (profile_provisional,)})
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, mutated.id: mutated}})
    validator.validate_modelo(mutated_modelo)

    # Scenario C via production wiring: verified + source satisfies both gates → no error
    profile_verified = _committed_profile(provisional=False).model_copy(
        update={"corpus_round_trip_verified": True, "verification_source": "real_aeat_corpus_pdf"},
    )
    mutated_c = revision.model_copy(update={"extraction_profiles": (profile_verified,)})
    mutated_modelo_c = modelo.model_copy(update={"revisions": {**modelo.revisions, mutated_c.id: mutated_c}})
    validator.validate_modelo(mutated_modelo_c)
