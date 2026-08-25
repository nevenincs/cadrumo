"""A real application-layer advisory reaches, and paints on, the status surface.

The status page previously had nowhere to put a non-blocking advisory: the
Textual surfaces carried zero references to the typed ``Notice`` channel the
CLI envelope already uses, so an advisory the application layer raised —
the no-AEAT-history nudge among them — reached a command-line operator and
was structurally invisible to a full-screen one.

These tests drive the real production chain end to end: a real profile, a
real (or absent) persisted calculation observation, the real
:func:`~cadrumo.application.overview.no_aeat_history_notice` producer, the
real :func:`~cadrumo.entrypoints.cli.build_status_page_data`
builder, and the real :class:`~cadrumo.entrypoints.tui.profile.status.StatusApp`
surface. No mock, stub, or reimplementation of what the wiring should do.
"""

from __future__ import annotations

import pytest
from textual.widgets import Static

from ....application.calculations import CalculationObservationRepository
from ....application.user_profile import login_profile, register_profile_with_credentials
from ....domain.calculations.registry import RegistryModeloObservation
from ....tests.secure_sql import isolated_profile_storage_root
from ...cli import build_status_page_data
from ..profile.status import StatusApp

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LABEL = "Status Notice Subject"
_PASSWORD = "status-notice-wiring-operator-secret"  # noqa: S105 - synthetic test fixture

_TERMINAL_SIZE = (140, 60)

# A real, registry-resolvable (modelo, filing_year, period) triple — the
# validator the repository runs (``_validate_observation_casilla_ids``)
# resolves a live snapshot for it, so an unreal triple would refuse the save
# before this test ever reaches the notice.
_MODELO = "303"
_FILING_YEAR = 2025
_PERIOD = "1T"


def _register_and_unlock() -> None:
    """Bring a profile into existence AND unlock it, which are two steps.

    Registration closes the session it opened, so a freshly registered profile
    is locked. The status surface reads facts and observations through an
    authenticated session, so registering alone leaves it with nothing to
    report -- no facts, no notices, and a runtime that answers not-ready. The
    absent advisory these cases were written to catch would then look like the
    producer failing rather than the profile never having been opened.
    """
    register_profile_with_credentials(
        recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSWORD
    )
    login_profile(name=_LABEL, passphrase_callback=lambda: _PASSWORD)


def test_a_fresh_profile_with_no_aeat_history_raises_a_real_info_notice(tmp_path) -> None:
    """The real producer fires on a profile holding no official observation."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _register_and_unlock()

        data = build_status_page_data()

        assert len(data.notices) == 1
        notice = data.notices[0]
        assert notice.severity == "info"
        assert notice.message
        assert notice.action_target == "aeat app live filed pull-all"


def test_one_official_observation_silences_the_notice(tmp_path) -> None:
    """Anti-tautology converse: a real official-source observation clears it.

    Proves the wiring reads the real repository rather than always
    returning the same fixed notice regardless of what is persisted.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _register_and_unlock()
        CalculationObservationRepository().save(
            CalculationObservationRepository().prepare_observation_envelope(
                RegistryModeloObservation(modelo=_MODELO, filing_year=_FILING_YEAR, period=_PERIOD),
                source_kind="aeat_sede_justificante",
            )
        )

        data = build_status_page_data()

        assert data.notices == ()


@pytest.mark.asyncio
async def test_the_real_notice_actually_paints_on_the_running_status_surface(tmp_path) -> None:
    """The last mile: what the application layer raised is what the screen shows.

    Builds the page from the real producer chain, then runs the REAL
    ``StatusApp`` against it and reads the rendered widget back — proving
    the notice is not merely present on the view-model but actually
    reaches a painted cell, which is the gap this fix closes.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _register_and_unlock()
        data = build_status_page_data()
        assert data.notices, "fixture premise: this profile must carry the real advisory"
        expected_message = data.notices[0].message
        expected_action_target = data.notices[0].action_target
        assert expected_action_target is not None

        app = StatusApp(data)
        async with app.run_test(size=_TERMINAL_SIZE):
            rendered_message = str(app.query_one("#notice-0", Static).content)
            assert expected_message in rendered_message
            rendered_action = str(app.query_one("#notice-0-action", Static).content)
            assert rendered_action == expected_action_target
