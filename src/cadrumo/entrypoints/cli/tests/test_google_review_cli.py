"""Publication consent binds a saved revision and refuses broader disclosure."""

from uuid import UUID

import pytest
import typer
from typer.main import get_command

from ....application.export.google_review_operation_contracts import (
    GOOGLE_REVIEW_OPERATION_DEFINITION_ID,
    GoogleReviewProjection,
    GoogleReviewRequest,
)
from ....application.export.publication_receipt import ReadablePayloadCategory
from ....application.operations.models import OperationIdentity
from ....core.operations import profile_operation_subject
from .._modelo_spreadsheet_command_specs import MODELO_SPREADSHEET_COMMAND_SPECS
from .._profile_authentication_gate import _uses_runtime_profile_client
from ..google_review_cli import accept_google_review, publish_google_review_cli
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
