"""Native descendant-family replacement preserves encrypted rows and CAS truth."""

from __future__ import annotations

import asyncio
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.application.user_profile.descendant_rows import (
    ProfileDescendantFact,
    ProfileDescendantRow,
    encode_descendant_rows,
)
from cadrumo.application.user_profile.profile_operation_contracts import (
    ProfileDescendantsOperationProjection,
    ProfileDescendantsOperationRequest,
)
from cadrumo.core.operations import OperationEffect, OperationFrontendProjection, OperationTerminalCondition
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.contribuyente.descendant import DescendantInfo
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


def _request(
    profile_id: UUID, *, revision: int, digest: str, descendants: tuple[ProfileDescendantRow, ...]
) -> ProfileDescendantsOperationRequest:
    return ProfileDescendantsOperationRequest(
        profile_id=profile_id,
        expected_revision=revision,
        expected_content_digest=digest,
        descendants=descendants,
    )


def _replace_with_family(
    client: FrontendClient,
    profile_id: UUID,
    baseline: UserProfileRecord,
    family_rows: tuple[ProfileDescendantRow, ...],
) -> tuple[int, str]:
    proof = bytearray(PROFILE_INPUT.encode())
    client.login_password(proof)
    assert not any(proof)
    revision, digest, facts = profile_view_facts(client)
    assert (revision, digest) == (baseline.record_revision, baseline.content_digest)
    assert not any(path.startswith("renta_family.descendiente.") for path in facts)

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
    revision, digest, facts = profile_view_facts(client)
    assert revision == first.projection.record_revision
    assert facts["renta_family.descendientes_count"] == "2"
    assert facts["renta_family.descendiente.0.birth_date"] == "2015-04-03"
    assert facts["renta_family.descendiente.0.custodia_compartida"] == "true"
    assert facts["renta_family.descendiente.0.prorrata_minimo"] == "true"
    assert facts["renta_family.descendiente.1.birth_date"] == "2020-08-09"
    return revision, digest


def _replay_unchanged_family(
    client: FrontendClient,
    profile_id: UUID,
    revision: int,
    digest: str,
    family_rows: tuple[ProfileDescendantRow, ...],
) -> None:
    unchanged = run_profile_mutation(
        client,
        _request(profile_id, revision=revision, digest=digest, descendants=family_rows),
        timeout=90,
    )
    assert unchanged.effect is OperationEffect.NONE
    assert type(unchanged.projection) is ProfileDescendantsOperationProjection
    assert (unchanged.projection.total, unchanged.projection.changed) == (2, False)
    assert unchanged.projection.record_revision == revision


def _refuse_stale_and_malformed(
    client: FrontendClient, profile_id: UUID, baseline: UserProfileRecord, revision: int, digest: str
) -> None:
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
    assert profile_view_facts(client)[:2] == (revision, digest)

    for malformed in (
        ProfileDescendantRow(
            facts=(
                ProfileDescendantFact(field_key="birth_date", value="2020-08-09"),
                ProfileDescendantFact(field_key="unknown_field", value="x"),
            )
        ),
        ProfileDescendantRow(facts=(ProfileDescendantFact(field_key="custodia_compartida", value="true"),)),
    ):
        with pytest.raises(ProfileMutationRunError) as invalid:
            run_profile_mutation(
                client,
                _request(profile_id, revision=revision, digest=digest, descendants=(malformed,)),
                timeout=90,
            )
        assert invalid.value.operation_id
        assert invalid.value.effect is OperationEffect.NONE
        assert invalid.value.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        assert profile_view_facts(client)[:2] == (revision, digest)


def _replace_with_younger_only(
    client: FrontendClient,
    profile_id: UUID,
    revision: int,
    digest: str,
    younger_rows: tuple[ProfileDescendantRow, ...],
) -> tuple[int, str]:
    replaced = run_profile_mutation(
        client,
        _request(profile_id, revision=revision, digest=digest, descendants=younger_rows),
        timeout=90,
    )
    assert replaced.effect is OperationEffect.UPDATED
    assert type(replaced.projection) is ProfileDescendantsOperationProjection
    assert (replaced.projection.total, replaced.projection.changed) == (1, True)
    assert replaced.projection.record_revision == revision + 1
    revision, digest, facts = profile_view_facts(client)
    assert facts["renta_family.descendientes_count"] == "1"
    assert facts["renta_family.descendiente.0.birth_date"] == "2020-08-09"
    assert not any(path.startswith("renta_family.descendiente.1.") for path in facts)
    assert "renta_family.descendiente.0.rentas_anuales" not in facts
    assert "renta_family.descendiente.0.prorrata_minimo" not in facts
    return revision, digest


def _clear_family_and_repeat(client: FrontendClient, profile_id: UUID, revision: int, digest: str) -> tuple[int, str]:
    cleared = run_profile_mutation(
        client,
        _request(profile_id, revision=revision, digest=digest, descendants=()),
        timeout=90,
    )
    assert cleared.effect is OperationEffect.UPDATED
    assert type(cleared.projection) is ProfileDescendantsOperationProjection
    assert (cleared.projection.total, cleared.projection.changed) == (0, True)
    assert cleared.projection.record_revision == revision + 1
    revision, digest, facts = profile_view_facts(client)
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
    return revision, digest


def _assert_final_records(
    root: Path,
    profile_id: UUID,
    foreign_id: UUID,
    baseline: UserProfileRecord,
    foreign_baseline: UserProfileRecord,
) -> None:
    final = stored_profile_record(profile_id, root=root)
    assert final.record_revision == baseline.record_revision + 3
    assert any(fact.path == "renta_family.descendiente.0.rentas_anuales" and fact.value is None for fact in final.facts)
    assert any(fact.path == "renta_family.descendiente.1.birth_date" and fact.value is None for fact in final.facts)
    assert next(fact.value for fact in final.facts if fact.path == "renta_family.descendientes_count") == Decimal(0)
    foreign_final = stored_profile_record(foreign_id, root=root)
    assert (foreign_final.record_revision, foreign_final.content_digest) == (
        foreign_baseline.record_revision,
        foreign_baseline.content_digest,
    )


def test_native_descendant_family_replace_reindex_clear_and_refuse_stale_intent(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
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
            capture_login=lambda _channel: SyntheticLogin("descendants-native-login"),
            secret_store=lambda: native,
            drain_seconds=15,
        ) as served:
            client = asyncio.run(
                FrontendClient.open(served.launch, profile_id=profile_id, frontend=OperationFrontendProjection.CLI)
            )
            with client:
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
                revision, digest = _replace_with_family(client, profile_id, baseline, family_rows)
                _replay_unchanged_family(client, profile_id, revision, digest, family_rows)
                _refuse_stale_and_malformed(client, profile_id, baseline, revision, digest)
                revision, digest = _replace_with_younger_only(client, profile_id, revision, digest, younger_rows)
                revision, digest = _clear_family_and_repeat(client, profile_id, revision, digest)
                with pytest.raises(FrontendRefusedError, match="profile_mismatch"):
                    run_profile_mutation(
                        client,
                        _request(foreign_id, revision=revision, digest=digest, descendants=family_rows),
                        timeout=90,
                    )
                assert profile_view_facts(client)[:2] == (revision, digest)
                client.lock()
        _assert_final_records(root, profile_id, foreign_id, baseline, foreign_baseline)
