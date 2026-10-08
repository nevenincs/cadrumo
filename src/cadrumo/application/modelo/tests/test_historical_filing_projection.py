"""Historical content uses the selected saved revision even after observations change."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.casilla_id import validated_casilla_id
from ....domain.calculations.registry.bindings import CasillaObservation
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    CalculationSourceIssue,
    derive_calculation_revision_id,
)
from ....domain.modelos.filing_record import derive_filing_record_id
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..filing_record_view_operation import ModeloFilingRecordViewRequest, _capture
from ..historical_filing_projection import ModeloHistoricalFilingContentProjection, project_historical_filing_content
from .test_filing_record_view_operation import _PROFILE, _bundle, _Repository, _source

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _revision() -> CalculationRevision:
    unit, _record = _source()
    casilla_id = validated_casilla_id("01", surface="saved filing test")
    outputs = {casilla_id: Decimal("7.125")}
    issues = (
        CalculationSourceIssue(
            reason="unresolved_binding",
            binding_source=None,
            message="Saved missing source",
            casilla_id=casilla_id,
        ),
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=outputs,
        source_provenance=(),
        source_issues=issues,
        filing_instance_evidence=None,
    )
    now = datetime(2026, 4, 10, 9, tzinfo=UTC)
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="303", modelo_year=2026, period="1T", revision_id="saved-2026"
        ),
        state=CalculationRevisionState.BORRADOR,
        casilla_values=outputs,
        observations=(
            CasillaObservation(
                casilla_id=casilla_id,
                value=Decimal("7.125"),
                legal_refs=("saved-law",),
                source_refs=("saved-publication",),
            ),
        ),
        source_provenance=(),
        source_issues=issues,
        filing_instance_evidence=None,
        created_at=now,
        updated_at=now,
    )


def test_real_filing_view_selects_historical_content_and_keeps_current_layers_separate() -> None:
    revision = _revision()
    unit, source_record = _source()
    record = source_record.model_copy(
        update={
            "calculation_revision_id": revision.calculation_revision_id,
            "filing_record_id": derive_filing_record_id(
                work_unit_id=revision.work_unit_id,
                calculation_revision_id=revision.calculation_revision_id,
                filed_by=source_record.filed_by,
            ),
        }
    )
    bundle = _bundle(record=record, unit=unit)
    object.__setattr__(
        bundle,
        "calculation",
        _Repository(
            str(_PROFILE),
            CalculationRevisionCatalogue(
                revisions={revision.calculation_revision_id: revision},
            ),
        ),
    )
    result = _capture(
        ModeloFilingRecordViewRequest(profile_id=_PROFILE, filing_record_id=record.filing_record_id), bundle
    )
    historical = result.historical_content
    assert historical.availability == "available"
    assert historical.observations[0].value == "7.125"
    assert historical.observations[0].legal_refs == ("saved-law",)
    assert historical.source_issues == revision.source_issues
    assert historical.registry_snapshot_ref is not None
    assert historical.registry_snapshot_ref.revision_id == revision.registry_snapshot_ref.revision_id
    assert result.observation_layers.official is not None
    assert result.observation_layers.official.casilla_values == (("01", "10.25"),)
    assert ModeloHistoricalFilingContentProjection.model_validate_json(historical.model_dump_json()) == historical


def test_missing_saved_revision_cannot_substitute_current_values() -> None:
    _unit, record = _source()
    result = _capture(
        ModeloFilingRecordViewRequest(profile_id=_PROFILE, filing_record_id=record.filing_record_id), _bundle()
    )
    assert result.historical_content.availability == "missing"
    assert result.historical_content.observations == ()
    with pytest.raises(ValidationError):
        ModeloHistoricalFilingContentProjection(
            calculation_revision_id=record.calculation_revision_id,
            availability="missing",
            state=CalculationRevisionState.BORRADOR,
        )


@pytest.mark.parametrize("defect", ["revision", "coordinate", "values", "observation"])
def test_historical_content_refuses_substitution_and_corrupt_saved_content(defect: str) -> None:
    revision = _revision()
    _unit, source_record = _source()
    record = source_record.model_copy(
        update={
            "calculation_revision_id": revision.calculation_revision_id,
            "filing_record_id": derive_filing_record_id(
                work_unit_id=revision.work_unit_id,
                calculation_revision_id=revision.calculation_revision_id,
                filed_by=source_record.filed_by,
            ),
        }
    )
    if defect == "revision":
        changed = revision.model_copy(update={"calculation_revision_id": "b" * 64})
    elif defect == "coordinate":
        changed = revision.model_copy(
            update={"registry_snapshot_ref": revision.registry_snapshot_ref.model_copy(update={"period": "2T"})}
        )
    elif defect == "values":
        changed = revision.model_copy(
            update={"casilla_values": {validated_casilla_id("01", surface="test"): Decimal("999")}}
        )
    else:
        changed = revision.model_copy(
            update={"observations": (revision.observations[0].model_copy(update={"value": Decimal("999")}),)}
        )
    with pytest.raises(ProfileAccessRefusedError):
        project_historical_filing_content(record, changed)
