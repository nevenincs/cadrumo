"""Contract parity between the config-help transport and the canonical HelpDocument.

``ConfigRootResult`` (plus its nested ``ConfigHelpSectionPayload`` /
``ConfigHelpEntryPayload`` rows) must refuse the malformed surface, bounds,
and empty-collection shapes the canonical ``HelpDocument`` / ``HelpSection``
/ ``HelpEntry`` models already refuse, and must accept a real
``build_help_document`` projection.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ....application.operator_surface import build_help_document
from .._config_help_payloads import ConfigHelpEntryPayload, ConfigHelpSectionPayload, ConfigRootResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _project(document) -> ConfigRootResult:
    return ConfigRootResult(
        surface=document.surface,
        heading=document.heading,
        paragraphs=list(document.paragraphs),
        sections=[
            ConfigHelpSectionPayload(
                title=section.title,
                entries=[
                    ConfigHelpEntryPayload(command=entry.command, description=entry.description)
                    for entry in section.entries
                ],
            )
            for section in document.sections
        ],
        footer=document.footer,
    )


def test_config_root_result_accepts_a_real_help_document() -> None:
    """A genuine ``build_help_document("config")`` projection validates cleanly."""
    document = build_help_document("config")

    result = _project(document)

    assert result.surface == document.surface
    assert len(result.sections) == len(document.sections)


def test_config_root_result_rejects_an_unknown_surface() -> None:
    """A surface outside the closed ``HelpSurface`` vocabulary is refused.

    Round-trips through the JSON-text path (``model_dump_json`` /
    ``model_validate_json``), not ``model_validate(x.model_dump(mode="json"))``:
    ``surface`` is a strict ``HelpSurface`` enum field, and its JSON-mode dict
    projection is a bare string that ``model_validate`` on a plain dict does not
    coerce back to the enum (only genuine JSON text gets that leniency). Feeding
    the dict form here raised on *any* string value, including a real member's
    own value, so it never actually exercised the closed-vocabulary rejection this
    test claims.
    """
    document = build_help_document("config")
    valid = _project(document)

    payload = json.loads(valid.model_dump_json())
    payload["surface"] = "bogus"

    with pytest.raises(ValidationError):
        ConfigRootResult.model_validate_json(json.dumps(payload))


def test_config_root_result_rejects_empty_paragraphs_and_sections() -> None:
    """An empty ``paragraphs`` or ``sections`` collection is refused."""
    document = build_help_document("config")
    valid = _project(document)
    dumped = valid.model_dump(mode="json")

    with pytest.raises(ValidationError):
        ConfigRootResult.model_validate({**dumped, "paragraphs": []})

    with pytest.raises(ValidationError):
        ConfigRootResult.model_validate({**dumped, "sections": []})


def test_config_help_section_rejects_a_blank_title_and_empty_entries() -> None:
    """A blank section title or an empty entry list is refused."""
    with pytest.raises(ValidationError):
        ConfigHelpSectionPayload(title="", entries=[ConfigHelpEntryPayload(command="x", description="y")])

    with pytest.raises(ValidationError):
        ConfigHelpSectionPayload(title="Profile", entries=[])


def test_config_help_entry_rejects_a_blank_command_or_description() -> None:
    """A blank command or description is refused."""
    with pytest.raises(ValidationError):
        ConfigHelpEntryPayload(command="", description="Show the active profile.")

    with pytest.raises(ValidationError):
        ConfigHelpEntryPayload(command="profile show", description="")
