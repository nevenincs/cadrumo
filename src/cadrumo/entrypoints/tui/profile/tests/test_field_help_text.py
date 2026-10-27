"""The manager shows the backend's served help for a field and falls back to the schema description."""

from __future__ import annotations

import pytest

from .....application.user_profile.overview import ProfileFieldView
from .....core.i18n.render import tr
from ..edit_screens import field_help_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _field(*, help_lines: tuple[str, ...] | None, about: str) -> ProfileFieldView:
    return ProfileFieldView(
        path="iva.regime",
        label="IVA regime",
        value=None,
        masked=False,
        required=False,
        help=help_lines,
        about=about,
    )


def test_served_help_is_shown_one_paragraph_per_line_without_headings() -> None:
    served = ("Which IVA regime applies?", "General regime: standard IVA.")

    assert field_help_text(_field(help_lines=served, about="Schema description.")) == "\n".join(served)


def test_a_field_without_served_help_is_explained_by_its_schema_description() -> None:
    text = field_help_text(_field(help_lines=None, about="Schema description."))

    assert text == f"{tr('flows.manager.help.about')} Schema description."


def test_a_field_with_neither_help_nor_description_shows_nothing() -> None:
    assert field_help_text(_field(help_lines=None, about="")) == ""
    assert field_help_text(_field(help_lines=(), about="")) == ""
