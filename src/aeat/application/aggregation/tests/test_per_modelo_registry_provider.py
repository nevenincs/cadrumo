"""Registry-provider integration for per-modelo aggregation."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core import Period
from ....core.aggregation import AggregationSourceKind
from ....core.resources import resources
from .. import (
    CounterpartObservation,
    OperationKind349,
    PerModeloAggregationCommand,
    PerModeloAggregationProvider,
    resolve_per_modelo_registry_binding_values,
)
from .._counterpart import CounterpartSourceKind
from .._registry_provider import PerModeloRegistryBindingResolution

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_P_2026_Q1 = Period.from_year_and_code(2026, "1T")


def _modelo_349_revision():
    return resources().modelos.authority.snapshot("349", filing_year=2026, period="1T").revision


def _counterpart_obs(
    *,
    source_id: str,
    nif: str,
    country: str,
    operation_kind: OperationKind349,
    base: str,
    name: str,
    source_kind: CounterpartSourceKind = AggregationSourceKind.COLLECTIBLE_INVOICE,
    groi_verified: bool = False,
    nif_iva_verified: bool = True,
) -> CounterpartObservation:
    return CounterpartObservation(
        source_kind=source_kind,
        source_object_id=source_id,
        counterparty_nif=nif,
        counterparty_name=name,
        counterparty_country=country,
        operation_kind=operation_kind.value,
        operation_period="2026-Q1",
        taxable_base=Decimal(base),
        invoice_total=Decimal(base),
        accrued_on="2026-03-01",
        groi_verified=groi_verified,
        nif_iva_verified=nif_iva_verified,
    )


def test_per_modelo_registry_binding_resolution_rejects_noncanonical_binding_keys() -> None:
    with pytest.raises(ValidationError) as scalar_exc:
        PerModeloRegistryBindingResolution(
            modelo="349",
            period=_P_2026_Q1,
            provider=PerModeloAggregationProvider.COUNTERPART,
            binding_values={"Bad Binding": Decimal("1.00")},
            source_observation_count=1,
        )
    assert scalar_exc.value.errors()[0]["loc"][0] == "binding_values"

    with pytest.raises(ValidationError) as row_exc:
        PerModeloRegistryBindingResolution(
            modelo="349",
            period=_P_2026_Q1,
            provider=PerModeloAggregationProvider.COUNTERPART,
            row_values={("Bad Binding", 1): Decimal("1.00")},
            source_observation_count=1,
        )
    assert row_exc.value.errors()[0]["loc"][0] == "row_values"


def test_per_modelo_counterpart_provider_resolves_committed_349_registry_bindings() -> None:
    command = PerModeloAggregationCommand(
        modelo="349",
        period=_P_2026_Q1,
        counterpart_observations=(
            _counterpart_obs(
                source_id="ledger-de-1",
                nif="DE111",
                country="DE",
                operation_kind=OperationKind349.INTRA_DELIVERY,
                base="1000.00",
                name="ALEMAN GMBH",
            ),
            _counterpart_obs(
                source_id="ledger-fr-1",
                nif="FR222",
                country="FR",
                operation_kind=OperationKind349.INTRA_SERVICE_OUT,
                base="500.50",
                name="FRANCE SARL",
            ),
        ),
    )

    resolution = resolve_per_modelo_registry_binding_values(command, _modelo_349_revision())

    assert resolution.modelo == "349"
    assert resolution.provider is PerModeloAggregationProvider.COUNTERPART
    assert resolution.source_observation_count == 2
    assert resolution.binding_values == {
        "iva-349-declarante-numero-operadores": Decimal("2"),
        "iva-349-declarante-importe-operaciones": Decimal("1500.50"),
        "iva-349-declarante-numero-rectificaciones": Decimal("0"),
        "iva-349-declarante-importe-rectificaciones": Decimal("0"),
    }
    assert resolution.casilla_values == {
        "decl.numero-operadores": Decimal("2"),
        "decl.importe-operaciones": Decimal("1500.50"),
        "decl.numero-rectificaciones": Decimal("0"),
        "decl.importe-rectificaciones": Decimal("0"),
    }
    assert resolution.row_values[("iva-349-operador-row-codigo-pais", 1)] == "DE"
    assert resolution.row_values[("iva-349-operador-row-nif", 1)] == "DE111"
    assert resolution.row_values[("iva-349-operador-row-clave", 1)] == "E"
    assert resolution.row_values[("iva-349-operador-row-base", 1)] == Decimal("1000.00")
    assert resolution.row_values[("iva-349-operador-row-codigo-pais", 2)] == "FR"
    assert resolution.row_values[("iva-349-operador-row-clave", 2)] == "S"


def test_per_modelo_registry_provider_uses_committed_source_kind_filters() -> None:
    command = PerModeloAggregationCommand(
        modelo="349",
        period=_P_2026_Q1,
        counterpart_observations=(
            _counterpart_obs(
                source_id="payable-de-1",
                nif="DE111",
                country="DE",
                operation_kind=OperationKind349.INTRA_DELIVERY,
                base="1000.00",
                name="ALEMAN GMBH",
                source_kind=AggregationSourceKind.PAYABLE_INVOICE,
            ),
        ),
    )

    resolution = resolve_per_modelo_registry_binding_values(command, _modelo_349_revision())

    assert resolution.source_observation_count == 0
    assert resolution.binding_values == {
        "iva-349-declarante-numero-operadores": Decimal("0"),
        "iva-349-declarante-importe-operaciones": Decimal("0"),
        "iva-349-declarante-numero-rectificaciones": Decimal("0"),
        "iva-349-declarante-importe-rectificaciones": Decimal("0"),
    }


@pytest.mark.parametrize(
    ("country", "groi_verified", "nif_iva_verified"),
    (
        ("DE", False, False),
        ("ES", False, True),
    ),
)
def test_per_modelo_registry_provider_excludes_349_rollups_without_readiness(
    country: str,
    groi_verified: bool,
    nif_iva_verified: bool,
) -> None:
    command = PerModeloAggregationCommand(
        modelo="349",
        period=_P_2026_Q1,
        counterpart_observations=(
            _counterpart_obs(
                source_id=f"ledger-{country.lower()}-1",
                nif=f"{country}111",
                country=country,
                operation_kind=OperationKind349.INTRA_DELIVERY,
                base="1000.00",
                name=f"{country} TRADER",
                groi_verified=groi_verified,
                nif_iva_verified=nif_iva_verified,
            ),
        ),
    )

    resolution = resolve_per_modelo_registry_binding_values(command, _modelo_349_revision())

    assert resolution.source_observation_count == 0
    assert resolution.casilla_values == {
        "decl.numero-operadores": Decimal("0"),
        "decl.importe-operaciones": Decimal("0"),
        "decl.numero-rectificaciones": Decimal("0"),
        "decl.importe-rectificaciones": Decimal("0"),
    }
