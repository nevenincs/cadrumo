"""Amendment labels belong to the selected saved calculation's exact registry scope."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.bindings import CasillaObservation
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.filing_record import derive_filing_record_id
from ...operations.owner import OperationExecutorContext
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..amendment_context_operation import ModeloWorkAmendmentContextRequest, _capture
from .test_filing_record_view_operation import PROFILE, filing_record_view_operation_bundle
from .test_work_amend_correction import _FILED, _unit_and_record

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _CalculationRepository:
    bucket_id = str(PROFILE)

    def __init__(self, revision: CalculationRevision) -> None:
        self._catalogue = CalculationRevisionCatalogue(revisions={revision.calculation_revision_id: revision})

    def load(self, *, operation: PinnedAuthorityOperation) -> CalculationRevisionCatalogue:
        return self._catalogue


def _saved_context(operation: PinnedAuthorityOperation, *, mismatch: str | None = None):
    unit, record = _unit_and_record(operation, "130", "1T")
    revision_id = derive_calculation_revision_id(
        work_unit_id=unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=_FILED,
        source_provenance=(),
        source_issues=(),
        filing_instance_evidence=None,
    )
    scope = RegistrySnapshotRef(
        modelo=str(unit.modelo),
        modelo_year=unit.filing_year,
        period=unit.period.registry_token,
        revision_id=unit.revision_id,
    )
    if mismatch is not None:
        changed = {
            "modelo": {"modelo": "131"},
            "year": {"modelo_year": unit.filing_year - 1},
            "period": {"period": "2T"},
            "revision": {"revision_id": "different-registry-revision"},
        }
        scope = scope.model_copy(update=changed[mismatch])
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=unit.work_unit_id,
        registry_snapshot_ref=scope,
        state=CalculationRevisionState.BORRADOR,
        casilla_values=_FILED,
        observations=tuple(
            CasillaObservation(casilla_id=key, value=value, legal_refs=("saved-law",), source_refs=("saved-source",))
            for key, value in _FILED.items()
        ),
        source_provenance=(),
        source_issues=(),
        filing_instance_evidence=None,
        created_at=record.filed_at,
        updated_at=record.filed_at,
    )
    record = record.model_copy(
        update={
            "calculation_revision_id": revision_id,
            "filing_record_id": derive_filing_record_id(
                work_unit_id=unit.work_unit_id,
                calculation_revision_id=revision_id,
                filed_by=record.filed_by,
            ),
        }
    )
    unit = unit.model_copy(
        update={
            "current_calculation_revision_id": "d" * 64,
            "filed_calculation_revision_id": revision_id,
            "current_filing_record_id": record.filing_record_id,
        }
    )
    bundle = filing_record_view_operation_bundle(unit=unit, record=record)
    object.__setattr__(bundle, "calculation", _CalculationRepository(revision))
    request = ModeloWorkAmendmentContextRequest(
        profile_id=PROFILE,
        filing_record_id=record.filing_record_id,
        output_language=OutputLanguage.EN,
    )
    context = cast(OperationExecutorContext, cast(object, SimpleNamespace(authority_operation=operation)))
    return request, bundle, context


@pytest.mark.parametrize("mismatch", ("modelo", "year", "period", "revision"))
def test_amendment_context_refuses_current_labels_for_a_different_saved_scope(
    operation: PinnedAuthorityOperation,
    mismatch: str,
) -> None:
    request, bundle, context = _saved_context(operation, mismatch=mismatch)

    with pytest.raises(ProfileAccessRefusedError) as refused:
        _capture(request, bundle, context)

    assert refused.value.reason is AccessDenialCode.OPERATION_DENIED


def test_same_scope_context_keeps_selected_saved_figures_even_when_current_head_differs(
    operation: PinnedAuthorityOperation,
) -> None:
    request, bundle, context = _saved_context(operation)

    result = _capture(request, bundle, context)

    assert result.correction is not None
    assert result.correction.filed.filing_record_id == request.filing_record_id
    assert result.calculation.calculation_revision_id == result.record.calculation_revision_id
    assert {row.casilla_id: row.filed_value for row in result.correction.rows} == {"01": "1000", "02": "250"}
