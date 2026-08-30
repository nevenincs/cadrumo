"""Approval-basis staleness coverage for the taxpayer profile-activity source.

Exercises the ``profile_activity_fingerprint`` added to
:class:`~domain.filing.ModeloApprovalBasis`: an ``APROBADO`` draft must go stale
with
:attr:`~application.filing.ModeloApprovalStaleReason.PROFILE_ACTIVITY_CHANGED`
when a taxpayer-profile fact that scopes relation resolution changes
(activity-start date, m111 no-retenciones attestations, declared income
categories), and must not be flagged when the profile is unchanged.

The digest is self-loaded from the bucket's
:class:`~application.user_profile.CommittedProfileRepository` via the wizard-free
canonical projection (:func:`~application.user_profile.record_to_path_values`),
the same projection the relation resolver reads, so change-detection is
reproducible at approve and refresh time with only ``bucket_id`` in scope, without
running the source mesh.

See Also:
    :func:`~application.filing.compute_current_approval_basis`
        Builds the current review fingerprints, including profile activity.
    :func:`~application.filing.approval_stale_reasons`
        Compares the stored basis with the current profile-activity digest.
    :func:`~application.filing.empty_profile_activity_fingerprint`
        Supplies the explicit empty-source fingerprint used by tests and
        overrides.
    :mod:`~application.filing.tests.test_review_prior_filing_staleness`
        Sister approval-basis coverage for another self-loaded source surface.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....core.bucket_pointer import read_pointer
from ....core.config import load_settings
from ....domain.filing.protocols import CasillaSchemaProvider
from ....domain.filing.schema import ModeloDraft
from ....domain.submission import ModeloDraftStatus
from ....domain.user_profile.values import UserProfileFact
from ....tests.profile_capsule import open_test_profile_session, set_active_test_profile_facts
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from .. import (
    ModeloApprovalStaleReason,
    approval_stale_reasons,
    approve_draft,
    build_draft,
    build_runtime_schema_provider,
)
from .._review import empty_profile_activity_fingerprint
from ..runtime import ModeloOperatorProfile

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PERIOD = Period.from_year_and_code(2026, "1T")
_PROFILE_ID = "12345678-1234-4234-8234-123456789abc"
_TAX_ID = "12345678Z"


@pytest.fixture
def _profile_storage(tmp_path: Path) -> Iterator[None]:
    """Isolate the encrypted profile store and bootstrap profile creation.

    The self-load path
    (:meth:`~application.user_profile.CommittedProfileRepository.load`) needs a
    genuinely provisioned profile: bucket directory, plaintext manifest, wrapped
    DEK, and encrypted record. The tests mint that profile through the same
    application create span used by the CLI rather than a partial record write.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path), open_test_profile_session(_PROFILE_ID):
        yield


def _active_bucket_id() -> str:
    pointer = read_pointer(load_settings().cadrumo_local_storage_root)
    assert pointer.bucket_id is not None, "config profile create did not mint an active bucket pointer"
    return pointer.bucket_id


def _schema_provider() -> CasillaSchemaProvider:
    return build_runtime_schema_provider(modelos=("130",), filing_year=_PERIOD.filing_year, period=_PERIOD)


def _create_profile_with_activity(activity: str) -> None:
    # Seeded through a detached WorkflowState, never a repository read: the
    # capsule publishes by an atomic no-replace rename onto
    # ``buckets/<profile-id>``, which a workflow-state repository
    # construction would otherwise materialise first and collide with.
    register_minimal_profile(
        profile_id=_PROFILE_ID,
        display_name="auton",
        overrides={"identity.tax_id": _TAX_ID, "activities.description": activity},
    )


def _edit_profile_activity(activity: str) -> None:
    set_active_test_profile_facts((UserProfileFact(path="activities.description", value=activity),))


def _ready_draft(schema_provider: CasillaSchemaProvider) -> ModeloDraft:
    return build_draft(
        modelo="130",
        period=_PERIOD,
        profile=ModeloOperatorProfile(tax_id=_TAX_ID, display_name="Profile activity staleness test"),
        inputs={
            "01": Decimal("100"),
            "02": Decimal("25"),
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        },
        schema_provider=schema_provider,
    )


def test_approval_goes_stale_when_profile_activity_changes(_profile_storage: None) -> None:
    _create_profile_with_activity("asesoria")
    bucket_id = _active_bucket_id()
    schema_provider = _schema_provider()
    draft = _ready_draft(schema_provider)

    with open_test_profile_session(bucket_id):
        approved = approve_draft(
            draft,
            bucket_id=bucket_id,
            approved_by="operator",
            schema_provider=schema_provider,
        )
    assert approved.status is ModeloDraftStatus.APROBADO
    assert approved.approval_basis is not None
    # The real profile was loaded (non-vacuous): the digest is not the empty one.
    assert approved.approval_basis.profile_activity_fingerprint != empty_profile_activity_fingerprint()

    # The taxpayer edits a relation-scoping profile fact through the real
    # application profile primitive; the self-loaded wizard-free projection
    # digest changes.
    _edit_profile_activity("comercio")

    with open_test_profile_session(bucket_id):
        reasons = approval_stale_reasons(approved, bucket_id=bucket_id, schema_provider=schema_provider)

    # Only the taxpayer profile changed: draft, transactions, invoices, prior
    # observations, category profiles, and schema are unchanged, so
    # PROFILE_ACTIVITY_CHANGED is the sole reason.
    assert reasons == (ModeloApprovalStaleReason.PROFILE_ACTIVITY_CHANGED,)


def test_approval_not_stale_when_profile_unchanged(_profile_storage: None) -> None:
    """Anti-tautology: an unchanged real profile produces NO stale reason.

    If :func:`approval_stale_reasons` flagged PROFILE_ACTIVITY_CHANGED regardless
    of whether the profile actually changed, the signal would be meaningless.
    Approving against a genuinely-loaded profile and re-checking without editing
    it must yield an empty reason tuple.
    """
    _create_profile_with_activity("asesoria")
    bucket_id = _active_bucket_id()
    schema_provider = _schema_provider()
    draft = _ready_draft(schema_provider)

    with open_test_profile_session(bucket_id):
        approved = approve_draft(
            draft,
            bucket_id=bucket_id,
            approved_by="operator",
            schema_provider=schema_provider,
        )
        # No mutation to any source between approval and the staleness check.
        reasons = approval_stale_reasons(approved, bucket_id=bucket_id, schema_provider=schema_provider)

    assert approved.approval_basis is not None
    assert approved.approval_basis.profile_activity_fingerprint != empty_profile_activity_fingerprint()
    assert ModeloApprovalStaleReason.PROFILE_ACTIVITY_CHANGED not in reasons
    assert reasons == ()
