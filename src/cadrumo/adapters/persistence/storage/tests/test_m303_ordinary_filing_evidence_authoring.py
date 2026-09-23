"""Ordinary M303 filing-evidence authoring through real secure applicability custody."""

from __future__ import annotations

from datetime import UTC, datetime
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
    author_ordinary_m303_filing_instance_evidence,
)
from cadrumo.core.period import Period
from cadrumo.domain.attachments.errors import AttachmentValidationError
from cadrumo.domain.attachments.m303_filing_evidence import M303Exonerado390ApplicabilityAssertion
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.filing_evidence import FilingEvidenceReference
from cadrumo.domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from cadrumo.domain.user_profile.values import UserProfileFact

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "3a1f0b2c-4d5e-4f60-8a71-92b3c4d5e6f7"
_PERIOD = Period.from_year_and_code(2025, "1T")
_CLOCK = datetime(2025, 4, 1, 10, tzinfo=UTC)


def _work_unit(operation: PinnedAuthorityOperation) -> WorkUnit:
    snapshot = operation.snapshot("303", filing_year=2025, period="1T")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=2025,
            period=_PERIOD,
            revision_id=snapshot.revision.id,
        ),
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=2025,
        period=_PERIOD,
        revision_id=snapshot.revision.id,
        name="303-2025-1T",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _attestation_reference(*, operation: PinnedAuthorityOperation) -> FilingEvidenceReference:
    return admit_m303_exonerado_390_applicability_attestation(
        bucket_id=_BUCKET_ID,
        request=M303Exonerado390ApplicabilityAttestationRequest(
            filing_year=2025,
            period=_PERIOD,
            asserted_value=M303Exonerado390ApplicabilityAssertion.NOT_APPLICABLE,
            observed_at=datetime(2025, 3, 31, 12, tzinfo=UTC),
        ),
        actor="operator:test",
        operation=operation,
        store=AttachmentStore(),
        clock=lambda: _CLOCK,
    ).filing_evidence_reference()


def test_authors_general_scope_evidence_from_current_profile_and_authority(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        seed_modelo_ready_profile_record(_BUCKET_ID, clock=_CLOCK)
        with bound_test_profile_record(_BUCKET_ID):
            evidence = author_ordinary_m303_filing_instance_evidence(
                work_unit=_work_unit(operation),
                request=OrdinaryM303FilingEvidenceRequest(
                    filing_year=2025,
                    period=_PERIOD,
                    joint_return_elected=True,
                    annual_volume_nonzero=True,
                    exonerado_390_applicability_reference=_attestation_reference(operation=operation),
                ),
                operation=operation,
                attachment_store=AttachmentStore(),
            )

    assert evidence.m303.joint_return_elected is True
    assert evidence.m303.annual_volume_nonzero is True
    assert evidence.m303.insolvency is None
    exonerado_390 = evidence.m303.exonerado_390
    assert exonerado_390 is not None
    assert exonerado_390.applicable is False
    assert evidence.m303.regimen_simplificado.scope_decision.is_not_claimed is True
    assert evidence.m303.regimen_simplificado.rows.activities == ()
    assert evidence.m303.regimen_simplificado.calculation_result.activities == ()


def _coordinate_work_unit(operation: PinnedAuthorityOperation, period: Period) -> WorkUnit:
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


@pytest.mark.parametrize(("filing_year", "code"), [(2022, "1T"), (2026, "1T")], ids=["earliest", "latest"])
def test_authors_every_quarter_whose_record_design_declares_the_ordinary_evidence_fields(
    tmp_path: Path, operation: PinnedAuthorityOperation, filing_year: int, code: str
) -> None:
    """Support follows the selected revision's record design, from its first to its latest authored year."""
    period = Period.from_year_and_code(filing_year, code)
    observed_at = datetime.combine(period.end_date, datetime.min.time(), tzinfo=UTC).replace(hour=12)
    clock = observed_at.replace(hour=13)
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        seed_modelo_ready_profile_record(_BUCKET_ID, clock=_CLOCK)
        with bound_test_profile_record(_BUCKET_ID):
            store = AttachmentStore()
            reference = admit_m303_exonerado_390_applicability_attestation(
                bucket_id=_BUCKET_ID,
                request=M303Exonerado390ApplicabilityAttestationRequest(
                    filing_year=filing_year,
                    period=period,
                    asserted_value=M303Exonerado390ApplicabilityAssertion.NOT_APPLICABLE,
                    observed_at=observed_at,
                ),
                actor="operator:test",
                operation=operation,
                store=store,
                clock=lambda: clock,
            ).filing_evidence_reference()
            evidence = author_ordinary_m303_filing_instance_evidence(
                work_unit=_coordinate_work_unit(operation, period),
                request=OrdinaryM303FilingEvidenceRequest(
                    filing_year=filing_year,
                    period=period,
                    joint_return_elected=False,
                    annual_volume_nonzero=False,
                    exonerado_390_applicability_reference=reference,
                ),
                operation=operation,
                attachment_store=store,
            )

    assert evidence.m303.period == period
    assert evidence.m303.joint_return_elected is False
    assert evidence.m303.annual_volume_nonzero is False
    exonerado_390 = evidence.m303.exonerado_390
    assert exonerado_390 is not None
    assert exonerado_390.applicable is False


def test_refuses_a_monthly_coordinate_before_admitting_any_attestation(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """The ordinary evidence path is quarterly; a monthly filer is refused rather than given quarterly evidence."""
    period = Period.from_year_and_code(2026, "01")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        seed_modelo_ready_profile_record(_BUCKET_ID, clock=_CLOCK)
        with bound_test_profile_record(_BUCKET_ID):
            store = AttachmentStore()
            with pytest.raises(AttachmentValidationError, match="quarterly"):
                admit_m303_exonerado_390_applicability_attestation(
                    bucket_id=_BUCKET_ID,
                    request=M303Exonerado390ApplicabilityAttestationRequest(
                        filing_year=2026,
                        period=period,
                        asserted_value=M303Exonerado390ApplicabilityAssertion.NOT_APPLICABLE,
                        observed_at=datetime(2026, 2, 1, 12, tzinfo=UTC),
                    ),
                    actor="operator:test",
                    operation=operation,
                    store=store,
                    clock=lambda: datetime(2026, 2, 2, 12, tzinfo=UTC),
                )
            assert tuple(store.iter_manifests()) == ()
            with pytest.raises(M303FilingEvidenceError, match="quarterly"):
                author_ordinary_m303_filing_instance_evidence(
                    work_unit=_coordinate_work_unit(operation, period),
                    request=OrdinaryM303FilingEvidenceRequest(
                        filing_year=2026,
                        period=period,
                        joint_return_elected=False,
                        annual_volume_nonzero=False,
                        exonerado_390_applicability_reference=FilingEvidenceReference(reference="attachment:none"),
                    ),
                    operation=operation,
                    attachment_store=store,
                )


def test_refuses_an_unresolved_secure_applicability_reference(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        seed_modelo_ready_profile_record(_BUCKET_ID, clock=_CLOCK)
        with bound_test_profile_record(_BUCKET_ID), pytest.raises(M303Exonerado390AttestationUnadmissibleError):
            author_ordinary_m303_filing_instance_evidence(
                work_unit=_work_unit(operation),
                request=OrdinaryM303FilingEvidenceRequest(
                    filing_year=2025,
                    period=_PERIOD,
                    joint_return_elected=False,
                    annual_volume_nonzero=False,
                    exonerado_390_applicability_reference=FilingEvidenceReference(reference="attachment:missing"),
                ),
                operation=operation,
                attachment_store=AttachmentStore(),
            )


def test_refuses_without_an_authenticated_current_profile(tmp_path: Path, operation: PinnedAuthorityOperation) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID), pytest.raises(ModeloProfileReadinessError):
        author_ordinary_m303_filing_instance_evidence(
            work_unit=_work_unit(operation),
            request=OrdinaryM303FilingEvidenceRequest(
                filing_year=2025,
                period=_PERIOD,
                joint_return_elected=False,
                annual_volume_nonzero=False,
                exonerado_390_applicability_reference=FilingEvidenceReference(reference="attachment:unresolved"),
            ),
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
                    work_unit=_work_unit(operation),
                    request=OrdinaryM303FilingEvidenceRequest(
                        filing_year=2025,
                        period=_PERIOD,
                        joint_return_elected=False,
                        annual_volume_nonzero=False,
                        exonerado_390_applicability_reference=FilingEvidenceReference(
                            reference="attachment:unresolved"
                        ),
                    ),
                    operation=operation,
                    attachment_store=AttachmentStore(),
                )
