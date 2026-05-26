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

from aeat.core.resources import bundled_path

from . import RegistryCatalogues, RegistryValidationError
from ._loader import load_registry_tree
from ._schema import ExtractionProfileDefinition, ModeloDefinition
from ._validate import RegistryValidator

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_DATA_ROOT = bundled_path()


@cache
def _committed_130() -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    return next(m for m in modelos if m.id == "130"), catalogues


def _committed_profile(
    *,
    provisional: bool = False,
    round_trip_verified: bool = False,
) -> ExtractionProfileDefinition:
    modelo, _catalogues = _committed_130()
    revision = modelo.revisions["2019-y-siguientes"]
    profile = next(p for p in revision.extraction_profiles if p.surface == "declaracion_pdf")
    return profile.model_copy(
        update={
            "provisional_pending_specimen": provisional,
            "corpus_round_trip_verified": round_trip_verified,
        }
    )


def _validator_with_corpus(corpus_root: Path, catalogues: RegistryCatalogues) -> RegistryValidator:
    return RegistryValidator(
        catalogues,
        source_root=bundled_path(),
        justificante_corpus_root=corpus_root,
    )


def _build_mutated_modelo(
    modelo: ModeloDefinition,
    profile: ExtractionProfileDefinition,
) -> ModeloDefinition:
    revision = modelo.revisions["2019-y-siguientes"]
    mutated = revision.model_copy(update={"extraction_profiles": (profile,)})
    return modelo.model_copy(update={"revisions": {**modelo.revisions, mutated.id: mutated}})


# --- (a) fixture exists + neither flag → FAIL --------------------------------


def test_fixture_exists_no_flags_fails(tmp_path: Path) -> None:
    """Corpus fixture present, both flags False: the round-trip gate must reject the profile."""
    modelo, catalogues = _committed_130()
    corpus_root = tmp_path / "justificantes"
    fixture_dir = corpus_root / "130"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "2024-1T.pdf").write_bytes(b"%PDF-1.4 stub")

    profile = _committed_profile(provisional=False, round_trip_verified=False)
    mutated_modelo = _build_mutated_modelo(modelo, profile)

    validator = _validator_with_corpus(corpus_root, catalogues)
    with pytest.raises(RegistryValidationError, match="corpus_round_trip_verified"):
        validator.validate_modelo(mutated_modelo)


# --- (b) fixture exists + corpus_round_trip_verified=true → OK ---------------


def test_fixture_exists_round_trip_verified_passes(tmp_path: Path) -> None:
    """Corpus fixture present, corpus_round_trip_verified=True: gate must pass cleanly."""
    modelo, catalogues = _committed_130()
    corpus_root = tmp_path / "justificantes"
    fixture_dir = corpus_root / "130"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "2024-1T.pdf").write_bytes(b"%PDF-1.4 stub")

    profile = _committed_profile(provisional=False, round_trip_verified=True)
    mutated_modelo = _build_mutated_modelo(modelo, profile)

    validator = _validator_with_corpus(corpus_root, catalogues)
    # No exception raised: corpus_round_trip_verified satisfies the gate
    validator.validate_modelo(mutated_modelo)


# --- (c) fixture exists + provisional_pending_specimen=true → OK -------------


def test_fixture_exists_provisional_flag_passes(tmp_path: Path) -> None:
    """Corpus fixture present, provisional_pending_specimen=True: gate must pass (opt-out wins)."""
    modelo, catalogues = _committed_130()
    corpus_root = tmp_path / "justificantes"
    fixture_dir = corpus_root / "130"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "2024-1T.pdf").write_bytes(b"%PDF-1.4 stub")

    profile = _committed_profile(provisional=True, round_trip_verified=False)
    mutated_modelo = _build_mutated_modelo(modelo, profile)

    validator = _validator_with_corpus(corpus_root, catalogues)
    # No exception raised: provisional flag satisfies the gate
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
