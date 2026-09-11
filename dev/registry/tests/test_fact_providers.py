"""Provider registration and directory-ownership contract tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.schema import GovernedFact

from ..compiler.fact_loader import load_governed_facts
from ..compiler.fact_providers import (
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
    assert "treaties" not in registered_fact_provider_directories()


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


def test_authored_provider_directly_owns_normalized_iva_facts_without_adapter_registration() -> None:
    authored = next(item for item in FACT_PROVIDER_REGISTRATIONS if item.provider_id == "authored-facts")
    projection = next(
        item for item in FACT_PROVIDER_REGISTRATIONS if item.provider_id == "modelo-parameter-projections"
    )
    direct_facts = {fact.fact_id: fact for fact in load_governed_facts(bundled_path("registry", "aeat", "facts"))}

    assert authored.owned_directories == ("facts",)
    assert {"iva-rate-schedule", "iva-recargo-by-applied-rate", "irnr.convenio.override"} <= direct_facts.keys()
    assert not any(registration.provider_id == "iva-rate-schedule" for registration in FACT_PROVIDER_REGISTRATIONS)
    assert projection.inherited_identity_domains == ("modelos",)
