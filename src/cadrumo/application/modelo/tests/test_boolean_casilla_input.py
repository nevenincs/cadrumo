"""Operator input for a boolean-declared casilla, on the real registry.

Modelo 100 declares operator-supplied boolean casillas whose answer the engine
reads out of the NUMERIC map as ``0`` / ``1``. The encoding is not cosmetic:
casilla ``0100`` marks the art. 23.2 arrendamiento-de-vivienda reducción of one
let property, and the property's row fills it beside the reducción in ``0150``
from the lease the profile records.

These tests exercise the real snapshot and the real validator rather than a
fixture revision, because the property under test is that the operator-facing
gate and the engine agree about which casillas may carry a value -- a fixture
that declares its own casilla could agree with itself while the shipped registry
still refused.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.renta_inmueble_bindings import renta_inmueble_columns
from ....domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
from ....domain.calculations.registry.tests.authored_editions import authored_revisions_where
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.contribuyente.inmueble_record import AdquisicionTitulo, ValorCatastral
from ....domain.renta.retencion_soportada import RetencionSoportadaRecord
from ....domain.transactions.models import TransactionCatalogue
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...aggregation.renta_inmueble_findings import RentaInmuebleDoor
from ...aggregation.renta_inmueble_resolver import RentaInmuebleSourceResolver
from ...aggregation.renta_inmueble_source import RentaInmuebleRowField
from ...aggregation.retencion_soportada_repository import RetencionSoportadaPorts
from ...aggregation.source_mesh import CalculationSourceContext, CalculationSourceResolution
from ...aggregation.tests.ledger_source_mesh_support import BUCKET_ID, InMemoryTransactionCatalogueRepository
from ...aggregation.tests.renta_inmueble_support import inmueble, lease, monthly_rent, profile_facts, with_fields
from ..registry_helpers import validate_casilla_input_ids
from ..work_profile import ModeloWorkProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PERIOD = "0A"
# The art. 23.2 reducción flag ("Marque con una X si el arrendamiento tiene
# derecho a reducción") and the rendimiento íntegro that feeds its base.
_REDUCCION_FLAG: CasillaId = validated_casilla_id("0100", surface="_REDUCCION_FLAG")
_REDUCCION_TARGET: CasillaId = validated_casilla_id("0150", surface="_REDUCCION_TARGET")
_RENDIMIENTO_INTEGRO: CasillaId = validated_casilla_id("0102", surface="_RENDIMIENTO_INTEGRO")
_TEXT_CASILLA: CasillaId = validated_casilla_id("0001", surface="_TEXT_CASILLA")
_NUMERIC_CASILLA: CasillaId = validated_casilla_id("0003", surface="_NUMERIC_CASILLA")


def _places_the_reduccion(revision: ModeloRevision) -> bool:
    """Whether the edition fills casilla 0150 from each let property's reducción column."""
    return any(
        provider.row_field == RentaInmuebleRowField.REDUCCION.value and provider.target_casilla_id == _REDUCCION_TARGET
        for _binding, provider in renta_inmueble_columns(revision)
    )


_YEAR = authored_revisions_where("100", _places_the_reduccion)[-1].valid_from.year
"""The newest Modelo 100 edition whose property rows carry the reducción, the wiring these tests pin."""
_MONTHLY_RENT = Decimal("950.00")


def _snapshot() -> RegistrySnapshot:
    return published_snapshot("100", filing_year=_YEAR, period=_PERIOD)


class _NoWithholding:
    """The suffered-withholding store of a filer whose tenants withheld nothing."""

    def load_records(self, ejercicio: int) -> tuple[RetencionSoportadaRecord, ...]:
        del ejercicio
        return ()


def _property_row(operation: PinnedAuthorityOperation, **lease_fields: object) -> CalculationSourceResolution:
    """Resolve one property let all year under one lease stating ``lease_fields``, through the real resolver."""
    first_day = date(_YEAR, 1, 1)
    property_record = inmueble(
        ejercicio=_YEAR,
        adquisicion_titulo=AdquisicionTitulo.ONEROSA,
        fecha_adquisicion=first_day,
        importe_adquisicion=Decimal(99000),
        gastos_tributos_adquisicion=Decimal(1000),
        valores_catastrales=(ValorCatastral(year=_YEAR, total=Decimal(80000), construccion=Decimal(64000)),),
    )
    facts = profile_facts((property_record,), (with_fields(lease(start=first_day), lease_fields),))
    repository = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    repository.save(TransactionCatalogue.from_transactions(tuple(monthly_rent(_YEAR, amount=_MONTHLY_RENT))))
    profile = ModeloWorkProfile(
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
    return RentaInmuebleSourceResolver(
        transaction_repository=repository,
        retencion_soportada_ports=RetencionSoportadaPorts(repository=_NoWithholding()),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="100",
            filing_year=_YEAR,
            period=Period.from_year_and_code(_YEAR, _PERIOD),
            revision=_snapshot().revision,
            profile=profile,
        )
    )


def _first_row(resolution: CalculationSourceResolution) -> dict[str, object]:
    """The first property row's values, keyed by the row field each column carries."""
    columns = {binding.id: provider.row_field for binding, provider in renta_inmueble_columns(_snapshot().revision)}
    return {
        columns[binding_id]: value for (binding_id, row), value in resolution.row_binding_values.items() if row == 1
    }


def test_boolean_casilla_is_declared_boolean_and_operator_supplied() -> None:
    """The premise the rest of the file rests on, read off the shipped registry."""
    casillas = {casilla.id: casilla for casilla in _snapshot().revision.casillas}

    assert casillas[_REDUCCION_FLAG].data_type == "boolean"
    assert casillas[_REDUCCION_FLAG].input_kind == "manual"


def test_operator_may_supply_a_boolean_casilla() -> None:
    """The gate accepts both encodings of a boolean-declared casilla."""
    revision = _snapshot().revision

    accepted = validate_casilla_input_ids(revision, {_REDUCCION_FLAG: Decimal("1")})

    assert accepted == {_REDUCCION_FLAG: Decimal("1")}
    assert validate_casilla_input_ids(revision, {_REDUCCION_FLAG: Decimal("0")}) == {_REDUCCION_FLAG: Decimal("0")}


def test_boolean_casilla_outside_zero_or_one_is_refused_instructively() -> None:
    """A value the engine would reject is named here, where the operator typed it."""
    with pytest.raises(RegistryValidationError) as exc_info:
        validate_casilla_input_ids(_snapshot().revision, {_REDUCCION_FLAG: Decimal("2")})

    # The accepted domain and the offending casilla are machine facts; the
    # sentence that used to carry them is catalogue-rendered now.
    context = exc_info.value.context
    assert context is not None
    assert context["accepted"] == "0,1"
    assert _REDUCCION_FLAG in str(context["casilla_ids"])
    assert context["values"] == "2"


def test_python_bool_stays_refused_on_the_casilla_channel() -> None:
    """The casilla channel carries Decimals only; a ``bool`` is still not one.

    Guards the direction this change must not drift in: a ``True`` reaching the
    numeric channel would render as ``1`` on an amount row, filing a figure the
    taxpayer never stated.
    """
    with pytest.raises(RegistryValidationError):
        validate_casilla_input_ids(_snapshot().revision, {_REDUCCION_FLAG: True})


def test_text_casilla_stays_refused_on_the_decimal_channel() -> None:
    """Accepting the boolean family must not accept every non-numeric family."""
    with pytest.raises(RegistryValidationError):
        validate_casilla_input_ids(_snapshot().revision, {_TEXT_CASILLA: Decimal("1")})


def test_numeric_casilla_keeps_its_unrestricted_domain() -> None:
    """The 0 / 1 restriction is scoped to the boolean family, not applied globally."""
    revision = _snapshot().revision

    assert validate_casilla_input_ids(revision, {_NUMERIC_CASILLA: Decimal("12000.25")}) == {
        _NUMERIC_CASILLA: Decimal("12000.25"),
    }


def test_reduccion_and_its_flag_are_decided_by_the_lease_on_the_property_row(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The lease on the property row decides the flag and the reducción, through the real resolver.

    Asserts the WIRING rather than the reduced amount: a dwelling lease marks the
    row and reduces its net yield, a lease that is not for a dwelling leaves both
    unmarked, and a lease that leaves a deciding fact unstated leaves the
    reducción uncomputed with the door that records the fact. Asserting the
    figure would only re-run the rate table and would pass just as happily if
    the rate were wrong.
    """
    flag = RentaInmuebleRowField.REDUCCION_APLICABLE.value
    reduccion = RentaInmuebleRowField.REDUCCION.value
    net = RentaInmuebleRowField.RENDIMIENTO_NETO.value
    reduced = RentaInmuebleRowField.RENDIMIENTO_NETO_REDUCIDO.value

    dwelling = _first_row(_property_row(authority_operation, zona_tensionada=False))
    business = _first_row(_property_row(authority_operation, uso_vivienda=False))
    unstated_resolution = _property_row(authority_operation, zona_tensionada=None)
    unstated = _first_row(unstated_resolution)

    assert dwelling[flag] is True, "a dwelling lease marks the property's reducción"
    reduction = dwelling[reduccion]
    assert isinstance(reduction, Decimal)
    assert reduction > Decimal(0), "the dwelling lease makes the reducción reachable"
    dwelling_net = dwelling[net]
    assert isinstance(dwelling_net, Decimal)
    assert dwelling[reduced] == dwelling_net - reduction

    assert flag not in business, "a lease not for a dwelling marks no reducción"
    assert reduccion not in business
    assert business[reduced] == business[net]

    assert flag not in unstated
    assert reduccion not in unstated, "an unstated lease fact leaves the reducción uncomputed, not zero"
    assert reduced not in unstated
    assert any(
        RentaInmuebleDoor.ARRENDAMIENTO_EDIT.value in (diagnostic.remedy or "")
        for diagnostic in unstated_resolution.diagnostics
    ), "the finding names the door that records the lease fact"
