"""Real proofs for provenance, conflict, and exact apply-or-reject rendering.

Drives a real registered profile record and the real Textual
`CensalFieldReviewScreen`/`ProfileManagerScreen` -- no mocks, no synthetic
schema. `test_census_sync_review.py` already proves the full operation
round-trip; this file proves the narrower D6 surface `W03.P06` adds:
provenance is read through the settled classification authority (never a
locally invented source), a conflict is exactly a persisted/observed
divergence and nothing more, a reject dismisses with `None` and the exact
accepted request contains only the operator's own selection, and a source
action is launched only through the injected door -- never implicitly.
"""

from __future__ import annotations

from pathlib import Path
from typing import override
from uuid import UUID

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, SelectionList

from .....application.user_profile.acquisition_sources import ProfileAcquisitionSourceV1
from .....application.user_profile.censal_operation import (
    CENSAL_ADOPTABLE_PATHS,
    CensalFieldIntent,
    CensalOperationRequest,
    CensalProfileBaseline,
    CensalReviewedFieldIntent,
    CensalReviewFieldProjectionV1,
    CensalReviewProjectionV1,
)
from .....application.user_profile.login_session import login_profile
from .....application.user_profile.overview import ProfileOverview, build_profile_overview
from .....application.user_profile.presentation import ProfileFieldSourceClass
from .....application.user_profile.profile_record_repository import ProfileRecordRepository
from .....application.user_profile.registration import register_profile_with_credentials
from .....domain.user_profile.values import UserProfileFact
from .....tests.secure_sql import isolated_profile_storage_root
from ...components.host import ScreenHostApp
from ..overview import ProfileManagerScreen
from ..sync_review import (
    CensalFieldReviewRowV1,
    CensalFieldReviewScreen,
    censal_field_review_rows,
    censal_operation_request_from_selection,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PASSPHRASE = "sync-review-passphrase"  # noqa: S105 - isolated integration fixture


def _real_record(tmp_path: Path, *, facts: tuple[UserProfileFact, ...]):
    with isolated_profile_storage_root(tmp_path=tmp_path):
        enrolled = register_profile_with_credentials(
            label="Sync review subject",
            passphrase=_PASSPHRASE,
            facts=facts,
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
        )
        login_profile(name=enrolled.profile_id, passphrase_callback=lambda: _PASSPHRASE)
        profile_id = UUID(enrolled.profile_id)
        return ProfileRecordRepository.for_current_session(profile_id).load(profile_id)


def test_provenance_is_read_through_the_settled_classification_authority_never_invented(tmp_path: Path) -> None:
    record = _real_record(
        tmp_path,
        facts=(UserProfileFact(path="contact.postcode", value="28001", source="aeat_censo_read"),),
    )
    baseline = CensalProfileBaseline.from_record(record)
    request = CensalOperationRequest(
        baseline=baseline,
        field_intents=tuple(
            CensalReviewedFieldIntent(path=path, intent=CensalFieldIntent.PRESERVE) for path in CENSAL_ADOPTABLE_PATHS
        ),
    )

    rows = censal_field_review_rows(request, record)

    row = next(row for row in rows if row.path == "contact.postcode")
    assert row.source is ProfileFieldSourceClass.AEAT_CENSUS_ACQUISITION
    assert row.has_conflict is False


def test_a_conflict_is_exactly_a_persisted_observed_divergence_nothing_more(tmp_path: Path) -> None:
    record = _real_record(
        tmp_path,
        facts=(UserProfileFact(path="contact.postcode", value="28001", source="manual_cli"),),
    )
    baseline = CensalProfileBaseline.from_record(record)
    request = CensalOperationRequest(
        baseline=baseline,
        field_intents=tuple(
            CensalReviewedFieldIntent(path=path, intent=CensalFieldIntent.PRESERVE) for path in CENSAL_ADOPTABLE_PATHS
        ),
    )
    projection = CensalReviewProjectionV1(
        projection_version=1,
        fields=tuple(
            CensalReviewFieldProjectionV1(
                path=path,
                intent=CensalFieldIntent.PRESERVE,
                observed_value="28002" if path == "contact.postcode" else "some-observed-value",
            )
            for path in CENSAL_ADOPTABLE_PATHS
        ),
    )

    rows = censal_field_review_rows(request, record, projection=projection)

    conflicting = next(row for row in rows if row.path == "contact.postcode")
    filling_a_blank = next(row for row in rows if row.path == "contact.fiscal_address")
    assert conflicting.has_conflict is True, "a persisted value diverging from the observed value is a real conflict"
    assert filling_a_blank.has_conflict is False, "filling a previously-blank field is not a conflict"


class _ReviewHostApp(App[None]):
    """A bare host: the review dialog is what these proofs drive."""

    @override
    def compose(self) -> ComposeResult:
        yield from ()


def _screen(baseline: CensalProfileBaseline, rows: tuple[CensalFieldReviewRowV1, ...]) -> CensalFieldReviewScreen:
    return CensalFieldReviewScreen(
        baseline,
        rows,
        stale=False,
        title="Review",
        stale_message="Stale",
        apply_all_label="Apply all",
        reject_label="Reject",
        confirm_label="Confirm",
    )


@pytest.mark.asyncio
async def test_reject_dismisses_with_none_and_never_touches_the_baseline(tmp_path: Path) -> None:
    record = _real_record(tmp_path, facts=())
    baseline = CensalProfileBaseline.from_record(record)
    request = CensalOperationRequest(
        baseline=baseline,
        field_intents=tuple(
            CensalReviewedFieldIntent(path=path, intent=CensalFieldIntent.ADOPT) for path in CENSAL_ADOPTABLE_PATHS
        ),
    )
    rows = censal_field_review_rows(request, record)

    app = _ReviewHostApp()
    async with app.run_test() as pilot:
        outcomes: list[CensalOperationRequest | None] = []
        app.app.push_screen(_screen(baseline, rows), callback=outcomes.append)
        await pilot.pause()
        await pilot.click("#btn-censal-reject")
        await pilot.pause()

    assert outcomes == [None]


@pytest.mark.asyncio
async def test_confirm_produces_the_exact_operator_selection_never_a_wider_or_narrower_set(tmp_path: Path) -> None:
    record = _real_record(tmp_path, facts=())
    baseline = CensalProfileBaseline.from_record(record)
    request = CensalOperationRequest(
        baseline=baseline,
        field_intents=tuple(
            CensalReviewedFieldIntent(
                path=path,
                intent=CensalFieldIntent.ADOPT if path == "contact.postcode" else CensalFieldIntent.PRESERVE,
            )
            for path in CENSAL_ADOPTABLE_PATHS
        ),
    )
    rows = censal_field_review_rows(request, record)

    app = _ReviewHostApp()
    async with app.run_test() as pilot:
        outcomes: list[CensalOperationRequest | None] = []
        app.app.push_screen(_screen(baseline, rows), callback=outcomes.append)
        await pilot.pause()
        # `app.query_one` always resolves against the App's DEFAULT screen, never a
        # pushed one (a documented Textual behaviour, not a flake) -- a pushed
        # modal's own contents must be queried through the active `app.app.screen`.
        choices = app.app.screen.query_one("#censal-field-review-choices", SelectionList)
        # SelectionList.select/deselect key on the option's own VALUE (the row's
        # path), never its list position.
        choices.deselect("contact.postcode")
        await pilot.pause(0.1)
        assert "contact.postcode" not in choices.selected, "the deselect must be visible before confirming"
        await pilot.click("#btn-censal-confirm")
        await pilot.pause()

    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome is not None
    accepted_paths = {intent.path for intent in outcome.field_intents if intent.intent is CensalFieldIntent.ADOPT}
    expected = censal_operation_request_from_selection(baseline, rows, frozenset())
    assert accepted_paths == set(), "deselecting the sole ADOPT suggestion must produce zero ADOPT paths"
    assert outcome == expected, "the dispatched request must be exactly the operator's rebuilt selection"


def _persist_not_exercised(path: str, value: str) -> ProfileOverview:
    raise AssertionError("no field edit is exercised by this test")


@pytest.mark.asyncio
async def test_source_action_launches_only_through_the_injected_door_never_implicitly(tmp_path: Path) -> None:
    record = _real_record(tmp_path, facts=())
    overview = build_profile_overview(record)
    launched: list[str] = []

    async def _launch(source: ProfileAcquisitionSourceV1) -> None:
        launched.append(source.key.value)

    app = ProfileManagerScreen(overview, persist=_persist_not_exercised, launch_source=_launch)
    async with ScreenHostApp(app).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        card = app.query_one("#source-censal_review")
        await pilot.click(card.query_one(Button))
        await pilot.pause(0.1)

    assert launched == ["censal_review"]


@pytest.mark.asyncio
async def test_source_action_is_disabled_not_silently_inert_with_no_launch_door(tmp_path: Path) -> None:
    record = _real_record(tmp_path, facts=())
    overview = build_profile_overview(record)

    app = ProfileManagerScreen(overview, persist=_persist_not_exercised)
    async with ScreenHostApp(app).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        card = app.query_one("#source-censal_review")
        assert card.query_one(Button).disabled is True


@pytest.mark.asyncio
async def test_apply_all_selects_by_value_reverting_to_the_suggested_intents(tmp_path: Path) -> None:
    """A prior operator selection can be reverted to the application's own suggestion.

    Regression proof: `SelectionList.select`/`deselect` key on the option's own
    VALUE, never its list position -- a loop-index call silently no-ops.
    """
    record = _real_record(tmp_path, facts=())
    baseline = CensalProfileBaseline.from_record(record)
    request = CensalOperationRequest(
        baseline=baseline,
        field_intents=tuple(
            CensalReviewedFieldIntent(
                path=path,
                intent=CensalFieldIntent.ADOPT if path == "contact.postcode" else CensalFieldIntent.PRESERVE,
            )
            for path in CENSAL_ADOPTABLE_PATHS
        ),
    )
    rows = censal_field_review_rows(request, record)

    app = _ReviewHostApp()
    async with app.run_test() as pilot:
        outcomes: list[CensalOperationRequest | None] = []
        app.app.push_screen(_screen(baseline, rows), callback=outcomes.append)
        await pilot.pause()
        choices = app.app.screen.query_one("#censal-field-review-choices", SelectionList)
        choices.deselect("contact.postcode")
        choices.select("contact.fiscal_address")
        await pilot.pause(0.1)
        assert set(choices.selected) == {"contact.fiscal_address"}

        await pilot.click("#btn-censal-apply-all")
        await pilot.pause(0.1)
        assert set(choices.selected) == {"contact.postcode"}, "apply-all must restore exactly the suggested ADOPT set"

        await pilot.click("#btn-censal-confirm")
        await pilot.pause()

    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome is not None
    accepted_paths = {intent.path for intent in outcome.field_intents if intent.intent is CensalFieldIntent.ADOPT}
    assert accepted_paths == {"contact.postcode"}
