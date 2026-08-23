"""Import-light output schemas for the config metadata surface."""

from __future__ import annotations

from pydantic import Field

from ...application.operator_surface import HelpSurface
from ...core.json_contract import OutputSchema


class ConfigHelpEntryPayload(OutputSchema):
    """One command row in the curated config help document."""

    command: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=80)


class ConfigHelpSectionPayload(OutputSchema):
    """One workflow-ordered section in the curated config help document."""

    title: str = Field(min_length=1, max_length=80)
    entries: list[ConfigHelpEntryPayload] = Field(min_length=1)


class ConfigRootResult(OutputSchema):
    """JSON envelope for bare ``aeat config`` and ``aeat config --help``."""

    surface: HelpSurface
    heading: str = Field(min_length=1, max_length=120)
    paragraphs: list[str] = Field(min_length=1)
    sections: list[ConfigHelpSectionPayload] = Field(min_length=1)
    footer: str = Field(min_length=1, max_length=120)


__all__ = ["ConfigHelpEntryPayload", "ConfigHelpSectionPayload", "ConfigRootResult"]
