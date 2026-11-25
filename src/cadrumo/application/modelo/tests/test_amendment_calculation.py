"""Hand-derived Modelo 130 amendment arithmetic against the published formula graph."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.identifiers import canonical_decimal_string
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.calculation_revision_operator_layer import CalculationOperatorLayer
from ....domain.modelos.filing_record import FilingDeclarationKind
from ..calculation_helpers import amendment_prior_paid_values, calculate_amendment, external_filing_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_AT = datetime(1980, 4, 20, tzinfo=UTC)
_YEAR = filing_year_envelope().horizon


def _box(token: str) -> CasillaId:
    return validated_casilla_id(token)


def _source(
    snapshot: RegistrySnapshot,
    *,
    prior_quarters: str = "0",
    negative_carry: str = "0",
    imported: bool = False,
    operator_layer: CalculationOperatorLayer | None = None,
) -> CalculationRevision:
    inputs = {_box(key): Decimal("0") for key in ("06", "16", "18", "rendimiento-neto-reducible-art-32-1")}
    inputs.update({_box("01"): Decimal("8840"), _box("gastos-deducibles-previos"): Decimal("4982")})
    bindings = {
        "modelo-130-actividad-economica-ingresos-cumulative": Decimal("8840"),
        "modelo-130-actividad-economica-gastos-cumulative": Decimal("4982"),
        "modelo-130-volumen-ingresos-agrario": Decimal("0"),
        "modelo-130-retenciones-agrarias": Decimal("0"),
        "modelo-130-pagos-fraccionados-anteriores": Decimal(prior_quarters),
        "modelo-130-resultados-negativos-anteriores": Decimal(negative_carry),
        "irpf.previous_year_economic_activity_net_income": Decimal("0"),
    }
    enum = {"modelo-130-estimacion-directa-modalidad": "directa_simplificada"}
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=bindings,
        enum_binding_values=enum,
        date_context={},
    )
    saved_inputs = {
        key: canonical_decimal_string(value) for key, value in (result.values if imported else inputs).items()
    }
    saved_bindings = {**{key: canonical_decimal_string(value) for key, value in bindings.items()}, **enum}
    observations = (
        external_filing_observations(casilla_values=result.values, snapshot=snapshot)
        if imported
        else result.observations
    )
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id=saved_inputs,
            binding_overrides=saved_bindings,
            casilla_values=result.values,
            source_provenance=(),
            filing_instance_evidence=None,
            operator_layer=operator_layer,
        ),
        work_unit_id="a" * 64,
        registry_snapshot_ref=snapshot.snapshot_ref,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id=saved_inputs,
        binding_overrides=saved_bindings,
        casilla_values=result.values,
        observations=observations,
        operator_layer=operator_layer,
        filing_instance_evidence=None,
        source_provenance=(),
        created_at=_AT,
        updated_at=_AT,
    )


@pytest.mark.parametrize("imported", [False, True], ids=["calculated", "imported-scalar-replay"])
def test_changed_withholding_recomputes_dependent_outputs_and_provenance(
    operation: PinnedAuthorityOperation,
    imported: bool,
) -> None:
    snapshot = operation.snapshot("130", filing_year=_YEAR, period="1T")
    source = _source(snapshot, imported=imported)
    saved = source.model_dump(mode="json")
    corrected = calculate_amendment(
        source_revision=source,
        overrides={_box("06"): Decimal("150")},
        prior_paid_values=amendment_prior_paid_values(
            baseline_revision=source,
            snapshot=snapshot,
            amendment_kind=FilingDeclarationKind.COMPLEMENTARIA,
        ),
        snapshot=snapshot,
    )
    # 733.02 - 0 - 150 = 583.02; less minoracion100 = 483.02;
    # the earlier payment633.02 leaves -150, which the legal-direction gate must refuse.
    assert corrected.casilla_values[_box("07")] == Decimal("583.02")
    assert corrected.casilla_values[_box("17")] == Decimal("483.02")
    assert corrected.casilla_values[_box("18")] == Decimal("633.02")
    assert corrected.casilla_values[_box("19")] == Decimal("-150.00")
    observation = next(item for item in corrected.observations if item.casilla_id == "07")
    assert observation.formula_id == "modelo-130-resultado-apartado-i"
    assert observation.operand_values == (Decimal("733.02"), Decimal("0"), Decimal("150"))
    assert corrected.input_values_by_casilla_id[_box("06")] == "150"
    assert _box("07") not in corrected.input_values_by_casilla_id
    assert source.model_dump(mode="json") == saved


def test_income_correction_recomputes_provision_and_keeps_prior_quarter_deductions(
    operation: PinnedAuthorityOperation,
) -> None:
    snapshot = operation.snapshot("130", filing_year=_YEAR, period="2T")
    source = _source(snapshot, prior_quarters="200", negative_carry="50")
    corrected = calculate_amendment(
        source_revision=source,
        overrides={_box("01"): Decimal("10000")},
        prior_paid_values=amendment_prior_paid_values(
            baseline_revision=source,
            snapshot=snapshot,
            amendment_kind=FilingDeclarationKind.COMPLEMENTARIA,
        ),
        snapshot=snapshot,
    )
    # (10000-4982)*5%=250.90; 20%*(10000-4982-250.90)=953.42.
    # Earlier quarters200, minoracion100 and negative carry50 give603.42;
    # earlier same-period payment383.02 leaves220.40.
    expected = {
        "02": "5232.90",
        "04": "953.42",
        "05": "200",
        "07": "753.42",
        "15": "50",
        "17": "603.42",
        "18": "383.02",
        "19": "220.40",
    }
    for key, amount in expected.items():
        assert corrected.casilla_values[_box(key)] == Decimal(amount)
    assert corrected.binding_overrides["modelo-130-actividad-economica-ingresos-cumulative"] == "10000"
    assert corrected.binding_overrides["modelo-130-pagos-fraccionados-anteriores"] == "200"


def test_a_saved_explicit_formula_override_remains_a_dependency_boundary(
    operation: PinnedAuthorityOperation,
) -> None:
    snapshot = operation.snapshot("130", filing_year=_YEAR, period="1T")
    source = _source(snapshot, operator_layer=CalculationOperatorLayer())
    first = calculate_amendment(
        source_revision=source,
        overrides={_box("07"): Decimal("800"), _box("16"): Decimal("20")},
        prior_paid_values={},
        snapshot=snapshot,
    )
    saved = source.model_copy(
        update={
            "casilla_values": first.casilla_values,
            "observations": first.observations,
            "input_values_by_casilla_id": first.input_values_by_casilla_id,
            "binding_overrides": first.binding_overrides,
            "operator_layer": first.operator_layer,
        }
    )
    second = calculate_amendment(
        source_revision=saved,
        overrides={_box("01"): Decimal("10000")},
        prior_paid_values={},
        snapshot=snapshot,
    )
    assert second.casilla_values[_box("04")] == Decimal("953.42")
    assert second.casilla_values[_box("07")] == Decimal("800")
    assert second.casilla_values[_box("16")] == Decimal("20")
    assert second.casilla_values[_box("17")] == Decimal("680")
    assert second.operator_layer is not None
    assert second.operator_layer.decimal_casilla_inputs[_box("07")] == "800"
