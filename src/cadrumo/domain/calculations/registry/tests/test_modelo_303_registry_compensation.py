"""Tests for Modelo 303 compensation relation and calculation behavior."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.resources.bundled_data import bundled_path
from .....tests.registry_observations import registry_grounded_modelo_observation
from ..bindings import resolve_available_bound_inputs_by_casilla_id
from ..snapshot import build_snapshot
from ._modelo_303_registry_support import (
    _M303_COMPENSACION_APLICADA_CASILLA,
    _M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA,
    _M303_DISPONIBLE_CASILLA,
    _M303_GENERADA_CASILLA,
    _M303_POSTERIOR_CASILLA,
    _M303_RESULTADO_CASILLA,
    load_modelo_303,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_303_compensation_chain_uses_current_record_design_casillas() -> None:
    modelo, _ = load_modelo_303()
    revision = modelo.revisions["2022"]
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    relation = next(item for item in revision.relations if item.id == "modelo-303-rel-self-compensacion-anteriores")

    assert casillas[_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA].number == "110"
    assert casillas[_M303_COMPENSACION_APLICADA_CASILLA].number == "78"
    assert casillas[_M303_POSTERIOR_CASILLA].number == "87"
    assert casillas[_M303_RESULTADO_CASILLA].number == "69"
    assert relation.target_periods == ("1T", "2T", "3T", "4T")
    assert relation.source_period_offset_from_target == -1
    assert relation.source_periods == ()
    assert relation.target_binding == "modelo-303-compensacion-pendiente-anteriores"


def test_modelo_303_previous_quarter_compensation_binding_resolves_from_source_casilla_id() -> None:
    from ..bindings_previous_filing import (
        previous_filing_observation_requirements,
        resolve_previous_filing_binding_values,
    )
    from ..relations import (
        materialize_relation_binding_values,
        relation_source_requirements,
        resolve_relation_values_from_observations,
    )

    modelo, _ = load_modelo_303()
    revision = modelo.revisions["2022"]
    observations = (
        registry_grounded_modelo_observation(
            modelo="303",
            filing_year=2025,
            period="1T",
            casilla_values={_M303_DISPONIBLE_CASILLA: Decimal("1200.00")},
        ),
    )

    binding_requirements = previous_filing_observation_requirements(revision, filing_year=2025, period="2T")
    assert [(item.periods, item.source_casilla_ids) for item in binding_requirements] == [
        (("1T",), (_M303_DISPONIBLE_CASILLA,)),
    ]

    relation_requirements = relation_source_requirements(revision, filing_year=2025, period="2T")
    assert [(item.periods, item.source_casilla_ids) for item in relation_requirements] == [
        (("1T",), (_M303_DISPONIBLE_CASILLA,)),
    ]

    assert resolve_previous_filing_binding_values(
        revision,
        observations,
        filing_year=2025,
        period="2T",
    ) == {"modelo-303-compensacion-pendiente-anteriores": Decimal("1200.00")}
    assert resolve_relation_values_from_observations(
        revision,
        observations,
        filing_year=2025,
        period="2T",
    ) == {"modelo-303-rel-self-compensacion-anteriores": Decimal("1200.00")}
    assert materialize_relation_binding_values(
        revision,
        {"modelo-303-rel-self-compensacion-anteriores": Decimal("1200.00")},
        period="2T",
    ) == {"modelo-303-compensacion-pendiente-anteriores": Decimal("1200.00")}


def test_modelo_303_first_quarter_compensation_resolves_from_previous_year_fourth_quarter() -> None:
    from ..bindings_previous_filing import (
        previous_filing_observation_requirements,
        resolve_previous_filing_binding_values,
    )
    from ..relations import (
        materialize_relation_binding_values,
        relation_source_requirements,
        resolve_relation_values_from_observations,
    )

    modelo, _ = load_modelo_303()
    revision = modelo.revisions["2022"]
    observations = (
        registry_grounded_modelo_observation(
            modelo="303",
            filing_year=2025,
            period="4T",
            casilla_values={_M303_DISPONIBLE_CASILLA: Decimal("450.00")},
        ),
    )

    binding_requirements = previous_filing_observation_requirements(revision, filing_year=2026, period="1T")
    assert [(item.filing_year, item.periods, item.source_casilla_ids) for item in binding_requirements] == [
        (2025, ("4T",), (_M303_DISPONIBLE_CASILLA,)),
    ]

    relation_requirements = relation_source_requirements(revision, filing_year=2026, period="1T")
    assert [(item.filing_year, item.periods, item.source_casilla_ids) for item in relation_requirements] == [
        (2025, ("4T",), (_M303_DISPONIBLE_CASILLA,)),
    ]

    assert resolve_previous_filing_binding_values(
        revision,
        observations,
        filing_year=2026,
        period="1T",
    ) == {"modelo-303-compensacion-pendiente-anteriores": Decimal("450.00")}
    assert resolve_relation_values_from_observations(
        revision,
        observations,
        filing_year=2026,
        period="1T",
    ) == {"modelo-303-rel-self-compensacion-anteriores": Decimal("450.00")}
    assert materialize_relation_binding_values(
        revision,
        {"modelo-303-rel-self-compensacion-anteriores": Decimal("450.00")},
        period="1T",
    ) == {"modelo-303-compensacion-pendiente-anteriores": Decimal("450.00")}


def test_modelo_303_compensation_calculation_applies_available_balance_and_carries_remainder() -> None:
    from ..formula_runtime import calculate_registry_snapshot

    modelo, catalogues = load_modelo_303()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="2T")

    binding_values = {
        "modelo-303-iva-repercutido-general-cuota": Decimal("1000.00"),
        "modelo-303-iva-repercutido-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-repercutido-super-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-interiores-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-importaciones-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-devengado-base": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-interior-devengado-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-interior-deducible-cuota": Decimal("0.00"),
        "modelo-303-casilla-59-entregas-intracomunitarias-base": Decimal("0"),
        "modelo-303-casilla-60-exportaciones-base": Decimal("0"),
        # No issued domestic reverse charge in this fixture either, so the
        # supplier-side base for casilla 122 resolves to zero. Supplied for the
        # same reason 59 and 60 are: a bound casilla demands its fact, and the
        # absence of contributing rows is stated rather than left missing.
        "modelo-303-casilla-122-inversion-sujeto-pasivo-base": Decimal("0"),
        # And no EU B2B service located outside the TAI, so the sibling
        # informacion-adicional box 120 resolves to zero for the same reason.
        "modelo-303-casilla-120-no-sujetas-localizacion-base": Decimal("0"),
        "modelo-303-iva-repercutido-general-base": Decimal("0"),
        "modelo-303-iva-repercutido-reducido-base": Decimal("0"),
        "modelo-303-iva-repercutido-super-reducido-base": Decimal("0"),
        "modelo-303-iva-soportado-interiores-base": Decimal("0"),
        "modelo-303-recargo-equivalencia-general-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-reducido-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-super-reducido-cuota": Decimal("0"),
        "modelo-303-compensacion-pendiente-anteriores": Decimal("1200.00"),
        # No autoconsumo promotor in this period; zero disables the formula path.
        "modelo-303-autoconsumo-promotor-base": Decimal("0.00"),
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
        # No criterio-de-caja operations in this fixture, so the art. 163
        # decies informational bindings (casillas 62/63/74/75) resolve to zero.
        "modelo-303-criterio-caja-entregas-art75-base": Decimal("0"),
        "modelo-303-criterio-caja-entregas-art75-cuota": Decimal("0"),
        "modelo-303-criterio-caja-adquisiciones-base": Decimal("0"),
        "modelo-303-criterio-caja-adquisiciones-cuota": Decimal("0"),
    }
    bound_inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    result = calculate_registry_snapshot(
        snapshot,
        inputs=bound_inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(2025, 6, 30)},
    )

    # Structural wiring: all compensation casillas must be present in the result.
    compensation_casillas = {
        _M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA,
        _M303_COMPENSACION_APLICADA_CASILLA,
        _M303_POSTERIOR_CASILLA,
        _M303_RESULTADO_CASILLA,
        _M303_GENERADA_CASILLA,
        _M303_DISPONIBLE_CASILLA,
    }
    for casilla_id in compensation_casillas:
        assert casilla_id in result.values, f"{casilla_id!r} must be computed by the compensation chain"

    # Compensation balance constraint: applied + remainder must equal the incoming balance.
    # This is a structural invariant of the compensation mechanism, not a hand-computed value.
    pendiente_anteriores = result.values[_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA]
    aplicada = result.values[_M303_COMPENSACION_APLICADA_CASILLA]
    pendiente_posteriores = result.values[_M303_POSTERIOR_CASILLA]
    assert aplicada + pendiente_posteriores == pendiente_anteriores, "applied + remainder must equal incoming balance"

    # When compensation exceeds IVA output, resultado must be zero (no tax due).
    # The binding carries compensacion_pendiente_anteriores=1200 > repercutido=1000,
    # so the full repercutido is absorbed and resultado must be 0.
    assert result.values[_M303_RESULTADO_CASILLA] == Decimal("0.00"), (
        "resultado must be zero when compensation balance exceeds IVA output"
    )

    # Applied amount must not exceed the IVA output for this period.
    assert aplicada <= binding_values["modelo-303-iva-repercutido-general-cuota"]

    # Disponible at end of period equals the remainder carried forward.
    assert result.values[_M303_DISPONIBLE_CASILLA] == pendiente_posteriores
