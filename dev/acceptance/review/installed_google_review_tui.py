"""Drive the production TUI against an already authenticated worktree runtime.

The runner owns runtime startup, credentials and authorization for the explicit
Publish click. This helper neither starts a runtime nor calls a provider itself.
It records worktree acceptance, not installed-wheel or release-package proof.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from urllib.parse import urlparse
from uuid import UUID

from rich.text import Text
from textual.app import App
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Link, Static

import cadrumo
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.profile_access import status_admits_session
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.hashing import sha256_file
from cadrumo.core.i18n.render import output_language
from cadrumo.entrypoints.review_publication_labels import GoogleReviewLabels
from cadrumo.entrypoints.tui.app import CadrumoTuiApp
from cadrumo.entrypoints.tui.declarations.grouped import GroupedDeclarationsScreen
from cadrumo.entrypoints.tui.google_saved_review import GoogleSavedReviewModal, GoogleSavedReviewScreen
from cadrumo.entrypoints.tui.home import HomeScreen
from cadrumo.entrypoints.tui.modelo.workbench.screen import ModeloWorkbenchScreen
from cadrumo.entrypoints.tui.navigation import TuiFocusIdentityV1, TuiNavigationTargetV1
from cadrumo.entrypoints.tui.runtime_workbench import RuntimeWorkbenchRoot


class GoogleReviewTuiAcceptanceError(RuntimeError):
    """The public TUI surface did not prove the requested acceptance stage."""


@dataclass(frozen=True, slots=True)
class GoogleReviewTuiDisclosureEvidence:
    """Exact source and destination exposed by the human disclosure."""

    calculation_revision_id: str
    root_folder_id: str
    snapshot_digest: str
    publication_id: str


@dataclass(frozen=True, slots=True)
class GoogleReviewTuiEvidence:
    """A sanitized receipt for one real production route and manual publication."""

    schema_version: str
    runtime_context: str
    profile_id: str
    work_unit_id: str
    calculation_revision_id: str
    modelo: str
    filing_year: int
    period: str
    publication_id: str
    root_folder_id: str
    snapshot_digest: str
    document_url: str
    document_id: str
    explicit_publish_clicked: bool
    public_success_notice: str
    product_origin: str
    product_init_sha256: str
    workspace_root: str
    screenshots: tuple[tuple[str, str], ...]

    def to_dict(self) -> dict[str, object]:
        """Return only nonsecret public evidence and artifact identities."""
        return dict(asdict(self))


def public_static_text(widget: Static) -> str:
    """Read public rendered content without reaching into a controller."""
    content = widget.content
    return content.plain if isinstance(content, Text) else str(content)


def read_public_disclosure(
    text: str, *, labels: GoogleReviewLabels, calculation_revision_id: str
) -> GoogleReviewTuiDisclosureEvidence:
    """Refuse incomplete, duplicated or wrong-source human disclosure rows."""
    values: dict[str, str] = {}
    for field in ("calculation_revision_id", "root_folder_id", "snapshot_digest", "publication_id"):
        prefix = labels(f"google_review.label.{field}") + ": "
        matches = [line.removeprefix(prefix).strip() for line in text.splitlines() if line.startswith(prefix)]
        if len(matches) != 1 or not matches[0]:
            raise GoogleReviewTuiAcceptanceError(f"disclosure lacks one exact {field} row")
        values[field] = matches[0]
    if values["calculation_revision_id"] != calculation_revision_id:
        raise GoogleReviewTuiAcceptanceError("disclosure selected a different saved calculation")
    if not re.fullmatch(r"[0-9a-f]{64}", values["snapshot_digest"]):
        raise GoogleReviewTuiAcceptanceError("disclosure snapshot identity is invalid")
    try:
        publication_id = str(UUID(values["publication_id"]))
    except ValueError as exc:
        raise GoogleReviewTuiAcceptanceError("disclosure publication identity is invalid") from exc
    return GoogleReviewTuiDisclosureEvidence(
        calculation_revision_id=calculation_revision_id,
        root_folder_id=values["root_folder_id"],
        snapshot_digest=values["snapshot_digest"],
        publication_id=publication_id,
    )


def google_document_id(url: str) -> str:
    """Accept only the canonical settled spreadsheet link shown by this door."""
    parsed = urlparse(url)
    match = re.fullmatch(r"/spreadsheets/d/([A-Za-z0-9_-]+)/edit", parsed.path)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "docs.google.com"
        or parsed.query
        or parsed.fragment
        or match is None
    ):
        raise GoogleReviewTuiAcceptanceError("settled link is not a canonical Google spreadsheet URL")
    return str(match.group(1))


def _capture_public_failure[T](app: App[T], output_dir: Path, *, stage: str, reason: str) -> None:
    """Keep the failed public surface and its notices without private controller data."""
    notice_ids = {
        "saved-google-review-notice",
        "operation-modal-status",
        "operation-modal-action-refusal",
        "operation-modal-receipt",
        "declarations-refusal",
        "wb-notice",
        "wb-loading",
    }
    notices = {
        widget.id: public_static_text(widget)
        for widget in app.screen.query(Static)
        if widget.id in notice_ids and widget.content
    }
    screenshot = Path(app.save_screenshot("05-failure.svg", str(output_dir)))
    (output_dir / "failure.json").write_text(
        json.dumps(
            {
                "schema_version": "google-saved-review-tui-failure-v1",
                "runtime_context": "worktree runtime",
                "stage": stage,
                "reason": reason,
                "screen_type": type(app.screen).__name__,
                "public_notices": notices,
                "screenshot": str(screenshot),
                "screenshot_sha256": sha256_file(screenshot),
                "publication_attempt_exists": (output_dir / "publication-attempt.json").exists(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


async def _until[T](
    pilot: Pilot[T],
    predicate: Callable[[], bool],
    *,
    deadline: float,
    stage: str,
    output_dir: Path,
    refusal: Callable[[], str | None] | None = None,
) -> None:
    while not predicate():
        refused = None if refusal is None else refusal()
        if refused:
            _capture_public_failure(pilot.app, output_dir, stage=stage, reason=refused)
            raise GoogleReviewTuiAcceptanceError(f"TUI acceptance refused at {stage}; inspect failure.json")
        if monotonic() >= deadline:
            _capture_public_failure(pilot.app, output_dir, stage=stage, reason="stage_timeout")
            raise GoogleReviewTuiAcceptanceError(f"TUI acceptance timed out at {stage}")
        await pilot.pause(0.1)


@asynccontextmanager
async def _reject_failed_prepublication(app: CadrumoTuiApp, output_dir: Path) -> AsyncIterator[None]:
    """Reject only this still-live session's untouched review after an acceptance failure."""
    try:
        yield
    except BaseException as original:
        if not (output_dir / "publication-attempt.json").exists():
            if not (output_dir / "failure.json").exists():
                _capture_public_failure(app, output_dir, stage="before Publish", reason=type(original).__name__)
            screens = [screen for screen in app.screen_stack if isinstance(screen, GoogleSavedReviewScreen)]
            cleanup: dict[str, object] = {"publish_attempted": False, "owned_review_found": len(screens) == 1}
            if len(screens) == 1:
                try:
                    cleanup["reject_sent"] = await screens[0].reject_pending_prepublication()
                except Exception as error:
                    # Preserve the initial failure; cleanup never retries or
                    # substitutes custody and reports only a safe error type.
                    cleanup["cleanup_error_type"] = type(error).__name__
            (output_dir / "prepublication-cleanup.json").write_text(
                json.dumps(cleanup, indent=2) + "\n", encoding="utf-8"
            )
        raise


async def run_google_saved_review_tui(
    client: RuntimeFrontendClient,
    *,
    work_unit_id: str,
    calculation_revision_id: str,
    profile_label: str,
    output_dir: Path,
    workspace_root: Path,
    seconds: float = 900,
    language: OutputLanguage = OutputLanguage.ES,
) -> GoogleReviewTuiEvidence:
    """Click the actual workbench door and Publish against the runner-owned runtime.

    Calling this function authorizes its explicit Publish click. The caller must
    supply its existing synthetic profile and a native-authenticated TUI lease.
    No replacement runtime, sign-in, recovery, consent or publication is retried.
    """
    if not isinstance(client, RuntimeFrontendClient) or client.frontend is not OperationFrontendProjection.TUI:
        raise GoogleReviewTuiAcceptanceError("acceptance requires a real native TUI client")
    if seconds <= 0 or not work_unit_id or not re.fullmatch(r"[0-9a-f]{64}", calculation_revision_id):
        raise GoogleReviewTuiAcceptanceError("acceptance selection or deadline is invalid")
    profile_id, session_id = client.profile_id, client.session_id
    status = await asyncio.to_thread(client.status)
    if not status_admits_session(
        status.status,
        profile_id=profile_id,
        session_id=session_id,
        at=datetime.now(UTC),
        requires_automation_grant=False,
    ):
        raise GoogleReviewTuiAcceptanceError("the native TUI lease is not authenticated for this profile")
    output_dir.mkdir(parents=True, exist_ok=False)
    deadline = monotonic() + seconds

    async def no_recovery() -> RuntimeFrontendClient:
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)

    root = RuntimeWorkbenchRoot(
        client, profile_label=profile_label, output_language=language, open_recovery_client=no_recovery
    )
    app = CadrumoTuiApp(load_root=root.load)
    screenshots: list[tuple[str, str]] = []

    async with app.run_test(size=(160, 55)) as pilot, _reject_failed_prepublication(app, output_dir):
        await _until(
            pilot,
            lambda: isinstance(app.screen, HomeScreen),
            deadline=min(deadline, monotonic() + 60),
            stage="production Home",
            output_dir=output_dir,
        )
        app.navigate_to(
            TuiNavigationTargetV1(
                destination="workbench.declarations",
                focus=TuiFocusIdentityV1(destination="workbench.declarations", semantic_key="declarations.work"),
            )
        )
        await _until(
            pilot,
            lambda: isinstance(app.screen, GroupedDeclarationsScreen) and bool(app.screen.rows),
            deadline=min(deadline, monotonic() + 60),
            stage="production declarations",
            output_dir=output_dir,
        )
        portfolio = app.screen
        if not isinstance(portfolio, GroupedDeclarationsScreen):
            raise GoogleReviewTuiAcceptanceError("the declaration surface changed before selection")
        matches = [
            row
            for row in portfolio.rows
            if row.declaration is not None and str(row.declaration.work_unit_id) == work_unit_id
        ]
        if len(matches) != 1:
            raise GoogleReviewTuiAcceptanceError("declarations do not expose one exact selected work unit")
        table = portfolio.query_one("#declarations-list", DataTable)
        row_indices = [index for index, row in enumerate(table.ordered_rows) if row.key.value == matches[0].key]
        if len(row_indices) != 1:
            raise GoogleReviewTuiAcceptanceError("the selected declaration is not visible in the production table")
        table.move_cursor(row=row_indices[0])
        table.focus()
        await pilot.press("enter")
        await _until(
            pilot,
            lambda: isinstance(app.screen, ModeloWorkbenchScreen) and app.screen.form is not None,
            deadline=min(deadline, monotonic() + 60),
            stage="selected saved workbench",
            output_dir=output_dir,
        )
        workbench = app.screen
        if not isinstance(workbench, ModeloWorkbenchScreen):
            raise GoogleReviewTuiAcceptanceError("the workbench surface changed before selection")
        form = workbench.form
        if form is None:
            raise GoogleReviewTuiAcceptanceError("the saved workbench form disappeared")
        if (
            form.work_unit_id != work_unit_id
            or form.calculation_revision_id != calculation_revision_id
            or workbench.staged_changes
        ):
            raise GoogleReviewTuiAcceptanceError("the production workbench differs from the exact saved selection")
        await pilot.pause()
        path = Path(app.save_screenshot("01-saved-workbench.svg", str(output_dir)))
        screenshots.append((str(path), sha256_file(path)))
        button = workbench.query_one("#wb-google-review", Button)
        if button.disabled or not await pilot.click("#wb-google-review"):
            raise GoogleReviewTuiAcceptanceError("the actual Google review workbench button is unavailable")

        def prepare_refusal() -> str | None:
            if isinstance(app.screen, GoogleSavedReviewScreen):
                return public_static_text(app.screen.query_one("#saved-google-review-notice", Static)) or None
            return None

        labels = GoogleReviewLabels(OutputLanguage(output_language()))

        def disclosure_ready() -> bool:
            if not isinstance(app.screen, GoogleSavedReviewModal):
                return False
            button = app.screen.query_one("#btn-operation-apply", Button)
            text = public_static_text(app.screen.query_one("#operation-modal-review", Static))
            return (
                not button.disabled
                and str(button.label) == labels("google_review.publish")
                and labels("google_review.offer.title") in text
                and labels("google_review.notice.external_copy") in text
                and labels("google_review.notice.evidence_index") in text
            )

        disclosure_deadline = min(deadline, monotonic() + 60)
        await _until(
            pilot,
            disclosure_ready,
            deadline=disclosure_deadline,
            stage="registered human disclosure",
            output_dir=output_dir,
            refusal=prepare_refusal,
        )
        await pilot.pause()
        path = Path(app.save_screenshot("02-human-disclosure.svg", str(output_dir)))
        screenshots.append((str(path), sha256_file(path)))
        await pilot.press("t")
        await _until(
            pilot,
            lambda: (
                isinstance(app.screen, GoogleSavedReviewModal)
                and labels("google_review.label.calculation_revision_id") + ": " + calculation_revision_id
                in public_static_text(app.screen.query_one("#operation-modal-review", Static))
            ),
            deadline=disclosure_deadline,
            stage="exact technical disclosure",
            output_dir=output_dir,
            refusal=prepare_refusal,
        )
        disclosure = read_public_disclosure(
            public_static_text(app.screen.query_one("#operation-modal-review", Static)),
            labels=labels,
            calculation_revision_id=calculation_revision_id,
        )
        path = Path(app.save_screenshot("03-exact-disclosure.svg", str(output_dir)))
        screenshots.append((str(path), sha256_file(path)))
        apply_button = app.screen.query_one("#btn-operation-apply", Button)
        if str(apply_button.label) != labels("google_review.publish"):
            raise GoogleReviewTuiAcceptanceError("the actual human response control does not say Publish")
        # Persist the exact publication identity BEFORE delivering its response.
        # An interrupted run must be reconciled against runtime/provider receipts;
        # invoking this helper again is never an automatic recovery action.
        (output_dir / "publication-attempt.json").write_text(
            json.dumps(
                {
                    "schema_version": "google-saved-review-tui-attempt-v1",
                    "runtime_context": "worktree runtime",
                    "state": "explicit_publish_about_to_be_clicked",
                    "recorded_at": datetime.now(UTC).isoformat(),
                    "profile_id": str(profile_id),
                    "work_unit_id": work_unit_id,
                    **asdict(disclosure),
                    "screenshots": screenshots,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        if not await pilot.click("#btn-operation-apply"):
            raise GoogleReviewTuiAcceptanceError("the explicit Publish click was not delivered")

        def published() -> bool:
            return (
                isinstance(app.screen, GoogleSavedReviewScreen)
                and not app.screen.query_one("#saved-google-review-link", Link).disabled
            )

        await _until(
            pilot,
            published,
            deadline=deadline,
            stage="registered verified publication",
            output_dir=output_dir,
            refusal=prepare_refusal,
        )
        url = app.screen.query_one("#saved-google-review-link", Link).url
        document_id = google_document_id(url)
        notice = public_static_text(app.screen.query_one("#saved-google-review-notice", Static))
        if notice != labels("google_review.publication.published"):
            raise GoogleReviewTuiAcceptanceError("the public terminal surface does not confirm verified publication")
        if client.profile_id != profile_id or client.session_id != session_id:
            raise GoogleReviewTuiAcceptanceError("the native profile session changed during acceptance")
        await pilot.pause()
        path = Path(app.save_screenshot("04-verified-publication.svg", str(output_dir)))
        screenshots.append((str(path), sha256_file(path)))

    product_init = Path(cadrumo.__file__ or "").resolve()
    evidence = GoogleReviewTuiEvidence(
        schema_version="google-saved-review-tui-worktree-v1",
        runtime_context="worktree runtime",
        profile_id=str(profile_id),
        work_unit_id=work_unit_id,
        calculation_revision_id=calculation_revision_id,
        modelo=str(form.modelo),
        filing_year=form.filing_year,
        period=form.period.registry_token,
        publication_id=disclosure.publication_id,
        root_folder_id=disclosure.root_folder_id,
        snapshot_digest=disclosure.snapshot_digest,
        document_url=url,
        document_id=document_id,
        explicit_publish_clicked=True,
        public_success_notice=notice,
        product_origin=str(product_init),
        product_init_sha256=sha256_file(product_init),
        workspace_root=str(workspace_root.resolve()),
        screenshots=tuple(screenshots),
    )
    (output_dir / "evidence.json").write_text(json.dumps(evidence.to_dict(), indent=2) + "\n", encoding="utf-8")
    return evidence
