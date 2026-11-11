"""A declaration's form says whether it asks for the income imputation election, from its revision's own bindings.

Driven over real encrypted storage and the pinned authority, then read back through
the form loading service. The flag follows the registry: a revision whose bindings
include a ledger resolver that places activity income or expense by the dated
criterion asks for the election, and one that declares none does not, whatever its
modelo number is.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.entrypoints.tests.modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work

from ...adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ...application.aggregation.modelo_bindings import LedgerRentaIncomeAggregationSourceResolver
from ...application.aggregation.modelo_bindings_renta_expenses import (
    LedgerRentaGastosEstimacionDirectaAggregationSourceResolver,
    LedgerRentaGastosPagoFraccionadoAggregationSourceResolver,
)
from ...application.aggregation.renta_imputation import (
    IMPUTATION_CRITERION_SOURCES,
    revision_reads_imputation_criterion,
)
from ...application.modelo.work_form_service import load_modelo_work_form
from ...core.external_constants import OutputLanguage
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...domain.user_profile.values import UserProfileFact

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: The taxpayer a modelo applies to, where the seeded estimación-directa activity is not one:
#: Modelo 131 is the pago fraccionado of an activity in estimación objetiva (módulos), and
#: Modelo 111 is filed only by a payer of income subject to retención. A modelo that does not
#: apply to the profile is refused before any form exists, so each is seeded for its own filer.
_ESTIMATION_REGIME_BY_MODELO = {"131": "objetiva"}
_EXTRA_FACTS_BY_MODELO = {
    "111": (UserProfileFact(path="withholding.pays_professionals_with_retencion", value=True),),
}


def _asks(work: SeededOperatorWork) -> bool:
    unit = work.work_unit
    return load_modelo_work_form(
        unit.bucket_id,
        unit.modelo,
        unit.filing_year,
        unit.period,
        operation=work.operation,
        work_unit_repository=work.ports.work_unit_repository,
        calculation_repository=work.ports.calculation_repository,
        verification_repository=VerificationReportCatalogueRepository(bucket_id=unit.bucket_id),
        admission=None,
        language=OutputLanguage.EN,
    ).form.asks_imputation_election


@pytest.mark.parametrize(
    ("modelo", "filing_year", "period_code", "asks"),
    [
        ("100", 2025, "0A", True),
        ("100", 2024, "0A", True),
        ("130", 2025, "1T", True),
        ("131", 2025, "1T", True),
        ("303", 2025, "1T", False),
        ("111", 2025, "1T", False),
    ],
)
def test_the_form_asks_for_the_election_exactly_where_its_revision_reads_the_criterion(
    tmp_path: Path, modelo: str, filing_year: int, period_code: str, asks: bool
) -> None:
    with seeded_operator_work(
        tmp_path,
        modelo=modelo,
        filing_year=filing_year,
        period_code=period_code,
        extra_facts=_EXTRA_FACTS_BY_MODELO.get(modelo, ()),
        estimation_regime=_ESTIMATION_REGIME_BY_MODELO.get(modelo, "directa_normal"),
    ) as work:
        assert _asks(work) is asks


def test_the_flag_follows_the_revisions_own_bindings_and_not_the_modelo_number() -> None:
    with bundled_indexed_authority().operation() as operation:
        reading = operation.revision_for_context("100", filing_year=filing_year_envelope().horizon, period="0A")
        silent = operation.revision_for_context("303", filing_year=filing_year_envelope().horizon, period="1T")
        assert revision_reads_imputation_criterion(reading) is True
        assert revision_reads_imputation_criterion(silent) is False
        without_ledger = reading.model_copy(
            update={
                "bindings": tuple(
                    binding for binding in reading.bindings if binding.source not in IMPUTATION_CRITERION_SOURCES
                )
            }
        )
        assert revision_reads_imputation_criterion(without_ledger) is False


def test_the_declared_sources_are_owned_by_the_resolvers_that_read_the_criterion() -> None:
    resolvers = (
        LedgerRentaIncomeAggregationSourceResolver,
        LedgerRentaGastosEstimacionDirectaAggregationSourceResolver,
        LedgerRentaGastosPagoFraccionadoAggregationSourceResolver,
    )
    for resolver in resolvers:
        assert IMPUTATION_CRITERION_SOURCES & set(resolver.owned_sources)
    assert {kind for resolver in resolvers for kind in resolver.owned_sources} >= IMPUTATION_CRITERION_SOURCES
