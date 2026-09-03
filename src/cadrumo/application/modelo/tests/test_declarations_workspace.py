"""Contract tests for the safe, preloaded Declarations projection."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....core.period import Period
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.filing_record import (
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordCatalogue,
    derive_filing_record_id,
)
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ..declarations_workspace import (
    DeclarationsLifecycleKind,
    DeclarationsSanitizedLifecycleFactV1,
    DeclarationsWorkspaceAvailability,
    DeclarationsWorkspaceProjectionError,
    DeclarationsWorkspaceSource,
    DeclarationsWorkspaceZone,
    DeclarationsWorkspaceZoneObservationV1,
    project_declarations_workspace,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "11111111-1111-4111-8111-111111111111"
_OTHER_BUCKET = "22222222-2222-4222-8222-222222222222"
_T0 = datetime(2026, 1, 2, 9, tzinfo=UTC)
_T1 = datetime(2026, 1, 3, 10, tzinfo=UTC)
_T2 = datetime(2026, 1, 4, 11, tzinfo=UTC)
_SECRET_NAME = "Taxpayer confidential declaration label"
_SECRET_ACTOR = "private-operator"
_SECRET_NOTES = "private filing notes"
_SECRET_REFERENCE = "AEAT-private-reference"
_SECRET_NIF = "12345678Z"


def _revision_id(work_unit_id: str) -> str:
    return derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )


def _filed_snapshot() -> tuple[WorkUnitCatalogue, CalculationRevisionCatalogue, ModeloRecordCatalogue]:
    period = Period.from_year_and_code(2026, "1T")
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET,
        modelo="130",
        filing_year=2026,
        period=period,
        revision_id="2026",
    )
    calculation_revision_id = _revision_id(work_unit_id)
    filing_record_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=calculation_revision_id,
        filed_by=_SECRET_ACTOR,
        member_nif=_SECRET_NIF,
    )
    unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=_BUCKET,
        modelo="130",
        filing_year=2026,
        period=period,
        revision_id="2026",
        name=_SECRET_NAME,
        created_at=_T0,
        updated_at=_T2,
        current_calculation_revision_id=calculation_revision_id,
        filed_calculation_revision_id=calculation_revision_id,
        current_filing_record_id=filing_record_id,
    )
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.PRESENTADO,
        input_values_by_casilla_id={},
        casilla_values={},
        created_at=_T0,
        updated_at=_T2,
        verified_at=_T1,
        verified_by=_SECRET_ACTOR,
        filed_at=_T2,
        filed_by=_SECRET_ACTOR,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    record = ModeloRecord(
        filing_record_id=filing_record_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=calculation_revision_id,
        bucket_id=_BUCKET,
        modelo="130",
        filing_year=2026,
        period=period,
        member_nif=_SECRET_NIF,
        filed_at=_T2,
        filed_by=_SECRET_ACTOR,
        notes=_SECRET_NOTES,
        aeat_accepted=True,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            reference_id=_SECRET_REFERENCE,
            imported_at=_T2,
        ),
    )
    return (
        WorkUnitCatalogue.from_work_units((unit,)),
        CalculationRevisionCatalogue(revisions={calculation_revision_id: revision}),
        ModeloRecordCatalogue(records={filing_record_id: record}),
    )


def _observations(
    *availability: DeclarationsWorkspaceAvailability,
) -> tuple[DeclarationsWorkspaceZoneObservationV1, ...]:
    values = availability or (DeclarationsWorkspaceAvailability.AVAILABLE,) * 3
    return tuple(
        DeclarationsWorkspaceZoneObservationV1(
            zone=zone,
            availability=state,
            observed_at=_T2
            if state in {DeclarationsWorkspaceAvailability.AVAILABLE, DeclarationsWorkspaceAvailability.STALE}
            else None,
            reason_code=None if state is DeclarationsWorkspaceAvailability.AVAILABLE else "declarations.source.unavailable",
        )
        for zone, state in zip(DeclarationsWorkspaceZone, values, strict=True)
    )


def _fact(work_unit_id: str, *, fact_id: str = "fact-1") -> DeclarationsSanitizedLifecycleFactV1:
    return DeclarationsSanitizedLifecycleFactV1(
        fact_id=fact_id,
        work_unit_id=work_unit_id,
        occurred_at=_T2,
        kind=DeclarationsLifecycleKind.FILED,
    )


def test_projection_preserves_exact_zone_source_state_and_count_matrix() -> None:
    work, revisions, filings = _filed_snapshot()
    work_unit_id = next(iter(work.values())).work_unit_id
    projection = project_declarations_workspace(
        bucket_id=_BUCKET,
        work_units=work,
        calculation_revisions=revisions,
        filing_records=filings,
        lifecycle_facts=(_fact(work_unit_id),),
        zone_observations=_observations(),
    )

    assert tuple((row.zone, row.sources, row.availability, row.item_count) for row in projection.zones) == (
        (
            DeclarationsWorkspaceZone.DECLARATIONS,
            (DeclarationsWorkspaceSource.LOCAL_DECLARATIONS,),
            DeclarationsWorkspaceAvailability.AVAILABLE,
            1,
        ),
        (
            DeclarationsWorkspaceZone.CALCULATION_REVISIONS,
            (DeclarationsWorkspaceSource.LOCAL_DECLARATIONS, DeclarationsWorkspaceSource.LOCAL_CALCULATIONS),
            DeclarationsWorkspaceAvailability.AVAILABLE,
            1,
        ),
        (
            DeclarationsWorkspaceZone.FILING_HISTORY,
            (
                DeclarationsWorkspaceSource.LOCAL_DECLARATIONS,
                DeclarationsWorkspaceSource.LOCAL_CALCULATIONS,
                DeclarationsWorkspaceSource.LOCAL_FILINGS,
                DeclarationsWorkspaceSource.LOCAL_LIFECYCLE,
                DeclarationsWorkspaceSource.AEAT_EVIDENCE,
            ),
            DeclarationsWorkspaceAvailability.AVAILABLE,
            2,
        ),
    )
    filing = projection.filings[0]
    assert filing.local_status.value == "vigente"
    assert filing.aeat_accepted is True
    assert filing.evidence_kind is ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF


def test_sensitive_payload_and_protected_identities_never_serialize_or_repr() -> None:
    work, revisions, filings = _filed_snapshot()
    unit = next(iter(work.values()))
    revision = next(iter(revisions.values()))
    filing = next(iter(filings.records.values()))
    projection = project_declarations_workspace(
        bucket_id=_BUCKET,
        work_units=work,
        calculation_revisions=revisions,
        filing_records=filings,
        lifecycle_facts=(_fact(unit.work_unit_id, fact_id="private-event-id"),),
        zone_observations=_observations(),
    )
    exposed = projection.model_dump_json() + repr(projection)
    for secret in (
        _BUCKET,
        unit.work_unit_id,
        revision.calculation_revision_id,
        filing.filing_record_id,
        _SECRET_NAME,
        _SECRET_ACTOR,
        _SECRET_NOTES,
        _SECRET_REFERENCE,
        _SECRET_NIF,
        "private-event-id",
    ):
        assert secret not in exposed


def test_unavailable_never_captured_and_stale_are_not_false_empty() -> None:
    work, revisions, filings = _filed_snapshot()
    unit = next(iter(work.values()))
    projection = project_declarations_workspace(
        bucket_id=_BUCKET,
        work_units=work,
        calculation_revisions=revisions,
        filing_records=filings,
        lifecycle_facts=(_fact(unit.work_unit_id),),
        zone_observations=_observations(
            DeclarationsWorkspaceAvailability.UNAVAILABLE,
            DeclarationsWorkspaceAvailability.NEVER_CAPTURED,
            DeclarationsWorkspaceAvailability.STALE,
        ),
    )
    assert projection.declarations == ()
    assert projection.calculation_revisions == ()
    assert len(projection.filings) == len(projection.lifecycle) == 1
    assert tuple(zone.item_count for zone in projection.zones) == (None, None, 2)
    assert projection.zones[2].observed_at == _T2


def test_available_empty_is_measured_zero_and_deterministic() -> None:
    arguments = dict(
        bucket_id=_BUCKET,
        work_units=WorkUnitCatalogue(),
        calculation_revisions=CalculationRevisionCatalogue(),
        filing_records=ModeloRecordCatalogue(),
        lifecycle_facts=(),
        zone_observations=_observations(),
    )
    first = project_declarations_workspace(**arguments)
    second = project_declarations_workspace(**arguments)
    assert tuple(zone.item_count for zone in first.zones) == (0, 0, 0)
    assert first == second
    assert first.model_dump_json() == second.model_dump_json()


def test_foreign_bucket_refuses_before_any_projection() -> None:
    work, revisions, filings = _filed_snapshot()
    unit = next(iter(work.values())).model_copy(update={"bucket_id": _OTHER_BUCKET})
    with pytest.raises(DeclarationsWorkspaceProjectionError, match="foreign bucket"):
        project_declarations_workspace(
            bucket_id=_BUCKET,
            work_units=WorkUnitCatalogue.model_construct(work_units={unit.work_unit_id: unit}),
            calculation_revisions=revisions,
            filing_records=filings,
            lifecycle_facts=(),
            zone_observations=_observations(),
        )


def test_orphan_revision_and_duplicate_lifecycle_identity_refuse() -> None:
    work, revisions, filings = _filed_snapshot()
    unit = next(iter(work.values()))
    revision = next(iter(revisions.values()))
    orphan_id = _revision_id("a" * 64)
    orphan = revision.model_copy(
        update={"calculation_revision_id": orphan_id, "work_unit_id": "a" * 64},
    )
    with pytest.raises(DeclarationsWorkspaceProjectionError, match="has no declaration"):
        project_declarations_workspace(
            bucket_id=_BUCKET,
            work_units=work,
            calculation_revisions=CalculationRevisionCatalogue(revisions={orphan_id: orphan}),
            filing_records=ModeloRecordCatalogue(),
            lifecycle_facts=(),
            zone_observations=_observations(),
        )
    duplicate = _fact(unit.work_unit_id)
    with pytest.raises(DeclarationsWorkspaceProjectionError, match="duplicate identities"):
        project_declarations_workspace(
            bucket_id=_BUCKET,
            work_units=work,
            calculation_revisions=revisions,
            filing_records=filings,
            lifecycle_facts=(duplicate, duplicate),
            zone_observations=_observations(),
        )


def test_defining_module_has_no_io_adapter_entrypoint_or_network_import() -> None:
    path = Path(__file__).parents[1] / "declarations_workspace.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not any(
        forbidden in imported
        for imported in imports
        for forbidden in ("adapters", "entrypoints", "pathlib", "requests", "httpx", "socket")
    )
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert calls.isdisjoint({"open", "print", "input"})
