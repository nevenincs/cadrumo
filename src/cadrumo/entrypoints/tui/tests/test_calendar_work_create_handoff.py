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
from ....core.errors.error_codes import resolve_error_message
from ....core.errors.hierarchy import CadrumoError
from ....core.filing_year import FILING_YEAR_MAX
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...adapter_composition import build_work_lifecycle_ports
from ..declarations.tests.calendar_fixtures import calendar_projection
from ..launcher import _calendar_work_create_handoff, _declarations_work_create_handoff

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
def operation() -> Iterator[PinnedAuthorityOperation]:
    """Pin one authority generation, as a TUI session does when it opens."""
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


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
    bucket_id: str, profile_decrypts: list[str], operation: PinnedAuthorityOperation
) -> None:
    entry = next(row for row in calendar_projection().entries if str(row.modelo) == "111")
    action = declare_next_action(
        "operator.modelo.work.create", modelo="111", year=entry.filing_year, period=str(entry.period)
    )
    handoff = _calendar_work_create_handoff(bucket_id=bucket_id, actor="operator", operation=operation)
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


def test_declarations_handoff_creates_and_reuses_2025_selected_work(
    bucket_id: str, operation: PinnedAuthorityOperation
) -> None:
    refreshes: list[str] = []
    handoff = _declarations_work_create_handoff(
        bucket_id=bucket_id,
        actor="operator",
        operation=operation,
        refresh_after_success=lambda: refreshes.append("refreshed"),
    )
    selected_period = Period.from_year_and_code(2025, "2T")

    created = handoff("111", 2025, selected_period)
    reused = handoff("111", 2025, selected_period)

    assert created.reused is False
    assert reused.reused is True
    assert refreshes == ["refreshed", "refreshed"]
    units = [
        unit
        for unit in build_work_lifecycle_ports(bucket_id=bucket_id).work_unit_repository.load().work_units.values()
        if (str(unit.modelo), unit.filing_year, unit.period) == ("111", 2025, selected_period)
    ]
    assert len(units) == 1


@pytest.mark.parametrize(
    ("modelo", "filing_year", "period_year", "period_code", "expected_key"),
    [
        ("600", 2025, 2025, "2T", "cli.app.modelo.work.create_stub_modelo_600_refused"),
        ("111", 2025, 2025, "0A", None),
        ("999", 2025, 2025, "2T", None),
        ("111", 2025, 2024, "2T", "tui.declarations.work_create.refusal.period"),
        ("111", FILING_YEAR_MAX + 1, FILING_YEAR_MAX + 1, "2T", "tui.declarations.work_create.refusal.year"),
        ("200", 2025, 2025, "0A", "tui.declarations.work_create.refusal.not_applicable"),
    ],
    ids=["ceded-modelo", "undeclared-period", "unknown-modelo", "year-period-mismatch", "year-range", "not-applicable"],
)
def test_declarations_handoff_refuses_before_persisting_or_refreshing(
    bucket_id: str,
    operation: PinnedAuthorityOperation,
    modelo: str,
    filing_year: int,
    period_year: int,
    period_code: str,
    expected_key: str | None,
) -> None:
    refreshes: list[str] = []
    handoff = _declarations_work_create_handoff(
        bucket_id=bucket_id,
        actor="operator",
        operation=operation,
        refresh_after_success=lambda: refreshes.append("refreshed"),
    )

    with pytest.raises(CadrumoError) as refusal:
        handoff(modelo, filing_year, Period.from_year_and_code(period_year, period_code))

    if expected_key is not None:
        assert refusal.value.translated_message == expected_key
    # Every refusal reaches the operator as words, never as an empty notice.
    assert resolve_error_message(refusal.value).strip()
    assert refreshes == []
    assert not build_work_lifecycle_ports(bucket_id=bucket_id).work_unit_repository.load().work_units
