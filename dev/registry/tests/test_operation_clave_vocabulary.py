"""The clave letters a binding selects and a producer yields are the ones the registry declares."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.aggregation.counterpart import counterpart_operation_catalogue_entries
from cadrumo.core.aggregation import BindingSourceKind, IntracomOperationType
from cadrumo.core.errors.hierarchy import InternalInvariantError
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.payloads import MappingFactPayload
from cadrumo.domain.calculations.registry.governed_fact_scope import CandidateFactAuthority, validating_governed_facts
from cadrumo.domain.calculations.registry.invoice_bindings import (
    CollectibleInvoiceProvider,
    InvoiceObservation,
    M347ThirdPartyOperationProvider,
    M349IntracommunityOperationProvider,
    PayableInvoiceProvider,
    resolve_invoice_binding_row_values,
    resolve_invoice_binding_values,
)
from cadrumo.domain.calculations.registry.tests.fact_scope import outside_governed_fact_validation

from ..compiler.loader import load_registry_tree
from ..compiler.validator import RegistryValidator

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_VOCABULARY_KEYS = {
    "347": "modelo.347.operation_claves",
    "349": "modelo.349.operation_claves",
}
_CLAVE_PROVIDERS = (
    CollectibleInvoiceProvider,
    M347ThirdPartyOperationProvider,
    M349IntracommunityOperationProvider,
    PayableInvoiceProvider,
)


def _vocabulary(operation: PinnedAuthorityOperation, modelo: str, effective_date: date) -> frozenset[str]:
    entries = counterpart_operation_catalogue_entries(effective_date, operation=operation)
    return frozenset(entries[_VOCABULARY_KEYS[modelo]].split(","))


def _floor_date(operation: PinnedAuthorityOperation) -> date:
    return date(operation.supported_filing_years().floor, 1, 1)


def test_the_m349_enum_spells_the_declared_vocabulary() -> None:
    with bundled_indexed_authority().operation() as operation:
        declared = _vocabulary(operation, "349", _floor_date(operation))
    assert frozenset(member.value for member in IntracomOperationType) == declared


@pytest.mark.parametrize("modelo", ["347", "349"])
def test_every_published_binding_selects_declared_claves(modelo: str) -> None:
    with bundled_indexed_authority().operation() as operation:
        floor = _floor_date(operation)
        selected: list[str] = []
        for metadata in operation.modelo_directory(modelo).revisions:
            if metadata.valid_to is not None and metadata.valid_to < floor:
                continue
            for binding in operation.revision(modelo, metadata.id).bindings:
                if isinstance(binding.provider, _CLAVE_PROVIDERS):
                    selected += binding.provider.claves
        declared = _vocabulary(operation, modelo, floor)
    assert selected or modelo == "347", "Modelo 347 selects by row field and names no clave in its bindings"
    assert set(selected) <= declared, sorted(set(selected) - declared)


def test_the_two_vocabularies_are_declared_apart() -> None:
    with bundled_indexed_authority().operation() as operation:
        floor = _floor_date(operation)
        assert _vocabulary(operation, "347", floor) != _vocabulary(operation, "349", floor)


@pytest.fixture(scope="module")
def candidate_registry():
    return load_registry_tree(bundled_path("registry", "aeat"))


def _with_selector_clave(revision, clave: str):
    index = next(i for i, binding in enumerate(revision.bindings) if isinstance(binding.provider, _CLAVE_PROVIDERS))
    binding = revision.bindings[index]
    provider = type(binding.provider).model_validate({**binding.provider.model_dump(), "claves": (clave,)})
    altered = binding.model_copy(update={"provider": provider})
    return revision.model_copy(
        update={"bindings": (*revision.bindings[:index], altered, *revision.bindings[index + 1 :])}
    )


@pytest.mark.parametrize(("modelo_id", "valid", "wrong_model"), [("347", "A", "I"), ("349", "E", "B")])
def test_candidate_revision_rejects_letters_outside_its_own_governed_catalogue(
    candidate_registry, modelo_id: str, valid: str, wrong_model: str
) -> None:
    modelos, catalogues = candidate_registry
    modelo = next(item for item in modelos if item.id == modelo_id)
    revision = next(iter(modelo.revisions.values()))
    validator = RegistryValidator(catalogues)
    authority = CandidateFactAuthority(catalogues.facts, catalogues.require_supported_filing_years())
    with validating_governed_facts(authority):
        assert not validator._validate_revision(modelo, _with_selector_clave(revision, valid))
        for invalid in (wrong_model, "Z", "Á"):
            failures = validator._validate_revision(modelo, _with_selector_clave(revision, invalid))
            assert any("unknown operation claves" in failure and invalid in failure for failure in failures)


def test_candidate_revision_uses_candidate_fact_not_the_installed_generation(candidate_registry) -> None:
    modelos, catalogues = candidate_registry
    modelo = next(item for item in modelos if item.id == "349")
    revision = next(iter(modelo.revisions.values()))
    fact_id = "m347-m349-counterpart-operation-catalogue"
    fact = catalogues.facts.facts[fact_id]
    variant = fact.variants[0]
    assert isinstance(variant.payload, MappingFactPayload)
    entries = tuple(
        entry.model_copy(update={"value": entry.value + ",Z"}) if entry.key == "modelo.349.operation_claves" else entry
        for entry in variant.payload.entries
    )
    changed = variant.model_copy(update={"payload": variant.payload.model_copy(update={"entries": entries})})
    facts = catalogues.facts.model_copy(
        update={"facts": {**catalogues.facts.facts, fact_id: fact.model_copy(update={"variants": (changed,)})}}
    )
    candidate = catalogues.model_copy(update={"facts": facts})
    validator = RegistryValidator(candidate)
    altered = _with_selector_clave(revision, "Z")
    assert not validator._invoice_clave_failures(modelo, altered, prefix="test")
    assert RegistryValidator(catalogues)._invoice_clave_failures(modelo, altered, prefix="test")
    observation = InvoiceObservation(
        invoice_id="candidate-only",
        source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
        party_tax_id="DE123456789",
        country_code="DE",
        transaction_date=date(2024, 1, 1),
        base_amount=Decimal("10"),
        intracommunity_clave="Z",
    )
    with validating_governed_facts(CandidateFactAuthority(facts, candidate.require_supported_filing_years())):
        values = resolve_invoice_binding_values(altered, (observation,), effective_date=date(2024, 12, 31))
    assert values[altered.bindings[0].id] == Decimal(1)


def test_candidate_revision_rechecks_the_fact_when_its_window_changes(candidate_registry) -> None:
    modelos, catalogues = candidate_registry
    modelo = next(item for item in modelos if item.id == "349")
    revision = next(iter(modelo.revisions.values()))
    fact_id = "m347-m349-counterpart-operation-catalogue"
    fact = catalogues.facts.facts[fact_id]
    assert len(fact.variants) == 1
    variant = fact.variants[0]
    assert isinstance(variant.payload, MappingFactPayload)
    entries = tuple(
        entry.model_copy(update={"value": ",".join(clave for clave in entry.value.split(",") if clave != "E")})
        if entry.key == "modelo.349.operation_claves"
        else entry
        for entry in variant.payload.entries
    )
    earlier = variant.model_copy(update={"valid_to": date(2025, 12, 31)})
    later = variant.model_copy(
        update={
            "variant_id": "candidate-operation-claves-2026",
            "valid_from": date(2026, 1, 1),
            "payload": variant.payload.model_copy(update={"entries": entries}),
        }
    )
    facts = catalogues.facts.model_copy(
        update={"facts": {**catalogues.facts.facts, fact_id: fact.model_copy(update={"variants": (earlier, later)})}}
    )
    candidate = catalogues.model_copy(update={"facts": facts})
    failures = RegistryValidator(candidate)._invoice_clave_failures(
        modelo, _with_selector_clave(revision, "E"), prefix="test"
    )
    assert any("2026-01-01" in failure and "'E'" in failure for failure in failures)


def test_candidate_revision_refuses_a_missing_catalogue(candidate_registry) -> None:
    modelos, catalogues = candidate_registry
    modelo = next(item for item in modelos if item.id == "349")
    revision = next(iter(modelo.revisions.values()))
    fact_id = "m347-m349-counterpart-operation-catalogue"
    facts = catalogues.facts.model_copy(
        update={"facts": {key: value for key, value in catalogues.facts.facts.items() if key != fact_id}}
    )
    candidate = catalogues.model_copy(update={"facts": facts})
    failures = RegistryValidator(candidate)._invoice_clave_failures(modelo, revision, prefix="test")
    assert any("invoice operation clave catalogue" in failure for failure in failures)


@pytest.mark.parametrize(
    ("modelo_id", "field", "wrong"), [("347", "operation_clave", "I"), ("349", "intracommunity_clave", "B")]
)
def test_calculation_input_refuses_cross_model_or_unknown_clave_at_filing_date(
    candidate_registry, modelo_id: str, field: str, wrong: str
) -> None:
    modelos, catalogues = candidate_registry
    modelo = next(item for item in modelos if item.id == modelo_id)
    revision = next(iter(modelo.revisions.values()))
    authority = CandidateFactAuthority(catalogues.facts, catalogues.require_supported_filing_years())
    observation = InvoiceObservation(
        invoice_id="candidate-test",
        source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
        party_tax_id="DE123456789",
        country_code="DE",
        transaction_date=date(2024, 1, 1),
        base_amount=Decimal("10"),
        **{field: wrong},
    )
    with validating_governed_facts(authority):
        with pytest.raises(RegistryValidationError, match="undeclared"):
            resolve_invoice_binding_values(revision, (observation,), effective_date=date(2024, 12, 31))
        with pytest.raises(RegistryValidationError, match="undeclared"):
            resolve_invoice_binding_row_values(revision, (observation,), effective_date=date(2024, 12, 31))
        with pytest.raises(RegistryValidationError, match="filing-period date"):
            resolve_invoice_binding_values(revision, (observation,))
    with outside_governed_fact_validation(), pytest.raises(InternalInvariantError, match="explicit"):
        resolve_invoice_binding_values(revision, (observation,), effective_date=date(2024, 12, 31))
    if modelo_id == "349":
        unrelated = observation.model_copy(update={"source_kind": BindingSourceKind.PURCHASE_INVOICE_EVIDENCE})
        with outside_governed_fact_validation():
            assert all(value == 0 for value in resolve_invoice_binding_values(revision, (unrelated,)).values())


def test_invoice_clave_shape_refuses_non_ascii_letters() -> None:
    with pytest.raises(RegistryValidationError):
        InvoiceObservation(
            invoice_id="bad-shape",
            source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
            party_tax_id="DE123456789",
            country_code="DE",
            transaction_date=date(2024, 1, 1),
            base_amount=Decimal("10"),
            intracommunity_clave="Á",
        )


@pytest.mark.parametrize(
    ("modelo_id", "provider_type", "field", "valid", "invalid"),
    [
        ("347", M347ThirdPartyOperationProvider, "operation_clave", "A", "I"),
        ("349", M349IntracommunityOperationProvider, "intracommunity_clave", "E", "B"),
    ],
)
def test_generic_invoice_provider_cannot_emit_an_undeclared_operation_clave(
    candidate_registry, modelo_id, provider_type, field, valid, invalid
) -> None:
    modelos, catalogues = candidate_registry
    modelo = next(item for item in modelos if item.id == modelo_id)
    revision = next(iter(modelo.revisions.values()))
    binding = next(
        item
        for item in revision.bindings
        if isinstance(item.provider, provider_type) and item.provider.row_field == "clave"
    )
    provider = CollectibleInvoiceProvider.model_validate(
        {**binding.provider.model_dump(), "kind": BindingSourceKind.COLLECTIBLE_INVOICE, "claves": ()}
    )
    revision = revision.model_copy(update={"bindings": (binding.model_copy(update={"provider": provider}),)})
    observation = InvoiceObservation(
        invoice_id="generic-source",
        source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
        party_tax_id="DE123456789",
        country_code="DE",
        transaction_date=date(2024, 1, 1),
        base_amount=Decimal("10"),
        invoice_total_amount=Decimal("10000"),
        **{field: invalid},
    )
    authority = CandidateFactAuthority(catalogues.facts, catalogues.require_supported_filing_years())
    with validating_governed_facts(authority):
        with pytest.raises(RegistryValidationError, match="undeclared"):
            resolve_invoice_binding_row_values(revision, (observation,), effective_date=date(2024, 12, 31))
        valid_observation = observation.model_copy(update={field: valid})
        rows = resolve_invoice_binding_row_values(revision, (valid_observation,), effective_date=date(2024, 12, 31))
        assert valid in rows.values()


def test_generic_scalar_clave_filter_does_not_silently_drop_an_invalid_input(candidate_registry) -> None:
    modelos, catalogues = candidate_registry
    modelo = next(item for item in modelos if item.id == "349")
    revision = next(iter(modelo.revisions.values()))
    binding = next(
        item
        for item in revision.bindings
        if isinstance(item.provider, M349IntracommunityOperationProvider) and item.provider.fact == "operator_count"
    )
    provider = CollectibleInvoiceProvider.model_validate(
        {**binding.provider.model_dump(), "kind": BindingSourceKind.COLLECTIBLE_INVOICE}
    )
    revision = revision.model_copy(update={"bindings": (binding.model_copy(update={"provider": provider}),)})
    observation = InvoiceObservation(
        invoice_id="generic-scalar",
        source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
        party_tax_id="DE123456789",
        country_code="DE",
        transaction_date=date(2024, 1, 1),
        base_amount=Decimal("10"),
        intracommunity_clave="B",
    )
    authority = CandidateFactAuthority(catalogues.facts, catalogues.require_supported_filing_years())
    with validating_governed_facts(authority):
        with pytest.raises(RegistryValidationError, match="undeclared"):
            resolve_invoice_binding_values(revision, (observation,), effective_date=date(2024, 12, 31))
        valid = observation.model_copy(update={"intracommunity_clave": "E"})
        assert resolve_invoice_binding_values(revision, (valid,), effective_date=date(2024, 12, 31))[binding.id] == 1


def test_specialized_provider_checks_each_clave_channel_it_consumes(candidate_registry) -> None:
    modelos, catalogues = candidate_registry
    modelo = next(item for item in modelos if item.id == "347")
    revision = next(iter(modelo.revisions.values()))
    binding = next(item for item in revision.bindings if isinstance(item.provider, M347ThirdPartyOperationProvider))
    provider = binding.provider.model_copy(update={"grouping": "operator_clave", "claves": ("E",)})
    revision = revision.model_copy(update={"bindings": (binding.model_copy(update={"provider": provider}),)})
    observation = InvoiceObservation(
        invoice_id="both-channels",
        source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
        party_tax_id="DE123456789",
        country_code="DE",
        transaction_date=date(2024, 1, 1),
        base_amount=Decimal("10"),
        operation_clave="A",
        intracommunity_clave="B",
    )
    authority = CandidateFactAuthority(catalogues.facts, catalogues.require_supported_filing_years())
    with validating_governed_facts(authority), pytest.raises(RegistryValidationError, match="undeclared 349"):
        resolve_invoice_binding_values(revision, (observation,), effective_date=date(2024, 12, 31))
