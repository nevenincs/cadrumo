"""Wiring contract for the Modelo 100 withholding credit casillas 0596 and 0597.

The credit belongs to the perceptor. Casilla 0596 (retenciones del trabajo) is
therefore bound to the payee's own salary-certificate figure, and casilla 0597
(retenciones de capital mobiliario) is keyed by the declarant until a typed
per-payer evidence family carries it. Neither is fed by a withholding-agent
return the declarant files for other people.

Binding-to-casilla plumbing contract (not a formula derivation):
  - binding ``renta-certificado-trabajo-retenciones`` -> casilla 0596
  - casilla 0597 takes a keyed manual amount

The certificate binding is an operator-keyed source, so its value reaches the
engine the way every calculate path sends it: through
``resolve_available_bound_inputs_by_casilla_id``, which projects a binding value
onto the casilla the registry binds it to. Asserting 0596 == the certificate
amount is therefore not tautological: a casilla that lost its
``input_kind``/``binding`` pair would earn no projection and silently stay at
zero. The formula 0609 = sum of the credit operands gives the independent
confirmation that the wired value propagates, and 0610 gives the sign.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import CasillaId, validated_casilla_id
from ..bindings import resolve_available_bound_inputs_by_casilla_id
from ..errors import RegistryValidationError
from ..formula_runtime import calculate_registry_snapshot
from ..ids import BindingId, RelationId
from ..schema import RegistrySnapshot
from ._modelo_100_registry_support import M100_2024_EMPTY_MATERNIDAD_BINDINGS
from .authored_editions import newest_authored_editions

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# The two newest Modelo 100 editions the registry authors. Both are exercised
# because each carries its own credit-casilla declarations.
_PRIOR_EDITION, _REVIEWED_EDITION = newest_authored_editions("100", 2)

_M100_2024_MATERNIDAD_BINDINGS = M100_2024_EMPTY_MATERNIDAD_BINDINGS


@pytest.fixture
def prior_edition_snapshot(registry_snapshot: Callable[..., RegistrySnapshot]) -> RegistrySnapshot:
    """The prior edition at calculation grade: these tests assert wiring, never filing eligibility."""
    return registry_snapshot("100", _PRIOR_EDITION, "0A", grade=RegistryAuthorityGrade.CALCULATION)


@pytest.fixture
def reviewed_edition_snapshot(registry_snapshot: Callable[..., RegistrySnapshot]) -> RegistrySnapshot:
    """The reviewed edition at calculation grade: these tests assert wiring, never filing eligibility."""
    return registry_snapshot("100", _REVIEWED_EDITION, "0A", grade=RegistryAuthorityGrade.CALCULATION)


_M100_MINIMO_PERSONAL_CASILLA: CasillaId = validated_casilla_id("0003", surface="_M100_MINIMO_PERSONAL_CASILLA")
_M100_RETENCIONES_TRABAJO_CASILLA: CasillaId = validated_casilla_id(
    "0596",
    surface="_M100_RETENCIONES_TRABAJO_CASILLA",
)
_M100_RETENCIONES_CAPITAL_MOBILIARIO_CASILLA: CasillaId = validated_casilla_id(
    "0597",
    surface="_M100_RETENCIONES_CAPITAL_MOBILIARIO_CASILLA",
)
_M100_TOTAL_PAGOS_A_CUENTA_CASILLA: CasillaId = validated_casilla_id(
    "0609",
    surface="_M100_TOTAL_PAGOS_A_CUENTA_CASILLA",
)
_M100_CUOTA_DIFERENCIAL_CASILLA: CasillaId = validated_casilla_id("0610", surface="_M100_CUOTA_DIFERENCIAL_CASILLA")

_PRIOR_DATE_CONTEXT = {"filing_period": date(_PRIOR_EDITION, 12, 31)}
_PRIOR_DATE_BINDINGS: dict[BindingId, date] = {"renta-profile-taxpayer-birth-date": date(_PRIOR_EDITION - 50, 6, 15)}
_REVIEWED_DATE_CONTEXT = {"filing_period": date(_REVIEWED_EDITION, 12, 31)}
_REVIEWED_DATE_BINDINGS: dict[BindingId, date] = {
    "renta-profile-taxpayer-birth-date": date(_REVIEWED_EDITION - 50, 6, 15)
}
# The scenarios model no maritime worker under the art. 75 Ley 19/1994 path.
_REVIEWED_BOOLEAN_BINDINGS: dict[BindingId, bool] = {"renta-maritime-path-rebeca": False}

_PRIOR_RELATION_VALUES: dict[RelationId, Decimal] = {
    "renta-modelo-130-pagos-fraccionados": Decimal("0"),
    "renta-modelo-131-pagos-fraccionados": Decimal("0"),
}
_REVIEWED_RELATION_VALUES: dict[RelationId, Decimal] = {
    "renta-modelo-130-pagos-fraccionados": Decimal("0"),
    "renta-modelo-131-pagos-fraccionados": Decimal("0"),
}


def _prior_base_binding_values(*, certificado_trabajo: Decimal | None = None) -> dict[BindingId, Decimal]:
    values: dict[BindingId, Decimal] = {
        "renta-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        "renta-profile-declaration-type": Decimal("1"),
        "renta-profile-family-minor-children-in-unit": Decimal("0"),
        # Art. 81.1 LIRPF maternity deduction: zero in these retenciones scenarios,
        # which declare no qualifying descendant.
        **_M100_2024_MATERNIDAD_BINDINGS,
        # Art. 81.2 LIRPF guarderia bindings: zero in non-guarderia scenarios.
        "renta-profile-guarderia-gastos-reales": Decimal("0"),
        "renta-profile-incremento-guarderia": Decimal("0"),
        "renta-profile-cotizaciones-ss-madre": Decimal("0"),
        "renta-profile-descendientes-guarderia": Decimal("0"),
        "renta-profile-minimo-descendientes-estatal": Decimal("0"),
        "renta-profile-minimo-descendientes-autonomico": Decimal("0"),
        "renta-profile-marriage-full-year": Decimal("0"),
        "renta-profile-marriage-month-start": Decimal("0"),
        "renta-profile-marriage-month-end": Decimal("0"),
        # BIN-pendiente fresh-filer baseline.
        "renta-base-liquidable-negativa-general-anterior": Decimal("0"),
    }
    if certificado_trabajo is not None:
        values["renta-certificado-trabajo-retenciones"] = certificado_trabajo
    return values


def _reviewed_base_binding_values(*, certificado_trabajo: Decimal | None = None) -> dict[BindingId, Decimal]:
    values: dict[BindingId, Decimal] = {
        # The production profile resolver supplies this predicate as 1/0 from
        # taxpayer_type.irpf_income_categories; the scenario models a directa filer.
        "renta-profile-has-economic-activity": Decimal("1"),
        "renta-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        "renta-modelo-184-atribucion-actividades-economicas": Decimal("0"),
        "renta-profile-declaration-type": Decimal("1"),
        "renta-profile-family-minor-children-in-unit": Decimal("0"),
        "renta-profile-marriage-full-year": Decimal("0"),
        "renta-profile-marriage-month-start": Decimal("0"),
        "renta-profile-marriage-month-end": Decimal("0"),
        "renta-base-liquidable-negativa-general-anterior": Decimal("0"),
        "renta-profile-minimo-descendientes-estatal": Decimal("0"),
        "renta-profile-minimo-descendientes-autonomico": Decimal("0"),
        # No maritime-worker income in these scenarios.
        "renta-maritime-gross-navigation-income": Decimal("0"),
        "renta-maritime-annual-salary": Decimal("0"),
        "renta-maritime-qualifying-days": Decimal("0"),
    }
    if certificado_trabajo is not None:
        values["renta-certificado-trabajo-retenciones"] = certificado_trabajo
    return values


def _with_bound_projection(
    snapshot: RegistrySnapshot,
    inputs: dict[CasillaId, Decimal],
    binding_values: dict[BindingId, Decimal],
) -> dict[CasillaId, Decimal]:
    """Mirror the calculate paths: project bound binding values onto their casillas."""
    return {**inputs, **resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)}


def test_salary_certificate_retenciones_binding_populates_prior_edition_casilla_0596(
    prior_edition_snapshot: RegistrySnapshot,
) -> None:
    """Payee salary-certificate withholding is the prior edition's source for 0596."""
    suffered_retenciones = Decimal("4500.00")
    binding_values = _prior_base_binding_values(certificado_trabajo=suffered_retenciones)

    result = calculate_registry_snapshot(
        prior_edition_snapshot,
        inputs=_with_bound_projection(
            prior_edition_snapshot,
            {_M100_MINIMO_PERSONAL_CASILLA: Decimal("30000.00")},
            binding_values,
        ),
        date_context=_PRIOR_DATE_CONTEXT,
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        binding_values=binding_values,
        relation_values=_PRIOR_RELATION_VALUES,
        date_binding_values=_PRIOR_DATE_BINDINGS,
    )

    assert result.values[_M100_RETENCIONES_TRABAJO_CASILLA] == suffered_retenciones
    assert result.values[_M100_TOTAL_PAGOS_A_CUENTA_CASILLA] == suffered_retenciones
    observation = next(obs for obs in result.observations if obs.casilla_id == _M100_RETENCIONES_TRABAJO_CASILLA)
    assert not observation.absent_by_design
    assert f"aeat-renta-{_PRIOR_EDITION}-manual-parte1" in observation.source_refs


def test_salary_certificate_retenciones_binding_populates_reviewed_edition_casilla_0596(
    reviewed_edition_snapshot: RegistrySnapshot,
) -> None:
    """The reviewed edition keeps parity for the payee salary-certificate withholding input."""
    suffered_retenciones = Decimal("4500.00")
    binding_values = _reviewed_base_binding_values(certificado_trabajo=suffered_retenciones)

    result = calculate_registry_snapshot(
        reviewed_edition_snapshot,
        inputs=_with_bound_projection(
            reviewed_edition_snapshot,
            {"0003": Decimal("30000.00"), "0102": Decimal("9600")},
            binding_values,
        ),
        date_context=_REVIEWED_DATE_CONTEXT,
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        binding_values=binding_values,
        relation_values=_REVIEWED_RELATION_VALUES,
        date_binding_values=_REVIEWED_DATE_BINDINGS,
        boolean_binding_values=_REVIEWED_BOOLEAN_BINDINGS,
    )

    assert result.values[_M100_RETENCIONES_TRABAJO_CASILLA] == suffered_retenciones
    assert result.values[_M100_TOTAL_PAGOS_A_CUENTA_CASILLA] == suffered_retenciones
    observation = next(obs for obs in result.observations if obs.casilla_id == _M100_RETENCIONES_TRABAJO_CASILLA)
    assert not observation.absent_by_design
    assert f"aeat-renta-{_REVIEWED_EDITION}-manual-parte1" in observation.source_refs


def test_zero_salary_certificate_retenciones_gives_zero_0596(prior_edition_snapshot: RegistrySnapshot) -> None:
    """Anti-tautology: with the certificate at zero, casilla 0596 must be zero.

    This test would pass trivially if 0596 were always zero. Together with the
    populate test above it proves the channel is responsive rather than constant.
    """
    binding_values = _prior_base_binding_values(certificado_trabajo=Decimal("0"))
    result = calculate_registry_snapshot(
        prior_edition_snapshot,
        inputs=_with_bound_projection(
            prior_edition_snapshot,
            {_M100_MINIMO_PERSONAL_CASILLA: Decimal("0")},
            binding_values,
        ),
        date_context=_PRIOR_DATE_CONTEXT,
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        binding_values=binding_values,
        relation_values=_PRIOR_RELATION_VALUES,
        date_binding_values=_PRIOR_DATE_BINDINGS,
    )

    assert result.values[_M100_RETENCIONES_TRABAJO_CASILLA] == Decimal("0")


def test_keyed_capital_mobiliario_retenciones_reach_0609(prior_edition_snapshot: RegistrySnapshot) -> None:
    """Casilla 0597 is keyed by the declarant and still reaches the credit total.

    0597 carries no binding, so the amount arrives as a manual casilla input.
    The formula renta-total-pagos-a-cuenta must still sum it into 0609.
    """
    capital_retenciones = Decimal("3800.00")
    result = calculate_registry_snapshot(
        prior_edition_snapshot,
        inputs={
            _M100_MINIMO_PERSONAL_CASILLA: Decimal("0"),
            _M100_RETENCIONES_CAPITAL_MOBILIARIO_CASILLA: capital_retenciones,
        },
        date_context=_PRIOR_DATE_CONTEXT,
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        binding_values=_prior_base_binding_values(),
        relation_values=_PRIOR_RELATION_VALUES,
        date_binding_values=_PRIOR_DATE_BINDINGS,
    )

    assert result.values[_M100_RETENCIONES_CAPITAL_MOBILIARIO_CASILLA] == capital_retenciones
    assert result.values[_M100_TOTAL_PAGOS_A_CUENTA_CASILLA] == capital_retenciones


def test_salary_certificate_retenciones_change_reflects_proportionally_in_0610(
    prior_edition_snapshot: RegistrySnapshot,
) -> None:
    """A change in the certificate amount moves 0609 up and 0610 down by the same delta.

    This guards against any intermediate transformation that would attenuate or
    amplify the credit between the binding and the cuota diferencial.
    """
    low_bindings = _prior_base_binding_values(certificado_trabajo=Decimal("1000.00"))
    high_bindings = _prior_base_binding_values(certificado_trabajo=Decimal("2000.00"))
    result_low = calculate_registry_snapshot(
        prior_edition_snapshot,
        inputs=_with_bound_projection(
            prior_edition_snapshot,
            {_M100_MINIMO_PERSONAL_CASILLA: Decimal("0")},
            low_bindings,
        ),
        date_context=_PRIOR_DATE_CONTEXT,
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        binding_values=low_bindings,
        relation_values=_PRIOR_RELATION_VALUES,
        date_binding_values=_PRIOR_DATE_BINDINGS,
    )
    result_high = calculate_registry_snapshot(
        prior_edition_snapshot,
        inputs=_with_bound_projection(
            prior_edition_snapshot,
            {_M100_MINIMO_PERSONAL_CASILLA: Decimal("0")},
            high_bindings,
        ),
        date_context=_PRIOR_DATE_CONTEXT,
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        binding_values=high_bindings,
        relation_values=_PRIOR_RELATION_VALUES,
        date_binding_values=_PRIOR_DATE_BINDINGS,
    )

    delta_0596 = (
        result_high.values[_M100_RETENCIONES_TRABAJO_CASILLA] - result_low.values[_M100_RETENCIONES_TRABAJO_CASILLA]
    )
    delta_0609 = (
        result_high.values[_M100_TOTAL_PAGOS_A_CUENTA_CASILLA] - result_low.values[_M100_TOTAL_PAGOS_A_CUENTA_CASILLA]
    )
    delta_0610 = (
        result_low.values[_M100_CUOTA_DIFERENCIAL_CASILLA] - result_high.values[_M100_CUOTA_DIFERENCIAL_CASILLA]
    )

    assert delta_0596 == Decimal("1000.00"), (
        f"expected 0596 to increase by 1000 when the certificate increases by 1000, got delta={delta_0596!r}"
    )
    assert delta_0609 == Decimal("1000.00"), (
        f"0609 should increase by the same 1000 delta as 0596, got delta={delta_0609!r}"
    )
    assert delta_0610 == Decimal("1000.00"), (
        f"0610 (cuota diferencial) should decrease by 1000 when the credit increases by 1000, got delta={delta_0610!r}"
    )


def test_conflicting_equivalent_binding_values_refuse_before_projection(
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
        if casilla.id == _M100_RETENCIONES_TRABAJO_CASILLA
        else casilla
        for casilla in prior_edition_snapshot.revision.casillas
    )
    revision = prior_edition_snapshot.revision.model_copy(update={"casillas": casillas})

    with pytest.raises(RegistryValidationError, match="conflicting equivalent binding values"):
        resolve_available_bound_inputs_by_casilla_id(
            revision,
            {
                "renta-certificado-trabajo-retenciones": Decimal("4500.00"),
                "renta-modelo-130-pagos-fraccionados": Decimal("4499.99"),
            },
        )
