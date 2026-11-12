"""The ``renta_inmueble`` resolver places each occurrence on its own row of the revision's columns.

Runs through the published registry revision of every supported year, the real
profile record and the real concept vocabulary; only the ledger store is an
in-memory stand-in for the encrypted one.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.gasto_capital_inmobiliario import resolve_gasto_capital_inmobiliario_catalogue
from ....domain.calculations.registry.governed_fact_scope import governed_facts_in_scope
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.renta_inmueble_bindings import renta_inmueble_columns
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.tests.authored_editions import (
    newest_authored_edition,
    supported_exercises_with_projection,
)
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...modelo.calculation_notes import GATE_REFUSED_REASONS
from ...modelo.work_profile import ModeloWorkProfile
from ..renta_inmueble_resolver import RentaInmuebleSourceResolver
from ..renta_inmueble_source import GASTO_COLUMN_PREFIX, RentaInmuebleRowField
from ..source_mesh import CalculationSourceContext, CalculationSourceResolution
from .ledger_source_mesh_support import BUCKET_ID, InMemoryTransactionCatalogueRepository, m100_revision
from .renta_inmueble_support import TENANT_NIF, expense, inmueble, lease, monthly_rent, profile_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_RENT = Decimal("950.00")


def _profile(facts: dict[str, str]) -> ModeloWorkProfile:
    operation = governed_facts_in_scope()
    assert isinstance(operation, PinnedAuthorityOperation)
    return ModeloWorkProfile(
        record=create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="X0001500M"),
                *(UserProfileFact(path=path, value=value) for path, value in facts.items()),
            ),
            context=operation.profile_create_context(),
        ),
        profile_decode_context=operation.profile_decode_context(),
    )


def _resolve(year: int, facts: dict[str, str], rows: tuple[Transaction, ...]) -> CalculationSourceResolution:
    repository = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    repository.save(TransactionCatalogue.from_transactions(rows))
    return RentaInmuebleSourceResolver(transaction_repository=repository).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="100",
            filing_year=year,
            period=Period.from_year_and_code(year, "0A"),
            revision=m100_revision(year),
            profile=_profile(facts),
        )
    )


def _column(revision: ModeloRevision, row_field: str) -> BindingId:
    return next(binding.id for binding, provider in renta_inmueble_columns(revision) if provider.row_field == row_field)


def _let_all_year(year: int) -> tuple[dict[str, str], tuple[Transaction, ...]]:
    facts = profile_facts((inmueble(ejercicio=year),), (lease(start=date(year - 1, 9, 1)),))
    rows = (
        *monthly_rent(year, amount=_RENT),
        expense("comunidad", concept="comunidad", amount=Decimal("540.00"), booked=date(year, 3, 10)),
    )
    return facts, rows


def test_every_supported_year_places_the_property_on_row_one_of_its_columns() -> None:
    for year in supported_exercises_with_projection("100"):
        revision = m100_revision(year)
        resolution = _resolve(year, *_let_all_year(year))
        values = resolution.row_binding_values

        assert values[(_column(revision, RentaInmuebleRowField.INGRESOS_INTEGROS.value), 1)] == _RENT * 12, year
        assert values[(_column(revision, "gasto_comunidad"), 1)] == Decimal("540.00"), year
        assert values[(_column(revision, RentaInmuebleRowField.INQUILINO_1_NIF.value), 1)] == TENANT_NIF, year
        assert values[(_column(revision, RentaInmuebleRowField.DIAS_ARRENDADO.value), 1)] == (
            (date(year, 12, 31) - date(year, 1, 1)).days + 1
        ), year
        assert (_column(revision, "gasto_suministros"), 1) not in values, year
        assert {key[1] for key in values} == {1}, year
        identities = {identity.source_row_identity for identity in resolution.row_source_identities.values()}
        assert identities == {"inmueble:0"}, year


def test_every_declared_column_is_one_the_source_reads_and_each_expense_fills_its_concept_box() -> None:
    for year in supported_exercises_with_projection("100"):
        declared = renta_inmueble_columns(m100_revision(year))
        vocabulary = resolve_gasto_capital_inmobiliario_catalogue(effective_date=date(year, 12, 31))
        deductible = {
            str(concept.token): concept.casilla_id for concept in vocabulary.concepts if not concept.capitalised
        }
        expenses = {
            provider.row_field.removeprefix(GASTO_COLUMN_PREFIX): provider.target_casilla_id
            for _binding, provider in declared
            if provider.row_field.startswith(GASTO_COLUMN_PREFIX)
        }
        fields = {provider.row_field for _binding, provider in declared} - {
            f"{GASTO_COLUMN_PREFIX}{concept}" for concept in expenses
        }

        assert expenses == deductible, year
        assert fields == {field.value for field in RentaInmuebleRowField}, year


def test_a_complete_occurrence_still_blocks_filing_until_its_net_chain_is_computed() -> None:
    year = newest_authored_edition("100")
    resolution = _resolve(year, *_let_all_year(year))
    by_reason = {diagnostic.reason for diagnostic in resolution.diagnostics}

    assert "source_domain_not_ready" in GATE_REFUSED_REASONS
    assert by_reason == {"source_domain_not_ready", "deferred_binding_source"}
    assert all(diagnostic.source_ref == "inmueble:0" for diagnostic in resolution.diagnostics)


def test_a_refusal_withholds_every_row_and_names_its_door() -> None:
    year = newest_authored_edition("100")
    facts, _rows = _let_all_year(year)
    resolution = _resolve(year, facts, ())

    assert not resolution.row_binding_values
    assert set(resolution.unresolved_binding_ids) == {
        binding.id for binding, _provider in renta_inmueble_columns(m100_revision(year))
    }
    refusals = [diagnostic for diagnostic in resolution.diagnostics if diagnostic.source_ref == "arrendamiento:0"]
    assert [diagnostic.remedy for diagnostic in refusals] == [
        "Settle it with app ledger classify, then calculate again."
    ]


def test_a_profile_with_no_property_resolves_no_row_and_no_finding() -> None:
    year = newest_authored_edition("100")
    resolution = _resolve(year, {}, ())

    assert not resolution.row_binding_values
    assert not resolution.unresolved_binding_ids
    assert not resolution.diagnostics
