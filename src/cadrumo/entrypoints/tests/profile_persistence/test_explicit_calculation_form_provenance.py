"""Explicit registered inputs survive encrypted save and actual work-form assembly."""

from decimal import Decimal

import pytest

from ....application.modelo.calculate_input import calculate_modelo_work_revision
from ....application.modelo.calculation_request_fields import ModeloCalculationInputFieldsV1, ModeloCalculationOverride
from ....application.modelo.work_form_models import ModeloFormOrigin, address_key
from ....application.modelo.work_form_service import load_modelo_work_form
from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from .file_flow_test_support import Repos, calculation_ports_for_test, seed_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_explicit_cli_bound_input_survives_saved_revision_and_form_context(
    repos: Repos, operation: PinnedAuthorityOperation
) -> None:
    units, calculations, _, verification, events = repos
    unit = seed_work_unit(units, filing_year=2025, period="4T")
    fields = ModeloCalculationInputFieldsV1(
        casilla_overrides=(
            ModeloCalculationOverride(key="05", value="355926.98"),
            ModeloCalculationOverride(key="06", value="0.00"),
        ),
        binding_overrides=(
            ModeloCalculationOverride(key="irpf.previous_year_economic_activity_net_income", value="13000"),
            ModeloCalculationOverride(key="modelo-130-resultados-negativos-anteriores", value="0"),
        ),
    )
    with calculation_ports_for_test(
        bucket_id=unit.bucket_id,
        work_unit_repository=units,
        calculation_repository=calculations,
        bucket_event_repository=events,
    ) as ports:
        inputs = fields.build_bundle(
            work_unit_id=unit.work_unit_id,
            ports=ports,
            profile=None,
            detail_rows=(),
            filing_instance_evidence=None,
        )
        assert inputs.record_operator_layer
        result = calculate_modelo_work_revision(
            work_unit_id=unit.work_unit_id,
            actor="synthetic-provenance-test",
            inputs=inputs,
            ports=ports,
        )
    retained = calculations.load(operation=operation).get(result.revision.calculation_revision_id)
    assert retained is not None
    assert retained.operator_layer is not None
    assert retained.operator_layer.decimal_casilla_inputs["05"] == "355926.98"
    assert "01" not in retained.operator_layer.decimal_casilla_inputs
    loaded = load_modelo_work_form(
        unit.bucket_id,
        unit.modelo,
        unit.filing_year,
        unit.period,
        operation=operation,
        work_unit_repository=units,
        calculation_repository=calculations,
        verification_repository=verification,
        admission=None,
        language=OutputLanguage.EN,
    )
    field = next(field for field in loaded.form.fields() if address_key(field.address) == ("casilla", "05"))
    assert field.value == Decimal("355926.98")
    assert field.origin is ModeloFormOrigin.OVERRIDES_SOURCE
    result_field = next(field for field in loaded.form.fields() if address_key(field.address) == ("casilla", "07"))
    assert result_field.value == Decimal("-355926.98")
