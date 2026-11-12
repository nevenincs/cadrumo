"""A filer states, property by property and origin year, what earlier years left pending on a let property.

LIRPF art. 23.1.a.1.º and RIRPF art. 13.a carry the excess of interest and
repairs over a property's gross income to the four following years, and anexo
C.1 follows it by the ejercicio it arose in. With no earlier return read, each
origin year's carry is unknown, never zero: the calculation keeps the
property's row and withholds its net yield with a blocking note. The filer
states each origin year on its opening column of the row the calculation
emitted, either that nothing is pending or the amount, and the statement stays
a statement: it is kept on the revision's operator layer, survives calculating
again, and never speaks of a row the declaration does not hold. Box 0103 only
sums the openings, so it takes no statement of its own.

Real behaviour throughout: an isolated encrypted profile and ledger, the
bundled authority, the production calculation and edit executors, every
Modelo 100 year the registry's support envelope admits.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....application.aggregation.renta_inmueble_findings import RentaInmuebleCause
from ....application.aggregation.renta_inmueble_source import RentaInmuebleRowField
from ....application.aggregation.tests.renta_inmueble_support import inmueble, lease, profile_facts, rent
from ....application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditWritableBindingOverrideSurfaceEntryV1,
)
from ....core.authority_grade import RegistryAuthorityGrade
from ....domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.renta_inmueble_bindings import (
    RentaInmuebleOriginPart,
    renta_inmueble_columns,
    renta_inmueble_origin_columns,
)
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ....domain.contribuyente.inmueble_record import ValorCatastral
from ....domain.modelos.calculation_revision import CalculationRevision
from ....domain.modelos.calculation_revision_operator_layer import ATTESTED_ZERO, RowCarryAttestation
from ....domain.transactions.enums import BusinessClassification
from ....domain.transactions.models import TransactionCatalogue
from ....domain.user_profile.tests.general_regime_facts import RENTA_UNMARRIED_TAXPAYER_FACTS
from ....domain.user_profile.values import UserProfileFact
from ...adapter_composition import profile_adapter_composition
from ..modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ROW = "inmueble:0"
_RENT = Decimal(900)
_NEGATIVE_BASE_CARRIES: tuple[BindingId, ...] = (
    "renta-base-liquidable-negativa-general-anterior",
    "renta-base-liquidable-negativa-general-em2-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em3-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em4-pendiente-inicio",
)
_PENDING_SENTENCE = f"renta_inmueble_{RentaInmuebleCause.PENDING_EXPENSES_UNSTATED.value}"
_LET_YEARS_BEFORE = 3
"""The property was first let this many ejercicios before the one filed, so as many origin years are asked."""


def _renta_years() -> tuple[int, ...]:
    """The Modelo 100 years the envelope admits at calculation grade."""
    support = published_supported_filing_years()
    assert support is not None
    admitted: list[int] = []
    for year in sorted(support.years):
        try:
            published_authority_operation().snapshot(
                "100", filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION
            )
        except FilingYearOutsideSupportEnvelopeError:
            continue
        admitted.append(year)
    return tuple(admitted)


def _facts(year: int) -> tuple[UserProfileFact, ...]:
    record = inmueble(
        ejercicio=year,
        importe_adquisicion=Decimal(150000),
        gastos_tributos_adquisicion=Decimal(10000),
        valores_catastrales=(ValorCatastral(year=year, total=Decimal(100000), construccion=Decimal(60000)),),
        arrendado_desde=date(year - _LET_YEARS_BEFORE, 1, 1),
    )
    let = profile_facts((record,), (lease(start=date(year - _LET_YEARS_BEFORE, 1, 1)),))
    return (
        UserProfileFact(path="tax_residence.ccaa", value="madrid"),
        *RENTA_UNMARRIED_TAXPAYER_FACTS,
        *(UserProfileFact(path=path, value=value) for path, value in let.items()),
    )


def _calculated(renta: SeededOperatorWork, year: int) -> CalculationRevision:
    ledger = renta.ports.transaction_repository
    assert isinstance(ledger, TransactionCatalogueRepository)
    # Rent is the filer's own income, not an activity's: the ledger classifies it personal.
    ledger.save(
        TransactionCatalogue.from_transactions(
            tuple(
                rent(
                    f"rent-{month}",
                    amount=_RENT,
                    booked=date(year, month, 1),
                    business_classification=BusinessClassification.PERSONAL,
                )
                for month in range(1, 13)
            )
        )
    )
    # The negative general bases pending from earlier years are another carry; stating them opens the calculation.
    stated = renta.apply(
        binding=tuple(
            _state(binding_id, ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT, row=None)
            for binding_id in _NEGATIVE_BASE_CARRIES
        )
    )
    assert stated.refusal is None
    return renta.require_head()


def _column(renta: SeededOperatorWork, field: RentaInmuebleRowField) -> BindingId:
    revision = renta.operation.revision(str(renta.work_unit.modelo), renta.work_unit.revision_id)
    return next(
        binding.id for binding, provider in renta_inmueble_columns(revision) if provider.row_field == field.value
    )


def _openings(renta: SeededOperatorWork) -> tuple[BindingId, ...]:
    """The opening column of each origin year the property must state, the newest first."""
    revision = renta.operation.revision(str(renta.work_unit.modelo), renta.work_unit.revision_id)
    columns = renta_inmueble_origin_columns(revision)[RentaInmuebleOriginPart.OPENING]
    return tuple(columns[back].id for back in range(1, _LET_YEARS_BEFORE + 1))


def _row_value(head: CalculationRevision, binding_id: BindingId) -> Decimal | None:
    value = head.row_binding_values.get(binding_id, {}).get("1")
    return None if value is None else Decimal(str(value))


def _pending_noted(head: CalculationRevision) -> bool:
    return any(
        issue.fact is not None and issue.fact.sentence.value == _PENDING_SENTENCE for issue in head.source_issues
    )


def _state(
    binding_id: BindingId,
    kind: ModeloEditBindingIntentKind,
    *,
    row: str | None = _ROW,
    value: Decimal | None = None,
) -> ModeloBindingEditIntentV1:
    return ModeloBindingEditIntentV1(
        address=ModeloEditBindingAddressV1(binding_id=binding_id, row_identity=row), kind=kind, value=value
    )


@pytest.mark.parametrize("year", _renta_years())
def test_a_filer_states_each_origin_year_s_carry_on_its_row_and_the_revision_keeps_it(
    tmp_path: Path, year: int
) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(
            tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_facts(year)
        ) as renta,
    ):
        openings = _openings(renta)
        total = _column(renta, RentaInmuebleRowField.GASTOS_PENDIENTES_ANTERIORES)
        net = _column(renta, RentaInmuebleRowField.RENDIMIENTO_NETO)
        head = _calculated(renta, year)
        # Nothing states the carry yet: the row stands, its net yield waits, and a note says why.
        assert _pending_noted(head)
        assert _row_value(head, net) is None
        statable = {
            entry.binding_id
            for entry in renta.baseline().permitted_surface
            if isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1)
            and ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT in entry.allowed_intents
        }
        assert set(openings) <= statable
        assert total not in statable

        nothing = tuple(_state(opening, ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT) for opening in openings)
        assert renta.apply(binding=nothing).refusal is None
        head = renta.require_head()
        assert head.operator_layer is not None
        assert set(head.operator_layer.row_attestations) == {
            RowCarryAttestation(binding_id=opening, source_row_identity=_ROW, amount=ATTESTED_ZERO, absent=True)
            for opening in openings
        }
        assert not _pending_noted(head)
        assert _row_value(head, total) is None
        assert _row_value(head, net) is not None

        newest = openings[0]
        stated = renta.apply(
            binding=(_state(newest, ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE, value=Decimal("300")),)
        )
        assert stated.refusal is None
        head = renta.require_head()
        assert head.operator_layer is not None
        assert set(head.operator_layer.row_attestations) == {
            RowCarryAttestation(binding_id=newest, source_row_identity=_ROW, amount="300"),
            *(
                RowCarryAttestation(binding_id=opening, source_row_identity=_ROW, amount=ATTESTED_ZERO, absent=True)
                for opening in openings[1:]
            ),
        }
        # The newest origin year opens 300 and box 0103 sums the openings.
        assert _row_value(head, newest) == Decimal(300)
        assert _row_value(head, total) == Decimal(300)

        # Calculating the declaration again keeps the statements as the filer made them.
        recalculated = renta.recalculate()
        assert recalculated.operator_layer is not None
        assert recalculated.operator_layer.row_attestations == head.operator_layer.row_attestations
        assert _row_value(recalculated, total) == Decimal(300)


@pytest.mark.parametrize("year", _renta_years())
def test_a_row_statement_names_a_calculated_row_of_a_row_stated_carry_and_never_a_negative_amount(
    tmp_path: Path, year: int
) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(
            tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_facts(year)
        ) as renta,
    ):
        opening = _openings(renta)[0]
        total = _column(renta, RentaInmuebleRowField.GASTOS_PENDIENTES_ANTERIORES)
        before = _calculated(renta, year)
        refused = (
            # A row the calculation did not emit.
            _state(opening, ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT, row="inmueble:9"),
            # The row-stated carry with no row named.
            _state(opening, ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT, row=None),
            # A pending amount below zero.
            _state(opening, ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE, value=Decimal("-1")),
            # Box 0103 sums the origin years' openings and takes no statement of its own.
            _state(total, ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT),
            # A row named on a carry that is not stated row by row.
            _state(_NEGATIVE_BASE_CARRIES[0], ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT),
        )
        for intent in refused:
            assert renta.apply(binding=(intent,)).refusal is not None, intent
        assert renta.require_head().calculation_revision_id == before.calculation_revision_id
