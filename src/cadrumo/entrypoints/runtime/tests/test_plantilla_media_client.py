"""Native year-keyed plantilla-media mutations retain exact encrypted CAS truth."""

from __future__ import annotations

import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.profile_mutations import ProfileMutationRunError, run_profile_mutation
from cadrumo.adapters.local_runtime.server import RuntimeTransportServer
from cadrumo.adapters.local_runtime.startup import RuntimeLaunchDoor
from cadrumo.adapters.local_runtime.tests.profile_worker_support import PROFILE_INPUT, owner_id, worker_profiles
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    load_test_profile_record,
    profile_authority_contexts,
)
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello
from cadrumo.application.user_profile.access_contracts import Availability, LoginEligibility, OsLoginContext
from cadrumo.application.user_profile.login_session import login_profile
from cadrumo.application.user_profile.operations import (
    ProfilePlantillaMediaOperationProjection,
    ProfilePlantillaMediaOperationRequest,
    ProfilePlantillaMediaRemove,
    ProfilePlantillaMediaSet,
)
from cadrumo.application.user_profile.view_operation import ProfileViewFactItem, ProfileViewPageKind
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.domain.user_profile.plantilla_media import PlantillaMediaState
from cadrumo.domain.user_profile.values import UserProfileRecord

from ..profile_connections import RuntimeProfileConnections

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


class _LoginObservation:
    login_id = "plantilla-media-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        """Supply explicit test OS facts while the worker owns private custody."""
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _view(client: RuntimeFrontendClient) -> tuple[int, str, dict[str, str]]:
    collection = client.read_profile_view((ProfileViewPageKind.FACTS,), timeout=90)
    items = collection.items(ProfileViewPageKind.FACTS)
    assert all(isinstance(item, ProfileViewFactItem) for item in items)
    facts = {item.path: item.value for item in items if isinstance(item, ProfileViewFactItem)}
    assert len(facts) == len(items)
    return collection.record_revision, collection.content_digest, facts


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


def _record(profile_id: UUID, *, root: Path) -> UserProfileRecord:
    """Read the real encrypted record, then release process-local custody."""
    _, decode = profile_authority_contexts()
    login_profile(name=str(profile_id), passphrase_callback=lambda: PROFILE_INPUT, profile_decode_context=decode)
    try:
        return load_test_profile_record(profile_id, root=root)
    finally:
        close_active_bucket_session()


def test_native_plantilla_media_set_noop_replace_remove_and_tombstone_index(tmp_path: Path) -> None:
    """Each changed three-leaf year is one revision; a cleared index stays owned."""
    with worker_profiles(tmp_path) as (root, targets):
        profile_id = targets[0][0].binding.profile_id
        foreign_id = targets[1][0].binding.profile_id
        baseline = _record(profile_id, root=root)
        endpoint = WindowsRuntimeEndpoint(storage_root=root)
        runtime_installation(storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity)
        stop, boot, native = Event(), uuid4(), MemoryNativePort()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: native,
        )
        server = RuntimeTransportServer(endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot)
        launch = RuntimeLaunchDoor(
            endpoint,
            expected=RuntimeClientHello(product_version="test", storage_identity=endpoint.storage_identity),
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                client = asyncio.run(
                    RuntimeFrontendClient.open(launch, profile_id=profile_id, frontend=OperationFrontendProjection.CLI)
                )
                with client:
                    password = bytearray(PROFILE_INPUT.encode())
                    client.login_password(password)
                    assert password == bytearray(len(password))
                    revision, digest, _ = _view(client)
                    assert (revision, digest) == (baseline.record_revision, baseline.content_digest)

                    first = run_profile_mutation(
                        client,
                        _request(
                            profile_id,
                            revision=revision,
                            digest=digest,
                            year=2025,
                            change=_set("12.50", PlantillaMediaState.COMMITTED),
                        ),
                        timeout=90,
                    )
                    assert first.effect is OperationEffect.UPDATED
                    assert type(first.projection) is ProfilePlantillaMediaOperationProjection
                    assert first.projection.year == 2025 and first.projection.changed
                    assert first.projection.record_revision == revision + 1
                    revision, digest, facts = _view(client)
                    assert revision == first.projection.record_revision
                    assert {
                        path: value for path, value in facts.items() if path.startswith("irpf.plantilla_media.")
                    } == {
                        "irpf.plantilla_media.0.year": "2025",
                        "irpf.plantilla_media.0.average_workforce": "12.50",
                        "irpf.plantilla_media.0.state": "committed",
                    }

                    unchanged = run_profile_mutation(
                        client,
                        _request(
                            profile_id,
                            revision=revision,
                            digest=digest,
                            year=2025,
                            change=_set("12.50", PlantillaMediaState.COMMITTED),
                        ),
                        timeout=90,
                    )
                    assert unchanged.effect is OperationEffect.NONE
                    assert type(unchanged.projection) is ProfilePlantillaMediaOperationProjection
                    assert not unchanged.projection.changed and unchanged.projection.record_revision == revision

                    with pytest.raises(ProfileMutationRunError) as stale:
                        run_profile_mutation(
                            client,
                            _request(
                                profile_id,
                                revision=baseline.record_revision,
                                digest=baseline.content_digest,
                                year=2025,
                                change=_set("11.75", PlantillaMediaState.OBSERVED),
                            ),
                            timeout=90,
                        )
                    assert stale.value.operation_id
                    assert stale.value.reason == "FAIL_PROFILE_RECORD_CONFLICT"
                    assert stale.value.terminal_condition is OperationTerminalCondition.FAILED
                    assert stale.value.effect is not OperationEffect.UPDATED
                    assert _view(client)[:2] == (revision, digest)

                    replaced = run_profile_mutation(
                        client,
                        _request(
                            profile_id,
                            revision=revision,
                            digest=digest,
                            year=2025,
                            change=_set("11.75", PlantillaMediaState.OBSERVED),
                        ),
                        timeout=90,
                    )
                    assert replaced.effect is OperationEffect.UPDATED
                    assert type(replaced.projection) is ProfilePlantillaMediaOperationProjection
                    assert replaced.projection.changed and replaced.projection.record_revision == revision + 1
                    revision, digest, facts = _view(client)
                    assert facts["irpf.plantilla_media.0.average_workforce"] == "11.75"
                    assert facts["irpf.plantilla_media.0.state"] == "observed"

                    removed = run_profile_mutation(
                        client,
                        _request(
                            profile_id,
                            revision=revision,
                            digest=digest,
                            year=2025,
                            change=ProfilePlantillaMediaRemove(),
                        ),
                        timeout=90,
                    )
                    assert removed.effect is OperationEffect.UPDATED
                    assert type(removed.projection) is ProfilePlantillaMediaOperationProjection
                    assert removed.projection.changed and removed.projection.record_revision == revision + 1
                    revision, digest, facts = _view(client)
                    assert not any(path.startswith("irpf.plantilla_media.") for path in facts)

                    next_year = run_profile_mutation(
                        client,
                        _request(
                            profile_id,
                            revision=revision,
                            digest=digest,
                            year=2024,
                            change=_set("10", PlantillaMediaState.OBSERVED),
                        ),
                        timeout=90,
                    )
                    assert next_year.effect is OperationEffect.UPDATED
                    assert type(next_year.projection) is ProfilePlantillaMediaOperationProjection
                    assert next_year.projection.changed and next_year.projection.record_revision == revision + 1
                    revision, digest, facts = _view(client)
                    assert {
                        path: value for path, value in facts.items() if path.startswith("irpf.plantilla_media.")
                    } == {
                        "irpf.plantilla_media.1.year": "2024",
                        "irpf.plantilla_media.1.average_workforce": "10",
                        "irpf.plantilla_media.1.state": "observed",
                    }

                    with pytest.raises(ProfileMutationRunError) as invalid:
                        run_profile_mutation(
                            client,
                            _request(
                                profile_id,
                                revision=revision,
                                digest=digest,
                                year=2026,
                                change=_set("12.505", PlantillaMediaState.OBSERVED),
                            ),
                            timeout=90,
                        )
                    assert invalid.value.operation_id
                    assert invalid.value.terminal_condition is OperationTerminalCondition.REFUSED
                    assert invalid.value.effect is not OperationEffect.UPDATED
                    assert _view(client)[:2] == (revision, digest)

                    with pytest.raises(RuntimeFrontendRefusedError, match="profile_mismatch"):
                        run_profile_mutation(
                            client,
                            _request(
                                foreign_id,
                                revision=revision,
                                digest=digest,
                                year=2026,
                                change=_set("1", PlantillaMediaState.COMMITTED),
                            ),
                            timeout=90,
                        )
                    client.lock()
            finally:
                stop.set()
                running.result(timeout=15)
                endpoint.close()

        final = _record(profile_id, root=root)
        assert final.record_revision == baseline.record_revision + 4
        assert {
            fact.path for fact in final.facts if fact.path.startswith("irpf.plantilla_media.0.") and fact.value is None
        } == {
            "irpf.plantilla_media.0.year",
            "irpf.plantilla_media.0.average_workforce",
            "irpf.plantilla_media.0.state",
        }
