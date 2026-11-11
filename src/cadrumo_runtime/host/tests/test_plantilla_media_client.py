"""Native year-keyed plantilla-media mutations retain exact encrypted CAS truth."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.application.user_profile.profile_operation_contracts import (
    ProfilePlantillaMediaOperationProjection,
    ProfilePlantillaMediaOperationRequest,
    ProfilePlantillaMediaRemove,
    ProfilePlantillaMediaSet,
)
from cadrumo.core.operations import OperationEffect, OperationFrontendProjection, OperationTerminalCondition
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.user_profile.plantilla_media import PlantillaMediaState
from cadrumo.domain.user_profile.values import UserProfileRecord
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.installation import installation
from cadrumo_client.transport.profile_mutations import ProfileMutationRunError, run_profile_mutation
from cadrumo_client.transport.windows import WindowsEndpoint

from ...adapters.tests.profile_worker_support import PROFILE_INPUT, owner_id, worker_profiles
from .profile_record_support import profile_view_facts, stored_profile_record
from .served_runtime import SyntheticLogin, serving_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

# Three distinct supported years: the one set, replaced and removed, the one added beside it,
# and the one the refused requests address.
_ADDED_YEAR, _SET_YEAR, _OTHER_YEAR = filing_year_envelope().years[-3:]


def _request(
    profile_id: UUID,
    *,
    revision: int,
    digest: str,
    year: int,
    change: ProfilePlantillaMediaSet | ProfilePlantillaMediaRemove,
) -> ProfilePlantillaMediaOperationRequest:
    return ProfilePlantillaMediaOperationRequest(
        profile_id=profile_id,
        expected_revision=revision,
        expected_content_digest=digest,
        year=year,
        change=change,
    )


def _set(amount: str, state: PlantillaMediaState) -> ProfilePlantillaMediaSet:
    return ProfilePlantillaMediaSet(average_workforce=amount, state=state)


def _set_and_repeat(client: FrontendClient, profile_id: UUID, baseline: UserProfileRecord) -> tuple[int, str]:
    password = bytearray(PROFILE_INPUT.encode())
    client.login_password(password)
    assert password == bytearray(len(password))
    revision, digest, _ = profile_view_facts(client)
    assert (revision, digest) == (baseline.record_revision, baseline.content_digest)

    first = run_profile_mutation(
        client,
        _request(
            profile_id,
            revision=revision,
            digest=digest,
            year=_SET_YEAR,
            change=_set("12.50", PlantillaMediaState.COMMITTED),
        ),
        timeout=90,
    )
    assert first.effect is OperationEffect.UPDATED
    assert type(first.projection) is ProfilePlantillaMediaOperationProjection
    assert first.projection.year == _SET_YEAR and first.projection.changed
    assert first.projection.record_revision == revision + 1
    revision, digest, facts = profile_view_facts(client)
    assert revision == first.projection.record_revision
    assert {path: value for path, value in facts.items() if path.startswith("irpf.plantilla_media.")} == {
        "irpf.plantilla_media.0.year": str(_SET_YEAR),
        "irpf.plantilla_media.0.average_workforce": "12.50",
        "irpf.plantilla_media.0.state": "committed",
    }

    unchanged = run_profile_mutation(
        client,
        _request(
            profile_id,
            revision=revision,
            digest=digest,
            year=_SET_YEAR,
            change=_set("12.50", PlantillaMediaState.COMMITTED),
        ),
        timeout=90,
    )
    assert unchanged.effect is OperationEffect.NONE
    assert type(unchanged.projection) is ProfilePlantillaMediaOperationProjection
    assert not unchanged.projection.changed and unchanged.projection.record_revision == revision
    return revision, digest


def _refuse_stale_baseline(
    client: FrontendClient, profile_id: UUID, baseline: UserProfileRecord, revision: int, digest: str
) -> None:
    with pytest.raises(ProfileMutationRunError) as stale:
        run_profile_mutation(
            client,
            _request(
                profile_id,
                revision=baseline.record_revision,
                digest=baseline.content_digest,
                year=_SET_YEAR,
                change=_set("11.75", PlantillaMediaState.OBSERVED),
            ),
            timeout=90,
        )
    assert stale.value.operation_id
    assert stale.value.reason == "FAIL_PROFILE_RECORD_CONFLICT"
    assert stale.value.terminal_condition is OperationTerminalCondition.FAILED
    assert stale.value.effect is not OperationEffect.UPDATED
    assert profile_view_facts(client)[:2] == (revision, digest)


def _replace_then_remove(client: FrontendClient, profile_id: UUID, revision: int, digest: str) -> tuple[int, str]:
    replaced = run_profile_mutation(
        client,
        _request(
            profile_id,
            revision=revision,
            digest=digest,
            year=_SET_YEAR,
            change=_set("11.75", PlantillaMediaState.OBSERVED),
        ),
        timeout=90,
    )
    assert replaced.effect is OperationEffect.UPDATED
    assert type(replaced.projection) is ProfilePlantillaMediaOperationProjection
    assert replaced.projection.changed and replaced.projection.record_revision == revision + 1
    revision, digest, facts = profile_view_facts(client)
    assert facts["irpf.plantilla_media.0.average_workforce"] == "11.75"
    assert facts["irpf.plantilla_media.0.state"] == "observed"

    removed = run_profile_mutation(
        client,
        _request(
            profile_id,
            revision=revision,
            digest=digest,
            year=_SET_YEAR,
            change=ProfilePlantillaMediaRemove(),
        ),
        timeout=90,
    )
    assert removed.effect is OperationEffect.UPDATED
    assert type(removed.projection) is ProfilePlantillaMediaOperationProjection
    assert removed.projection.changed and removed.projection.record_revision == revision + 1
    revision, digest, facts = profile_view_facts(client)
    assert not any(path.startswith("irpf.plantilla_media.") for path in facts)
    return revision, digest


def _add_next_year(client: FrontendClient, profile_id: UUID, revision: int, digest: str) -> tuple[int, str]:
    next_year = run_profile_mutation(
        client,
        _request(
            profile_id,
            revision=revision,
            digest=digest,
            year=_ADDED_YEAR,
            change=_set("10", PlantillaMediaState.OBSERVED),
        ),
        timeout=90,
    )
    assert next_year.effect is OperationEffect.UPDATED
    assert type(next_year.projection) is ProfilePlantillaMediaOperationProjection
    assert next_year.projection.changed and next_year.projection.record_revision == revision + 1
    revision, digest, facts = profile_view_facts(client)
    assert {path: value for path, value in facts.items() if path.startswith("irpf.plantilla_media.")} == {
        "irpf.plantilla_media.1.year": str(_ADDED_YEAR),
        "irpf.plantilla_media.1.average_workforce": "10",
        "irpf.plantilla_media.1.state": "observed",
    }
    return revision, digest


def _refuse_invalid_and_foreign(
    client: FrontendClient, profile_id: UUID, foreign_id: UUID, revision: int, digest: str
) -> None:
    with pytest.raises(ProfileMutationRunError) as invalid:
        run_profile_mutation(
            client,
            _request(
                profile_id,
                revision=revision,
                digest=digest,
                year=_OTHER_YEAR,
                change=_set("12.505", PlantillaMediaState.OBSERVED),
            ),
            timeout=90,
        )
    assert invalid.value.operation_id
    assert invalid.value.terminal_condition is OperationTerminalCondition.REFUSED
    assert invalid.value.effect is not OperationEffect.UPDATED
    assert profile_view_facts(client)[:2] == (revision, digest)

    with pytest.raises(FrontendRefusedError, match="profile_mismatch"):
        run_profile_mutation(
            client,
            _request(
                foreign_id,
                revision=revision,
                digest=digest,
                year=_OTHER_YEAR,
                change=_set("1", PlantillaMediaState.COMMITTED),
            ),
            timeout=90,
        )


def _assert_tombstoned_index(final: UserProfileRecord, baseline: UserProfileRecord) -> None:
    assert final.record_revision == baseline.record_revision + 4
    assert {
        fact.path for fact in final.facts if fact.path.startswith("irpf.plantilla_media.0.") and fact.value is None
    } == {
        "irpf.plantilla_media.0.year",
        "irpf.plantilla_media.0.average_workforce",
        "irpf.plantilla_media.0.state",
    }


def test_native_plantilla_media_set_noop_replace_remove_and_tombstone_index(tmp_path: Path) -> None:
    """Each changed three-leaf year is one revision; a cleared index stays owned."""
    with worker_profiles(tmp_path) as (root, targets):
        profile_id = targets[0][0].binding.profile_id
        foreign_id = targets[1][0].binding.profile_id
        baseline = stored_profile_record(profile_id, root=root)
        endpoint = WindowsEndpoint(storage_root=root)
        installation(storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity)
        native = MemoryNativePort()
        with serving_runtime(
            endpoint,
            root,
            capture_login=lambda _channel: SyntheticLogin("plantilla-media-native-login"),
            secret_store=lambda: native,
            drain_seconds=15,
        ) as served:
            client = asyncio.run(
                FrontendClient.open(served.launch, profile_id=profile_id, frontend=OperationFrontendProjection.CLI)
            )
            with client:
                revision, digest = _set_and_repeat(client, profile_id, baseline)
                _refuse_stale_baseline(client, profile_id, baseline, revision, digest)
                revision, digest = _replace_then_remove(client, profile_id, revision, digest)
                revision, digest = _add_next_year(client, profile_id, revision, digest)
                _refuse_invalid_and_foreign(client, profile_id, foreign_id, revision, digest)
                client.lock()
        _assert_tombstoned_index(stored_profile_record(profile_id, root=root), baseline)
