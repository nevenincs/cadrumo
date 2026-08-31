"""Import-light output schemas for the config metadata surface."""

from __future__ import annotations

from ...application.operator_surface.help_models import HelpLabel, HelpProse, HelpSurface
from ...core.json_contract import OutputSchema
from ...core.text_bounds import NonEmptyList


class ConfigHelpEntryPayload(OutputSchema):
    """One command row in the curated config help document."""

    command: HelpLabel
    description: HelpLabel


class ConfigHelpSectionPayload(OutputSchema):
    """One workflow-ordered section in the curated config help document."""

    title: HelpLabel
    entries: NonEmptyList[ConfigHelpEntryPayload]


class ConfigRootResult(OutputSchema):
    """JSON envelope for bare ``aeat config`` and ``aeat config --help``."""

    surface: HelpSurface
    heading: HelpProse
    paragraphs: NonEmptyList[str]
    sections: NonEmptyList[ConfigHelpSectionPayload]
    footer: HelpProse


__all__ = ["ConfigHelpEntryPayload", "ConfigHelpSectionPayload", "ConfigRootResult"]
