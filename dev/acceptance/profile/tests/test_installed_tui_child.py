"""Visible no-op outcome checks for the PROFILE-01 installed TUI child."""

from __future__ import annotations

import pytest

from cadrumo.core.i18n.render import tr

from ..installed_tui_child import _is_exact_visible_no_op_outcome

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_visible_no_op_predicate_requires_the_localized_no_change_status() -> None:
    """A real no-op may be recorded only after its exact operator outcome appears."""
    assert _is_exact_visible_no_op_outcome(
        status_tone="success",
        status_message=tr("flows.manager.edit.no_change"),
        field_visible=True,
    )


def test_visible_no_op_predicate_rejects_the_localized_saved_status() -> None:
    """A successful write outcome must never be promoted to no-op evidence."""
    saved = tr("flows.manager.edit.saved")
    no_change = tr("flows.manager.edit.no_change")

    assert saved != no_change
    assert not _is_exact_visible_no_op_outcome(
        status_tone="success",
        status_message=saved,
        field_visible=True,
    )
