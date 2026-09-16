"""The calendar's "create this declaration" action decrypts the profile once.

The handoff runs the foral guard and the work-unit writer, which replays the
baseline and full readiness gates. It loads the profile once and hands that
record to each of them. The count is taken at the capsule store on the real
encrypted repository.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile
from ....application.modelo.declarations_calendar import DeclarationsCalendarEntryRefV1
from ....application.operator_actions.models import ActionReference, DeclaredNextAction
from ....application.overview.calendar_models import OverviewCalendarEntrySource, OverviewPeriodState
from ....application.user_profile.capsule_record import LoadedProfileRecord, ProfileRecordStore
from ....core.period import Period
from ....domain.calculations.registry.tests.published_authority import leased_profile_create_context
from ....domain.deadlines.models import ObligationStatus
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ..launcher import _calendar_work_create_handoff

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_PROFILE_ID = "0ac1e000-0000-4000-8000-000000370002"
_LABEL = "Calendar create profile load count"


@pytest.fixture
def runtime_profile(tmp_path: Path, authority_operation: object) -> Iterator[TestRuntimeProfile]:
    del authority_operation  # the record is created under the leased generation
    with isolated_cli_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID, label=_LABEL) as profile:
        record = create_user_profile_record(
            profile_id=_PROFILE_ID,
            setup_state=ProfileSetupState.COMPLETE,
            facts=(
                UserProfileFact(path="identity.name", value="Marta"),
                UserProfileFact(path="identity.surnames", value="Diaz Ortega"),
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="activities.description", value="economic activity"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="provenance.source", value="manual_cli"),
                UserProfileFact(path="renta_taxpayer.birth_date", value="1985-06-15"),
                UserProfileFact(path="renta_filing.declaration_type", value="1"),
            ),
            context=leased_profile_create_context(),
        )
        seed_test_profile_record(record, root=profile.storage_root, label=_LABEL)
        yield profile


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


@pytest.mark.usefixtures("runtime_profile")
def test_calendar_create_decrypts_the_profile_once(profile_decrypts: list[str]) -> None:
    create = _calendar_work_create_handoff(bucket_id=_PROFILE_ID, actor="operator")
    entry = DeclarationsCalendarEntryRefV1(
        modelo="100",
        filing_year=2024,
        period=Period.from_year_and_code(2024, "0A"),
        opens_on=date(2025, 4, 2),
        adjusted_closes_on=date(2025, 6, 30),
        legal_status=ObligationStatus.UPCOMING,
        user_state=OverviewPeriodState.DUE,
        local_filing_state=None,
        aeat_submission_state=None,
        justificante_verified=None,
        source=OverviewCalendarEntrySource.REGISTRY_DEADLINE,
    )

    create(DeclaredNextAction(action=ActionReference(action_id="operator.modelo.work.create")), entry)

    assert profile_decrypts == [_PROFILE_ID]
