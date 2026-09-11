"""Authority attachment tests for the governed-fact catalogue."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactCatalogue

from ..compiler import fact_providers
from ..compiler.fact_providers import compile_registered_fact_providers

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _write_scalar_fact(path: Path) -> None:
    path.write_text(
        """[fact]
fact_id = "test.threshold"
family = "scalar"

[[fact.variants]]
variant_id = "test.threshold.2025"
date_axis = "filing_period"
valid_from = 2025-01-01
legal_refs = ["test-law"]
source_refs = ["test-source"]
review_status = "pending_review"
ownership = "authored"

[[fact.variants.source_citations]]
source_ref = "test-source"
required_text = ["threshold"]

[fact.variants.payload]
kind = "scalar"
value = "10"
unit = "EUR"
""",
        encoding="utf-8",
    )


def _limit_to_authored_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate the one provider whose scratch declaration this test authors."""
    authored = next(item for item in fact_providers.FACT_PROVIDER_REGISTRATIONS if item.provider_id == "authored-facts")
    monkeypatch.setattr(fact_providers, "FACT_PROVIDER_REGISTRATIONS", (authored,))


def test_registered_providers_compile_an_identity_keyed_catalogue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()
    _write_scalar_fact(facts_dir / "0001-test-threshold.toml")
    _limit_to_authored_provider(monkeypatch)

    catalogue = compile_registered_fact_providers(tmp_path)

    assert tuple(catalogue.facts) == ("test.threshold",)
    assert catalogue.facts["test.threshold"].fact_id == "test.threshold"


def test_catalogue_refuses_a_key_that_differs_from_semantic_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()
    _write_scalar_fact(facts_dir / "0001-test-threshold.toml")
    _limit_to_authored_provider(monkeypatch)
    fact = compile_registered_fact_providers(tmp_path).facts["test.threshold"]

    with pytest.raises(ValidationError, match="does not match fact_id"):
        GovernedFactCatalogue(facts={"other.threshold": fact})


def test_validated_authority_exposes_the_attached_fact_catalogue(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    assert isinstance(registry_authority.catalogues.facts, GovernedFactCatalogue)
