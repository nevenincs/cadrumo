"""Operator input for a boolean-declared casilla, on the real registry.

Modelo 100 declares 92 operator-supplied boolean casillas whose answer the engine
reads out of the NUMERIC map as ``0`` / ``1``. Two of them are read by live
formulas, so the encoding is not cosmetic: casilla ``0100`` is a multiplicative
operand of the art. 23.2 arrendamiento-de-vivienda reducción, meaning an
unsupplied flag arrives as zero and withholds the reducción without any refusal.

These tests exercise the real snapshot and the real validator rather than a
fixture revision, because the property under test is that the operator-facing
gate and the engine agree about which casillas may carry a value -- a fixture
that declares its own casilla could agree with itself while the shipped registry
still refused.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.relations import relation_prefill_bindings_for_period
from ....domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.calculations.registry.tests.authored_editions import authored_revisions_where
from ....domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context,
    published_snapshot,
)
from ....domain.user_profile.registry_contract import profile_binding_selectors
from ....domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    create_user_profile_record,
)
from ...aggregation.source_mesh import CalculationSourceResolution
from ..profile_binding import resolve_profile_sourced_bindings
from ..profile_rental_reduction import RENTAL_REDUCTION_APLICABLE_PATH, RENTAL_REDUCTION_TIER_PATH
from ..registry_helpers import validate_casilla_input_ids

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PERIOD = "0A"
# The art. 23.2 reducción flag ("Marque con una X si el arrendamiento tiene
# derecho a reducción") and the rendimiento íntegro that feeds its base.
_REDUCCION_FLAG: CasillaId = validated_casilla_id("0100", surface="_REDUCCION_FLAG")
_REDUCCION_TARGET: CasillaId = validated_casilla_id("0150", surface="_REDUCCION_TARGET")
_RENDIMIENTO_INTEGRO: CasillaId = validated_casilla_id("0102", surface="_RENDIMIENTO_INTEGRO")
_TEXT_CASILLA: CasillaId = validated_casilla_id("0001", surface="_TEXT_CASILLA")
_NUMERIC_CASILLA: CasillaId = validated_casilla_id("0003", surface="_NUMERIC_CASILLA")


def _computes_the_reduccion(revision: ModeloRevision) -> bool:
    """Whether the edition derives casilla 0150 from the flag rather than taking it as an input."""
    return next(casilla for casilla in revision.casillas if casilla.id == _REDUCCION_TARGET).input_kind is (
        InputKind.COMPUTED
    )


_YEAR = authored_revisions_where("100", _computes_the_reduccion)[-1].valid_from.year
"""The newest Modelo 100 edition whose flag gates a computed reducción, the wiring these tests pin."""
_CLOCK = datetime(_YEAR, 5, 21, 10, 0, 0, tzinfo=UTC)
"""A record timestamp inside that edition's ejercicio; the value decides nothing."""
_PROFILE_ID = "10010010-0100-4100-8100-100100100100"


def _snapshot() -> RegistrySnapshot:
    return published_snapshot("100", filing_year=_YEAR, period=_PERIOD)


def _lease_record(**lease: object) -> UserProfileRecord:
    """A profile whose one lease is active in the ejercicio, stating ``lease`` at signing."""
    stated: dict[str, object] = {
        "inmueble": 0,
        "fecha_contrato": date(_YEAR, 1, 1),
        "fecha_inicio": date(_YEAR, 1, 1),
        "uso_vivienda": True,
        "zona_tensionada": False,
    }
    stated.update(lease)
    return create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="capital_inmobiliario"),
            *(
                UserProfileFact(path=f"renta_arrendamiento.0.{leaf}", value=value)
                for leaf, value in stated.items()
                if value is not None
            ),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        context=leased_profile_create_context(),
    )


def _rental_reduction_binding_ids(revision: ModeloRevision) -> frozenset[BindingId]:
    """The bindings the profile derives from the lease rather than reads as stated facts."""
    derived = {RENTAL_REDUCTION_APLICABLE_PATH, RENTAL_REDUCTION_TIER_PATH}
    return frozenset(
        binding.id
        for binding in revision.bindings
        if binding.source is BindingSourceKind.PROFILE and derived & set(profile_binding_selectors(binding.provider))
    )


def _calculate(
    snapshot: RegistrySnapshot,
    inputs: dict[CasillaId, Decimal],
    profile: CalculationSourceResolution,
) -> dict[CasillaId, Decimal]:
    """Run the real registry engine, resolving every non-casilla channel to zero.

    The channels are filled wholesale rather than one at a time so the test states
    one fact -- what the CASILLA inputs do -- instead of silently depending on
    which bindings the revision happens to declare this year. The lease-derived
    reduction bindings are the exception: they come only from ``profile``, the
    real profile resolver's answer, and stay unresolved where it gives none.
    """
    revision = snapshot.revision
    derived = _rental_reduction_binding_ids(revision)
    supplied = {*profile.binding_values, *profile.enum_binding_values, *profile.boolean_binding_values}
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={"filing_year_end": date(_YEAR, 12, 31)},
        binding_values={
            **{binding.id: Decimal(0) for binding in revision.bindings if binding.id not in derived},
            **{binding_id: value for binding_id, value in profile.binding_values.items() if binding_id in derived},
        },
        enum_binding_values={
            "renta-profile-tax-residence-ccaa": "madrid",
            **{binding_id: value for binding_id, value in profile.enum_binding_values.items() if binding_id in derived},
        },
        boolean_binding_values={
            binding_id: value for binding_id, value in profile.boolean_binding_values.items() if binding_id in derived
        },
        unresolved_binding_ids=tuple(sorted(derived - supplied)),
        relation_values={binding.id: Decimal(0) for binding, _ in relation_prefill_bindings_for_period(revision)},
        date_binding_values={binding.id: date(1980, 1, 2) for binding in revision.bindings},
        text_inputs={},
    )
    values: dict[CasillaId, Decimal] = {}
    for observation in result.observations:
        value = observation.value
        assert isinstance(value, Decimal)
        values[observation.casilla_id] = value
    return values


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


def test_reduccion_is_withheld_unset_reached_from_the_lease_and_refused_with_its_door(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The flag and the lease decide the reducción together, through the real resolver.

    Asserts the WIRING rather than the reduced amount: the flag stands between a
    declared arrendamiento and its reducción, the lease the profile records
    supplies whether it applies and at which rate, and a lease that leaves a
    deciding fact unstated leaves the box unresolved with the door that records
    the fact. Asserting the figure would only re-run the registry's own formula
    and would pass just as happily if the rate were wrong.
    """
    snapshot = _snapshot()
    base = {_RENDIMIENTO_INTEGRO: Decimal("10000")}

    def resolved(record: UserProfileRecord) -> CalculationSourceResolution:
        return resolve_profile_sourced_bindings(
            snapshot, bucket_id=_PROFILE_ID, profile_record=record, operation=authority_operation
        )

    lease = resolved(_lease_record())
    unstated = resolved(_lease_record(zona_tensionada=None))

    withheld = _calculate(snapshot, dict(base), lease)
    claimed = _calculate(snapshot, {**base, _REDUCCION_FLAG: Decimal("1")}, lease)
    refused = _calculate(snapshot, {**base, _REDUCCION_FLAG: Decimal("1")}, unstated)

    assert withheld[_REDUCCION_FLAG] == Decimal("0"), "an unsupplied flag reaches the engine as zero"
    assert withheld[_REDUCCION_TARGET] == Decimal("0"), "so the reducción is withheld"
    assert claimed[_REDUCCION_FLAG] == Decimal("1")
    assert claimed[_REDUCCION_TARGET] > Decimal("0"), "the flag and the lease make the reducción reachable"
    assert _REDUCCION_TARGET not in refused, "an unstated lease fact leaves the reducción unresolved, not zero"
    assert [
        (diagnostic.reason, diagnostic.remedy)
        for diagnostic in unstated.diagnostics
        if diagnostic.casilla_id == _REDUCCION_TARGET
    ] == [("source_issue", "aeat config profile arrendamiento edit")]
