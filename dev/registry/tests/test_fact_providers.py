"""Provider registration and directory-ownership contract tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.schema import GovernedFact
from dev.registry.compiler.fact_providers import (
    FACT_PROVIDER_REGISTRATIONS,
    FactProviderCompiler,
    FactProviderRegistration,
    registered_fact_provider_directories,
    validate_fact_provider_registrations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _empty_compile(registry_root: Path) -> tuple[GovernedFact, ...]:
    del registry_root
    return ()


def _registration(
    provider_id: str,
    *directories: str,
    compile: FactProviderCompiler | None = None,
) -> FactProviderRegistration:
    return FactProviderRegistration(
        provider_id=provider_id,
        owned_directories=directories,
        compile=_empty_compile if compile is None else compile,
        collect_fingerprints=lambda _root: (),
        reset=lambda: None,
    )


def test_authored_provider_owns_compilation_identity_reset_and_directory(tmp_path: Path) -> None:
    registration = FACT_PROVIDER_REGISTRATIONS[0]
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()
    (facts_dir / "0001-value.toml").write_text("[fact]\n", encoding="utf-8")

    assert registration.provider_id == "authored-facts"
    assert registration.owned_directories == ("facts",)
    assert len(registration.collect_fingerprints(tmp_path)) == 1
    registration.reset()
    assert registered_fact_provider_directories()["facts"] == registration
    assert registered_fact_provider_directories()["treaties"].provider_id == "convenio-overrides"


@pytest.mark.parametrize(
    "directory",
    ("", "/facts", "../facts", "facts/../other", "facts\\iva", "facts/"),
)
def test_registration_refuses_noncanonical_directory_ownership(directory: str) -> None:
    with pytest.raises(RegistryValidationError, match="invalid relative directory"):
        validate_fact_provider_registrations((_registration("provider", directory),))


def test_registration_refuses_duplicate_provider_identity() -> None:
    with pytest.raises(RegistryValidationError, match="duplicate governed fact provider id"):
        validate_fact_provider_registrations(
            (_registration("provider", "facts-a"), _registration("provider", "facts-b")),
        )


def test_registration_refuses_empty_or_overlapping_directory_ownership() -> None:
    with pytest.raises(RegistryValidationError, match="at least one directory"):
        validate_fact_provider_registrations((_registration("provider"),))
    with pytest.raises(RegistryValidationError, match="overlaps"):
        validate_fact_provider_registrations(
            (_registration("first", "facts"), _registration("second", "facts/iva")),
        )


def test_combined_iva_lifecycle_and_modelo_inherited_identity_are_explicit() -> None:
    iva = next(item for item in FACT_PROVIDER_REGISTRATIONS if item.provider_id == "iva-rate-schedule")
    projection = next(
        item for item in FACT_PROVIDER_REGISTRATIONS if item.provider_id == "modelo-parameter-projections"
    )

    assert iva.lifecycle_components == ("iva-rates", "iva-recargo-equivalencia")
    assert projection.inherited_identity_domains == ("modelos",)
