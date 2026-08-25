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
from ..schema import ExtractionProfileDefinition, ModeloDefinition
from ..validate import RegistryValidator
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


def _committed_profile(provisional: bool = False) -> ExtractionProfileDefinition:
    """Return the committed M130 declaracion_pdf profile, optionally overriding provisional flag."""
    modelo, _catalogues = _committed_130()
    revision = modelo.revisions["2019-y-siguientes"]
    profile = next(p for p in revision.extraction_profiles if p.surface == "declaracion_pdf")
    return profile.model_copy(
        update={
            "provisional_pending_specimen": provisional,
            "confidence": "review_required" if provisional else profile.confidence,
            "corpus_round_trip_verified": False if provisional else profile.corpus_round_trip_verified,
        },
    )


def _validator(
    catalogues: RegistryCatalogues,
    *,
    justificante_corpus_root: Path | None = None,
) -> RegistryValidator:
    return RegistryValidator(
        catalogues,
        source_root=_DATA_ROOT,
        justificante_corpus_root=justificante_corpus_root,
    )


def _assert_justificante_corpus_root(
    validator: RegistryValidator,
    *,
    missing_message: str,
) -> Path:
    corpus_root = validator.justificante_corpus_root
    assert corpus_root is not None, missing_message
    return corpus_root


@pytest.mark.parametrize(
    ("provisional", "expected"),
    [
        (False, False),
        (True, True),
    ],
    ids=("default-false", "explicit-true"),
)
def test_provisional_field_round_trips(provisional: bool, expected: bool) -> None:
    profile = _committed_profile(provisional=provisional)
    assert profile.provisional_pending_specimen is expected


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

    validator = _validator(catalogues, justificante_corpus_root=empty_corpus_root)
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
    # Place a minimal PDF-like fixture to satisfy the fixture check.
    (modelo_fixture_dir / "2024-1T.pdf").write_bytes(b"%PDF-1.4 specimen fixture")

    revision = modelo.revisions["2019-y-siguientes"]
    profile = _committed_profile(provisional=False).model_copy(
        update={
            "corpus_round_trip_verified": True,
            "verification_source": "synthetic_from_aeat_published_text",
        },
    )
    mutated = revision.model_copy(update={"extraction_profiles": (profile,)})
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, mutated.id: mutated}})

    validator = _validator(catalogues, justificante_corpus_root=corpus_root)
    # No exception raised: fixture present + corpus_round_trip_verified satisfies both gates
    validator.validate_modelo(mutated_modelo)


# --- Explicit injection: the committed synthetic fixture corpus, supplied verbatim --


def test_corpus_root_resolves_when_explicitly_supplied() -> None:
    """The committed synthetic fixture corpus root is honoured verbatim when explicitly supplied.

    RegistryValidator never derives justificante_corpus_root from source_root
    (test_justificante_corpus_derivation.py pins that one-way property); an
    authoring tool that wants the specimen gate to run supplies the committed
    synthetic src/cadrumo/tests/fixtures/justificantes tree explicitly, exactly
    as this test does.
    """
    _modelo, catalogues = _committed_130()
    validator = _validator(catalogues, justificante_corpus_root=_JUSTIFICANTE_CORPUS_ROOT)
    corpus_root = _assert_justificante_corpus_root(
        validator,
        missing_message="explicitly supplied corpus root was not honoured",
    )
    assert corpus_root.is_dir(), f"supplied corpus root {corpus_root} is not a directory"
    assert corpus_root.name == "justificantes"


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

    validator = _validator(catalogues, justificante_corpus_root=empty_corpus_root)
    _assert_justificante_corpus_root(
        validator,
        missing_message="corpus root must be set; gate would be silent",
    )
    with pytest.raises(RegistryValidationError, match="provisional_pending_specimen"):
        validator.validate_modelo(mutated_modelo)


def test_gate_silent_against_the_committed_synthetic_corpus_for_provisional_and_verified_profiles() -> None:
    """Specimen gate exercises against the committed synthetic fixture corpus.

    NOTE ON COVERAGE BOUNDARY: The specimen gate fires when no corpus fixture exists
    for a model with a declaracion_pdf profile and provisional_pending_specimen=False.
    All committed modelos with declaracion_pdf profiles have at least one committed
    synthetic fixture under tests/fixtures/justificantes/, so the specimen-gate "fires" scenario
    (no fixture + no flag) cannot be triggered against the committed synthetic corpus without
    swapping in an empty corpus_root.  This is a structural property of the fixture
    inventory, not a gap in the (removed) derivation logic.

    What exercising against the committed synthetic corpus CAN assert about the specimen gate:
      - The supplied root resolves to the committed synthetic corpus directory
        (guarding against a silent empty corpus going unnoticed).
      - The gate is silent for M130 when provisional_pending_specimen=True (Scenario B).
      - The gate is silent for M130 when corpus + round_trip_verified satisfies both
        gates (Scenario C), confirming no spurious specimen-gate firing on verified
        profiles.

    The "gate fires" scenario (Scenario A) is covered by test_gate_fires_no_fixture_no_flag
    which injects an empty corpus root to isolate that branch from fixture inventory.
    """
    modelo, catalogues = _committed_130()

    validator = _validator(catalogues, justificante_corpus_root=_JUSTIFICANTE_CORPUS_ROOT)
    corpus_root = _assert_justificante_corpus_root(
        validator,
        missing_message="explicitly supplied corpus root was not honoured; specimen gate would be silently disabled",
    )
    assert corpus_root.is_dir(), f"supplied corpus root {corpus_root} is not a directory"

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
