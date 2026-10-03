"""Native descendant-family replacement preserves encrypted rows and CAS truth."""

from __future__ import annotations

import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
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
from cadrumo.application.user_profile.descendant_rows import (
    ProfileDescendantFact,
    ProfileDescendantRow,
    encode_descendant_rows,
)
from cadrumo.application.user_profile.login_session import login_profile
from cadrumo.application.user_profile.profile_operation_contracts import (
    ProfileDescendantsOperationProjection,
    ProfileDescendantsOperationRequest,
)
from cadrumo.application.user_profile.view_operation import ProfileViewFactItem, ProfileViewPageKind
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.contribuyente.descendant import DescendantInfo
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
    login_id = "descendants-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _record(profile_id: UUID, *, root: Path) -> UserProfileRecord:
    """Read the actual encrypted record without retaining parent custody."""
    _, decode = profile_authority_contexts()
    login_profile(name=str(profile_id), passphrase_callback=lambda: PROFILE_INPUT, profile_decode_context=decode)
    try:
        return load_test_profile_record(profile_id, root=root)
    finally:
        close_active_bucket_session()


def _view(client: RuntimeFrontendClient) -> tuple[int, str, dict[str, str]]:
    page = client.read_profile_view((ProfileViewPageKind.FACTS,), timeout=90)
    items = page.items(ProfileViewPageKind.FACTS)
    assert all(isinstance(item, ProfileViewFactItem) for item in items)
    facts = {item.path: item.value for item in items if isinstance(item, ProfileViewFactItem)}
    assert len(facts) == len(items)
    return page.record_revision, page.content_digest, facts


def _request(
    profile_id: UUID, *, revision: int, digest: str, descendants: tuple[ProfileDescendantRow, ...]
) -> ProfileDescendantsOperationRequest:
    return ProfileDescendantsOperationRequest(
        profile_id=profile_id,
        expected_revision=revision,
        expected_content_digest=digest,
        descendants=descendants,
    )


def test_native_descendant_family_replace_reindex_clear_and_refuse_stale_intent(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    with worker_profiles(tmp_path) as (root, targets):
        profile_id = targets[0][0].binding.profile_id
        foreign_id = targets[1][0].binding.profile_id
        baseline = _record(profile_id, root=root)
        foreign_baseline = _record(foreign_id, root=root)
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
        profiles.prepare_registry()
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
                    proof = bytearray(PROFILE_INPUT.encode())
                    client.login_password(proof)
                    assert not any(proof)
                    revision, digest, facts = _view(client)
                    assert (revision, digest) == (baseline.record_revision, baseline.content_digest)
                    assert not any(path.startswith("renta_family.descendiente.") for path in facts)

                    older = DescendantInfo(
                        birth_date=date(2015, 4, 3),
                        custodia_compartida=True,
                        prorrata_minimo=True,
                        rentas_anuales_euros=Decimal("1200.00"),
                    )
                    younger = DescendantInfo(birth_date=date(2020, 8, 9), dependencia_economica=False)
                    family = (older, younger)
                    family_rows = encode_descendant_rows(family, authority=authority_operation)
                    younger_rows = encode_descendant_rows((younger,), authority=authority_operation)
                    first = run_profile_mutation(
                        client,
                        _request(profile_id, revision=revision, digest=digest, descendants=family_rows),
                        timeout=90,
                    )
                    assert first.operation_id and first.effect is OperationEffect.UPDATED
                    assert type(first.projection) is ProfileDescendantsOperationProjection
                    assert (first.projection.total, first.projection.changed) == (2, True)
                    assert first.projection.profile_id == profile_id
                    assert first.projection.record_revision == revision + 1
                    revision, digest, facts = _view(client)
                    assert revision == first.projection.record_revision
                    assert facts["renta_family.descendientes_count"] == "2"
                    assert facts["renta_family.descendiente.0.birth_date"] == "2015-04-03"
                    assert facts["renta_family.descendiente.0.custodia_compartida"] == "true"
                    assert facts["renta_family.descendiente.0.prorrata_minimo"] == "true"
                    assert facts["renta_family.descendiente.1.birth_date"] == "2020-08-09"

                    unchanged = run_profile_mutation(
                        client,
                        _request(profile_id, revision=revision, digest=digest, descendants=family_rows),
                        timeout=90,
                    )
                    assert unchanged.effect is OperationEffect.NONE
                    assert type(unchanged.projection) is ProfileDescendantsOperationProjection
                    assert (unchanged.projection.total, unchanged.projection.changed) == (2, False)
                    assert unchanged.projection.record_revision == revision

                    with pytest.raises(ProfileMutationRunError) as stale:
                        run_profile_mutation(
                            client,
                            _request(
                                profile_id,
                                revision=baseline.record_revision,
                                digest=baseline.content_digest,
                                descendants=(),
                            ),
                            timeout=90,
                        )
                    assert stale.value.operation_id
                    assert stale.value.reason == "FAIL_PROFILE_RECORD_CONFLICT"
                    assert stale.value.terminal_condition is OperationTerminalCondition.FAILED
                    assert stale.value.effect is not OperationEffect.UPDATED
                    assert _view(client)[:2] == (revision, digest)

                    for malformed in (
                        ProfileDescendantRow(
                            facts=(
                                ProfileDescendantFact(field_key="birth_date", value="2020-08-09"),
                                ProfileDescendantFact(field_key="unknown_field", value="x"),
                            )
                        ),
                        ProfileDescendantRow(
                            facts=(ProfileDescendantFact(field_key="custodia_compartida", value="true"),)
                        ),
                    ):
                        with pytest.raises(ProfileMutationRunError) as invalid:
                            run_profile_mutation(
                                client,
                                _request(profile_id, revision=revision, digest=digest, descendants=(malformed,)),
                                timeout=90,
                            )
                        assert invalid.value.operation_id
                        assert invalid.value.effect is not OperationEffect.UPDATED
                        assert _view(client)[:2] == (revision, digest)

                    replaced = run_profile_mutation(
                        client,
                        _request(profile_id, revision=revision, digest=digest, descendants=younger_rows),
                        timeout=90,
                    )
                    assert replaced.effect is OperationEffect.UPDATED
                    assert type(replaced.projection) is ProfileDescendantsOperationProjection
                    assert (replaced.projection.total, replaced.projection.changed) == (1, True)
                    assert replaced.projection.record_revision == revision + 1
                    revision, digest, facts = _view(client)
                    assert facts["renta_family.descendientes_count"] == "1"
                    assert facts["renta_family.descendiente.0.birth_date"] == "2020-08-09"
                    assert not any(path.startswith("renta_family.descendiente.1.") for path in facts)
                    assert "renta_family.descendiente.0.rentas_anuales" not in facts
                    assert "renta_family.descendiente.0.prorrata_minimo" not in facts

                    cleared = run_profile_mutation(
                        client,
                        _request(profile_id, revision=revision, digest=digest, descendants=()),
                        timeout=90,
                    )
                    assert cleared.effect is OperationEffect.UPDATED
                    assert type(cleared.projection) is ProfileDescendantsOperationProjection
                    assert (cleared.projection.total, cleared.projection.changed) == (0, True)
                    assert cleared.projection.record_revision == revision + 1
                    revision, digest, facts = _view(client)
                    assert facts["renta_family.descendientes_count"] == "0"
                    assert not any(path.startswith("renta_family.descendiente.") for path in facts)

                    empty_again = run_profile_mutation(
                        client,
                        _request(profile_id, revision=revision, digest=digest, descendants=()),
                        timeout=90,
                    )
                    assert empty_again.effect is OperationEffect.NONE
                    assert type(empty_again.projection) is ProfileDescendantsOperationProjection
                    assert (empty_again.projection.total, empty_again.projection.changed) == (0, False)
                    assert empty_again.projection.record_revision == revision

                    with pytest.raises(RuntimeFrontendRefusedError, match="profile_mismatch"):
                        run_profile_mutation(
                            client,
                            _request(foreign_id, revision=revision, digest=digest, descendants=family_rows),
                            timeout=90,
                        )
                    assert _view(client)[:2] == (revision, digest)
                    client.lock()
            finally:
                stop.set()
                running.result(timeout=15)
                endpoint.close()

        final = _record(profile_id, root=root)
        assert final.record_revision == baseline.record_revision + 3
        assert any(
            fact.path == "renta_family.descendiente.0.rentas_anuales" and fact.value is None for fact in final.facts
        )
        assert any(fact.path == "renta_family.descendiente.1.birth_date" and fact.value is None for fact in final.facts)
        assert next(fact.value for fact in final.facts if fact.path == "renta_family.descendientes_count") == Decimal(0)
        foreign_final = _record(foreign_id, root=root)
        assert (foreign_final.record_revision, foreign_final.content_digest) == (
            foreign_baseline.record_revision,
            foreign_baseline.content_digest,
        )
