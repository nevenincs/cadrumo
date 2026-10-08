"""Census evidence survives the workbench's strict transport round trip."""

from datetime import UTC, datetime
from typing import cast

import pytest
from pydantic import AnyHttpUrl

from cadrumo.application.aeat_sync.workspace import (
    AeatSyncWorkspaceAvailability,
    AeatSyncWorkspaceProjectionV1,
    AeatSyncWorkspaceZone,
    AeatSyncWorkspaceZoneStateV1,
)
from cadrumo.application.operations.public_mirror import project_public_mirror, restore_public_mirror
from cadrumo.application.user_profile.censal_observation import (
    CensalObservation,
    CensalObservationAddress,
    CensalObservationIdentity,
)
from cadrumo.application.workbench_generation_public_contracts import PublicAeatSyncWorkspaceProjectionV1

from ...tests.aeat_literal_fixtures import (
    SEDE_ROOT_URL_FIXTURE,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("captured", [False, True])
def test_census_observation_survives_workbench_transport(captured: bool) -> None:
    observation = (
        CensalObservation(
            identity=CensalObservationIdentity(apellidos_y_nombre="Synthetic taxpayer"),
            domicilio_fiscal=CensalObservationAddress(municipio="Synthetic municipality"),
            domicilio_notificacion=CensalObservationAddress(),
            captured_at=datetime(2023, 6, 1, tzinfo=UTC),
            source_url=AnyHttpUrl(SEDE_ROOT_URL_FIXTURE),
        )
        if captured
        else None
    )
    canonical = AeatSyncWorkspaceProjectionV1(
        zones=tuple(
            AeatSyncWorkspaceZoneStateV1(
                zone=zone,
                availability=AeatSyncWorkspaceAvailability.NEVER_CAPTURED,
                sources=(),
                item_count=None,
            )
            for zone in AeatSyncWorkspaceZone
        ),
        census_observation=observation,
    )
    public = cast(
        PublicAeatSyncWorkspaceProjectionV1,
        project_public_mirror(canonical, AeatSyncWorkspaceProjectionV1, PublicAeatSyncWorkspaceProjectionV1),
    )
    decoded = PublicAeatSyncWorkspaceProjectionV1.model_validate_json(public.model_dump_json(), strict=True)
    assert decoded.census_observation == observation
    assert (
        restore_public_mirror(decoded, AeatSyncWorkspaceProjectionV1, PublicAeatSyncWorkspaceProjectionV1) == canonical
    )
