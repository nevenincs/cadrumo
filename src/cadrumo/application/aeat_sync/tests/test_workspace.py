"""Adversarial contract tests for the safe AEAT Sync workspace."""

from __future__ import annotations

import ast
import pickle
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from ....core.hashing import content_hash_hex
from ....core.period import Period
from ....domain.modelos.codes import ModeloCode
from ...operations.registry import OperationPublicContractSetV1
from ...operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE, ActionCatalogue, ActionCatalogueEntry
from ...operator_actions.models import ActionReference
from ...user_profile.censal_operation import CENSAL_OPERATION_DEFINITION, build_censal_operation_registration
from .. import workspace as workspace_module
from ..workspace import (
    AeatSyncAeatObservationState,
    AeatSyncCensusCategory,
    AeatSyncCensusStatus,
    AeatSyncDiscrepancyKind,
    AeatSyncDocumentCustodyState,
    AeatSyncJustificanteState,
    AeatSyncLocalFilingState,
    AeatSyncNotificationCategory,
    AeatSyncNotificationReadState,
    AeatSyncOverviewArea,
    AeatSyncReconciliationState,
    AeatSyncSourceState,
    AeatSyncWorkspaceAvailability,
    AeatSyncWorkspaceCensusRowV1,
    AeatSyncWorkspaceEvidenceComparisonRowV1,
    AeatSyncWorkspaceFactV1,
    AeatSyncWorkspaceFiledDeclarationRowV1,
    AeatSyncWorkspaceNotificationRowV1,
    AeatSyncWorkspaceOverviewRowV1,
    AeatSyncWorkspaceProjectionError,
    AeatSyncWorkspaceProjectionV1,
    AeatSyncWorkspaceReconciliationRowV1,
    AeatSyncWorkspaceSource,
    AeatSyncWorkspaceSourceObservationV1,
    AeatSyncWorkspaceZone,
    AeatSyncWorkspaceZoneObservationV1,
    aeat_sync_workspace_sources,
    project_aeat_sync_workspace,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

BUCKET = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
SUBJECT = "private-subject"
T1 = datetime(2026, 1, 3, 10, tzinfo=UTC)
T2 = datetime(2026, 1, 4, 11, tzinfo=UTC)
SECRET_VALUES = (
    BUCKET,
    SUBJECT,
    "12345678Z",
    "Protected Name",
    "https://private.invalid/evidence",
    "document prose",
    "certificate-private",
    "notification-private",
)


def _period(modelo: str = "130") -> Period:
    return Period.from_year_and_code(2026, "1T" if modelo != "303" else "2T")


def _source(
    source: AeatSyncWorkspaceSource,
    availability: AeatSyncWorkspaceAvailability = AeatSyncWorkspaceAvailability.AVAILABLE,
    *,
    count: int = 1,
) -> AeatSyncWorkspaceSourceObservationV1:
    observable = availability in {AeatSyncWorkspaceAvailability.AVAILABLE, AeatSyncWorkspaceAvailability.STALE}
    return AeatSyncWorkspaceSourceObservationV1(
        source=source,
        availability=availability,
        observed_at=T2 if observable else None,
        refusal=None if availability is AeatSyncWorkspaceAvailability.AVAILABLE else "aeat.sync.source.refused",
        item_count=count if observable else None,
    )


def _observations(
    *,
    overrides: dict[tuple[AeatSyncWorkspaceZone, AeatSyncWorkspaceSource], AeatSyncWorkspaceAvailability] | None = None,
) -> tuple[AeatSyncWorkspaceZoneObservationV1, ...]:
    overrides = overrides or {}
    return tuple(
        AeatSyncWorkspaceZoneObservationV1(
            zone=zone,
            sources=tuple(
                _source(source, overrides.get((zone, source), AeatSyncWorkspaceAvailability.AVAILABLE))
                for source in aeat_sync_workspace_sources(zone)
            ),
        )
        for zone in AeatSyncWorkspaceZone
    )


def _action(action_id: str) -> ActionReference:
    return ActionReference(action_id=action_id)


def _fact(row, *, bucket: str = BUCKET, subject: str = SUBJECT, private_identity: str | None = None):
    return AeatSyncWorkspaceFactV1(bucket_id=bucket, subject_key=subject, row=row, private_identity=private_identity)


def _overview(
    area: AeatSyncOverviewArea = AeatSyncOverviewArea.CENSUS, actions: tuple[ActionReference, ...] = ()
) -> AeatSyncWorkspaceOverviewRowV1:
    return AeatSyncWorkspaceOverviewRowV1(
        area=area,
        local_state=AeatSyncSourceState.PRESENT,
        aeat_state=AeatSyncSourceState.PRESENT,
        local_observed_at=T1,
        aeat_observed_at=T2,
        discrepancy_kind=AeatSyncDiscrepancyKind.NONE,
        supported_actions=actions,
    )


def _census(
    path: str = "address", category: AeatSyncCensusCategory = AeatSyncCensusCategory.ADDRESS
) -> AeatSyncWorkspaceCensusRowV1:
    return AeatSyncWorkspaceCensusRowV1(path=path, category=category, status=AeatSyncCensusStatus.CONFLICT)


def _filed(
    modelo: str = "130",
    *,
    local: AeatSyncLocalFilingState = AeatSyncLocalFilingState.FILED,
    aeat: AeatSyncAeatObservationState = AeatSyncAeatObservationState.ACCEPTED,
) -> AeatSyncWorkspaceFiledDeclarationRowV1:
    return AeatSyncWorkspaceFiledDeclarationRowV1(
        modelo=ModeloCode(modelo),
        filing_year=2026,
        period=_period(modelo),
        local_filing_state=local,
        local_filed_at=T1 if local is AeatSyncLocalFilingState.FILED else None,
        aeat_observation_state=aeat,
        aeat_observed_at=T2 if aeat is not AeatSyncAeatObservationState.NOT_OBSERVED else None,
        justificante_state=AeatSyncJustificanteState.VERIFIED
        if aeat is AeatSyncAeatObservationState.ACCEPTED
        else AeatSyncJustificanteState.NOT_OBSERVED,
        justificante_observed_at=T2 if aeat is AeatSyncAeatObservationState.ACCEPTED else None,
    )


def _notification() -> AeatSyncWorkspaceNotificationRowV1:
    return AeatSyncWorkspaceNotificationRowV1(
        issued_on=date(2026, 1, 2),
        read_on=date(2026, 1, 3),
        read_state=AeatSyncNotificationReadState.READ,
        category=AeatSyncNotificationCategory.FORMAL,
        document_custody_state=AeatSyncDocumentCustodyState.HELD,
        document_custody_observed_at=T2,
    )


def _comparison(modelo: str = "130") -> AeatSyncWorkspaceEvidenceComparisonRowV1:
    return AeatSyncWorkspaceEvidenceComparisonRowV1(
        modelo=ModeloCode(modelo),
        filing_year=2026,
        period=_period(modelo),
        local_state=AeatSyncSourceState.PRESENT,
        aeat_state=AeatSyncSourceState.ABSENT,
        local_observed_at=T1,
        aeat_observed_at=T2,
        discrepancy_kind=AeatSyncDiscrepancyKind.LOCAL_ONLY,
        supported_actions=(_action("operator.overview.explain"),),
    )


def _reconciliation(*, no_action: bool = False) -> AeatSyncWorkspaceReconciliationRowV1:
    return AeatSyncWorkspaceReconciliationRowV1(
        modelo=ModeloCode("130"),
        filing_year=2026,
        period=_period(),
        local_state=AeatSyncSourceState.PRESENT,
        aeat_state=AeatSyncSourceState.PRESENT if no_action else AeatSyncSourceState.ABSENT,
        local_observed_at=T1,
        aeat_observed_at=T2,
        discrepancy_kind=AeatSyncDiscrepancyKind.NONE if no_action else AeatSyncDiscrepancyKind.LOCAL_ONLY,
        reconciliation_state=AeatSyncReconciliationState.NO_ACTION
        if no_action
        else AeatSyncReconciliationState.KEEP_LOCAL,
        supported_actions=() if no_action else (_action("operator.overview.explain"),),
    )


def _projection(**updates):
    arguments = dict(
        bucket_id=BUCKET,
        subject_key=SUBJECT,
        zone_observations=_observations(),
        action_catalogue=OPERATOR_ACTION_CATALOGUE,
        operation_contracts=OperationPublicContractSetV1.build(
            (build_censal_operation_registration(CENSAL_OPERATION_DEFINITION).contract,)
        ),
        overview=(_fact(_overview()),),
        census=(_fact(_census()),),
        filed_declarations=(_fact(_filed()),),
        notifications=(_fact(_notification(), private_identity="notification-private"),),
        evidence_comparison=(_fact(_comparison()),),
        reconciliation=(_fact(_reconciliation()),),
    )
    arguments.update(updates)
    return cast(Any, project_aeat_sync_workspace)(**arguments)


def test_exact_six_zones_and_deterministic_safe_projection() -> None:
    first = _projection(census=(_fact(_census("z")), _fact(_census("a"))))
    second = _projection(census=(_fact(_census("a")), _fact(_census("z"))))
    assert tuple(zone.zone for zone in first.zones) == tuple(AeatSyncWorkspaceZone)
    assert tuple(row.path for row in first.census) == ("a", "z")
    assert first == second
    assert first.model_dump_json() == second.model_dump_json()


def test_notification_selection_identity_is_stable_opaque_and_order_independent() -> None:
    first = _projection(
        notifications=(
            _fact(_notification(), private_identity="notification-alpha"),
            _fact(_notification(), private_identity="notification-beta"),
        )
    )
    second = _projection(
        notifications=(
            _fact(_notification(), private_identity="notification-beta"),
            _fact(_notification(), private_identity="notification-alpha"),
        )
    )
    assert first == second
    keys = tuple(row.selection_key for row in first.notifications)
    assert all(key is not None for key in keys)
    assert len(set(keys)) == 2
    assert all(key.startswith("aeat_sync.notification.") and len(key) <= 160 for key in keys if key is not None)
    single = _projection(notifications=(_fact(_notification(), private_identity="notification-alpha"),))
    single_key = single.notifications[0].selection_key
    assert single_key is not None
    raw_digest = content_hash_hex(
        {
            "namespace": "aeat_sync.notification.selection.v1",
            "private_identity": "notification-alpha",
        }
    )
    assert single_key.removeprefix("aeat_sync.notification.") != raw_digest
    encoded = first.model_dump_json() + repr(first)
    assert "notification-alpha" not in encoded
    assert "notification-beta" not in encoded
    assert b"notification-alpha" not in pickle.dumps(first)
    assert b"notification-beta" not in pickle.dumps(first)

    invalid = first.model_dump(mode="python")
    invalid["notifications"] = ({**invalid["notifications"][0], "selection_key": None},)
    with pytest.raises(ValidationError, match="selection keys"):
        AeatSyncWorkspaceProjectionV1.model_validate(invalid)
    duplicate = first.model_dump(mode="python")
    duplicate_row = first.notifications[0].model_dump(mode="python")
    duplicate["notifications"] = (duplicate_row, duplicate_row)
    with pytest.raises(ValidationError, match="selection keys must be unique"):
        AeatSyncWorkspaceProjectionV1.model_validate(duplicate)


def test_notification_selection_identity_collision_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        workspace_module,
        "_notification_selection_key",
        lambda _: "aeat_sync.notification.collision",
    )
    with pytest.raises(AeatSyncWorkspaceProjectionError, match="selection identities"):
        _projection(
            notifications=(
                _fact(_notification(), private_identity="notification-alpha"),
                _fact(_notification(), private_identity="notification-beta"),
            )
        )


@pytest.mark.parametrize(
    "bad_key",
    (
        "aeat_sync.other." + "a" * 64,
        "aeat_sync.notification." + "a" * 63,
        "aeat_sync.notification." + "A" * 64,
        "aeat_sync.notification." + "g" * 64,
    ),
)
def test_notification_selection_key_shape_is_closed(bad_key: str) -> None:
    row_values = _notification().model_dump(mode="python")
    row_values["selection_key"] = bad_key
    with pytest.raises(ValidationError):
        AeatSyncWorkspaceNotificationRowV1.model_validate(row_values)

    projection = _projection()
    projection_values = projection.model_dump(mode="python")
    projection_values["notifications"] = ({**projection_values["notifications"][0], "selection_key": bad_key},)
    with pytest.raises(ValidationError):
        AeatSyncWorkspaceProjectionV1.model_validate(projection_values)


def test_output_physically_omits_protected_scope_payload_and_identity() -> None:
    projection = _projection()
    encoded = pickle.dumps(projection) + projection.model_dump_json().encode() + repr(projection).encode()
    for secret in SECRET_VALUES:
        assert secret.encode() not in encoded
    forbidden = {
        "bucket_id",
        "subject_key",
        "private_identity",
        "semantic_identity",
        "name",
        "nif",
        "source_url",
        "document_text",
        "raw_evidence",
        "secret",
        "certificado_id",
        "concepto",
    }
    for value in (
        projection,
        *projection.overview,
        *projection.census,
        *projection.filed_declarations,
        *projection.notifications,
        *projection.evidence_comparison,
        *projection.reconciliation,
    ):
        assert forbidden.isdisjoint(vars(value))
        for name in forbidden:
            assert not hasattr(value, name)
    with pytest.raises(ValidationError):
        projection.contract_version = 2  # type: ignore[misc]


def test_scope_is_mandatory_and_projected_away() -> None:
    with pytest.raises((TypeError, ValueError)):
        AeatSyncWorkspaceFactV1(bucket_id=BUCKET, subject_key="", row=_census())
    with pytest.raises(AeatSyncWorkspaceProjectionError, match="foreign bucket"):
        _projection(census=(_fact(_census(), bucket=OTHER),))
    with pytest.raises(AeatSyncWorkspaceProjectionError, match="mixed subjects"):
        _projection(census=(_fact(_census(), subject="other"),))
    with pytest.raises(TypeError):
        cast(Any, AeatSyncWorkspaceFactV1)(row=_census())
    with pytest.raises((TypeError, ValueError)):
        cast(Any, AeatSyncWorkspaceFactV1)(bucket_id=None, subject_key=SUBJECT, row=_census())
    with pytest.raises((TypeError, ValueError)):
        cast(Any, project_aeat_sync_workspace)(
            bucket_id=None,
            subject_key=SUBJECT,
            zone_observations=_observations(),
            action_catalogue=OPERATOR_ACTION_CATALOGUE,
            operation_contracts=OperationPublicContractSetV1.build(
                (build_censal_operation_registration(CENSAL_OPERATION_DEFINITION).contract,)
            ),
        )


def test_logical_duplicates_refuse_disagreement() -> None:
    with pytest.raises(AeatSyncWorkspaceProjectionError, match="overview areas"):
        _projection(overview=(_fact(_overview()), _fact(_overview())))
    with pytest.raises(AeatSyncWorkspaceProjectionError, match="census paths"):
        _projection(census=(_fact(_census("Address")), _fact(_census("address", AeatSyncCensusCategory.OTHER))))
    with pytest.raises(AeatSyncWorkspaceProjectionError, match="census paths"):
        _projection(census=(_fact(_census("tax   address")), _fact(_census(" Tax Address "))))
    with pytest.raises(AeatSyncWorkspaceProjectionError, match="notification identities"):
        _projection(
            notifications=(
                _fact(_notification(), private_identity="same"),
                _fact(_notification(), private_identity="same"),
            )
        )


def test_actions_require_catalogue_admission_and_area_state_closure() -> None:
    canonical = OPERATOR_ACTION_CATALOGUE.lookup("operator.profile.edit")
    forged = ActionCatalogueEntry(action_id=canonical.action_id, target_command_key="forged.command")
    with pytest.raises(AeatSyncWorkspaceProjectionError, match="differs from canonical"):
        _projection(action_catalogue=ActionCatalogue(entries=(forged,)))
    with pytest.raises(AeatSyncWorkspaceProjectionError, match="not allowed"):
        _projection(overview=(_fact(_overview(actions=(_action("operator.live.notifications.list"),))),))
    with pytest.raises(ValidationError, match="NO_ACTION"):
        row = _reconciliation(no_action=True)
        AeatSyncWorkspaceReconciliationRowV1.model_validate(
            {**row.model_dump(), "supported_actions": (_action("operator.overview.explain"),)}
        )
    admitted_operation = _overview().model_copy(update={"supported_operations": ("user-profile.censo-review",)})
    assert _projection(overview=(_fact(admitted_operation),)).overview[0].supported_operations == (
        "user-profile.censo-review",
    )
    for row in (_overview(), _census(), _filed(), _comparison(), _reconciliation()):
        assert row.supported_actions == () or row.supported_actions
        assert row.supported_operations == ()
        assert "supported_actions" in row.model_dump()
        assert "supported_operations" in row.model_dump()


def test_notification_rows_have_exact_safe_fields_and_no_capabilities() -> None:
    assert set(AeatSyncWorkspaceNotificationRowV1.model_fields) == {
        "issued_on",
        "read_on",
        "read_state",
        "category",
        "document_custody_state",
        "document_custody_observed_at",
        "selection_key",
    }
    projected = _projection().notifications[0]
    assert not hasattr(projected, "supported_actions")
    assert not hasattr(projected, "supported_operations")
    assert "supported_actions" not in projected.model_dump()
    assert "supported_operations" not in projected.model_dump()


def test_row_subclass_protected_fields_are_reconstructed_away() -> None:
    class UnsafeCensusRow(AeatSyncWorkspaceCensusRowV1):
        nif: str

    unsafe = UnsafeCensusRow(
        path="address",
        category=AeatSyncCensusCategory.ADDRESS,
        status=AeatSyncCensusStatus.CONFLICT,
        nif="12345678Z",
    )
    projection = _projection(census=(_fact(unsafe),))
    assert type(projection.census[0]) is AeatSyncWorkspaceCensusRowV1
    assert "12345678Z" not in repr(projection)
    assert b"12345678Z" not in pickle.dumps(projection)
    assert "nif" not in projection.census[0].__dict__


def test_independent_source_axes_keep_known_empty_and_unknown_distinct() -> None:
    key = (AeatSyncWorkspaceZone.FILED_DECLARATIONS, AeatSyncWorkspaceSource.AEAT_FILED_DECLARATIONS)
    observations = _observations(overrides={key: AeatSyncWorkspaceAvailability.LOCKED})
    local_only = _filed(aeat=AeatSyncAeatObservationState.NOT_OBSERVED)
    projection = _projection(zone_observations=observations, filed_declarations=(_fact(local_only),))
    state = projection.zones[2]
    assert state.availability is AeatSyncWorkspaceAvailability.STALE
    assert state.item_count == 1
    assert state.sources[0].item_count == 1
    assert state.sources[1].availability is AeatSyncWorkspaceAvailability.LOCKED
    assert state.sources[1].item_count is None
    with pytest.raises(AeatSyncWorkspaceProjectionError, match="AEAT filing"):
        _projection(zone_observations=observations, filed_declarations=(_fact(_filed()),))
    empty = _projection(filed_declarations=())
    assert empty.zones[2].item_count == 0


def test_unrelated_observable_sources_cannot_back_area_or_census_claims() -> None:
    locked = {
        (AeatSyncWorkspaceZone.OVERVIEW, AeatSyncWorkspaceSource.LOCAL_PROFILE): (AeatSyncWorkspaceAvailability.LOCKED),
        (AeatSyncWorkspaceZone.OVERVIEW, AeatSyncWorkspaceSource.AEAT_CENSUS): (AeatSyncWorkspaceAvailability.LOCKED),
        (AeatSyncWorkspaceZone.CENSUS, AeatSyncWorkspaceSource.LOCAL_PROFILE): (AeatSyncWorkspaceAvailability.LOCKED),
        (AeatSyncWorkspaceZone.CENSUS, AeatSyncWorkspaceSource.AEAT_CENSUS): (AeatSyncWorkspaceAvailability.LOCKED),
    }
    observations = _observations(overrides=locked)
    with pytest.raises(AeatSyncWorkspaceProjectionError, match="local"):
        _projection(zone_observations=observations, overview=(_fact(_overview()),))
    with pytest.raises(AeatSyncWorkspaceProjectionError, match=r"unobservable|local census"):
        _projection(zone_observations=observations, overview=(), census=(_fact(_census()),))


def test_unavailable_sources_cannot_carry_confident_rows() -> None:
    overrides = {
        (AeatSyncWorkspaceZone.CENSUS, source): AeatSyncWorkspaceAvailability.UNAVAILABLE
        for source in (AeatSyncWorkspaceSource.LOCAL_PROFILE, AeatSyncWorkspaceSource.AEAT_CENSUS)
    }
    with pytest.raises(AeatSyncWorkspaceProjectionError, match="unobservable zone"):
        _projection(zone_observations=_observations(overrides=overrides), census=(_fact(_census()),))


def test_zero_count_source_rejects_confident_rows() -> None:
    observations = list(_observations())
    census = observations[1]
    observations[1] = census.model_copy(
        update={
            "sources": (
                census.sources[0],
                census.sources[1].model_copy(update={"item_count": 0}),
            )
        }
    )
    with pytest.raises(AeatSyncWorkspaceProjectionError, match="AEAT census"):
        _projection(zone_observations=tuple(observations), census=(_fact(_census()),))


def test_no_adapter_entrypoint_io_imports_and_initializer_is_inert() -> None:
    module = Path(__file__).parents[1] / "workspace.py"
    tree = ast.parse(module.read_text(encoding="utf-8"))
    imports = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)} | {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    }
    assert not any(
        token in item
        for item in imports
        for token in ("adapters", "entrypoints", "pathlib", "requests", "httpx", "socket", "tui")
    )
    calls = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert calls.isdisjoint({"open", "print", "input"})
    initializer = ast.parse((module.parent / "__init__.py").read_text(encoding="utf-8"))
    assert not any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(initializer))
