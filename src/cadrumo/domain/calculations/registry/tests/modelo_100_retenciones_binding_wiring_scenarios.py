"""Scenario bodies for test_modelo_100_retenciones_binding_wiring, called by its authored-source and published-authority tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from ..bindings import resolve_available_bound_inputs_by_casilla_id
from ..errors import RegistryValidationError
from ..formula_runtime import calculate_registry_snapshot
from ..ids import BindingId, RelationId
from ..schema import RegistrySnapshot
from .authored_editions import newest_authored_editions
from .modelo_100_registry_support import (
    M100_NO_DESCENDANT_MATERNIDAD_BINDINGS,
    M100_NO_MARITIME_WORKER_BINDINGS,
    M100_NO_MARITIME_WORKER_BOOLEAN_BINDINGS,
)

# The two newest Modelo 100 editions the registry authors. Both are exercised
# because each carries its own credit-casilla declarations.
PRIOR_EDITION, REVIEWED_EDITION = newest_authored_editions("100", 2)


M100_MINIMO_PERSONAL_CASILLA: CasillaId = validated_casilla_id("0003", surface="M100_MINIMO_PERSONAL_CASILLA")

M100_RETENCIONES_TRABAJO_CASILLA: CasillaId = validated_casilla_id(
    "0596",
    surface="M100_RETENCIONES_TRABAJO_CASILLA",
)

M100_RETENCIONES_CAPITAL_MOBILIARIO_CASILLA: CasillaId = validated_casilla_id(
    "0597",
    surface="M100_RETENCIONES_CAPITAL_MOBILIARIO_CASILLA",
)

# The payer-record family bindings of the two credit casillas: the mesh sums the
# taxpayer's payer certificates of the class and hands the engine that one value.
M100_RETENCIONES_TRABAJO_BINDING: BindingId = "renta-retencion-soportada-trabajo"
M100_RETENCIONES_CAPITAL_MOBILIARIO_BINDING: BindingId = "renta-retencion-soportada-capital-mobiliario"

M100_TOTAL_PAGOS_A_CUENTA_CASILLA: CasillaId = validated_casilla_id(
    "0609",
    surface="M100_TOTAL_PAGOS_A_CUENTA_CASILLA",
)

M100_CUOTA_DIFERENCIAL_CASILLA: CasillaId = validated_casilla_id("0610", surface="M100_CUOTA_DIFERENCIAL_CASILLA")


PRIOR_DATE_CONTEXT = {"filing_period": date(PRIOR_EDITION, 12, 31)}

PRIOR_DATE_BINDINGS: dict[BindingId, date] = {"renta-profile-taxpayer-birth-date": date(PRIOR_EDITION - 50, 6, 15)}

REVIEWED_DATE_CONTEXT = {"filing_period": date(REVIEWED_EDITION, 12, 31)}

REVIEWED_DATE_BINDINGS: dict[BindingId, date] = {
    "renta-profile-taxpayer-birth-date": date(REVIEWED_EDITION - 50, 6, 15)
}

# The scenarios model no maritime worker under the art. 75 Ley 19/1994 path.
REVIEWED_BOOLEAN_BINDINGS: dict[BindingId, bool] = {"renta-maritime-path-rebeca": False}


PRIOR_RELATION_VALUES: dict[RelationId, Decimal] = {
    "renta-modelo-130-pagos-fraccionados": Decimal("0"),
    "renta-modelo-131-pagos-fraccionados": Decimal("0"),
}

REVIEWED_RELATION_VALUES: dict[RelationId, Decimal] = {
    "renta-modelo-130-pagos-fraccionados": Decimal("0"),
    "renta-modelo-131-pagos-fraccionados": Decimal("0"),
}


def prior_base_binding_values(
    *, certificado_trabajo: Decimal | None = None, certificado_capital: Decimal | None = None
) -> dict[BindingId, Decimal]:
    values: dict[BindingId, Decimal] = {
        "renta-profile-has-economic-activity": Decimal("1"),
        "renta-profile-income-family-excluded-capital-mobiliario": Decimal("0"),
        "renta-profile-income-family-excluded-capital-inmobiliario": Decimal("0"),
        "renta-profile-income-family-excluded-ganancias-patrimoniales": Decimal("0"),
        "renta-profile-estimacion-directa": Decimal("1"),
        "renta-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        "renta-profile-declaration-type": Decimal("1"),
        "renta-profile-family-minor-children-in-unit": Decimal("0"),
        # Art. 81.1 LIRPF maternity deduction: zero in these retenciones scenarios,
        # which declare no qualifying descendant.
        **M100_NO_DESCENDANT_MATERNIDAD_BINDINGS,
        # Art. 81.2 LIRPF guarderia bindings: zero in non-guarderia scenarios.
        "renta-profile-incremento-guarderia": Decimal("0"),
        "renta-profile-minimo-descendientes-estatal": Decimal("0"),
        "renta-profile-minimo-descendientes-autonomico": Decimal("0"),
        "renta-profile-marriage-full-year": Decimal("0"),
        "renta-profile-marriage-month-start": Decimal("0"),
        "renta-profile-marriage-month-end": Decimal("0"),
        # BIN-pendiente fresh-filer baseline.
        "renta-base-liquidable-negativa-general-anterior": Decimal("0"),
        "renta-base-liquidable-negativa-general-em4-pendiente-inicio": Decimal("0"),
        "renta-base-liquidable-negativa-general-em3-pendiente-inicio": Decimal("0"),
        "renta-base-liquidable-negativa-general-em2-pendiente-inicio": Decimal("0"),
        "renta-retencion-soportada-arrendamiento-actividad": Decimal("0"),
        **M100_NO_MARITIME_WORKER_BINDINGS,
    }
    if certificado_trabajo is not None:
        values[M100_RETENCIONES_TRABAJO_BINDING] = certificado_trabajo
    if certificado_capital is not None:
        values[M100_RETENCIONES_CAPITAL_MOBILIARIO_BINDING] = certificado_capital
    return values


def reviewed_base_binding_values(*, certificado_trabajo: Decimal | None = None) -> dict[BindingId, Decimal]:
    values: dict[BindingId, Decimal] = {
        # The production profile resolver supplies this predicate as 1/0 from
        # taxpayer_type.irpf_income_categories; the scenario models a directa filer.
        "renta-profile-has-economic-activity": Decimal("1"),
        "renta-profile-income-family-excluded-capital-mobiliario": Decimal("0"),
        "renta-profile-income-family-excluded-capital-inmobiliario": Decimal("0"),
        "renta-profile-income-family-excluded-ganancias-patrimoniales": Decimal("0"),
        "renta-profile-estimacion-directa": Decimal("1"),
        "renta-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        "renta-profile-declaration-type": Decimal("1"),
        "renta-profile-family-minor-children-in-unit": Decimal("0"),
        "renta-profile-marriage-full-year": Decimal("0"),
        "renta-profile-marriage-month-start": Decimal("0"),
        "renta-profile-marriage-month-end": Decimal("0"),
        "renta-base-liquidable-negativa-general-anterior": Decimal("0"),
        "renta-base-liquidable-negativa-general-em4-pendiente-inicio": Decimal("0"),
        "renta-base-liquidable-negativa-general-em3-pendiente-inicio": Decimal("0"),
        "renta-base-liquidable-negativa-general-em2-pendiente-inicio": Decimal("0"),
        "renta-retencion-soportada-arrendamiento-actividad": Decimal("0"),
        "renta-profile-minimo-descendientes-estatal": Decimal("0"),
        "renta-profile-minimo-descendientes-autonomico": Decimal("0"),
        # No maritime-worker income in these scenarios.
        "renta-maritime-gross-navigation-income": Decimal("0"),
        "renta-maritime-annual-salary": Decimal("0"),
        "renta-maritime-qualifying-days": Decimal("0"),
        # The Art. 81.2 guarderia increment is declared year-free in every edition;
        # neutral zero for a filer with no childcare spend.
        "renta-profile-incremento-guarderia": Decimal("0"),
        # The Art. 81.1 maternidad deducción of an edition that computes casilla 0611;
        # neutral zero for a scenario with no descendants.
        **M100_NO_DESCENDANT_MATERNIDAD_BINDINGS,
    }
    if certificado_trabajo is not None:
        values[M100_RETENCIONES_TRABAJO_BINDING] = certificado_trabajo
    return values


def with_bound_projection(
    snapshot: RegistrySnapshot,
    inputs: dict[CasillaId, Decimal],
    binding_values: dict[BindingId, Decimal],
) -> dict[CasillaId, Decimal]:
    """Mirror the calculate paths: project bound binding values onto their casillas."""
    return {**inputs, **resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)}


def check_salary_certificate_retenciones_binding_populates_prior_edition_casilla_0596(
    prior_edition_snapshot: RegistrySnapshot,
) -> None:
    """Payee salary-certificate withholding is the prior edition's source for 0596."""
    suffered_retenciones = Decimal("4500.00")
    binding_values = prior_base_binding_values(certificado_trabajo=suffered_retenciones)

    result = calculate_registry_snapshot(
        prior_edition_snapshot,
        inputs=with_bound_projection(
            prior_edition_snapshot,
            {M100_MINIMO_PERSONAL_CASILLA: Decimal("30000.00")},
            binding_values,
        ),
        date_context=PRIOR_DATE_CONTEXT,
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        binding_values=binding_values,
        relation_values=PRIOR_RELATION_VALUES,
        date_binding_values=PRIOR_DATE_BINDINGS,
        boolean_binding_values=dict(M100_NO_MARITIME_WORKER_BOOLEAN_BINDINGS),
    )

    assert result.values[M100_RETENCIONES_TRABAJO_CASILLA] == suffered_retenciones
    assert result.values[M100_TOTAL_PAGOS_A_CUENTA_CASILLA] == suffered_retenciones
    observation = next(obs for obs in result.observations if obs.casilla_id == M100_RETENCIONES_TRABAJO_CASILLA)
    assert not observation.absent_by_design
    assert f"aeat-renta-{PRIOR_EDITION}-manual-parte1" in observation.source_refs


def check_salary_certificate_retenciones_binding_populates_reviewed_edition_casilla_0596(
    reviewed_edition_snapshot: RegistrySnapshot,
) -> None:
    """The reviewed edition keeps parity for the payee salary-certificate withholding input."""
    suffered_retenciones = Decimal("4500.00")
    binding_values = reviewed_base_binding_values(certificado_trabajo=suffered_retenciones)

    result = calculate_registry_snapshot(
        reviewed_edition_snapshot,
        inputs=with_bound_projection(
            reviewed_edition_snapshot,
            {"0003": Decimal("30000.00"), "0102": Decimal("9600")},
            binding_values,
        ),
        date_context=REVIEWED_DATE_CONTEXT,
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        binding_values=binding_values,
        relation_values=REVIEWED_RELATION_VALUES,
        date_binding_values=REVIEWED_DATE_BINDINGS,
        boolean_binding_values=REVIEWED_BOOLEAN_BINDINGS,
    )

    assert result.values[M100_RETENCIONES_TRABAJO_CASILLA] == suffered_retenciones
    assert result.values[M100_TOTAL_PAGOS_A_CUENTA_CASILLA] == suffered_retenciones
    observation = next(obs for obs in result.observations if obs.casilla_id == M100_RETENCIONES_TRABAJO_CASILLA)
    assert not observation.absent_by_design
    assert f"aeat-renta-{REVIEWED_EDITION}-manual-parte1" in observation.source_refs


def check_zero_salary_certificate_retenciones_gives_zero_0596(prior_edition_snapshot: RegistrySnapshot) -> None:
    """Anti-tautology: with the certificate at zero, casilla 0596 must be zero.

    This test would pass trivially if 0596 were always zero. Together with the
    populate test above it proves the channel is responsive rather than constant.
    """
    binding_values = prior_base_binding_values(certificado_trabajo=Decimal("0"))
    result = calculate_registry_snapshot(
        prior_edition_snapshot,
        inputs=with_bound_projection(
            prior_edition_snapshot,
            {M100_MINIMO_PERSONAL_CASILLA: Decimal("0")},
            binding_values,
        ),
        date_context=PRIOR_DATE_CONTEXT,
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        binding_values=binding_values,
        relation_values=PRIOR_RELATION_VALUES,
        date_binding_values=PRIOR_DATE_BINDINGS,
        boolean_binding_values=dict(M100_NO_MARITIME_WORKER_BOOLEAN_BINDINGS),
    )

    assert result.values[M100_RETENCIONES_TRABAJO_CASILLA] == Decimal("0")


def check_capital_mobiliario_retenciones_binding_reaches_0609(prior_edition_snapshot: RegistrySnapshot) -> None:
    """Casilla 0597 takes its payer-record family value and still reaches the credit total.

    The formula renta-total-pagos-a-cuenta must sum it into 0609.
    """
    capital_retenciones = Decimal("3800.00")
    binding_values = prior_base_binding_values(
        certificado_trabajo=Decimal("0"), certificado_capital=capital_retenciones
    )
    result = calculate_registry_snapshot(
        prior_edition_snapshot,
        inputs=with_bound_projection(
            prior_edition_snapshot,
            {M100_MINIMO_PERSONAL_CASILLA: Decimal("0")},
            binding_values,
        ),
        date_context=PRIOR_DATE_CONTEXT,
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        binding_values=binding_values,
        relation_values=PRIOR_RELATION_VALUES,
        date_binding_values=PRIOR_DATE_BINDINGS,
        boolean_binding_values=dict(M100_NO_MARITIME_WORKER_BOOLEAN_BINDINGS),
    )

    assert result.values[M100_RETENCIONES_CAPITAL_MOBILIARIO_CASILLA] == capital_retenciones
    assert result.values[M100_TOTAL_PAGOS_A_CUENTA_CASILLA] == capital_retenciones


def check_salary_certificate_retenciones_change_reflects_proportionally_in_0610(
    prior_edition_snapshot: RegistrySnapshot,
) -> None:
    """A change in the certificate amount moves 0609 up and 0610 down by the same delta.

    This guards against any intermediate transformation that would attenuate or
    amplify the credit between the binding and the cuota diferencial.
    """
    low_bindings = prior_base_binding_values(certificado_trabajo=Decimal("1000.00"))
    high_bindings = prior_base_binding_values(certificado_trabajo=Decimal("2000.00"))
    result_low = calculate_registry_snapshot(
        prior_edition_snapshot,
        inputs=with_bound_projection(
            prior_edition_snapshot,
            {M100_MINIMO_PERSONAL_CASILLA: Decimal("0")},
            low_bindings,
        ),
        date_context=PRIOR_DATE_CONTEXT,
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        binding_values=low_bindings,
        relation_values=PRIOR_RELATION_VALUES,
        date_binding_values=PRIOR_DATE_BINDINGS,
        boolean_binding_values=dict(M100_NO_MARITIME_WORKER_BOOLEAN_BINDINGS),
    )
    result_high = calculate_registry_snapshot(
        prior_edition_snapshot,
        inputs=with_bound_projection(
            prior_edition_snapshot,
            {M100_MINIMO_PERSONAL_CASILLA: Decimal("0")},
            high_bindings,
        ),
        date_context=PRIOR_DATE_CONTEXT,
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        binding_values=high_bindings,
        relation_values=PRIOR_RELATION_VALUES,
        date_binding_values=PRIOR_DATE_BINDINGS,
        boolean_binding_values=dict(M100_NO_MARITIME_WORKER_BOOLEAN_BINDINGS),
    )

    delta_0596 = (
        result_high.values[M100_RETENCIONES_TRABAJO_CASILLA] - result_low.values[M100_RETENCIONES_TRABAJO_CASILLA]
    )
    delta_0609 = (
        result_high.values[M100_TOTAL_PAGOS_A_CUENTA_CASILLA] - result_low.values[M100_TOTAL_PAGOS_A_CUENTA_CASILLA]
    )
    delta_0610 = result_low.values[M100_CUOTA_DIFERENCIAL_CASILLA] - result_high.values[M100_CUOTA_DIFERENCIAL_CASILLA]

    assert delta_0596 == Decimal("1000.00"), (
        f"expected 0596 to increase by 1000 when the certificate increases by 1000, got delta={delta_0596!r}"
    )
    assert delta_0609 == Decimal("1000.00"), (
        f"0609 should increase by the same 1000 delta as 0596, got delta={delta_0609!r}"
    )
    assert delta_0610 == Decimal("1000.00"), (
        f"0610 (cuota diferencial) should decrease by 1000 when the credit increases by 1000, got delta={delta_0610!r}"
    )


def check_conflicting_equivalent_binding_values_refuse_before_projection(
    prior_edition_snapshot: RegistrySnapshot,
) -> None:
    """Two reviewed equivalent sources for one casilla must agree exactly.

    Modelo 100 declares no equivalent pair today, so the refusal is exercised
    against an in-memory revision that gives 0596 a second, deliberately
    disagreeing source. Nothing on disk is touched, and the refusal comes from
    the same projection every calculate path calls.
    """
    casillas = tuple(
        casilla.model_copy(update={"alternate_bindings": ("renta-modelo-130-pagos-fraccionados",)})
        if casilla.id == M100_RETENCIONES_TRABAJO_CASILLA
        else casilla
        for casilla in prior_edition_snapshot.revision.casillas
    )
    revision = prior_edition_snapshot.revision.model_copy(update={"casillas": casillas})

    with pytest.raises(RegistryValidationError, match="conflicting equivalent binding values"):
        resolve_available_bound_inputs_by_casilla_id(
            revision,
            {
                M100_RETENCIONES_TRABAJO_BINDING: Decimal("4500.00"),
                "renta-modelo-130-pagos-fraccionados": Decimal("4499.99"),
            },
        )
