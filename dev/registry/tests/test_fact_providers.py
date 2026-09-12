"""Provider registration and directory-ownership contract tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryLoadError, RegistryValidationError
from cadrumo.domain.calculations.registry.facts.schema import GovernedFact

from ..compiler.fact_loader import load_governed_facts
from ..compiler import fact_providers
from ..compiler.fact_providers import (
    FACT_PROVIDER_REGISTRATIONS,
    FactProviderCompiler,
    FactProviderRegistration,
    compile_authored_fact_catalogue,
    fact_catalogue_digest,
    registered_fact_provider_directories,
    serialize_fact_catalogue,
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


def _write_scalar_fact(path: Path, fact_id: str) -> None:
    path.write_text(
        f'''[fact]
fact_id = "{fact_id}"
family = "scalar"

[[fact.variants]]
variant_id = "{fact_id}.2025"
date_axis = "filing_period"
valid_from = 2025-01-01
legal_refs = ["test-law"]
source_refs = ["test-source"]
review_status = "pending_review"
ownership = "authored"

[[fact.variants.source_citations]]
source_ref = "test-source"
required_text = ["{fact_id}"]

[fact.variants.payload]
kind = "scalar"
value = "10"
unit = "EUR"
''',
        encoding="utf-8",
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


def test_facts_only_boundary_refuses_missing_or_empty_authored_tree(tmp_path: Path) -> None:
    with pytest.raises(RegistryLoadError, match="directory is missing"):
        compile_authored_fact_catalogue(tmp_path / "missing")

    (tmp_path / "facts").mkdir()
    with pytest.raises(RegistryLoadError, match="contains no TOML declarations"):
        compile_authored_fact_catalogue(tmp_path)


def test_facts_only_boundary_refuses_invalid_authored_schema(tmp_path: Path) -> None:
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()
    (facts_dir / "0001-invalid.toml").write_text(
        '[fact]\nfact_id = "invalid.fact"\nfamily = "scalar"\n',
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="invalid governed fact"):
        compile_authored_fact_catalogue(tmp_path)


def test_facts_only_candidate_index_and_digest_are_order_independent(tmp_path: Path) -> None:
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()
    _write_scalar_fact(facts_dir / "0002-zeta.toml", "zeta.fact")
    _write_scalar_fact(facts_dir / "0001-alpha.toml", "alpha.fact")

    first = compile_authored_fact_catalogue(tmp_path)
    first_bytes = serialize_fact_catalogue(first)
    first_digest = fact_catalogue_digest(first)

    (facts_dir / "0001-alpha.toml").rename(facts_dir / "0003-alpha.toml")
    (facts_dir / "0002-zeta.toml").rename(facts_dir / "0001-zeta.toml")
    second = compile_authored_fact_catalogue(tmp_path)

    assert tuple(first.facts) == ("alpha.fact", "zeta.fact")
    assert tuple(second.facts) == tuple(first.facts)
    assert first_bytes == serialize_fact_catalogue(second)
    assert first_digest == fact_catalogue_digest(second)


def test_facts_only_boundary_does_not_call_full_registry_compiler(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()
    _write_scalar_fact(facts_dir / "0001-alpha.toml", "alpha.fact")

    def fail_if_full_compiler_is_called(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("facts-only compilation called the full registry compiler")

    monkeypatch.setattr(fact_providers, "compile_registered_fact_providers", fail_if_full_compiler_is_called)

    catalogue = compile_authored_fact_catalogue(tmp_path)

    assert tuple(catalogue.facts) == ("alpha.fact",)


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
