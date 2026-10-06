"""Isolated refusal policy checks; transport doubles establish no provider success."""

from types import SimpleNamespace
from uuid import UUID

import pytest

from ...storage.calc_sheets.records import SheetExportPlan, SheetReviewMetadata
from .. import google_operation
from ..google_operation import (
    GoogleSheetsExportActiveProfileRequiredError,
    GoogleSheetsExportSubjectMismatchError,
    prepare_google_review_plan,
    publish_google_review,
)
from ..publication_receipt import PublicationFailure, PublicationReceipt, PublicationState
from ..review_snapshot import CalculationReviewSelection
from .review_publication_fixture import (
    EXPORTED_AT,
    PROFILE_ID,
    acceptance_authorization,
    acceptance_label,
    acceptance_publication,
    acceptance_snapshot,
    completed_acceptance_receipt,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def admitted_local_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    """Supply policy identity while keeping the owning preparation validator real."""
    monkeypatch.setattr(google_operation, "require_active_bucket_id", lambda: str(PROFILE_ID))
    monkeypatch.setattr(google_operation, "resolve_active_capability", lambda _: SimpleNamespace(enabled=True))


class _ForbiddenTransport:
    """A refusal must occur before any publication attempt is delegated."""

    def execute(
        self, plan: SheetExportPlan[SheetReviewMetadata], publication: PublicationReceipt
    ) -> PublicationReceipt:
        del plan, publication
        raise AssertionError("invalid selection reached the transport")


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("work_unit_id", "6" * 64),
        ("calculation_revision_id", "7" * 64),
        ("authority_generation", "8" * 64),
        ("registry_digest", "9" * 64),
    ),
)
def test_exact_saved_work_revision_and_authority_mismatch_refuses_before_transport(
    field: str, replacement: str
) -> None:
    snapshot = acceptance_snapshot()
    assert isinstance(snapshot.selection, CalculationReviewSelection)
    selection = CalculationReviewSelection.model_validate({**snapshot.selection.model_dump(), field: replacement})
    publication = acceptance_publication(snapshot)
    with pytest.raises(GoogleSheetsExportSubjectMismatchError, match="identities"):
        publish_google_review(
            snapshot,
            selection=selection,
            publication=publication,
            authorization=acceptance_authorization(publication),
            prepared=_ForbiddenTransport(),
            exported_at=EXPORTED_AT,
            label=acceptance_label,
        )


def test_changed_active_profile_refuses_before_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot = acceptance_snapshot()
    publication = acceptance_publication(snapshot)
    monkeypatch.setattr(google_operation, "require_active_bucket_id", lambda: str(UUID(int=999)))
    with pytest.raises(GoogleSheetsExportActiveProfileRequiredError):
        publish_google_review(
            snapshot,
            selection=snapshot.selection,
            publication=publication,
            authorization=acceptance_authorization(publication),
            prepared=_ForbiddenTransport(),
            exported_at=EXPORTED_AT,
            label=acceptance_label,
        )


@pytest.mark.parametrize("state", (PublicationState.PARTIAL, PublicationState.UNCERTAIN, PublicationState.PUBLISHED))
def test_incomplete_or_completed_receipt_is_never_blindly_populated(state: PublicationState) -> None:
    snapshot = acceptance_snapshot()
    prepared = acceptance_publication(snapshot)
    completed = completed_acceptance_receipt(prepared)
    if state is PublicationState.PUBLISHED:
        receipt = completed
    elif state is PublicationState.UNCERTAIN:
        receipt = prepared.advance(state, failure=PublicationFailure.CREATE_UNKNOWN)
    else:
        receipt = prepared.advance(PublicationState.REMOTE_CREATED, artifacts=completed.artifacts).advance(
            state, failure=PublicationFailure.POPULATION
        )
    with pytest.raises(GoogleSheetsExportSubjectMismatchError, match="reconciliation"):
        publish_google_review(
            snapshot,
            selection=snapshot.selection,
            publication=receipt,
            authorization=acceptance_authorization(receipt),
            prepared=_ForbiddenTransport(),
            exported_at=EXPORTED_AT,
            label=acceptance_label,
        )


def test_review_preparation_cannot_reassemble_or_recalculate_current_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot = acceptance_snapshot()
    publication = acceptance_publication(snapshot)

    def forbidden_source_read(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("review attempted current-source assembly or regulated recalculation")

    monkeypatch.setattr(google_operation, "build_export_plan", forbidden_source_read)
    monkeypatch.setattr(google_operation, "resolve_relations_from_local_store", forbidden_source_read)
    plan = prepare_google_review_plan(
        snapshot,
        selection=snapshot.selection,
        publication=publication,
        authorization=acceptance_authorization(publication),
        exported_at=EXPORTED_AT,
        label=acceptance_label,
    )
    assert plan.metadata.snapshot_digest == snapshot.snapshot_digest
