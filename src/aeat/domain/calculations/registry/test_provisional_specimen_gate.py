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

from aeat.core.resources import bundled_path

from . import RegistryCatalogues, RegistryValidationError
from ._loader import load_registry_tree
from ._schema import ExtractionProfileDefinition, ModeloDefinition
from ._validate import RegistryValidator

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = bundled_path("registry", "aeat")


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


def test_fixture_present_no_flag_validates(tmp_path: Path) -> None:
    """Profile with a corpus fixture PDF and default provisional_pending_specimen=False must pass."""
    modelo, catalogues = _committed_130()
    corpus_root = tmp_path / "justificantes"
    modelo_fixture_dir = corpus_root / "130"
    modelo_fixture_dir.mkdir(parents=True)
    # Place a stub PDF file to satisfy the fixture check
    (modelo_fixture_dir / "2024-1T.pdf").write_bytes(b"%PDF-1.4 stub")

    revision = modelo.revisions["2019-y-siguientes"]
    profile = _committed_profile(provisional=False)
    mutated = revision.model_copy(update={"extraction_profiles": (profile,)})
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, mutated.id: mutated}})

    validator = RegistryValidator(
        catalogues,
        source_root=bundled_path(),
        justificante_corpus_root=corpus_root,
    )
    # No exception raised: fixture present satisfies the gate
    validator.validate_modelo(mutated_modelo)
