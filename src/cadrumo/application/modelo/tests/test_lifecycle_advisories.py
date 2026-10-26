"""Writer-bound, locale-neutral lifecycle advisory projections."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.casilla_id import validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.bindings import CasillaObservation
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.row_models import Modelo184MemberRow, ModeloDetailRow
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ...operations.registry_schema_validation import strict_model_json_schema
from .. import result_disposition_resolution
from ..lifecycle_advisories import (
    Modelo184SocioHandoffV1,
    ModeloLifecycleAdvisories,
    ModeloM210PlazoAdvisoryV1,
    build_modelo_lifecycle_advisories,
)
from ..work_plazo import calculated_m210_plazo_resolution

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_BUCKET_ID = "915b0469-91b1-4787-a650-9aad55564dd3"


def _profile() -> TaxpayerProfile:
    return TaxpayerProfile(tax_id="X1234567L", iva_regime=IVARegime("GENERAL"))


def _work_unit(operation: PinnedAuthorityOperation, modelo: str) -> WorkUnit:
    period = Period.from_year_and_code(2025, "0A")
    revision_id = operation.snapshot(modelo, filing_year=2025, period="0A").snapshot_ref.revision_id
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=modelo,
            filing_year=2025,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(modelo),
        filing_year=2025,
        period=period,
        revision_id=revision_id,
        name=f"{modelo} annual",
        created_at=_NOW,
        updated_at=_NOW,
    )


def _revision(
    work_unit: WorkUnit,
    *,
    rows: tuple[ModeloDetailRow, ...] = (),
    values: dict[str, Decimal] | None = None,
    tipo_renta_code: str | None = None,
) -> CalculationRevision:
    casilla_values = {
        validated_casilla_id(key, surface="lifecycle advisory test"): value for key, value in (values or {}).items()
    }
    observations = tuple(
        CasillaObservation(
            casilla_id=casilla_id,
            value=value,
            legal_refs=("ley-58-2003:art-120",),
            source_refs=("lifecycle-advisory-fixture",),
        )
        for casilla_id, value in casilla_values.items()
    )
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values=casilla_values,
            detail_rows=rows,
            m210_official_tipo_renta_code=tipo_renta_code,
            filing_instance_evidence=None,
            source_provenance=(),
        ),
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=work_unit.modelo,
            revision_id=work_unit.revision_id,
            modelo_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        ),
        state=CalculationRevisionState.BORRADOR,
        casilla_values=casilla_values,
        observations=observations,
        detail_rows=rows,
        m210_official_tipo_renta_code=tipo_renta_code,
        created_at=_NOW,
        updated_at=_NOW,
        filing_instance_evidence=None,
        source_provenance=(),
    )


def test_m184_handoffs_capture_actual_rows_and_registry_target(operation: PinnedAuthorityOperation) -> None:
    unit = _work_unit(operation, "184")
    rows = (
        Modelo184MemberRow(
            nif="12345678A", nombre="Ana Socia", porcentaje=Decimal("60.00"), importe=Decimal("58100.00"), clave="D"
        ),
        Modelo184MemberRow(
            nif="87654321B", nombre="Beto Comunero", porcentaje=Decimal("40.00"), importe=Decimal("38700.00"), clave="D"
        ),
    )
    revision = _revision(unit, rows=rows)

    facts = build_modelo_lifecycle_advisories(
        work_unit=unit, revision=revision, workflow_profile=_profile(), operation=operation
    )

    assert facts.work_unit_id == unit.work_unit_id
    assert facts.calculation_revision_id == revision.calculation_revision_id
    assert facts.m210_plazo is None
    assert [(row.nif, row.nombre, row.porcentaje, row.importe) for row in facts.m184_socio_handoffs] == [
        (row.nif, row.nombre, str(row.porcentaje), str(row.importe)) for row in rows
    ]
    assert all(row.code and row.target_casilla == "1577" and row.legal_refs for row in facts.m184_socio_handoffs)
    assert ModeloLifecycleAdvisories.model_validate_json(facts.model_dump_json()) == facts


def test_empty_handoff_is_explicit_and_mismatched_revision_refuses(operation: PinnedAuthorityOperation) -> None:
    unit = _work_unit(operation, "184")
    revision = _revision(unit)
    facts = build_modelo_lifecycle_advisories(
        work_unit=unit, revision=revision, workflow_profile=_profile(), operation=operation
    )
    assert facts.m184_socio_handoffs == ()
    assert facts.m210_plazo is None

    foreign_unit = _work_unit(operation, "210")
    with pytest.raises(ValueError, match="does not match"):
        build_modelo_lifecycle_advisories(
            work_unit=foreign_unit, revision=revision, workflow_profile=_profile(), operation=operation
        )


def test_m210_window_reconstructs_canonical_renderer_facts(operation: PinnedAuthorityOperation) -> None:
    unit = _work_unit(operation, "210")
    revision = _revision(unit, values={"base_imponible": Decimal("900.00")}, tipo_renta_code="01")
    expected = calculated_m210_plazo_resolution(work_unit=unit, revision=revision, workflow_profile=_profile())
    assert expected is not None

    facts = build_modelo_lifecycle_advisories(
        work_unit=unit, revision=revision, workflow_profile=_profile(), operation=operation
    )

    assert facts.m210_plazo is not None
    assert facts.m210_plazo.to_resolution() == expected
    assert facts.m184_socio_handoffs == ()
    reloaded = ModeloLifecycleAdvisories.model_validate_json(facts.model_dump_json())
    assert reloaded.m210_plazo is not None
    assert reloaded.m210_plazo.to_resolution() == expected


def test_m210_advisory_uses_supplied_authority_without_second_lease(
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unit = _work_unit(operation, "210")
    revision = _revision(unit, values={"base_imponible": Decimal("900.00")}, tipo_renta_code="01")
    expected = calculated_m210_plazo_resolution(
        work_unit=unit, revision=revision, workflow_profile=_profile(), operation=operation
    )
    assert expected is not None

    def _no_fallback() -> None:
        raise AssertionError("M210 advisory opened a second authority operation")

    monkeypatch.setattr(result_disposition_resolution, "bundled_indexed_authority", _no_fallback)

    facts = build_modelo_lifecycle_advisories(
        work_unit=unit, revision=revision, workflow_profile=_profile(), operation=operation
    )

    assert facts.m210_plazo is not None
    assert facts.m210_plazo.to_resolution() == expected


def test_public_advisories_refuse_mismatched_form_and_malformed_facts() -> None:
    with pytest.raises(ValidationError):
        Modelo184SocioHandoffV1(
            nif="12345678A",
            nombre="Ana",
            porcentaje="NaN",
            importe="10.00",
            code="handoff",
            target_casilla="1577",
            legal_refs="law",
        )
    with pytest.raises(ValidationError):
        Modelo184SocioHandoffV1(
            nif="12345678A",
            nombre="Ana",
            porcentaje="101",
            importe="10.00",
            code="handoff",
            target_casilla="1577",
            legal_refs="law",
        )
    with pytest.raises(ValidationError):
        ModeloM210PlazoAdvisoryV1(
            filing_year=2025,
            period="0A",
            resultado="I",
            deadline_window_id="window",
            opens_on="2025-04-31",
            closes_on="2025-05-01",
            legal_refs="law",
            source_refs="source",
        )
    with pytest.raises(ValidationError):
        ModeloLifecycleAdvisories(
            work_unit_id="a" * 64,
            calculation_revision_id="b" * 64,
            modelo="184",
            filing_year=2025,
            period="0A",
            m210_plazo=ModeloM210PlazoAdvisoryV1(
                filing_year=2025,
                period="0A",
                resultado="I",
                deadline_window_id="window",
                opens_on="2025-04-01",
                closes_on="2025-05-01",
                legal_refs="law",
                source_refs="source",
            ),
        )
    assert strict_model_json_schema(ModeloLifecycleAdvisories)
