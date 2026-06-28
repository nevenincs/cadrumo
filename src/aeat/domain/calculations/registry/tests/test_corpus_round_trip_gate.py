"""Tests for the declaracion_pdf corpus_round_trip_verified gate.

The gate enforces that a ``declaracion_pdf`` extraction profile whose corpus
fixture directory contains at least one PDF file must either set
``corpus_round_trip_verified = true`` (author asserts a real parametrized
round-trip test exists) or ``provisional_pending_specimen = true`` (author
explicitly acknowledges unverified status).  Profiles that have corpus but
neither flag cause a hard snapshot-build failure.  Profiles without corpus
are not in scope for this gate — the existing specimen gate handles that case.
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
from ._gate_support import catalogues_for_m130_gate_tests

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_DATA_ROOT = bundled_path()


@cache
def _committed_130() -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    return next(m for m in modelos if m.id == "130"), catalogues_for_m130_gate_tests(catalogues)


def _committed_profile(
    *,
    provisional: bool = False,
    round_trip_verified: bool = False,
    verification_source: str | None = None,
) -> ExtractionProfileDefinition:
    modelo, _catalogues = _committed_130()
    revision = modelo.revisions["2019-y-siguientes"]
    profile = next(p for p in revision.extraction_profiles if p.surface == "declaracion_pdf")
    return profile.model_copy(
        update={
            "provisional_pending_specimen": provisional,
            "corpus_round_trip_verified": round_trip_verified,
            "verification_source": verification_source,
        },
    )


def _validator_with_corpus(corpus_root: Path, catalogues: RegistryCatalogues) -> RegistryValidator:
    return RegistryValidator(
        catalogues,
        source_root=bundled_path(),
        justificante_corpus_root=corpus_root,
        catalogue_corpus_strict=False,
    )


def _validator_from_data_root(catalogues: RegistryCatalogues) -> RegistryValidator:
    return RegistryValidator(catalogues, source_root=_DATA_ROOT, catalogue_corpus_strict=False)


def _build_mutated_modelo(
    modelo: ModeloDefinition,
    profile: ExtractionProfileDefinition,
) -> ModeloDefinition:
    revision = modelo.revisions["2019-y-siguientes"]
    mutated = revision.model_copy(update={"extraction_profiles": (profile,)})
    return modelo.model_copy(update={"revisions": {**modelo.revisions, mutated.id: mutated}})


def _write_corpus_pdf_fixture(corpus_root: Path) -> None:
    fixture_dir = corpus_root / "130"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "2024-1T.pdf").write_bytes(b"%PDF-1.4 corpus fixture sample")


def _assert_justificante_corpus_root(
    validator: RegistryValidator,
    *,
    missing_message: str,
) -> Path:
    corpus_root = validator.justificante_corpus_root
    assert corpus_root is not None, missing_message
    return corpus_root


# --- (a) fixture exists + neither flag → FAIL --------------------------------


def test_fixture_exists_no_flags_fails(tmp_path: Path) -> None:
    """Corpus fixture present, both flags False: the round-trip gate must reject the profile."""
    modelo, catalogues = _committed_130()
    corpus_root = tmp_path / "justificantes"
    _write_corpus_pdf_fixture(corpus_root)

    profile = _committed_profile(provisional=False, round_trip_verified=False)
    mutated_modelo = _build_mutated_modelo(modelo, profile)

    validator = _validator_with_corpus(corpus_root, catalogues)
    with pytest.raises(RegistryValidationError, match="corpus_round_trip_verified"):
        validator.validate_modelo(mutated_modelo)


# --- (b) fixture exists + corpus_round_trip_verified=true → OK ---------------


def test_fixture_exists_round_trip_verified_passes(tmp_path: Path) -> None:
    """corpus_round_trip_verified=True + verification_source set: gate must pass cleanly."""
    modelo, catalogues = _committed_130()
    corpus_root = tmp_path / "justificantes"
    _write_corpus_pdf_fixture(corpus_root)

    profile = _committed_profile(
        provisional=False,
        round_trip_verified=True,
        verification_source="synthetic_from_aeat_published_text",
    )
    mutated_modelo = _build_mutated_modelo(modelo, profile)

    validator = _validator_with_corpus(corpus_root, catalogues)
    # No exception raised: corpus_round_trip_verified + verification_source satisfies the gate
    validator.validate_modelo(mutated_modelo)


# --- (c) fixture exists + provisional_pending_specimen=true → OK -------------


def test_fixture_exists_provisional_flag_passes(tmp_path: Path) -> None:
    """Corpus fixture present, provisional_pending_specimen=True: gate must pass (opt-out wins)."""
    modelo, catalogues = _committed_130()
    corpus_root = tmp_path / "justificantes"
    _write_corpus_pdf_fixture(corpus_root)

    profile = _committed_profile(provisional=True, round_trip_verified=False)
    mutated_modelo = _build_mutated_modelo(modelo, profile)

    validator = _validator_with_corpus(corpus_root, catalogues)
    # No exception raised: provisional flag satisfies the gate
    validator.validate_modelo(mutated_modelo)


# --- (e) production path: corpus derivation from source_root -----------------


def test_corpus_root_derived_from_bundled_path() -> None:
    """RegistryValidator must derive a valid corpus root from bundled_path().

    Mirrors test_corpus_root_derived_from_bundled_path in the specimen gate.
    Exercises the production code path where justificante_corpus_root is NOT
    injected directly — the validator must derive it from source_root.
    """
    _modelo, catalogues = _committed_130()
    validator = _validator_from_data_root(catalogues)
    corpus_root = _assert_justificante_corpus_root(
        validator,
        missing_message=(
            "corpus root derivation from bundled_path() returned None; the round-trip gate is disabled in production"
        ),
    )
    assert corpus_root.is_dir(), f"derived corpus root {corpus_root} is not a directory"
    assert corpus_root.name == "justificantes"


def test_round_trip_gate_fires_via_production_path() -> None:
    """Round-trip gate must fire via the production wiring (no direct injection).

    Scenario A: M130 has real corpus fixtures under tests/fixtures/justificantes/130/.
    A profile with corpus_round_trip_verified=False and
    provisional_pending_specimen=False must raise RegistryValidationError
    when validated through the production RegistryValidator path where the
    corpus root is derived from source_root=bundled_path().

    This test catches the class of bug where corpus_root derivation silently
    returns None (disabling the gate) while unit tests using direct injection
    continue to pass.
    """
    modelo, catalogues = _committed_130()
    profile = _committed_profile(provisional=False, round_trip_verified=False)
    mutated_modelo = _build_mutated_modelo(modelo, profile)

    # Production wiring: no justificante_corpus_root injected
    validator = _validator_from_data_root(catalogues)
    _assert_justificante_corpus_root(
        validator,
        missing_message=(
            "corpus root derivation returned None; gate would be silently disabled — "
            "fix the derivation in _validate.py before this test can exercise the gate"
        ),
    )
    with pytest.raises(RegistryValidationError, match="corpus_round_trip_verified"):
        validator.validate_modelo(mutated_modelo)


def test_round_trip_gate_provisional_flag_silences_via_production_path() -> None:
    """Scenario B: provisional_pending_specimen=True must silence the round-trip gate.

    M130 has real corpus fixtures, so the gate would fire for an unverified profile.
    Setting provisional_pending_specimen=True is the explicit opt-out; the gate must
    not raise even when corpus exists and corpus_round_trip_verified=False.

    Pure-production wiring: no justificante_corpus_root injected.  A derivation
    bug returning None would cause the gate to pass silently for the wrong reason;
    the pre-assertion guards against that false positive.
    """
    modelo, catalogues = _committed_130()
    profile = _committed_profile(provisional=True, round_trip_verified=False)
    mutated_modelo = _build_mutated_modelo(modelo, profile)

    validator = _validator_from_data_root(catalogues)
    _assert_justificante_corpus_root(
        validator,
        missing_message=(
            "corpus root derivation returned None; gate is silently disabled — "
            "the provisional-flag opt-out cannot be verified against the derived path"
        ),
    )
    # No exception raised: provisional flag opts out of the round-trip gate
    validator.validate_modelo(mutated_modelo)


def test_round_trip_gate_verified_profile_passes_via_production_path() -> None:
    """Scenario C: corpus_round_trip_verified=True + verification_source set must pass.

    M130 has real corpus fixtures.  A profile declaring corpus_round_trip_verified=True
    with a valid verification_source satisfies both the round-trip gate and the
    provenance gate.  The validator must not raise.

    Pure-production wiring: no justificante_corpus_root injected.  The pre-assertion
    ensures the derivation path resolved a real corpus directory so the gate was
    actually evaluated, not silently bypassed.
    """
    modelo, catalogues = _committed_130()
    profile = _committed_profile(
        provisional=False,
        round_trip_verified=True,
        verification_source="real_aeat_corpus_pdf",
    )
    mutated_modelo = _build_mutated_modelo(modelo, profile)

    validator = _validator_from_data_root(catalogues)
    _assert_justificante_corpus_root(
        validator,
        missing_message=(
            "corpus root derivation returned None; gate is silently disabled — "
            "the verified-profile pass cannot be confirmed against the derived path"
        ),
    )
    # No exception raised: verified + verification_source satisfies both gates
    validator.validate_modelo(mutated_modelo)


# --- (d) no fixture → this gate is dormant; specimen gate handles it ---------


def test_no_fixture_round_trip_gate_is_dormant(tmp_path: Path) -> None:
    """No corpus fixture: round-trip gate must NOT fire; specimen gate fires instead.

    When no fixture exists the specimen gate raises RegistryValidationError with the
    ``provisional_pending_specimen`` message.  The round-trip gate message
    (``corpus_round_trip_verified``) must NOT appear — confirming the two gates do
    not double-report the same profile when there is no fixture.
    """
    modelo, catalogues = _committed_130()
    empty_corpus_root = tmp_path / "justificantes"
    empty_corpus_root.mkdir()

    profile = _committed_profile(provisional=False, round_trip_verified=False)
    mutated_modelo = _build_mutated_modelo(modelo, profile)

    validator = _validator_with_corpus(empty_corpus_root, catalogues)
    with pytest.raises(RegistryValidationError) as exc_info:
        validator.validate_modelo(mutated_modelo)

    error_text = str(exc_info.value)
    # Specimen gate fires
    assert "provisional_pending_specimen" in error_text
    # Round-trip gate does NOT fire (no fixture → not its domain)
    assert "corpus_round_trip_verified" not in error_text


# --- verification_source gate rules ------------------------------------------


def test_corpus_round_trip_verified_without_verification_source_fails(tmp_path: Path) -> None:
    """corpus_round_trip_verified=True but verification_source=None must fail the gate."""
    modelo, catalogues = _committed_130()
    corpus_root = tmp_path / "justificantes"
    _write_corpus_pdf_fixture(corpus_root)

    profile = _committed_profile(provisional=False, round_trip_verified=True, verification_source=None)
    mutated_modelo = _build_mutated_modelo(modelo, profile)

    validator = _validator_with_corpus(corpus_root, catalogues)
    with pytest.raises(RegistryValidationError, match="verification_source"):
        validator.validate_modelo(mutated_modelo)


@pytest.mark.parametrize(
    "verification_source",
    [
        "real_aeat_corpus_pdf",
        "synthetic_from_aeat_published_text",
        "historical_suppression",
        "not_applicable",
    ],
)
def test_corpus_round_trip_verified_with_each_verification_source_passes(
    tmp_path: Path,
    verification_source: str,
) -> None:
    """corpus_round_trip_verified=True with any valid verification_source enum value must pass."""
    modelo, catalogues = _committed_130()
    corpus_root = tmp_path / "justificantes"
    _write_corpus_pdf_fixture(corpus_root)

    profile = _committed_profile(
        provisional=False,
        round_trip_verified=True,
        verification_source=verification_source,
    )
    mutated_modelo = _build_mutated_modelo(modelo, profile)

    validator = _validator_with_corpus(corpus_root, catalogues)
    # No exception: any non-None verification_source satisfies the provenance gate
    validator.validate_modelo(mutated_modelo)


def test_verification_source_gate_fires_via_production_path() -> None:
    """verification_source gate must fire via the production wiring (no direct injection).

    M130 has real corpus fixtures.  A profile with corpus_round_trip_verified=True and
    verification_source=None must raise RegistryValidationError when validated through
    the production RegistryValidator path where corpus root is derived from
    source_root=bundled_path().

    This test covers the production-wiring gap analogous to the one that silently
    disabled the specimen gate: tests using direct justificante_corpus_root injection
    pass regardless of whether the derivation path works, masking gate failures.
    """
    modelo, catalogues = _committed_130()
    profile = _committed_profile(provisional=False, round_trip_verified=True, verification_source=None)
    mutated_modelo = _build_mutated_modelo(modelo, profile)

    # Production wiring: no justificante_corpus_root injected
    validator = _validator_from_data_root(catalogues)
    _assert_justificante_corpus_root(
        validator,
        missing_message="corpus root derivation returned None; gate would be silently disabled",
    )
    with pytest.raises(RegistryValidationError, match="verification_source"):
        validator.validate_modelo(mutated_modelo)


def test_corpus_round_trip_not_verified_with_no_verification_source_is_dormant(
    tmp_path: Path,
) -> None:
    """verification_source=None when corpus_round_trip_verified=False must not trigger the provenance gate.

    The provenance gate only fires when corpus_round_trip_verified=True; the
    round-trip gate fires instead (fixture present, neither flag set).
    """
    modelo, catalogues = _committed_130()
    corpus_root = tmp_path / "justificantes"
    _write_corpus_pdf_fixture(corpus_root)

    profile = _committed_profile(provisional=False, round_trip_verified=False, verification_source=None)
    mutated_modelo = _build_mutated_modelo(modelo, profile)

    validator = _validator_with_corpus(corpus_root, catalogues)
    with pytest.raises(RegistryValidationError) as exc_info:
        validator.validate_modelo(mutated_modelo)
    # Round-trip gate fires (not the provenance gate)
    assert "corpus_round_trip_verified" in str(exc_info.value)
    assert "verification_source" not in str(exc_info.value)
