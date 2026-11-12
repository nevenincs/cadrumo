"""A pending interest and repair amount on a let property blocks until its split by year of origin can be filed.

LIRPF art. 23.1.a.1.º and RIRPF art. 13.a carry the excess of a property's
interest and repairs over its gross income to the four following years, and the
return states what is pending split by the ejercicio it arose in. The property
states one total, so that split is never invented: a property with an amount
pending, carried in or left over by the year, blocks with a finding that names
its row and the per-row statement. A property with nothing pending raises none.

Where the previous ejercicio's return is held, nothing matches its pending
amounts to a property, so an unstated property says they must be stated per
property; with no return held the existing finding stands.

Real behaviour: the published Modelo 100 revision of every year of the support
envelope, the real profile record and the real resolver; only the ledger and
withholding stores, and the held-return reader, are in-memory stand-ins.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.governed_fact_scope import governed_facts_in_scope
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.renta_inmueble_bindings import renta_inmueble_columns
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.contribuyente.inmueble_record import ValorCatastral
from ....domain.modelos.calculation_revision_operator_layer import ATTESTED_ZERO, RowCarryAttestation
from ....domain.modelos.calculation_revision_sources import CalculationNoteFact, CalculationNoteSentence
from ....domain.renta.retencion_soportada import RetencionSoportadaRecord
from ....domain.transactions.models import TransactionCatalogue
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...modelo.work_profile import ModeloWorkProfile
from ..renta_inmueble_findings import RentaInmuebleCause, RentaInmuebleDoor
from ..renta_inmueble_resolver import RentaInmuebleSourceResolver
from ..renta_inmueble_source import RentaInmuebleRowField
from ..retencion_soportada_repository import RetencionSoportadaPorts
from ..source_mesh import CalculationSourceContext, CalculationSourceDiagnostic, CalculationSourceResolution
from .ledger_source_mesh_support import BUCKET_ID, InMemoryTransactionCatalogueRepository, m100_revision
from .renta_inmueble_support import expense, inmueble, lease, monthly_rent, profile_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_RENT = Decimal(900)
_ROW = "inmueble:3"
_YEARS = filing_year_envelope().years
_PENDING_CAUSES = (
    RentaInmuebleCause.PENDING_EXPENSES_ORIGIN_UNSPLIT,
    RentaInmuebleCause.PENDING_EXPENSES_UNSTATED,
    RentaInmuebleCause.PENDING_EXPENSES_HELD_RETURN_UNSTATED,
)


def _sentence(cause: RentaInmuebleCause) -> CalculationNoteSentence:
    return CalculationNoteSentence(f"renta_inmueble_{cause.value}")


class _NoWithholding:
    def load_records(self, ejercicio: int) -> tuple[RetencionSoportadaRecord, ...]:
        del ejercicio
        return ()


def _facts(year: int) -> dict[str, str]:
    record = inmueble(
        3,
        ejercicio=year,
        importe_adquisicion=Decimal(150000),
        gastos_tributos_adquisicion=Decimal(10000),
        valores_catastrales=(ValorCatastral(year=year, total=Decimal(100000), construccion=Decimal(60000)),),
    )
    return profile_facts((record,), (lease(0, inmueble_clave=3, start=date(year - 3, 1, 1)),))


def _pending_column(revision: ModeloRevision) -> BindingId:
    return next(
        binding.id
        for binding, provider in renta_inmueble_columns(revision)
        if provider.row_field == RentaInmuebleRowField.GASTOS_PENDIENTES_ANTERIORES.value
    )


def _stated(year: int, amount: str | None) -> tuple[RowCarryAttestation, ...]:
    """The filer's statement of what earlier years left pending; ``None`` states nothing."""
    pending = _pending_column(m100_revision(year))
    if amount is None:
        return ()
    if amount == ATTESTED_ZERO:
        return (RowCarryAttestation(binding_id=pending, source_row_identity=_ROW, amount=ATTESTED_ZERO, absent=True),)
    return (RowCarryAttestation(binding_id=pending, source_row_identity=_ROW, amount=amount),)


def _profile(year: int, operation: PinnedAuthorityOperation) -> ModeloWorkProfile:
    return ModeloWorkProfile(
        record=create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="X0001500M"),
                *(UserProfileFact(path=path, value=value) for path, value in _facts(year).items()),
            ),
            context=operation.profile_create_context(),
        ),
        profile_decode_context=operation.profile_decode_context(),
    )


def _resolve(
    year: int, *, repairs: Decimal, pending: str | None, held: bool | None = None
) -> CalculationSourceResolution:
    """Resolve the property; ``held`` is what the held-return reader answers, ``None`` for no reader."""
    operation = governed_facts_in_scope()
    assert isinstance(operation, PinnedAuthorityOperation)
    repository = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    repository.save(
        TransactionCatalogue.from_transactions(
            (
                *monthly_rent(year, amount=_RENT),
                expense(
                    "reparacion",
                    concept="reparacion_conservacion",
                    inmueble_clave=3,
                    amount=repairs,
                    booked=date(year, 6, 30),
                ),
            )
        )
    )
    asked: list[Period] = []

    def held_reader(context: CalculationSourceContext) -> bool:
        asked.append(context.period)
        return bool(held)

    period = Period.from_year_and_code(year, "0A")
    resolution = RentaInmuebleSourceResolver(
        transaction_repository=repository,
        retencion_soportada_ports=RetencionSoportadaPorts(repository=_NoWithholding()),
        prior_return_held=None if held is None else held_reader,
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="100",
            filing_year=year,
            period=period,
            revision=m100_revision(year),
            profile=_profile(year, operation),
            caller_row_attestations=_stated(year, pending),
        )
    )
    assert asked == ([] if held is None else [period])
    return resolution


def _findings(resolution: CalculationSourceResolution, cause: RentaInmuebleCause) -> list[CalculationSourceDiagnostic]:
    sentence = _sentence(cause)
    return [
        diagnostic
        for diagnostic in resolution.diagnostics
        if diagnostic.fact is not None and diagnostic.fact.sentence == sentence
    ]


def _assert_blocks_on_the_row(finding: CalculationSourceDiagnostic, cause: RentaInmuebleCause) -> None:
    assert finding.fact == CalculationNoteFact.of(_sentence(cause), rows=(_ROW,), record="3")
    assert finding.reason == "source_domain_not_ready"
    assert finding.source_ref == _ROW
    assert finding.remedy is not None
    assert f"{RentaInmuebleDoor.ATTEST_NO_AMOUNT.value} --row {_ROW}" in finding.remedy


@pytest.mark.parametrize("year", _YEARS)
def test_a_property_with_nothing_pending_and_no_excess_raises_no_finding(year: int) -> None:
    resolution = _resolve(year, repairs=Decimal(1000), pending=ATTESTED_ZERO)

    for cause in _PENDING_CAUSES:
        assert _findings(resolution, cause) == [], (year, cause)


@pytest.mark.parametrize("year", _YEARS)
def test_a_nonzero_amount_pending_from_earlier_years_blocks_on_its_row(year: int) -> None:
    # 500 earlier and 1.000 of the year both fit in the 10.800 of rent: nothing is left over, yet 500 was pending.
    resolution = _resolve(year, repairs=Decimal(1000), pending="500")

    (finding,) = _findings(resolution, RentaInmuebleCause.PENDING_EXPENSES_ORIGIN_UNSPLIT)
    _assert_blocks_on_the_row(finding, RentaInmuebleCause.PENDING_EXPENSES_ORIGIN_UNSPLIT)


@pytest.mark.parametrize("year", _YEARS)
def test_repairs_beyond_the_year_s_income_block_on_their_row(year: int) -> None:
    # 12.000 of repairs over 10.800 of rent leave 1.200 pending for the following years.
    resolution = _resolve(year, repairs=Decimal(12000), pending=ATTESTED_ZERO)

    (finding,) = _findings(resolution, RentaInmuebleCause.PENDING_EXPENSES_ORIGIN_UNSPLIT)
    _assert_blocks_on_the_row(finding, RentaInmuebleCause.PENDING_EXPENSES_ORIGIN_UNSPLIT)


@pytest.mark.parametrize("year", _YEARS)
def test_repairs_beyond_the_income_block_while_the_earlier_amount_is_unstated(year: int) -> None:
    resolution = _resolve(year, repairs=Decimal(12000), pending=None)

    assert len(_findings(resolution, RentaInmuebleCause.PENDING_EXPENSES_UNSTATED)) == 1
    (finding,) = _findings(resolution, RentaInmuebleCause.PENDING_EXPENSES_ORIGIN_UNSPLIT)
    _assert_blocks_on_the_row(finding, RentaInmuebleCause.PENDING_EXPENSES_ORIGIN_UNSPLIT)


@pytest.mark.parametrize("year", _YEARS)
def test_a_held_earlier_return_asks_for_the_pending_amount_per_property(year: int) -> None:
    resolution = _resolve(year, repairs=Decimal(1000), pending=None, held=True)

    assert _findings(resolution, RentaInmuebleCause.PENDING_EXPENSES_UNSTATED) == []
    (finding,) = _findings(resolution, RentaInmuebleCause.PENDING_EXPENSES_HELD_RETURN_UNSTATED)
    _assert_blocks_on_the_row(finding, RentaInmuebleCause.PENDING_EXPENSES_HELD_RETURN_UNSTATED)


@pytest.mark.parametrize("year", _YEARS)
def test_without_a_held_earlier_return_the_unstated_finding_stands(year: int) -> None:
    resolution = _resolve(year, repairs=Decimal(1000), pending=None, held=False)

    assert _findings(resolution, RentaInmuebleCause.PENDING_EXPENSES_HELD_RETURN_UNSTATED) == []
    (finding,) = _findings(resolution, RentaInmuebleCause.PENDING_EXPENSES_UNSTATED)
    _assert_blocks_on_the_row(finding, RentaInmuebleCause.PENDING_EXPENSES_UNSTATED)


@pytest.mark.parametrize("year", _YEARS)
def test_a_statement_that_nothing_is_pending_settles_the_held_return_finding(year: int) -> None:
    resolution = _resolve(year, repairs=Decimal(1000), pending=ATTESTED_ZERO, held=True)

    for cause in _PENDING_CAUSES:
        assert _findings(resolution, cause) == [], (year, cause)
