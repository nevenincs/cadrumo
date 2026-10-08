"""Publication consent binds a saved revision and refuses broader disclosure."""

from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
import typer
from typer.main import get_command

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.export.google_review_operation_contracts import (
    GOOGLE_REVIEW_OPERATION_DEFINITION_ID,
    GOOGLE_REVIEW_RESPONSE_SCHEMA_BINDING,
    GOOGLE_REVIEW_REVIEW_SCHEMA_BINDING,
    GoogleReviewProjection,
    GoogleReviewRequest,
    GoogleReviewResult,
)
from ....application.export.publication_receipt import ReadablePayloadCategory
from ....application.operations.frontend_projection import OperationReviewProjectionReferenceV1
from ....application.operations.models import OperationIdentity
from ....application.runtime.contracts import RuntimeRefusalError
from ....core.operations import OperationEffect, profile_operation_subject
from .. import google_review_cli
from .._modelo_spreadsheet_command_specs import MODELO_SPREADSHEET_COMMAND_SPECS
from .._profile_authentication_gate import _uses_runtime_profile_client
from ..google_review_cli import accept_google_review, publish_google_review_cli
from ..registered_operation_contracts import RegisteredOperationCompletion, RegisteredOperationReviewHandler
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _request() -> GoogleReviewRequest:
    return GoogleReviewRequest(
        profile_id=UUID("5aa00000-0000-4000-8000-0000000000aa"),
        calculation_revision_id="a" * 64,
        publication_id=UUID("6bb00000-0000-4000-8000-0000000000bb"),
    )


def _review(request: GoogleReviewRequest) -> GoogleReviewProjection:
    return GoogleReviewProjection(
        identity=OperationIdentity(
            operation_id="b" * 64,
            definition_id=GOOGLE_REVIEW_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(request.profile_id)),
        ),
        revision=1,
        profile_id=request.profile_id,
        publication_id=request.publication_id,
        calculation_revision_id=request.calculation_revision_id,
        filing_record_id=request.filing_record_id,
        root_folder_id="confirmed-profile-root",
        snapshot_digest="c" * 64,
        payload_categories=(ReadablePayloadCategory.CALCULATION, ReadablePayloadCategory.LEDGER),
        reviewed_proposal_digest="d" * 64,
    )


def test_publish_help_exposes_saved_revision_and_readable_disclosure() -> None:
    result = invoke_cached_cli(["--language", "en", "app", "modelo", "spreadsheet", "publish", "--help"])
    assert result.exit_code == 0, result.output
    assert "--calculation-revision-id" in result.output
    assert "--publication-id" in result.output
    assert "--filing-record-id" in result.output
    assert "--accept-readable-export" in result.output


def test_publish_routes_through_native_runtime_profile_admission() -> None:
    spec = next(item for item in MODELO_SPREADSHEET_COMMAND_SPECS if item.key == "app_modelo_spreadsheet_publish")
    assert _uses_runtime_profile_client(spec, {"calculation_revision_id": "a" * 64, "accept_readable_export": True})


def test_missing_disclosure_flag_refuses_before_profile_or_runtime_access() -> None:
    # No bound profile exists in this context: accessing one would fail instead.
    app = typer.Typer()

    @app.command()
    def publish() -> None:
        """Construct a real Typer command without a profile context."""

    context = typer.Context(get_command(app))
    with pytest.raises(typer.BadParameter):
        publish_google_review_cli(context, calculation_revision_id="a" * 64)


def test_explicit_disclosure_accepts_exact_runtime_review() -> None:
    request = _request()
    assert accept_google_review(request, _review(request)) == "apply"


@pytest.mark.parametrize(
    "change",
    [
        {"profile_id": UUID("7cc00000-0000-4000-8000-0000000000cc")},
        {"publication_id": UUID("7cc00000-0000-4000-8000-0000000000cc")},
        {"calculation_revision_id": "e" * 64},
        {"filing_record_id": "e" * 64},
        {"root_folder_id": " "},
        {"payload_categories": ()},
        {"payload_categories": (ReadablePayloadCategory.CALCULATION, ReadablePayloadCategory.ORIGINAL_ATTACHMENT)},
        {"payload_categories": (ReadablePayloadCategory.CALCULATION, ReadablePayloadCategory.EVIDENCE_PACKAGE)},
    ],
)
def test_substituted_review_or_broader_disclosure_is_refused(change: dict[str, object]) -> None:
    request = _request()
    review = _review(request).model_copy(update=change)
    with pytest.raises(ValueError, match="does not match"):
        accept_google_review(request, review)


@pytest.mark.parametrize("change", [{"definition_id": "other.operation"}, {"subject_ref": "other-profile"}])
def test_other_operation_identity_is_refused(change: dict[str, object]) -> None:
    request = _request()
    review = _review(request)
    review = review.model_copy(update={"identity": review.identity.model_copy(update=change)})
    with pytest.raises(ValueError, match="does not match"):
        accept_google_review(request, review)


def test_exact_historical_filing_disclosure_retains_the_selected_identity() -> None:
    request = _request().model_copy(update={"filing_record_id": "e" * 64})
    assert accept_google_review(request, _review(request)) == "apply"
    with pytest.raises(ValueError, match="does not match"):
        accept_google_review(request, _review(request).model_copy(update={"filing_record_id": None}))


@pytest.mark.parametrize(
    "defect",
    ["none", "review-operation", "review-revision", "profile", "publication", "snapshot", "root", "operation"],
)
def test_cli_publication_binds_disclosure_and_receipt_before_emitting_link(
    monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    request = _request().model_copy(update={"filing_record_id": "f" * 64})
    client = cast(RuntimeFrontendClient, SimpleNamespace(profile_id=request.profile_id))
    calls: list[str] = []
    emitted: list[dict[str, Any]] = []
    monkeypatch.setattr(google_review_cli, "bound_profile_client", lambda _: client)
    monkeypatch.setattr(google_review_cli, "emit_envelope", lambda _, **kwargs: emitted.append(kwargs))

    def run(
        actual_client: RuntimeFrontendClient, payload: GoogleReviewRequest, **kwargs: Any
    ) -> RegisteredOperationCompletion[GoogleReviewResult]:
        assert actual_client is client and payload == request
        assert kwargs["definition_id"] == GOOGLE_REVIEW_OPERATION_DEFINITION_ID
        assert kwargs["subject_ref"] == profile_operation_subject(str(request.profile_id))
        assert kwargs["result_type"] is GoogleReviewResult
        handler = kwargs["review"]
        assert isinstance(handler, RegisteredOperationReviewHandler)
        assert handler.review_schema == GOOGLE_REVIEW_REVIEW_SCHEMA_BINDING.identity
        assert handler.response_schema == GOOGLE_REVIEW_RESPONSE_SCHEMA_BINDING.identity
        reference = OperationReviewProjectionReferenceV1(
            operation_id="b" * 64,
            interaction_id="e" * 64,
            revision=1,
            review_projection_schema=handler.review_schema,
            definition_contract_digest="0" * 64,
            expires_at=None,
        )
        review = _review(payload)
        if defect == "review-operation":
            review = review.model_copy(
                update={"identity": review.identity.model_copy(update={"operation_id": "9" * 64})}
            )
        elif defect == "review-revision":
            review = review.model_copy(update={"revision": 2})
        assert handler.validate_reference is not None
        calls.append("validate")
        handler.validate_reference(review, reference)
        calls.append("decide")
        assert handler.decide(review) == "apply"
        result = GoogleReviewResult(
            profile_id=UUID(int=9) if defect == "profile" else request.profile_id,
            publication_id=UUID(int=9) if defect == "publication" else request.publication_id,
            snapshot_digest="9" * 64 if defect == "snapshot" else review.snapshot_digest,
            root_folder_id="other-root" if defect == "root" else review.root_folder_id,
            spreadsheet_id="saved-review",
            spreadsheet_url="https://docs.google.com/spreadsheets/d/saved-review/edit",
        )
        return RegisteredOperationCompletion(
            operation_id="9" * 64 if defect == "operation" else reference.operation_id,
            projection=result,
            effect=OperationEffect.UPDATED,
        )

    monkeypatch.setattr(google_review_cli, "run_registered_operation", run)

    def publish() -> None:
        publish_google_review_cli(
            cast(typer.Context, SimpleNamespace()),
            calculation_revision_id=request.calculation_revision_id,
            filing_record_id=request.filing_record_id,
            publication_id=str(request.publication_id),
            accept_readable_export=True,
        )

    if defect.startswith("review-"):
        with pytest.raises(RuntimeRefusalError):
            publish()
        assert calls == ["validate"] and not emitted
    elif defect != "none":
        with pytest.raises(ValueError, match="receipt does not match"):
            publish()
        assert calls == ["validate", "decide"] and not emitted
    else:
        publish()
        assert calls == ["validate", "decide"]
        assert len(emitted) == 1
        assert emitted[0]["command"] == "modelo.spreadsheet.publish"
        assert emitted[0]["result"].publication.publication_id == request.publication_id
        assert emitted[0]["lines"] == ("spreadsheet_url\thttps://docs.google.com/spreadsheets/d/saved-review/edit",)
