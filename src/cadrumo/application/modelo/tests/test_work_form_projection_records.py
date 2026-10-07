"""Saved activity projections preserve occurrence, numeric zero and missing data."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from cadrumo.core.filing_projection_ref import M303RegimenSimplificadoFact
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.form_projection_fields import resolve_form_projection_fields
from cadrumo.domain.calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from cadrumo.domain.calculations.registry.m303_schema_vocabulary import m303_regime_composition_simplified_scope
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormContextFieldBlock,
    FormRepeatingColumn,
    FormRepeatingGroupBlock,
)
from cadrumo.domain.filing_evidence import FilingEvidenceReference
from cadrumo.domain.iva.regimen_simplificado_rows import (
    ActividadNoAgricolaSimplificado,
    EntradaModuloSimplificado,
    HechoActividadSimplificado,
    LorcaActivityEligibility,
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
)
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.modelos.calculation_revision_m303_evidence import (
    M303Exonerado390ActivityRowEvidence,
    M303Exonerado390EndpointEvidence,
    M303Exonerado390FilingEvidence,
)
from cadrumo.domain.modelos.calculation_revision_m303_handoff import (
    FilingInstanceEvidence,
    M303FilingInstanceEvidence,
)

from ...calculations.tests.filing_evidence import general_m303_filing_evidence, regimen_simplificado_filing_evidence
from ..work_form_context_values import form_context_value
from ..work_form_records import saved_form_records

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _annual_block(snapshot: RegistrySnapshot, number: int) -> FormContextFieldBlock:
    return FormContextFieldBlock(
        id=f"annual-{number}",
        export_layout_id=snapshot.revision.export_layouts[0].id,
        export_record_id="m303-exonerado-390",
        export_field_id=f"m303-2026.dp30304.f{number:03}",
        heading_key="test.form.annual",
        official_heading="Actividad anual",
    )


@pytest.fixture
def annual_saved(operation: PinnedAuthorityOperation):
    snapshot = operation.snapshot("303", filing_year=2026, period="4T")
    envelope = general_m303_filing_evidence(
        Period.from_year_and_code(2026, "4T"), reference="test:annual-form", operation=operation
    )
    reference = FilingEvidenceReference(reference="test:annual-form")
    annual = M303Exonerado390FilingEvidence(
        applicable=True,
        applicability_reference=reference,
        endpoints=(
            M303Exonerado390EndpointEvidence(casilla_id="80", value=Decimal("100"), evidence_reference=reference),
        ),
        activity_rows=(
            M303Exonerado390ActivityRowEvidence(
                slot=1, codigo_actividad="A03", epigrafe_iae="6732", evidence_reference=reference
            ),
        ),
        operaciones_terceros_declarables=False,
        operaciones_terceros_reference=reference,
    )
    envelope = envelope.model_copy(update={"m303": envelope.m303.model_copy(update={"exonerado_390": annual})})
    return snapshot, _revision(snapshot, envelope)


def test_annual_context_reads_exact_slots_and_preserves_explicit_false(annual_saved):
    snapshot, revision = annual_saved
    values = [form_context_value(snapshot, _annual_block(snapshot, n), revision=revision) for n in range(6, 19)]
    assert values == ["A03", "6732", *([None] * 10), False]
    assert form_context_value(snapshot, _annual_block(snapshot, 6)) is None


def test_annual_context_missing_and_nonapplicable_evidence_stay_unknown(annual_saved):
    snapshot, revision = annual_saved
    envelope = revision.filing_instance_evidence
    assert envelope is not None
    for annual in (
        None,
        envelope.m303.exonerado_390.model_copy(
            update={
                "applicable": False,
                "endpoints": (),
                "activity_rows": (),
                "operaciones_terceros_declarables": None,
                "operaciones_terceros_reference": None,
            }
        ),
    ):
        saved = _revision(
            snapshot, envelope.model_copy(update={"m303": envelope.m303.model_copy(update={"exonerado_390": annual})})
        )
        assert form_context_value(snapshot, _annual_block(snapshot, 18), revision=saved) is None


def test_annual_context_rejects_foreign_saved_coordinate_and_period(annual_saved):
    snapshot, revision = annual_saved
    foreign = revision.model_copy(
        update={"registry_snapshot_ref": revision.registry_snapshot_ref.model_copy(update={"period": "3T"})}
    )
    with pytest.raises(RegistryValidationError, match="another registry coordinate"):
        form_context_value(snapshot, _annual_block(snapshot, 6), revision=foreign)
    envelope = revision.filing_instance_evidence
    corrupt = revision.model_copy(
        update={
            "filing_instance_evidence": envelope.model_copy(
                update={"m303": envelope.m303.model_copy(update={"period": Period.from_year_and_code(2026, "3T")})}
            )
        }
    )
    with pytest.raises(RegistryValidationError, match="another filing period"):
        form_context_value(snapshot, _annual_block(snapshot, 6), revision=corrupt)


def test_annual_context_rejects_incomplete_projection_population(annual_saved):
    snapshot, revision = annual_saved
    export = snapshot.revision.export_layouts[0]
    record = next(record for record in export.records if record.id == "m303-exonerado-390")
    changed = record.model_copy(
        update={"fields": tuple(field for field in record.fields if field.id != "m303-2026.dp30304.f017")}
    )
    export = export.model_copy(
        update={"records": tuple(changed if item.id == record.id else item for item in export.records)}
    )
    broken = snapshot.model_copy(
        update={"revision": snapshot.revision.model_copy(update={"export_layouts": (export,)})}
    )
    with pytest.raises(RegistryValidationError, match="six activity-code/IAE pairs"):
        form_context_value(broken, _annual_block(broken, 6), revision=revision)


def _block(*field_numbers: int) -> FormRepeatingGroupBlock:
    return FormRepeatingGroupBlock(
        id="activity",
        row_source="export_record",
        export_record_id="m303-regimen-simplificado",
        max_rows=3,
        columns=tuple(
            FormRepeatingColumn(
                key=f"field-{n}",
                heading_key=f"test.form.field-{n}",
                official_heading=f"Dato {n}",
                export_field_id=f"m303-2026.dp30302.f{n:03}",
            )
            for n in field_numbers
        ),
    )


def _revision(snapshot: RegistrySnapshot, evidence: FilingInstanceEvidence | None) -> CalculationRevision:
    work_id = "a" * 64
    now = datetime(2026, 7, 1, tzinfo=UTC)
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            source_transaction_ids=(),
            filing_instance_evidence=evidence,
            source_provenance=(),
        ),
        work_unit_id=work_id,
        registry_snapshot_ref=snapshot.snapshot_ref,
        state=CalculationRevisionState.BORRADOR,
        created_at=now,
        updated_at=now,
        filing_instance_evidence=evidence,
        source_provenance=(),
    )


@pytest.fixture
def snapshot(operation: PinnedAuthorityOperation) -> RegistrySnapshot:
    return operation.snapshot("303", filing_year=2026, period="2T")


@pytest.fixture
def saved(snapshot: RegistrySnapshot, operation: PinnedAuthorityOperation) -> CalculationRevision:
    return _saved(snapshot, operation)


def _saved(
    snapshot: RegistrySnapshot, operation: PinnedAuthorityOperation, *, activity_count: int = 3
) -> CalculationRevision:
    year = snapshot.filing_year
    period = Period.from_year_and_code(year, "2T")
    scope = M303RegimenSimplificadoScopeDecision(scope=m303_regime_composition_simplified_scope("simplified"))
    regimen = resolve_m303_regimen_simplificado_snapshot(registry_snapshot=snapshot, scope_decision=scope)
    annual = tuple(activity for activity in regimen.orden.activities if activity.kind == "no_agricola")[:activity_count]
    assert len(annual) == activity_count
    reference = FilingEvidenceReference(reference=regimen.orden.source_ref)
    activities = []
    for index, activity in enumerate(annual, 1):
        assert activity.iae_epigrafe is not None
        activities.append(
            ActividadNoAgricolaSimplificado(
                orden_id=activity.orden_id,
                ejercicio=year,
                activity_id=activity.orden_id,
                iae_epigrafe=activity.iae_epigrafe,
                auxiliary_activity_indicator=activity.auxiliary_activity_indicator,
                modulos=tuple(
                    EntradaModuloSimplificado(
                        module_identity=module.identity,
                        declared_quantity=Decimal(index - 1),
                        evidence_reference=reference,
                    )
                    for module in activity.modulos
                ),
                facts=tuple(
                    HechoActividadSimplificado(
                        fact=M303RegimenSimplificadoFact.CUOTA_DEVENGADA_OPERACIONES_CORRIENTES,
                        value=Decimal("1"),
                        evidence_reference=reference,
                    )
                    for _ in activity.applicable_fact_identities
                ),
                lorca_eligibility=LorcaActivityEligibility(eligible=False, evidence_reference=reference),
                evidence_reference=reference,
            )
        )
    simplified = regimen_simplificado_filing_evidence(
        period=period,
        scope_decision=scope,
        rows=RegimenSimplificadoFilingRows(ejercicio=year, activities=tuple(activities)),
        regimen_snapshot=regimen,
        dana_eligibility=None,
        operation=operation,
    )
    return _revision(
        snapshot,
        FilingInstanceEvidence(
            m303=M303FilingInstanceEvidence(
                period=period,
                joint_return_elected=False,
                annual_volume_nonzero=None,
                insolvency=None,
                exonerado_390=None,
                regimen_simplificado=simplified,
            )
        ),
    )


def test_saved_modules_preserve_page_occurrence_and_zero(snapshot, saved):
    # First and second activity, module-one quantity and calculated amount.
    block = _block(24, 25, 52, 53)
    known, rows = saved_form_records(snapshot=snapshot, revision=saved, block=block, column_casillas=(None,) * 4)
    assert known and [row.index for row in rows] == [1, 2]
    assert [row.values[0] for row in rows] == [Decimal("0"), Decimal("2")]
    assert rows[0].values[2] == Decimal("1")
    assert rows[1].values[2:] == (None, None)
    evidence = saved.filing_instance_evidence.m303.regimen_simplificado
    assert rows[0].values[1] == evidence.calculation_result.activities[0].module_results[0].cuota_devengada
    assert rows[1].values[1] == evidence.calculation_result.activities[2].module_results[0].cuota_devengada


def test_single_historical_record_reads_one_occurrence_and_refuses_overflow(operation):
    snapshot = operation.snapshot("303", filing_year=2022, period="2T")
    block = _block(24, 25)
    columns = []
    for column in block.columns:
        assert column.export_field_id is not None
        columns.append(column.model_copy(update={"export_field_id": column.export_field_id.replace("2026", "2022")}))
    block = block.model_copy(
        update={
            "max_rows": 1,
            "columns": tuple(columns),
        }
    )
    assert len(resolve_form_projection_fields(snapshot.revision, block)) == 2
    known, rows = saved_form_records(
        snapshot=snapshot,
        revision=_saved(snapshot, operation, activity_count=1),
        block=block,
        column_casillas=(None,) * 2,
    )
    assert known and len(rows) == 1 and rows[0].index == 1
    assert rows[0].values[0] == Decimal("0")
    for capacity in (None, 2):
        with pytest.raises(RegistryValidationError, match="bounded to one row"):
            resolve_form_projection_fields(snapshot.revision, block.model_copy(update={"max_rows": capacity}))
    with pytest.raises(RegistryValidationError, match="record capacity"):
        saved_form_records(
            snapshot=snapshot, revision=_saved(snapshot, operation), block=block, column_casillas=(None,) * 2
        )


def test_missing_evidence_is_unknown_but_not_claimed_scope_is_known_empty(snapshot, operation):
    block = _block(24)
    assert saved_form_records(
        snapshot=snapshot, revision=_revision(snapshot, None), block=block, column_casillas=(None,)
    ) == (False, ())
    evidence = general_m303_filing_evidence(
        Period.from_year_and_code(2026, "2T"), reference="test:form", operation=operation
    )
    assert saved_form_records(
        snapshot=snapshot, revision=_revision(snapshot, evidence), block=block, column_casillas=(None,)
    ) == (True, ())


def test_foreign_saved_coordinate_is_rejected(snapshot, saved):
    other = saved.model_copy(
        update={"registry_snapshot_ref": saved.registry_snapshot_ref.model_copy(update={"period": "3T"})}
    )
    with pytest.raises(RegistryValidationError, match="another registry coordinate"):
        saved_form_records(snapshot=snapshot, revision=other, block=_block(24), column_casillas=(None,))


def test_foreign_evidence_period_is_rejected(snapshot, saved):
    facts = saved.filing_instance_evidence.m303.model_copy(update={"period": Period.from_year_and_code(2026, "3T")})
    corrupt = saved.model_copy(
        update={"filing_instance_evidence": saved.filing_instance_evidence.model_copy(update={"m303": facts})}
    )
    with pytest.raises(RegistryValidationError, match="another filing period"):
        saved_form_records(snapshot=snapshot, revision=corrupt, block=_block(24), column_casillas=(None,))


def test_changed_record_design_pin_is_rejected(snapshot, saved):
    facts = saved.filing_instance_evidence.m303
    evidence = facts.regimen_simplificado
    regimen = evidence.regimen_snapshot
    altered = regimen.record_design.model_copy(update={"sha256": "0" * 64})
    regimen = regimen.model_copy(update={"record_design": altered})
    evidence = evidence.model_copy(update={"regimen_snapshot": regimen})
    facts = facts.model_copy(update={"regimen_simplificado": evidence})
    corrupt = saved.model_copy(
        update={"filing_instance_evidence": saved.filing_instance_evidence.model_copy(update={"m303": facts})}
    )
    with pytest.raises(RegistryValidationError, match="record-design source"):
        saved_form_records(snapshot=snapshot, revision=corrupt, block=_block(24), column_casillas=(None,))


@pytest.mark.parametrize("number", [1, 80, 999])
def test_non_projection_or_missing_endpoint_is_rejected(snapshot, number):
    with pytest.raises(RegistryValidationError, match="typed projection"):
        resolve_form_projection_fields(snapshot.revision, _block(number))


def test_one_column_cannot_have_two_value_owners():
    with pytest.raises(ValidationError, match="both a casilla and an export field"):
        FormRepeatingColumn(key="x", heading_key="test.form.x", casilla_id="47", export_field_id="field")


@pytest.fixture
def projection_block() -> FormRepeatingGroupBlock:
    return _block(24, 25, 52, 53)
