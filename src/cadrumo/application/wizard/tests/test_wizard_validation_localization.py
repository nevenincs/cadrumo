"""Real-behavior tests for localized wizard answer-validation refusals.

Free-text date / decimal / cross-field answers skip the widget layer and
fail at profile-answer validation. The refusal detail must be a localized
message resolved from a translation-key mapping keyed on the pydantic error
``type`` / ``loc`` — never the raw English pydantic ``msg``.

The refusals are driven through the ``edit`` arm. They were driven through
``create`` until credential registration became the only creation door: the
``create`` arm now refuses before any answer is validated, so it cannot reach
this surface at all, while ``edit`` still validates every supplied flag and
raises the same localized refusals. The subject is the localization, not the
verb, so the verb moved and the assertions did not.

No mocks: the real ``SETUP_FLOW`` descriptor, the real Typer command, the
real pydantic model, and the real i18n backend under an ``es`` settings
override. Expected detail strings are resolved through the i18n API at test
time (never hardcoded prose), so a locale edit updates test and code together.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest
import typer

from ....core.config import override_settings
from ....core.i18n import tr
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_cli_profile
from .._catalogue import SETUP_FLOW
from .._commands import build_wizard_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALE = "es"

_BASE_EDIT_ARGS: tuple[str, ...] = ("operator", "--quiet")

_SEED_FACTS = {
    "identity.tax_id": "00000000T",
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Operator",
    "identity.surnames": "Tester",
    "activities.description": "Servicios",
}


def _refusal_message(args: Sequence[str], tmp_path: Path) -> str:
    """Drive the non-interactive edit patch and return the localized refusal body.

    The storage root is pytest's ``tmp_path`` rather than a self-cleaning
    temporary directory: registering a profile leaves a live bucket session,
    and its open database file makes an eager rmtree fail on Windows.
    """
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        override_settings(cadrumo_output_language=_LOCALE),
    ):
        register_cli_profile(label="operator", facts=_SEED_FACTS)
        app = typer.Typer()
        app.command()(build_wizard_command(SETUP_FLOW, mode="edit"))
        command = typer.main.get_command(app)
        with pytest.raises(typer.BadParameter) as caught:
            command.main(args=list(args), standalone_mode=False)
        return caught.value.format_message()


def test_bad_date_answer_maps_to_localized_invalid_date_key(tmp_path: Path) -> None:
    """A malformed ISO date surfaces the ``wizard.errors.invalid_date`` rendering."""
    message = _refusal_message((*_BASE_EDIT_ARGS, "--taxpayer-marriage-date", "31/12/2020"), tmp_path)
    expected = tr(
        "wizard.errors.invalid_date",
        flag="--taxpayer-marriage-date",
        got="31/12/2020",
        locale=_LOCALE,
    )
    assert expected in message
    # The raw English pydantic prose must never leak into the refusal.
    assert "Value error" not in message
    assert "ISO-8601 date (YYYY-MM-DD), got" not in message


def test_bad_decimal_answer_maps_to_localized_invalid_decimal_key(tmp_path: Path) -> None:
    """A malformed decimal surfaces the ``wizard.errors.invalid_decimal`` rendering."""
    message = _refusal_message((*_BASE_EDIT_ARGS, "--incn-prior-12-months", "1.2.3"), tmp_path)
    expected = tr(
        "wizard.errors.invalid_decimal",
        flag="--incn-prior-12-months",
        got="1.2.3",
        locale=_LOCALE,
    )
    assert expected in message
    assert "Value error" not in message
    assert "must be a decimal number" not in message


def test_joint_taxation_missing_spouse_maps_to_localized_cross_field_key(tmp_path: Path) -> None:
    """Joint taxation without a spouse tax id surfaces its cross-field key."""
    message = _refusal_message((*_BASE_EDIT_ARGS, "--taxation-type", "2"), tmp_path)
    expected = tr(
        "wizard.errors.spouse_tax_id_required_joint",
        flag="--spouse-tax-id",
        condition_flag="--taxation-type",
        locale=_LOCALE,
    )
    assert expected in message
    assert "Value error" not in message
    assert "spouse_tax_id is required" not in message
