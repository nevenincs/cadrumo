"""Adversarial contract tests for the safe AEAT Sync workspace projection."""

from __future__ import annotations

import ast
import pickle
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from ...operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE
from ...operations.registry import OperationPublicContractSetV1
from ...user_profile.censal_operation import (
    CENSAL_OPERATION_DEFINITION,
    build_censal_operation_registration,
)
from ..workspace import (
    AeatSyncCapabilityAuthority,
    AeatSyncCensusCategory,
    AeatSyncCensusStatus,
    AeatSyncDiscrepancyKind,
    AeatSyncOverviewArea,
    AeatSyncReconciliationState,
    AeatSyncSourceState,
    AeatSyncWorkspaceAvailability,
    AeatSyncWorkspaceCapabilityV1,
    AeatSyncWorkspaceCensusInputV1,
    AeatSyncWorkspaceOverviewInputV1,
    AeatSyncWorkspaceProjectionError,
    AeatSyncWorkspaceProvenanceV1,
    AeatSyncWorkspaceReconciliationInputV1,
    AeatSyncWorkspaceSource,
    AeatSyncWorkspaceSourceObservationV1,
    AeatSyncWorkspaceZone,
    project_aeat_sync_workspace,
)
from ....core.period import Period
from ....domain.modelos.codes import ModeloCode

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "11111111-1111-4111-8111-111111111111"
_OTHER_BUCKET = "22222222-2222-4222-8222-222222222222"
_SUBJECT = "subject:synthetic"
_NOW = datetime(2026, 1, 4, 11, tzinfo=UTC)
_SECRET = "protected-sentinel-12345678Z"


def _contracts() -> OperationPublicContractSetV1:
    registration = build_censal_operation_registration(CENSAL_OPERATION_DEFINITION)
    return OperationPublicContractSetV1.build((registration.contract,))


def _sources(
    *,
    aeat_census: AeatSyncWorkspaceAvailability = AeatSyncWorkspaceAvailability.AVAILABLE,
) -> tuple[AeatSyncWorkspaceSourceObservationV1, ...]:
    values = []
    for source in AeatSyncWorkspaceSource:
        availability = (
            aeat_census if source is AeatSyncWorkspaceSource.AEAT_CENSUS else AeatSyncWorkspaceAvailability.AVAILABLE
        )
        observable = availability in {
            AeatSyncWorkspaceAvailability.AVAILABLE,
            AeatSyncWorkspaceAvailability.STALE,
        }
        values.append(
            AeatSyncWorkspaceSourceObservationV1(
                source=source,
                availability=availability,
                observed_at=_NOW if observable else None,
                item_count=1 if observable else None,
                refusal=None if availability is AeatSyncWorkspaceAvailability.AVAILABLE else "aeat.sync.source.blocked",
            )
        )
    return tuple(values)


def _provenance(identity: str, *, bucket: str = _BUCKET) -> AeatSyncWorkspaceProvenanceV1:
    return AeatSyncWorkspaceProvenanceV1(
        bucket_id=bucket,
        subject_key=_SUBJECT,
        source_record_id=identity,
    )


def _overview(
    *,
    area: AeatSyncOverviewArea = AeatSyncOverviewArea.CENSUS,
    identity: str = "overview:census",
    actions: tuple[AeatSyncWorkspaceCapabilityV1, ...] = (),
) -> AeatSyncWorkspaceOverviewInputV1:
    return AeatSyncWorkspaceOverviewInputV1(
        provenance=_provenance(identity),
        area=area,
        local_state=AeatSyncSourceState.PRESENT,
        aeat_state=AeatSyncSourceState.PRESENT,
        local_observed_at=_NOW,
        aeat_observed_at=_NOW,
        discrepancy_kind=AeatSyncDiscrepancyKind.NONE,
        supported_actions=actions,
    )


def _project(**kwargs: object):
    return project_aeat_sync_workspace(
        bucket_id=_BUCKET,
        subject_key=_SUBJECT,
        source_observations=_sources(),
        action_catalogue=OPERATOR_ACTION_CATALOGUE,
        operation_contracts=_contracts(),
        **kwargs,
    )


def test_package_initializer_is_inert_and_tests_use_defining_module() -> None:
    package = Path(__file__).parents[1] / "__init__.py"
    tree = ast.parse(package.read_text(encoding="utf-8"))
    assert not any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in tree.body)


def test_sources_keep_local_and_aeat_availability_freshness_and_refusal_independent() -> None:
    projection = project_aeat_sync_workspace(
        bucket_id=_BUCKET,
        subject_key=_SUBJECT,
        source_observations=_sources(aeat_census=AeatSyncWorkspaceAvailability.LOCKED),
        action_catalogue=OPERATOR_ACTION_CATALOGUE,
        operation_contracts=_contracts(),
        overview=(_overview(),),
    )
    census_zone = {zone.zone: zone for zone in projection.zones}[AeatSyncWorkspaceZone.CENSUS]
    local, aeat = census_zone.sources
    assert local.availability is AeatSyncWorkspaceAvailability.AVAILABLE
    assert local.observed_at == _NOW and local.item_count == 1 and local.refusal is None
    assert aeat.availability is AeatSyncWorkspaceAvailability.LOCKED
    assert aeat.observed_at is None and aeat.item_count is None
    assert aeat.refusal == "aeat.sync.source.blocked"


def test_protected_inputs_are_not_retainable_by_public_models_repr_pickle_or_internals() -> None:
    source = AeatSyncWorkspaceCensusInputV1(
        provenance=_provenance("census:path"),
        path="tax.address.postcode",
        category=AeatSyncCensusCategory.ADDRESS,
        status=AeatSyncCensusStatus.CONFLICT,
        taxpayer_name=_SECRET,
        nif=_SECRET,
        source_url=_SECRET,
        evidence_identifier=_SECRET,
        custody_identifier=_SECRET,
        document_text=_SECRET,
        raw_evidence={"secret": _SECRET},
        secret=object(),
    )
    projection = _project(census=(source,))
    public_bytes = pickle.dumps(projection)
    assert _SECRET not in repr(projection)
    assert _SECRET.encode() not in public_bytes
    assert _SECRET not in projection.model_dump_json()
    assert "provenance" not in projection.census[0].__dict__
    forbidden = {"nif", "taxpayer_name", "source_url", "raw_evidence", "secret", "bucket_id", "subject_key"}
    for model in (projection, projection.census[0]):
        assert forbidden.isdisjoint(model.__dict__)
        assert forbidden.isdisjoint(type(model).model_fields)


def test_catalogue_and_operation_capabilities_are_admitted_for_exact_area() -> None:
    operation = AeatSyncWorkspaceCapabilityV1(
        authority=AeatSyncCapabilityAuthority.OPERATION,
        reference_id="user-profile.censo-review",
    )
    action = AeatSyncWorkspaceCapabilityV1(
        authority=AeatSyncCapabilityAuthority.OPERATOR_ACTION,
        reference_id="operator.profile.edit",
    )
    projection = _project(overview=(_overview(actions=(operation, action)),))
    assert projection.overview[0].supported_actions == (action, operation)


@pytest.mark.parametrize(
    "capability",
    [
        AeatSyncWorkspaceCapabilityV1(
            authority=AeatSyncCapabilityAuthority.OPERATOR_ACTION,
            reference_id="operator.live.notifications.list",
        ),
        AeatSyncWorkspaceCapabilityV1(
            authority=AeatSyncCapabilityAuthority.OPERATOR_ACTION,
            reference_id="operator.unknown.action",
        ),
        AeatSyncWorkspaceCapabilityV1(
            authority=AeatSyncCapabilityAuthority.OPERATION,
            reference_id="unknown.operation",
        ),
    ],
)
def test_unknown_or_wrong_area_capability_fails_closed(capability: AeatSyncWorkspaceCapabilityV1) -> None:
    with pytest.raises(AeatSyncWorkspaceProjectionError):
        _project(overview=(_overview(actions=(capability,)),))


def test_no_action_reconciliation_refuses_executable_capability() -> None:
    action = AeatSyncWorkspaceCapabilityV1(
        authority=AeatSyncCapabilityAuthority.OPERATOR_ACTION,
        reference_id="operator.profile.archive.reconcile",
    )
    row = AeatSyncWorkspaceReconciliationInputV1(
        provenance=_provenance("reconciliation:303:2026:1T"),
        modelo=ModeloCode("303"),
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        local_state=AeatSyncSourceState.PRESENT,
        aeat_state=AeatSyncSourceState.PRESENT,
        local_observed_at=_NOW,
        aeat_observed_at=_NOW,
        discrepancy_kind=AeatSyncDiscrepancyKind.NONE,
        reconciliation_state=AeatSyncReconciliationState.NO_ACTION,
        supported_actions=(action,),
    )
    with pytest.raises(AeatSyncWorkspaceProjectionError):
        _project(reconciliation=(row,))


def test_provenance_is_required_and_foreign_scope_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AeatSyncWorkspaceCensusInputV1.model_validate({"path": "tax.address", "category": "address", "status": "unset"})
    foreign = AeatSyncWorkspaceCensusInputV1(
        provenance=_provenance("foreign", bucket=_OTHER_BUCKET),
        path="tax.address",
        category=AeatSyncCensusCategory.ADDRESS,
        status=AeatSyncCensusStatus.UNSET,
    )
    with pytest.raises(AeatSyncWorkspaceProjectionError):
        _project(census=(foreign,))


def test_logical_duplicates_are_rejected_despite_distinct_source_ids() -> None:
    with pytest.raises(AeatSyncWorkspaceProjectionError, match="overview areas"):
        _project(overview=(_overview(identity="one"), _overview(identity="two")))
    first = AeatSyncWorkspaceCensusInputV1(
        provenance=_provenance("census:one"),
        path="tax.address",
        category=AeatSyncCensusCategory.ADDRESS,
        status=AeatSyncCensusStatus.UNSET,
    )
    second = AeatSyncWorkspaceCensusInputV1(
        provenance=_provenance("census:two"),
        path="tax.address",
        category=AeatSyncCensusCategory.OTHER,
        status=AeatSyncCensusStatus.CONFLICT,
    )
    with pytest.raises(AeatSyncWorkspaceProjectionError, match="census paths"):
        _project(census=(first, second))


def test_public_projection_is_frozen() -> None:
    projection = _project(overview=(_overview(),))
    with pytest.raises(ValidationError):
        projection.overview[0].area = AeatSyncOverviewArea.NOTIFICATIONS
