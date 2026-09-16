"""The calendar's "create this declaration" handoff decrypts the profile once.

The calendar runs the handoff on a worker thread while it shows its progress,
so every extra profile decrypt is time the operator waits for nothing. The
readiness gate and the foral guard both read the profile; the handoff loads it
once and hands that record to both. The count is taken at the capsule store,
so a consumer that bypasses the record repository is counted too.
"""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest

from ....adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from ....adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from ....adapters.persistence.storage.tests.secure_sql import (
    isolated_cli_backend as _isolated_cli_backend,
)
from ....application.overview.next_actions import declare_next_action
from ....application.user_profile.capsule_record import LoadedProfileRecord, ProfileRecordStore
from ....core.bucket_pointer import resolve_active_bucket_id
from ...adapter_composition import build_work_lifecycle_ports
from ..declarations.tests.test_calendar import _projection
from ..launcher import _calendar_work_create_handoff

__all__ = ["_isolated_cli_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


# Modelo 111 readiness needs the colegio concertado answer on top of identity.
_OPERATOR_FACTS = {
    "identity.tax_id": "12345678Z",
    "identity.name": "Operator",
    "identity.surnames": "Readiness",
    "activities.description": "design",
    "withholding.colegio_concertado": "false",
}


@pytest.fixture
def bucket_id() -> Iterator[str]:
    """Publish and select one complete synthetic profile for the test."""
    profile_id = str(uuid4())
    with open_test_profile_session(profile_id):
        register_minimal_profile(profile_id=profile_id, display_name="operator", overrides=_OPERATOR_FACTS)
        active = resolve_active_bucket_id()
        assert active is not None
        yield active


@pytest.fixture
def profile_decrypts(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record every profile-record decrypt in the process, still performing it."""
    decrypts: list[str] = []
    real_load = ProfileRecordStore.load

    def counting_load(self: ProfileRecordStore) -> LoadedProfileRecord:
        decrypts.append(str(self.session.profile_id))
        return real_load(self)

    monkeypatch.setattr(ProfileRecordStore, "load", counting_load)
    return decrypts


def test_the_calendar_handoff_creates_the_declaration_decrypting_the_profile_once(
    bucket_id: str, profile_decrypts: list[str]
) -> None:
    entry = next(row for row in _projection().entries if str(row.modelo) == "111")
    action = declare_next_action(
        "operator.modelo.work.create", modelo="111", year=entry.filing_year, period=str(entry.period)
    )
    handoff = _calendar_work_create_handoff(bucket_id=bucket_id, actor="operator")
    profile_decrypts.clear()

    handoff(action, entry)

    assert len(profile_decrypts) == 1, profile_decrypts
    created = [
        unit
        for unit in build_work_lifecycle_ports(bucket_id=bucket_id).work_unit_repository.load().work_units.values()
        if (str(unit.modelo), unit.filing_year, str(unit.period))
        == (str(entry.modelo), entry.filing_year, str(entry.period))
    ]
    assert len(created) == 1, "the handoff must actually create the declaration, or the count proves nothing"
