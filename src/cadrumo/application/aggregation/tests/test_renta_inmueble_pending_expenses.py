"""What earlier years left pending on a let property comes from the filer's statement for that property.

LIRPF art. 23.1.a.1.º and RIRPF art. 13.a carry the excess of interest and
repairs over a property's gross income to the four following years, property
by property. With no earlier return held, that carry is unknown, never zero:
the resolver keeps the rows, withholds the net yield and says so with a
finding whose door is the per-row statement. A statement settles only the
property it names, on the column whose registry family takes it.

Every finding states its facts in each output language, naming the property
or lease it speaks of by the record's own number.

Real behaviour: the published Modelo 100 revision of every year of the support
envelope, the real profile record and the real resolver; only the ledger and
withholding stores are in-memory stand-ins.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import lookup_translation
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
from ...modelo.calculation_notes import fact_locale_key, note_fact_text
from ...modelo.work_profile import ModeloWorkProfile
from ..renta_inmueble_findings import RentaInmuebleCause, RentaInmuebleDoor
from ..renta_inmueble_resolver import RentaInmuebleSourceResolver
from ..renta_inmueble_source import RentaInmuebleRowField
from ..retencion_soportada_repository import RetencionSoportadaPorts
from ..source_mesh import CalculationSourceContext, CalculationSourceDiagnostic, CalculationSourceResolution
from .ledger_source_mesh_support import BUCKET_ID, InMemoryTransactionCatalogueRepository, m100_revision
from .renta_inmueble_support import expense, inmueble, lease, monthly_rent, profile_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_PENDING_SENTENCE = CalculationNoteSentence(f"renta_inmueble_{RentaInmuebleCause.PENDING_EXPENSES_UNSTATED.value}")
_RENT = Decimal(900)


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


def _column(revision: ModeloRevision, field: RentaInmuebleRowField) -> BindingId:
    return next(
        binding.id for binding, provider in renta_inmueble_columns(revision) if provider.row_field == field.value
    )


def _resolve(year: int, *statements: RowCarryAttestation) -> CalculationSourceResolution:
    operation = governed_facts_in_scope()
    assert isinstance(operation, PinnedAuthorityOperation)
    repository = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    repository.save(
        TransactionCatalogue.from_transactions(
            (
                *monthly_rent(year, amount=_RENT),
                expense(
                    "intereses",
                    concept="interes_financiacion",
                    inmueble_clave=3,
                    amount=Decimal(1000),
                    booked=date(year, 6, 30),
                ),
            )
        )
    )
    profile = ModeloWorkProfile(
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
    return RentaInmuebleSourceResolver(
        transaction_repository=repository,
        retencion_soportada_ports=RetencionSoportadaPorts(repository=_NoWithholding()),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="100",
            filing_year=year,
            period=Period.from_year_and_code(year, "0A"),
            revision=m100_revision(year),
            profile=profile,
            caller_row_attestations=statements,
        )
    )


def _pending_findings(resolution: CalculationSourceResolution) -> list[CalculationSourceDiagnostic]:
    return [
        diagnostic
        for diagnostic in resolution.diagnostics
        if diagnostic.fact is not None and diagnostic.fact.sentence is _PENDING_SENTENCE
    ]


_YEARS = filing_year_envelope().years


@pytest.mark.parametrize("year", _YEARS)
def test_an_unstated_carry_keeps_the_rows_and_withholds_the_net_yield(year: int) -> None:
    revision = m100_revision(year)
    resolution = _resolve(year)
    values = resolution.row_binding_values

    (finding,) = _pending_findings(resolution)
    assert finding.fact == CalculationNoteFact.of(_PENDING_SENTENCE, rows=("inmueble:3",), record="3")
    assert finding.reason == "source_domain_not_ready"
    assert finding.remedy is not None and RentaInmuebleDoor.ATTEST_NO_AMOUNT.value in finding.remedy
    assert values[(_column(revision, RentaInmuebleRowField.INGRESOS_INTEGROS), 1)] == _RENT * 12
    for field in (
        RentaInmuebleRowField.GASTOS_PENDIENTES_ANTERIORES,
        RentaInmuebleRowField.INTERESES_REPARACION_APLICADOS,
        RentaInmuebleRowField.RENDIMIENTO_NETO,
        RentaInmuebleRowField.RENDIMIENTO_NETO_REDUCIDO,
    ):
        assert (_column(revision, field), 1) not in values, (year, field)


@pytest.mark.parametrize("year", _YEARS)
def test_a_stated_amount_is_applied_first_and_the_year_s_own_takes_the_room_left(year: int) -> None:
    revision = m100_revision(year)
    pending = _column(revision, RentaInmuebleRowField.GASTOS_PENDIENTES_ANTERIORES)
    resolution = _resolve(
        year, RowCarryAttestation(binding_id=pending, source_row_identity="inmueble:3", amount="10000")
    )
    values = resolution.row_binding_values

    assert _pending_findings(resolution) == []
    # The limit is the 10.800 of rent: 10.000 earlier first, then 800 of the year's 1.000; 200 carry on.
    assert values[(pending, 1)] == Decimal(10000)
    assert values[(_column(revision, RentaInmuebleRowField.GASTOS_PENDIENTES_APLICADOS), 1)] == Decimal(10000)
    assert values[(_column(revision, RentaInmuebleRowField.INTERESES_REPARACION_APLICADOS), 1)] == Decimal(800)
    assert values[(_column(revision, RentaInmuebleRowField.INTERESES_REPARACION_PENDIENTES), 1)] == Decimal(200)
    assert values[(_column(revision, RentaInmuebleRowField.INTERESES_REPARACION_PENDIENTES_FUTUROS), 1)] == Decimal(200)


@pytest.mark.parametrize("year", _YEARS)
def test_a_statement_that_nothing_is_pending_settles_the_property_and_fills_no_carry_box(year: int) -> None:
    revision = m100_revision(year)
    pending = _column(revision, RentaInmuebleRowField.GASTOS_PENDIENTES_ANTERIORES)
    resolution = _resolve(
        year,
        RowCarryAttestation(binding_id=pending, source_row_identity="inmueble:3", amount=ATTESTED_ZERO, absent=True),
    )

    assert _pending_findings(resolution) == []
    assert (pending, 1) not in resolution.row_binding_values
    assert (_column(revision, RentaInmuebleRowField.RENDIMIENTO_NETO), 1) in resolution.row_binding_values


@pytest.mark.parametrize("year", _YEARS)
def test_a_statement_for_another_property_or_another_column_settles_nothing(year: int) -> None:
    revision = m100_revision(year)
    pending = _column(revision, RentaInmuebleRowField.GASTOS_PENDIENTES_ANTERIORES)
    applied = _column(revision, RentaInmuebleRowField.GASTOS_PENDIENTES_APLICADOS)

    elsewhere = _resolve(
        year,
        RowCarryAttestation(binding_id=pending, source_row_identity="inmueble:4", amount=ATTESTED_ZERO, absent=True),
    )
    wrong_column = _resolve(
        year,
        RowCarryAttestation(binding_id=applied, source_row_identity="inmueble:3", amount=ATTESTED_ZERO, absent=True),
    )

    assert len(_pending_findings(elsewhere)) == 1
    assert len(_pending_findings(wrong_column)) == 1


def test_every_finding_reads_in_every_language_naming_its_record() -> None:
    for cause in RentaInmuebleCause:
        sentence = CalculationNoteSentence(f"renta_inmueble_{cause.value}")
        key = fact_locale_key(sentence)
        authored = {language: lookup_translation(key, locale=language.value) for language in OutputLanguage}
        assert all(words is not None for words in authored.values()), (key, authored)
        assert len(set(authored.values())) == len(authored), (key, authored)
        named = "{record}" in (authored[OutputLanguage.EN] or "")
        assert all(("{record}" in (words or "")) == named for words in authored.values()), (key, authored)
        if named:
            fact = CalculationNoteFact.of(sentence, rows=("inmueble:7",), record="7")
            for language in OutputLanguage:
                text = note_fact_text(fact, locale=language.value)
                assert "7" in text and "{" not in text, (key, language, text)
