"""Approval-basis staleness coverage for the taxpayer profile-activity source.

Exercises the ``profile_activity_fingerprint`` added to
:class:`~aeat.domain.filing.ModeloApprovalBasis` (calculation-source-connectivity
ADR, Phase 9 / W05.P10.S63): an ``APROBADO`` draft must go stale with
:attr:`~aeat.application.filing.ModeloApprovalStaleReason.PROFILE_ACTIVITY_CHANGED`
when a taxpayer-profile fact that scopes relation resolution changes (activity-start
date, m111 no-retenciones attestations, declared income categories), and must NOT be
flagged when the profile is unchanged.

The digest is self-loaded from the bucket's
:class:`~aeat.application.user_profile.ProfileRepository` via the wizard-free
canonical projection (:func:`~aeat.application.user_profile.record_to_path_values`)
— the SAME projection the relation resolver reads — so change-detection is
reproducible at approve and refresh time with only ``bucket_id`` in scope, without
running the source mesh.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period, read_pointer
from ....core.config import load_settings
from ....domain.submission import ModeloDraftStatus
from ....entrypoints.cli.tests._profile_cli_support import create_quiet_profile, edit_quiet_profile
from ....tests.secure_sql import isolated_profile_storage_root
from ...user_profile import profile_storage_session
from .. import (
    CasillaSchemaProvider,
    ModeloApprovalStaleReason,
    ModeloDraft,
    approval_stale_reasons,
    approve_draft,
    build_draft,
    build_runtime_schema_provider,
)
from .._review import _profile_activity_fingerprint, empty_profile_activity_fingerprint
from ..testing import ModeloTestProfile

_PERIOD = Period.from_year_and_code(2026, "1T")
_TAX_ID = "12345678Z"


@pytest.fixture
def _profile_storage(tmp_path: Path) -> Iterator[None]:
    """Isolate the encrypted profile store so ``config profile`` CRUD is real.

    The self-load path (:func:`ProfileRepository.load`) needs a genuinely
    provisioned profile — bucket directory, plaintext manifest, wrapped DEK, and
    encrypted record — so these integration tests mint one through the real
    ``config profile create`` command rather than a partial record write.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def _active_bucket_id() -> str:
    pointer = read_pointer(load_settings().aeat_local_storage_root)
    assert pointer is not None, "config profile create did not mint an active bucket pointer"
    return pointer.bucket_id


def _schema_provider() -> CasillaSchemaProvider:
    return build_runtime_schema_provider(modelos=("130",), filing_year=_PERIOD.filing_year, period=_PERIOD)


def _ready_draft(schema_provider: CasillaSchemaProvider) -> ModeloDraft:
    return build_draft(
        modelo="130",
        period=_PERIOD,
        profile=ModeloTestProfile(tax_id=_TAX_ID, display_name="Profile activity staleness test"),
        inputs={
            "01": Decimal("100"),
            "02": Decimal("25"),
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        },
        schema_provider=schema_provider,
    )


@pytest.mark.integration
@pytest.mark.hex_application
def test_approval_goes_stale_when_profile_activity_changes(_profile_storage: None) -> None:
    result = create_quiet_profile("auton", "--tax-id", _TAX_ID, "--activity", "asesoria")
    assert result.exit_code == 0, result.output
    bucket_id = _active_bucket_id()
    schema_provider = _schema_provider()
    draft = _ready_draft(schema_provider)

    with profile_storage_session(bucket_id):
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

    # The taxpayer edits a relation-scoping profile fact through the real CLI;
    # the self-loaded wizard-free projection digest changes.
    edited = edit_quiet_profile("auton", "--activity", "comercio")
    assert edited.exit_code == 0, edited.output

    with profile_storage_session(bucket_id):
        reasons = approval_stale_reasons(approved, bucket_id=bucket_id, schema_provider=schema_provider)

    # Only the taxpayer profile changed: draft, transactions, invoices, prior
    # observations, category profiles, and schema are unchanged, so
    # PROFILE_ACTIVITY_CHANGED is the sole reason.
    assert reasons == (ModeloApprovalStaleReason.PROFILE_ACTIVITY_CHANGED,)


@pytest.mark.integration
@pytest.mark.hex_application
def test_approval_not_stale_when_profile_unchanged(_profile_storage: None) -> None:
    """Anti-tautology: an unchanged real profile produces NO stale reason.

    If :func:`approval_stale_reasons` flagged PROFILE_ACTIVITY_CHANGED regardless
    of whether the profile actually changed, the signal would be meaningless.
    Approving against a genuinely-loaded profile and re-checking without editing
    it must yield an empty reason tuple.
    """
    result = create_quiet_profile("auton", "--tax-id", _TAX_ID, "--activity", "asesoria")
    assert result.exit_code == 0, result.output
    bucket_id = _active_bucket_id()
    schema_provider = _schema_provider()
    draft = _ready_draft(schema_provider)

    with profile_storage_session(bucket_id):
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


# Registry-free unit coverage of the fingerprint mechanism the profile-activity
# stale detection relies on. These fingerprint the wizard-free projection directly
# (a plain path->value mapping), so they exercise the change-detection signal
# without a schema provider or the secure backend.


@pytest.mark.unit
@pytest.mark.hex_application
def test_profile_activity_fingerprint_changes_when_a_fact_changes() -> None:
    before = _profile_activity_fingerprint({"censo.activity_start_date": "2024-01-01"})
    after = _profile_activity_fingerprint({"censo.activity_start_date": "2024-06-01"})

    assert before != after


@pytest.mark.unit
@pytest.mark.hex_application
def test_profile_activity_fingerprint_is_order_independent() -> None:
    one = _profile_activity_fingerprint({"a.b": "1", "c.d": "2"})
    other = _profile_activity_fingerprint({"c.d": "2", "a.b": "1"})

    assert one == other


@pytest.mark.unit
@pytest.mark.hex_application
def test_profile_activity_fingerprint_distinguishes_empty_from_populated() -> None:
    empty = _profile_activity_fingerprint(None)
    populated = _profile_activity_fingerprint({"censo.activity_start_date": "2024-01-01"})

    assert empty != populated
    # The exported empty helper matches both a None and an empty projection.
    assert empty == empty_profile_activity_fingerprint()
    assert empty == _profile_activity_fingerprint({})
