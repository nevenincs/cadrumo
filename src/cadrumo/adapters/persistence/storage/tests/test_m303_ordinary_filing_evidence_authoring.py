"""Ordinary M303 filing-evidence authoring through real secure applicability custody.

DP30301 Nota 4 asks the Modelo 390 exemption only in the last settlement period
of the year (12 or 4T), so only those periods carry an attestation.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    seed_modelo_ready_profile_record,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.action_errors import (
    M303Exonerado390AttestationUnadmissibleError,
    M303FilingEvidenceError,
    ModeloProfileReadinessError,
)
from cadrumo.application.modelo.m303_exonerado_390_applicability_attestation import (
    M303Exonerado390ApplicabilityAttestationRequest,
    admit_m303_exonerado_390_applicability_attestation,
)
from cadrumo.application.modelo.m303_ordinary_filing_evidence_authoring import (
    OrdinaryM303FilingEvidenceRequest,
    author_ordinary_m303_evidence_for_work,
    author_ordinary_m303_filing_instance_evidence,
)
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.core.period import Period, PeriodKind
from cadrumo.domain.attachments.m303_filing_evidence import M303Exonerado390ApplicabilityAssertion
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.filing_evidence import FilingEvidenceReference
from cadrumo.domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from cadrumo.domain.user_profile.values import UserProfileFact

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "3a1f0b2c-4d5e-4f60-8a71-92b3c4d5e6f7"
_CLOCK = datetime(2025, 4, 1, 10, tzinfo=UTC)
_FIRST_QUARTER = Period.from_year_and_code(2025, "1T")
_LAST_QUARTER = Period.from_year_and_code(2025, "4T")
_OUTSIDE_LAST_PERIOD = "modelo.work.calculate.m303_filing_evidence.exonerado_390_attestation_outside_last_period"


def _work_unit(operation: PinnedAuthorityOperation, period: Period) -> WorkUnit:
    snapshot = operation.snapshot("303", filing_year=period.filing_year, period=period.registry_token)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=period.filing_year,
            period=period,
            revision_id=snapshot.revision.id,
        ),
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=period.filing_year,
        period=period,
        revision_id=snapshot.revision.id,
        name=f"303-{period.filing_year}-{period.registry_token}",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _attestation_reference(
    *, operation: PinnedAuthorityOperation, store: AttachmentStore, period: Period
) -> FilingEvidenceReference:
    """Admit the operator's not-applicable answer on the day the period closes."""
    observed_at = datetime.combine(period.end_date, time(12), tzinfo=UTC)
    return admit_m303_exonerado_390_applicability_attestation(
        bucket_id=_BUCKET_ID,
        request=M303Exonerado390ApplicabilityAttestationRequest(
            filing_year=period.filing_year,
            period=period,
            asserted_value=M303Exonerado390ApplicabilityAssertion.NOT_APPLICABLE,
            observed_at=observed_at,
        ),
        actor="operator:test",
        operation=operation,
        store=store,
        clock=lambda: observed_at + timedelta(days=1),
    ).filing_evidence_reference()


def _settle_monthly(profiles: ProfileRecordRepository) -> None:
    """Register the taxpayer in REDEME, which RD 1624/1992 art. 71 makes a monthly filer."""
    current = profiles.load(_BUCKET_ID)
    profiles.apply_fact_changes(
        _BUCKET_ID,
        facts=tuple(
            UserProfileFact(path=fact.path, value=True) if fact.path == "iva.redeme_enrolled" else fact
            for fact in current.facts
        ),
        expected_revision=current.record_revision,
        expected_content_digest=current.content_digest,
        event_type=BucketEventType.PROFILE_VALUES_UPDATED,
        event_payload={},
        now=current.updated_at,
    )


def _request(period: Period, reference: FilingEvidenceReference | None) -> OrdinaryM303FilingEvidenceRequest:
    return OrdinaryM303FilingEvidenceRequest(
        filing_year=period.filing_year,
        period=period,
        joint_return_elected=False,
        exonerado_390_applicability_reference=reference,
    )


@pytest.mark.parametrize(
    ("filing_year", "code"),
    [(2022, "1T"), (2025, "1T"), (2026, "1T"), (2025, "11"), (2026, "01")],
    ids=["earliest-quarter", "quarter", "latest-quarter", "month-before-12", "latest-month"],
)
def test_a_period_before_the_last_authors_without_the_exemption_question(
    tmp_path: Path, operation: PinnedAuthorityOperation, filing_year: int, code: str
) -> None:
    """Quarterly and monthly periods before the last carry no exemption evidence and no annual-volume answer."""
    period = Period.from_year_and_code(filing_year, code)
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        seed_modelo_ready_profile_record(_BUCKET_ID, clock=_CLOCK)
        with bound_test_profile_record(_BUCKET_ID) as profiles:
            if period.kind is PeriodKind.MONTHLY:
                _settle_monthly(profiles)
            evidence = author_ordinary_m303_filing_instance_evidence(
                work_unit=_work_unit(operation, period),
                request=_request(period, None),
                operation=operation,
                attachment_store=AttachmentStore(),
            )

    assert evidence.m303.period == period
    assert evidence.m303.joint_return_elected is False
    assert evidence.m303.exonerado_390 is None
    assert evidence.m303.annual_volume_nonzero is None
    assert evidence.m303.regimen_simplificado.scope_decision.is_not_claimed is True


@pytest.mark.parametrize(
    ("filing_year", "code"), [(2022, "4T"), (2025, "4T"), (2025, "12")], ids=["earliest", "quarter", "month"]
)
def test_the_last_period_authors_the_attested_exemption(
    tmp_path: Path, operation: PinnedAuthorityOperation, filing_year: int, code: str
) -> None:
    period = Period.from_year_and_code(filing_year, code)
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        seed_modelo_ready_profile_record(_BUCKET_ID, clock=_CLOCK)
        with bound_test_profile_record(_BUCKET_ID) as profiles:
            if period.kind is PeriodKind.MONTHLY:
                _settle_monthly(profiles)
            store = AttachmentStore()
            reference = _attestation_reference(operation=operation, store=store, period=period)
            evidence = author_ordinary_m303_filing_instance_evidence(
                work_unit=_work_unit(operation, period),
                request=_request(period, reference),
                operation=operation,
                attachment_store=store,
            )

    exonerado_390 = evidence.m303.exonerado_390
    assert exonerado_390 is not None
    assert exonerado_390.applicable is False
    assert exonerado_390.applicability_reference == reference
    assert evidence.m303.annual_volume_nonzero is None


def test_the_last_period_refuses_without_an_attestation(tmp_path: Path, operation: PinnedAuthorityOperation) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        seed_modelo_ready_profile_record(_BUCKET_ID, clock=_CLOCK)
        with bound_test_profile_record(_BUCKET_ID), pytest.raises(M303FilingEvidenceError) as raised:
            author_ordinary_m303_filing_instance_evidence(
                work_unit=_work_unit(operation, _LAST_QUARTER),
                request=_request(_LAST_QUARTER, None),
                operation=operation,
                attachment_store=AttachmentStore(),
            )

    failure = raised.value.precondition_failure
    assert failure is not None
    assert failure.scenario_id == "modelo.work.calculate.m303_filing_evidence.missing"


def test_an_attestation_outside_the_last_period_is_refused_before_custody(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """A supplied attestation is refused rather than ignored, and custody is never read."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        seed_modelo_ready_profile_record(_BUCKET_ID, clock=_CLOCK)
        with bound_test_profile_record(_BUCKET_ID), pytest.raises(M303FilingEvidenceError) as raised:
            author_ordinary_m303_filing_instance_evidence(
                work_unit=_work_unit(operation, _FIRST_QUARTER),
                request=_request(_FIRST_QUARTER, FilingEvidenceReference(reference="attachment:unread")),
                operation=operation,
                attachment_store=AttachmentStore(),
            )

    failure = raised.value.precondition_failure
    assert failure is not None
    assert failure.scenario_id == _OUTSIDE_LAST_PERIOD


def test_an_incomplete_attestation_identity_refuses_at_the_shared_entry(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """Every entrypoint passes the two public identifiers; one without the other is refused."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        seed_modelo_ready_profile_record(_BUCKET_ID, clock=_CLOCK)
        with bound_test_profile_record(_BUCKET_ID), pytest.raises(M303Exonerado390AttestationUnadmissibleError):
            author_ordinary_m303_evidence_for_work(
                work_unit=_work_unit(operation, _LAST_QUARTER),
                joint_return_elected=False,
                exonerado_390_attachment_id="a" * 64,
                exonerado_390_sha256=None,
                operation=operation,
                open_attachment_store=AttachmentStore,
            )


def test_refuses_an_unresolved_secure_applicability_reference(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        seed_modelo_ready_profile_record(_BUCKET_ID, clock=_CLOCK)
        with bound_test_profile_record(_BUCKET_ID), pytest.raises(M303Exonerado390AttestationUnadmissibleError):
            author_ordinary_m303_filing_instance_evidence(
                work_unit=_work_unit(operation, _LAST_QUARTER),
                request=_request(_LAST_QUARTER, FilingEvidenceReference(reference="attachment:missing")),
                operation=operation,
                attachment_store=AttachmentStore(),
            )


def test_refuses_without_an_authenticated_current_profile(tmp_path: Path, operation: PinnedAuthorityOperation) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID), pytest.raises(ModeloProfileReadinessError):
        author_ordinary_m303_filing_instance_evidence(
            work_unit=_work_unit(operation, _FIRST_QUARTER),
            request=_request(_FIRST_QUARTER, None),
            operation=operation,
            attachment_store=AttachmentStore(),
        )


def test_refuses_a_simplified_scope_profile_before_using_the_ordinary_branch(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        seed_modelo_ready_profile_record(_BUCKET_ID, clock=_CLOCK)
        with bound_test_profile_record(_BUCKET_ID) as profiles:
            current = profiles.load(_BUCKET_ID)
            profiles.apply_fact_changes(
                _BUCKET_ID,
                facts=tuple(
                    UserProfileFact(path=fact.path, value="simplified")
                    if fact.path == "iva.m303_regime_composition"
                    else fact
                    for fact in current.facts
                ),
                expected_revision=current.record_revision,
                expected_content_digest=current.content_digest,
                event_type=BucketEventType.PROFILE_VALUES_UPDATED,
                event_payload={},
                now=current.updated_at,
            )

            with pytest.raises(M303FilingEvidenceError, match="unsupported"):
                author_ordinary_m303_filing_instance_evidence(
                    work_unit=_work_unit(operation, _FIRST_QUARTER),
                    request=_request(_FIRST_QUARTER, None),
                    operation=operation,
                    attachment_store=AttachmentStore(),
                )


@pytest.mark.parametrize(
    ("code", "monthly_filer"), [("01", False), ("1T", True)], ids=["quarterly-filer-month", "monthly-filer-quarter"]
)
def test_a_period_outside_the_profile_filing_schedule_is_refused(
    tmp_path: Path, operation: PinnedAuthorityOperation, code: str, monthly_filer: bool
) -> None:
    """RD 1624/1992 art. 71 settles REDEME and large-company filers monthly and everyone else quarterly."""
    period = Period.from_year_and_code(2025, code)
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        seed_modelo_ready_profile_record(_BUCKET_ID, clock=_CLOCK)
        with bound_test_profile_record(_BUCKET_ID) as profiles:
            if monthly_filer:
                _settle_monthly(profiles)
            with pytest.raises(M303FilingEvidenceError) as raised:
                author_ordinary_m303_filing_instance_evidence(
                    work_unit=_work_unit(operation, period),
                    request=_request(period, None),
                    operation=operation,
                    attachment_store=AttachmentStore(),
                )

    failure = raised.value.precondition_failure
    assert failure is not None
    assert failure.scenario_id == "modelo.work.calculate.m303_filing_evidence.period_outside_filing_schedule"
