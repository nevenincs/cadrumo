"""Native ascendant replacement preserves encrypted rows and CAS truth, and a refusal changes nothing."""

from __future__ import annotations

import asyncio
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.application.user_profile.ascendant_rows import ProfileAscendantFact, ProfileAscendantRow
from cadrumo.application.user_profile.profile_operation_contracts import (
    ProfileAscendantsOperationProjection,
    ProfileAscendantsOperationRequest,
)
from cadrumo.core.operations import OperationEffect, OperationFrontendProjection, OperationTerminalCondition
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
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

_COUNT = "renta_family.ascendientes_count"
_OBJECT = "renta_family.ascendiente"
# The 2025 Modelo 100 XSD declares Ascendiente with maxOccurs 4.
_LIMIT = 4


def _row(**leaves: str) -> ProfileAscendantRow:
    return ProfileAscendantRow(
        facts=tuple(ProfileAscendantFact(field_key=key, value=value) for key, value in leaves.items())
    )


def _request(
    profile_id: UUID, *, revision: int, digest: str, ascendants: tuple[ProfileAscendantRow, ...]
) -> ProfileAscendantsOperationRequest:
    return ProfileAscendantsOperationRequest(
        profile_id=profile_id,
        expected_revision=revision,
        expected_content_digest=digest,
        ascendants=ascendants,
    )


def _replace(
    client: FrontendClient, profile_id: UUID, revision: int, digest: str, *rows: ProfileAscendantRow
) -> ProfileAscendantsOperationProjection:
    completion = run_profile_mutation(
        client, _request(profile_id, revision=revision, digest=digest, ascendants=rows), timeout=90
    )
    assert type(completion.projection) is ProfileAscendantsOperationProjection
    return completion.projection


def _replace_with_two_ascendants(
    client: FrontendClient, profile_id: UUID, baseline: UserProfileRecord, rows: tuple[ProfileAscendantRow, ...]
) -> tuple[int, str]:
    proof = bytearray(PROFILE_INPUT.encode())
    client.login_password(proof)
    assert not any(proof)
    revision, digest, facts = profile_view_facts(client)
    assert (revision, digest) == (baseline.record_revision, baseline.content_digest)
    assert not any(path.startswith(f"{_OBJECT}.") for path in facts)

    first = run_profile_mutation(
        client, _request(profile_id, revision=revision, digest=digest, ascendants=rows), timeout=90
    )
    assert first.operation_id and first.effect is OperationEffect.UPDATED
    assert type(first.projection) is ProfileAscendantsOperationProjection
    assert (first.projection.total, first.projection.changed) == (2, True)
    assert first.projection.profile_id == profile_id
    assert first.projection.record_revision == revision + 1
    revision, digest, facts = profile_view_facts(client)
    assert revision == first.projection.record_revision
    assert facts[_COUNT] == "2"
    assert facts[f"{_OBJECT}.0.nif"] == "12345678Z"
    assert facts[f"{_OBJECT}.0.birth_date"] == "1948-03-04"
    assert facts[f"{_OBJECT}.0.convivientes"] == "2"
    assert facts[f"{_OBJECT}.1.birth_date"] == "1951-11-30"
    assert facts[f"{_OBJECT}.1.fallecimiento"] == date(filing_year_envelope().horizon, 2, 1).isoformat()
    return revision, digest


def _refuse_what_the_declaration_cannot_hold(
    client: FrontendClient, profile_id: UUID, revision: int, digest: str
) -> None:
    too_many = tuple(_row(birth_date=f"19{40 + index}-01-01") for index in range(_LIMIT + 1))
    for refused in (
        too_many,
        (_row(nif="12345678A", birth_date="1948-03-04"),),
        (_row(nif="12345678Z"),),
        (_row(birth_date="1948-03-04", fallecimiento="1947-01-01"),),
        (_row(birth_date="1948-03-04", convivientes="11"),),
    ):
        with pytest.raises(ProfileMutationRunError) as invalid:
            run_profile_mutation(
                client, _request(profile_id, revision=revision, digest=digest, ascendants=refused), timeout=90
            )
        assert invalid.value.operation_id
        assert invalid.value.effect is OperationEffect.NONE
        assert invalid.value.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        assert profile_view_facts(client)[:2] == (revision, digest)


def _replace_clear_and_repeat(
    client: FrontendClient, profile_id: UUID, revision: int, digest: str, younger: ProfileAscendantRow
) -> tuple[int, str]:
    replaced = _replace(client, profile_id, revision, digest, younger)
    assert (replaced.total, replaced.changed, replaced.record_revision) == (1, True, revision + 1)
    revision, digest, facts = profile_view_facts(client)
    assert facts[_COUNT] == "1"
    assert not any(path.startswith(f"{_OBJECT}.1.") for path in facts)
    assert f"{_OBJECT}.0.nif" not in facts

    cleared = _replace(client, profile_id, revision, digest)
    assert (cleared.total, cleared.changed, cleared.record_revision) == (0, True, revision + 1)
    revision, digest, facts = profile_view_facts(client)
    assert facts[_COUNT] == "0"
    assert not any(path.startswith(f"{_OBJECT}.") for path in facts)

    again = _replace(client, profile_id, revision, digest)
    assert (again.total, again.changed, again.record_revision) == (0, False, revision)
    return revision, digest


def test_native_ascendants_replace_clear_refuse_and_settle_without_effect(
    tmp_path: Path,
) -> None:
    with worker_profiles(tmp_path) as (root, targets):
        profile_id = targets[0][0].binding.profile_id
        foreign_id = targets[1][0].binding.profile_id
        baseline = stored_profile_record(profile_id, root=root)
        foreign_baseline = stored_profile_record(foreign_id, root=root)
        endpoint = WindowsEndpoint(storage_root=root)
        installation(storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity)
        native = MemoryNativePort()
        with serving_runtime(
            endpoint,
            root,
            capture_login=lambda _channel: SyntheticLogin("ascendants-native-login"),
            secret_store=lambda: native,
            drain_seconds=15,
        ) as served:
            client = asyncio.run(
                FrontendClient.open(served.launch, profile_id=profile_id, frontend=OperationFrontendProjection.CLI)
            )
            with client:
                older = _row(nif="12345678z", birth_date="1948-03-04", convivientes="2")
                younger = _row(
                    birth_date="1951-11-30", fallecimiento=date(filing_year_envelope().horizon, 2, 1).isoformat()
                )
                revision, digest = _replace_with_two_ascendants(client, profile_id, baseline, (older, younger))
                unchanged = _replace(client, profile_id, revision, digest, older, younger)
                assert (unchanged.total, unchanged.changed, unchanged.record_revision) == (2, False, revision)
                with pytest.raises(ProfileMutationRunError) as stale:
                    run_profile_mutation(
                        client,
                        _request(
                            profile_id,
                            revision=baseline.record_revision,
                            digest=baseline.content_digest,
                            ascendants=(),
                        ),
                        timeout=90,
                    )
                assert stale.value.reason == "FAIL_PROFILE_RECORD_CONFLICT"
                assert stale.value.effect is not OperationEffect.UPDATED
                assert profile_view_facts(client)[:2] == (revision, digest)
                _refuse_what_the_declaration_cannot_hold(client, profile_id, revision, digest)
                revision, digest = _replace_clear_and_repeat(client, profile_id, revision, digest, younger)
                with pytest.raises(FrontendRefusedError, match="profile_mismatch"):
                    run_profile_mutation(
                        client,
                        _request(foreign_id, revision=revision, digest=digest, ascendants=(older,)),
                        timeout=90,
                    )
                assert profile_view_facts(client)[:2] == (revision, digest)
                client.lock()
        final = stored_profile_record(profile_id, root=root)
        assert final.record_revision == baseline.record_revision + 3
        assert next(fact.value for fact in final.facts if fact.path == _COUNT) == Decimal(0)
        assert any(fact.path == f"{_OBJECT}.0.birth_date" and fact.value is None for fact in final.facts)
        foreign_final = stored_profile_record(foreign_id, root=root)
        assert (foreign_final.record_revision, foreign_final.content_digest) == (
            foreign_baseline.record_revision,
            foreign_baseline.content_digest,
        )
