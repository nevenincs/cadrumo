"""Textual proof for explicit ordinary-M303 filing-evidence entry."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from textual.app import App
from textual.widgets import Button, Input, Select, Static

from ......application.modelo.operation_definitions import ModeloWorkCalculateOrdinaryM303EvidenceRequestV1
from ......core.i18n.render import tr
from ...m303_evidence import OrdinaryM303FilingEvidenceScreen, OrdinaryM303FilingEvidenceSubmission
from ..overview import ModeloWorkspaceOverviewScreen

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ATTACHMENT_ID = "a" * 64


@pytest.mark.asyncio
async def test_m303_evidence_screen_requires_two_explicit_booleans_and_a_complete_existing_pair() -> None:
    """Blank selectors never become false, while selected false values remain filing facts."""
    app = App[None]()
    dismissed: list[OrdinaryM303FilingEvidenceSubmission | None] = []

    async with app.run_test() as pilot:
        app.push_screen(OrdinaryM303FilingEvidenceScreen(work_unit_id="work-unit-303"), dismissed.append)
        await pilot.pause()

        app.screen.query_one("#m303-evidence-submit", Button).press()
        await pilot.pause()
        assert str(app.screen.query_one("#m303-evidence-notice", Static).content)

        app.screen.query_one("#m303-evidence-joint-return-elected", Select).value = "false"
        app.screen.query_one("#m303-evidence-annual-volume-nonzero", Select).value = "false"
        app.screen.query_one("#m303-evidence-attachment-id", Input).value = _ATTACHMENT_ID
        app.screen.query_one("#m303-evidence-sha256", Input).value = _ATTACHMENT_ID
        app.screen.query_one("#m303-evidence-submit", Button).press()
        await pilot.pause()

        assert len(dismissed) == 1
        submission = dismissed[0]
        assert submission is not None
        assert submission.work_unit_id == "work-unit-303"
        assert submission.joint_return_elected is False
        assert submission.annual_volume_nonzero is False
        assert submission.existing_evidence is not None
        assert submission.observed_at is None
        app.exit(None)


@pytest.mark.asyncio
async def test_m303_evidence_screen_can_request_secure_admission_at_an_explicit_observation_time() -> None:
    """A new attestation carries an operator-supplied instant, not a TUI-derived current time."""
    app = App[None]()
    dismissed: list[OrdinaryM303FilingEvidenceSubmission | None] = []

    async with app.run_test() as pilot:
        app.push_screen(OrdinaryM303FilingEvidenceScreen(work_unit_id="work-unit-303"), dismissed.append)
        await pilot.pause()
        app.screen.query_one("#m303-evidence-joint-return-elected", Select).value = "true"
        app.screen.query_one("#m303-evidence-annual-volume-nonzero", Select).value = "false"
        app.screen.query_one("#m303-evidence-observed-at", Input).value = "2026-09-22T12:00:00Z"
        app.screen.query_one("#m303-evidence-submit", Button).press()
        await pilot.pause()

        submission = dismissed[0]
        assert submission is not None
        assert submission.existing_evidence is None
        assert submission.observed_at is not None
        assert submission.observed_at.isoformat() == "2026-09-22T12:00:00+00:00"
        app.exit(None)


def _overview(
    monkeypatch: pytest.MonkeyPatch,
    *,
    actions: object,
    target_work_unit_id: str = "current-work-unit",
) -> tuple[ModeloWorkspaceOverviewScreen, list[str], list[Callable[[], Awaitable[object]]]]:
    """Build an unmounted overview whose notice and worker seams record what the handler did."""
    notices: list[str] = []
    started: list[Callable[[], Awaitable[object]]] = []
    overview = object.__new__(ModeloWorkspaceOverviewScreen)
    object.__setattr__(
        overview,
        "_session",
        SimpleNamespace(
            projection=SimpleNamespace(target=SimpleNamespace(work_unit_id=target_work_unit_id)),
            lifecycle_actions=actions,
        ),
    )
    monkeypatch.setattr(ModeloWorkspaceOverviewScreen, "_notice", lambda _self, message: notices.append(message))
    monkeypatch.setattr(
        ModeloWorkspaceOverviewScreen,
        "_start_lifecycle_action",
        lambda _self, submit, **_kwargs: started.append(submit),
    )
    return overview, notices, started


def _existing_evidence() -> ModeloWorkCalculateOrdinaryM303EvidenceRequestV1:
    return ModeloWorkCalculateOrdinaryM303EvidenceRequestV1(
        joint_return_elected=False,
        annual_volume_nonzero=False,
        m303_exonerado_390_attachment_id=_ATTACHMENT_ID,
        m303_exonerado_390_sha256=_ATTACHMENT_ID,
    )


def test_overview_refuses_a_returned_evidence_form_for_a_different_work_unit(monkeypatch: pytest.MonkeyPatch) -> None:
    """A modal result from a stale selected work unit cannot start calculation for the current one."""

    async def calculate(**_kwargs: object) -> object:
        pytest.fail("a stale evidence form must not submit calculation")

    overview, notices, started = _overview(
        monkeypatch, actions=SimpleNamespace(work_unit_id="current-work-unit", calculate=calculate)
    )
    submission = OrdinaryM303FilingEvidenceSubmission(
        work_unit_id="different-work-unit",
        joint_return_elected=False,
        annual_volume_nonzero=False,
        existing_evidence=_existing_evidence(),
    )

    overview._calculate_with_ordinary_m303_evidence(submission)

    assert started == []
    assert notices == [tr("tui.modelo.m303_evidence.stale_context")]


def test_overview_reports_a_cancelled_evidence_form_without_submitting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Escape or Cancel is an explicit outcome on the workspace, not a silent no-op or a default."""
    overview, notices, started = _overview(monkeypatch, actions=SimpleNamespace(work_unit_id="current-work-unit"))

    overview._calculate_with_ordinary_m303_evidence(None)

    assert started == []
    assert notices == [tr("tui.modelo.m303_evidence.cancelled")]


def test_overview_refuses_new_attestation_when_the_session_cannot_admit_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the admission door the observation-time path refuses instead of calculating without evidence."""

    async def calculate(**_kwargs: object) -> object:
        pytest.fail("calculation must not run without admitted evidence")

    overview, notices, started = _overview(
        monkeypatch, actions=SimpleNamespace(work_unit_id="current-work-unit", calculate=calculate)
    )
    submission = OrdinaryM303FilingEvidenceSubmission(
        work_unit_id="current-work-unit",
        joint_return_elected=True,
        annual_volume_nonzero=False,
        observed_at=datetime(2025, 4, 1, 12, tzinfo=UTC),
    )

    overview._calculate_with_ordinary_m303_evidence(submission)

    assert started == []
    assert notices == [tr("tui.modelo.m303_evidence.admission_unavailable")]


@pytest.mark.asyncio
async def test_overview_admits_new_evidence_then_calculates_the_same_work_unit_in_one_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The admitted coordinates, with the explicit answers, are exactly what reaches calculation."""
    calls: list[tuple[str, dict[str, object]]] = []
    admitted = _existing_evidence().model_copy(update={"joint_return_elected": True})

    async def author(**kwargs: object) -> ModeloWorkCalculateOrdinaryM303EvidenceRequestV1:
        calls.append(("author", kwargs))
        return admitted

    async def calculate(**kwargs: object) -> str:
        calls.append(("calculate", kwargs))
        return "controller"

    overview, notices, started = _overview(
        monkeypatch,
        actions=SimpleNamespace(
            work_unit_id="current-work-unit",
            calculate=calculate,
            author_ordinary_m303_filing_evidence=author,
        ),
    )
    observed_at = datetime(2025, 4, 1, 12, tzinfo=UTC)
    overview._calculate_with_ordinary_m303_evidence(
        OrdinaryM303FilingEvidenceSubmission(
            work_unit_id="current-work-unit",
            joint_return_elected=True,
            annual_volume_nonzero=False,
            observed_at=observed_at,
        )
    )

    assert notices == []
    assert len(started) == 1
    assert await started[0]() == "controller"
    assert calls == [
        ("author", {"joint_return_elected": True, "annual_volume_nonzero": False, "observed_at": observed_at}),
        ("calculate", {"ordinary_m303_filing_evidence": admitted}),
    ]


@pytest.mark.parametrize(
    ("receipt_kind", "receipt_ref", "explained"),
    [
        ("refusal", "REFUSED_MODELO_EXPORT_PRODUCT_IDENTITY_UNAVAILABLE", True),
        ("refusal", "REFUSED_PROFILE_LIFO_FORBIDDEN", False),
    ],
)
def test_overview_keeps_a_public_refusal_explanation_after_the_modal_settles(
    monkeypatch: pytest.MonkeyPatch, receipt_kind: str, receipt_ref: str, explained: bool
) -> None:
    """The modal dismisses on settlement, so the workspace notice carries the only lasting reason."""
    from ......core.operations import OperationTerminalCondition
    from ....operations.modal import OperationModalSettledOutcomeV1

    overview, notices, _started = _overview(monkeypatch, actions=None)
    outcome = OperationModalSettledOutcomeV1.model_construct(
        view_model=SimpleNamespace(
            projection=SimpleNamespace(terminal_condition=OperationTerminalCondition.REFUSED),
            receipt_kind=receipt_kind,
            receipt_ref=receipt_ref,
        )
    )

    overview._on_lifecycle_operation_settled(outcome)

    refused = tr("operation.modal.terminal.refused")
    explanation = tr("errors.refused.refused_modelo_export_product_identity_unavailable")
    assert notices == [f"{refused}: {explanation}" if explained else refused]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("attachment_id", "sha256", "observed_at"),
    [
        (_ATTACHMENT_ID, "", ""),
        ("", _ATTACHMENT_ID, ""),
        (_ATTACHMENT_ID, _ATTACHMENT_ID, "2025-04-01T12:00:00Z"),
        ("", "", ""),
        ("", "", "2025-04-01T12:00:00"),
        ("not-a-digest", "not-a-digest", ""),
    ],
    ids=["id-only", "sha-only", "both-paths", "neither-path", "naive-instant", "malformed-pair"],
)
async def test_m303_evidence_screen_refuses_partial_or_ambiguous_evidence(
    attachment_id: str, sha256: str, observed_at: str
) -> None:
    """Only one complete evidence path is admitted; everything else stays on the form with a notice."""
    app = App[None]()
    dismissed: list[OrdinaryM303FilingEvidenceSubmission | None] = []

    async with app.run_test() as pilot:
        app.push_screen(OrdinaryM303FilingEvidenceScreen(work_unit_id="work-unit-303"), dismissed.append)
        await pilot.pause()
        app.screen.query_one("#m303-evidence-joint-return-elected", Select).value = "false"
        app.screen.query_one("#m303-evidence-annual-volume-nonzero", Select).value = "false"
        app.screen.query_one("#m303-evidence-attachment-id", Input).value = attachment_id
        app.screen.query_one("#m303-evidence-sha256", Input).value = sha256
        app.screen.query_one("#m303-evidence-observed-at", Input).value = observed_at
        app.screen.query_one("#m303-evidence-submit", Button).press()
        await pilot.pause()

        assert dismissed == []
        notice = str(app.screen.query_one("#m303-evidence-notice", Static).content)
        assert notice == tr("tui.modelo.m303_evidence.required")
        app.exit(None)


@pytest.mark.asyncio
async def test_m303_evidence_screen_escape_dismisses_without_a_submission() -> None:
    """Escape is cancellation, never an implicit answer."""
    app = App[None]()
    dismissed: list[OrdinaryM303FilingEvidenceSubmission | None] = []

    async with app.run_test() as pilot:
        app.push_screen(OrdinaryM303FilingEvidenceScreen(work_unit_id="work-unit-303"), dismissed.append)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert dismissed == [None]
        app.exit(None)
