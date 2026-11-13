"""A property at its owner's disposal before it is let imputes income on its Inmueble row, casillas 0083 to 0089.

The 2025 Renta manual's flat: cadastral value 46.200, revised in a collective
valuation still in force, at its owner's disposal from January to March and let
from April, imputes "1,1% (46.200 x (90/365)) = 125,31". The expected figures
are recomputed by hand from the manual's rate and 365 divisor for each year's
own January-to-March days, independently of the registry the calculation reads.

Real behaviour throughout: an isolated encrypted profile and ledger, the
published authority, the production calculation, every Modelo 100 year the
registry's support envelope admits.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
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
)
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.casilla_id import validated_casilla_id
from ....domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.renta_inmueble_bindings import renta_inmueble_columns
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ....domain.contribuyente.inmueble_record import UsoInmueble, UsoInmuebleTipo, ValorCatastral
from ....domain.modelos.calculation_revision import CalculationRevision
from ....domain.transactions.enums import BusinessClassification
from ....domain.transactions.models import TransactionCatalogue
from ....domain.user_profile.tests.general_regime_facts import RENTA_UNMARRIED_TAXPAYER_FACTS
from ....domain.user_profile.values import UserProfileFact
from ...adapter_composition import profile_adapter_composition
from ..modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_RENT = Decimal(900)
_VALUE = Decimal("46200")
_REDUCED = Decimal("0.011")
_YEAR_DAYS = 365
_NEGATIVE_BASE_CARRIES: tuple[BindingId, ...] = (
    "renta-base-liquidable-negativa-general-anterior",
    "renta-base-liquidable-negativa-general-em2-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em3-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em4-pendiente-inicio",
    *(
        f"renta-saldo-negativo-{kind}-ahorro-{origin}-pendiente-inicio"
        for kind in ("gyp", "rcm")
        for origin in ("em1", "em2", "em3", "em4")
    ),
)
_VIGOR_SENTENCE = f"renta_inmueble_{RentaInmuebleCause.IMPUTACION_VIGOR_UNSTATED.value}"


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


def _facts(year: int, *, vigor: int | None) -> tuple[UserProfileFact, ...]:
    """The profile of a flat at its owner's disposal from January to March and let from April of ``year``."""
    let_from = date(year, 4, 1)
    record = inmueble(
        ejercicio=year,
        importe_adquisicion=Decimal(150000),
        gastos_tributos_adquisicion=Decimal(10000),
        valores_catastrales=(ValorCatastral(year=year, total=_VALUE, construccion=Decimal(27720), vigor=vigor),),
        usos=(
            UsoInmueble(
                tipo=UsoInmuebleTipo.DISPOSICION_PROPIETARIO, desde=date(year - 2, 1, 1), hasta=date(year, 3, 31)
            ),
        ),
        arrendado_desde=let_from,
    )
    let = profile_facts((record,), (lease(start=let_from),))
    return (
        UserProfileFact(path="tax_residence.ccaa", value="madrid"),
        *RENTA_UNMARRIED_TAXPAYER_FACTS,
        *(UserProfileFact(path=path, value=value) for path, value in let.items()),
    )


def _calculated(renta: SeededOperatorWork, year: int) -> CalculationRevision:
    ledger = renta.ports.transaction_repository
    assert isinstance(ledger, TransactionCatalogueRepository)
    ledger.save(
        TransactionCatalogue.from_transactions(
            tuple(
                rent(
                    f"rent-{month}",
                    amount=_RENT,
                    booked=date(year, month, 1),
                    business_classification=BusinessClassification.PERSONAL,
                )
                for month in range(4, 13)
            )
        )
    )
    # The negative bases and savings balances pending from earlier years are other carries; stating them opens
    # the calculation.
    stated = renta.apply(
        binding=tuple(
            ModeloBindingEditIntentV1(
                address=ModeloEditBindingAddressV1(binding_id=binding_id, row_identity=None),
                kind=ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT,
            )
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


def _row_value(head: CalculationRevision, binding_id: BindingId) -> object:
    return head.row_binding_values.get(binding_id, {}).get("1")


@pytest.mark.parametrize("year", _renta_years())
def test_the_flat_at_disposal_before_its_lease_imputes_the_manual_amount_on_its_row_and_in_box_0155(
    tmp_path: Path, year: int
) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(
            tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_facts(year, vigor=year)
        ) as renta,
    ):
        head = _calculated(renta, year)
        days = (date(year, 3, 31) - date(year, 1, 1)).days + 1
        expected = (_VALUE * _REDUCED * days / _YEAR_DAYS).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        assert Decimal(str(_row_value(head, _column(renta, RentaInmuebleRowField.RENTA_IMPUTADA)))) == expected
        assert Decimal(str(_row_value(head, _column(renta, RentaInmuebleRowField.IMPUTACION_DIAS)))) == days
        assert (
            Decimal(str(_row_value(head, _column(renta, RentaInmuebleRowField.IMPUTACION_VALOR_CATASTRAL)))) == _VALUE
        )
        assert head.casilla_values[validated_casilla_id("0155", surface="test")] == expected
        if days == 90:
            assert expected == Decimal("125.31")
        assert not any(
            issue.fact is not None and issue.fact.sentence.value == _VIGOR_SENTENCE for issue in head.source_issues
        )


@pytest.mark.parametrize("year", _renta_years())
def test_an_unstated_valuation_year_withholds_the_imputed_income_with_a_note(tmp_path: Path, year: int) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(
            tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_facts(year, vigor=None)
        ) as renta,
    ):
        head = _calculated(renta, year)

        assert _row_value(head, _column(renta, RentaInmuebleRowField.RENTA_IMPUTADA)) is None
        assert any(
            issue.fact is not None and issue.fact.sentence.value == _VIGOR_SENTENCE for issue in head.source_issues
        )
