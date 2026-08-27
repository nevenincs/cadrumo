"""Tests for the declaracion_pdf corpus_round_trip_verified gate.

The gate enforces that a ``declaracion_pdf`` extraction profile whose corpus
fixture directory contains at least one PDF file must either set
``corpus_round_trip_verified = true`` (author asserts a committed parametrized
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
from .._validate import RegistryValidator
from ..errors import RegistryValidationError
from ..schema import ModeloDefinition, RegistryCatalogues
from ..schema_extraction import ExtractionProfileDefinition
from ._gate_support import catalogues_for_m130_gate_tests
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DATA_ROOT = bundled_path()
# The validator never derives this path (see test_justificante_corpus_derivation.py,
# which pins that one-way property); it must be supplied explicitly, exactly as an
# authoring tool would supply the committed synthetic fixture tree.
_JUSTIFICANTE_CORPUS_ROOT = _DATA_ROOT.parent / "tests" / "fixtures" / "justificantes"


@cache
def _committed_130() -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelo, catalogues = _committed_modelo("130")
    return modelo, catalogues_for_m130_gate_tests(catalogues)


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
            "confidence": "review_required" if provisional else profile.confidence,
            "corpus_round_trip_verified": round_trip_verified,
            "verification_source": verification_source,
        },
    )


def _validator_with_corpus(corpus_root: Path, catalogues: RegistryCatalogues) -> RegistryValidator:
    return RegistryValidator(
        catalogues,
        source_root=bundled_path(),
        justificante_corpus_root=corpus_root,
    )


def _validator_from_data_root(catalogues: RegistryCatalogues) -> RegistryValidator:
    """A validator wired against the committed synthetic fixture corpus, supplied explicitly.

    RegistryValidator never derives justificante_corpus_root from source_root
    (test_justificante_corpus_derivation.py pins that one-way property); this
    helper supplies the committed synthetic src/cadrumo/tests/fixtures/justificantes
    tree so the gates below exercise that committed synthetic fixture inventory rather
    than a synthetic tmp_path corpus.
    """
    return RegistryValidator(
        catalogues,
        source_root=_DATA_ROOT,
        justificante_corpus_root=_JUSTIFICANTE_CORPUS_ROOT,
    )


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


# --- (e) explicit injection: gates exercised against the committed synthetic fixture corpus --


def test_corpus_root_resolves_when_explicitly_supplied() -> None:
    """The committed synthetic fixture corpus root is honoured verbatim when explicitly supplied.

    Mirrors test_corpus_root_resolves_when_explicitly_supplied in the specimen
    gate. RegistryValidator never derives justificante_corpus_root from
    source_root; _validator_from_data_root supplies the committed synthetic fixture tree
    explicitly.
    """
    _modelo, catalogues = _committed_130()
    validator = _validator_from_data_root(catalogues)
    corpus_root = _assert_justificante_corpus_root(
        validator,
        missing_message="explicitly supplied corpus root was not honoured; the round-trip gate would be disabled",
    )
    assert corpus_root.is_dir(), f"supplied corpus root {corpus_root} is not a directory"
    assert corpus_root.name == "justificantes"


def test_round_trip_gate_fires_against_the_committed_synthetic_corpus() -> None:
    """Round-trip gate must fire against the committed synthetic fixture corpus.

    Scenario A: M130 has committed synthetic fixtures under tests/fixtures/justificantes/130/.
    A profile with corpus_round_trip_verified=False and
    provisional_pending_specimen=False must raise RegistryValidationError
    when validated with the committed synthetic corpus explicitly supplied.

    This test catches the class of bug where the supplied corpus_root is
    silently None (disabling the gate) while unit tests using a synthetic
    tmp_path corpus continue to pass.
    """
    modelo, catalogues = _committed_130()
    profile = _committed_profile(provisional=False, round_trip_verified=False)
    mutated_modelo = _build_mutated_modelo(modelo, profile)

    validator = _validator_from_data_root(catalogues)
    _assert_justificante_corpus_root(
        validator,
        missing_message="explicitly supplied corpus root was not honoured; gate would be silently disabled",
    )
    with pytest.raises(RegistryValidationError, match="corpus_round_trip_verified"):
        validator.validate_modelo(mutated_modelo)


def test_round_trip_gate_provisional_flag_silences_against_the_committed_synthetic_corpus() -> None:
    """Scenario B: provisional_pending_specimen=True must silence the round-trip gate.

    M130 has committed synthetic corpus fixtures, so the gate would fire for an unverified profile.
    Setting provisional_pending_specimen=True is the explicit opt-out; the gate must
    not raise even when corpus exists and corpus_round_trip_verified=False.

    Exercised against the committed synthetic corpus, explicitly supplied. A gap where the
    supplied corpus_root silently resolved to None would cause the gate to
    pass silently for the wrong reason; the pre-assertion guards against that
    false positive.
    """
    modelo, catalogues = _committed_130()
    profile = _committed_profile(provisional=True, round_trip_verified=False)
    mutated_modelo = _build_mutated_modelo(modelo, profile)

    validator = _validator_from_data_root(catalogues)
    _assert_justificante_corpus_root(
        validator,
        missing_message=(
            "explicitly supplied corpus root was not honoured; gate is silently disabled — "
            "the provisional-flag opt-out cannot be verified against the committed synthetic corpus"
        ),
    )
    # No exception raised: provisional flag opts out of the round-trip gate
    validator.validate_modelo(mutated_modelo)


def test_round_trip_gate_verified_profile_passes_against_the_committed_synthetic_corpus() -> None:
    """Scenario C: corpus_round_trip_verified=True + verification_source set must pass.

    M130 has committed synthetic corpus fixtures. A profile declaring corpus_round_trip_verified=True
    with a valid verification_source satisfies both the round-trip gate and the
    provenance gate.  The validator must not raise.

    Exercised against the committed synthetic corpus, explicitly supplied. The pre-assertion
    ensures that corpus directory was actually supplied so the gate was
    genuinely evaluated, not silently bypassed.
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
            "explicitly supplied corpus root was not honoured; gate is silently disabled — "
            "the verified-profile pass cannot be confirmed against the committed synthetic corpus"
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


def test_verification_source_gate_fires_against_the_committed_synthetic_corpus() -> None:
    """verification_source gate must fire against the committed synthetic fixture corpus.

    M130 has committed synthetic corpus fixtures. A profile with corpus_round_trip_verified=True and
    verification_source=None must raise RegistryValidationError when validated with
    the committed synthetic corpus explicitly supplied.

    This test covers the same class of gap as the one that could silently disable
    the specimen gate: a test using only a synthetic tmp_path corpus passes
    regardless of whether the committed synthetic fixture inventory agrees, masking gate failures.
    """
    modelo, catalogues = _committed_130()
    profile = _committed_profile(provisional=False, round_trip_verified=True, verification_source=None)
    mutated_modelo = _build_mutated_modelo(modelo, profile)

    validator = _validator_from_data_root(catalogues)
    _assert_justificante_corpus_root(
        validator,
        missing_message="explicitly supplied corpus root was not honoured; gate would be silently disabled",
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
