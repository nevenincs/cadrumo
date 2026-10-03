"""Textual proof for explicit ordinary-M303 filing-evidence entry."""

from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import Button, Input, Select, Static

from .....application.modelo.work_calculation_contracts import ModeloWorkCalculateOrdinaryM303EvidenceRequestV2
from .....core.i18n.render import tr
from ..m303_evidence import OrdinaryM303FilingEvidenceScreen, OrdinaryM303FilingEvidenceSubmission

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ATTACHMENT_ID = "a" * 64


@pytest.mark.asyncio
async def test_m303_evidence_screen_requires_an_explicit_answer_and_a_complete_existing_pair() -> None:
    """Blank selectors never become false, while selected false values remain filing facts."""
    app = App[None]()
    dismissed: list[OrdinaryM303FilingEvidenceSubmission | None] = []

    async with app.run_test() as pilot:
        app.push_screen(
            OrdinaryM303FilingEvidenceScreen(work_unit_id="work-unit-303", asks_modelo_390=True), dismissed.append
        )
        await pilot.pause()

        app.screen.query_one("#m303-evidence-submit", Button).press()
        await pilot.pause()
        assert str(app.screen.query_one("#m303-evidence-notice", Static).content)

        app.screen.query_one("#m303-evidence-joint-return-elected", Select).value = "false"
        app.screen.query_one("#m303-evidence-attachment-id", Input).value = _ATTACHMENT_ID
        app.screen.query_one("#m303-evidence-sha256", Input).value = _ATTACHMENT_ID
        app.screen.query_one("#m303-evidence-submit", Button).press()
        await pilot.pause()

        assert len(dismissed) == 1
        submission = dismissed[0]
        assert submission is not None
        assert submission.work_unit_id == "work-unit-303"
        assert submission.joint_return_elected is False
        assert submission.existing_evidence is not None
        assert submission.observed_at is None
        app.exit(None)


@pytest.mark.asyncio
async def test_m303_evidence_screen_can_request_secure_admission_at_an_explicit_observation_time() -> None:
    """A new attestation carries an operator-supplied instant, not a TUI-derived current time."""
    app = App[None]()
    dismissed: list[OrdinaryM303FilingEvidenceSubmission | None] = []

    async with app.run_test() as pilot:
        app.push_screen(
            OrdinaryM303FilingEvidenceScreen(work_unit_id="work-unit-303", asks_modelo_390=True), dismissed.append
        )
        await pilot.pause()
        app.screen.query_one("#m303-evidence-joint-return-elected", Select).value = "true"
        app.screen.query_one("#m303-evidence-observed-at", Input).value = "2026-09-22T12:00:00Z"
        app.screen.query_one("#m303-evidence-submit", Button).press()
        await pilot.pause()

        submission = dismissed[0]
        assert submission is not None
        assert submission.existing_evidence is None
        assert submission.observed_at is not None
        assert submission.observed_at.isoformat() == "2026-09-22T12:00:00+00:00"
        app.exit(None)


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
        app.push_screen(
            OrdinaryM303FilingEvidenceScreen(work_unit_id="work-unit-303", asks_modelo_390=True), dismissed.append
        )
        await pilot.pause()
        app.screen.query_one("#m303-evidence-joint-return-elected", Select).value = "false"
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
        app.push_screen(
            OrdinaryM303FilingEvidenceScreen(work_unit_id="work-unit-303", asks_modelo_390=True), dismissed.append
        )
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert dismissed == [None]
        app.exit(None)


@pytest.mark.asyncio
async def test_a_period_that_does_not_ask_the_exemption_offers_only_the_joint_return_question() -> None:
    """Before the last period the form has no attestation inputs and submits the joint-return answer alone."""
    app = App[None]()
    dismissed: list[OrdinaryM303FilingEvidenceSubmission | None] = []

    async with app.run_test() as pilot:
        app.push_screen(
            OrdinaryM303FilingEvidenceScreen(work_unit_id="work-unit-303", asks_modelo_390=False), dismissed.append
        )
        await pilot.pause()
        assert not app.screen.query("#m303-evidence-attachment-id")
        assert not app.screen.query("#m303-evidence-observed-at")
        assert str(app.screen.query_one("#m303-evidence-hint", Static).content) == tr(
            "tui.modelo.m303_evidence.no_modelo_390_question_hint"
        )

        app.screen.query_one("#m303-evidence-submit", Button).press()
        await pilot.pause()
        assert dismissed == []

        app.screen.query_one("#m303-evidence-joint-return-elected", Select).value = "true"
        app.screen.query_one("#m303-evidence-submit", Button).press()
        await pilot.pause()

        submission = dismissed[0]
        assert submission is not None
        assert submission.observed_at is None
        assert submission.existing_evidence == ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(
            joint_return_elected=True
        )
        app.exit(None)
