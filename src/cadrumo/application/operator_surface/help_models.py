"""Import-light typed records for operator help and root landing output."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


class HelpSurface(StrEnum):
    """Curated help surfaces accepted by :func:`build_help_document`."""

    ROOT = "root"
    CONFIG = "config"
    APP = "app"



HelpLabel = Annotated[str, StringConstraints(min_length=1, max_length=80)]
"""One line of the help surface: a command, its description, a section title."""

HelpProse = Annotated[str, StringConstraints(min_length=1, max_length=120)]
"""A heading or footer, which gets more room than a single help line."""


class HelpEntry(BaseModel):
    """One localized command row in a curated :class:`HelpSection`."""

    model_config = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

    command: HelpLabel
    description: HelpLabel


class HelpSection(BaseModel):
    """One workflow-ordered section in a curated :class:`HelpDocument`."""

    model_config = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

    title: HelpLabel
    entries: tuple[HelpEntry, ...] = Field(min_length=1)


class HelpDocument(BaseModel):
    """Localized operator-help document for one accepted surface."""

    model_config = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

    surface: HelpSurface
    heading: HelpProse
    paragraphs: tuple[str, ...] = Field(min_length=1)
    sections: tuple[HelpSection, ...] = Field(min_length=1)
    footer: HelpProse


class RootLandingReport(BaseModel):
    """Bare-root landing report built from caller-projected profile state."""

    model_config = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

    profile_selected: bool = False
    active_profile: str | None = None
    command: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=160)

    @model_validator(mode="after")
    def _selected_profile_owns_display_identity(self) -> RootLandingReport:
        """Reject a display label that has no corresponding selected profile."""
        if self.active_profile is not None and not self.profile_selected:
            raise ValueError("active profile label requires a selected profile")
        return self


__all__ = ["HelpDocument", "HelpEntry", "HelpSection", "HelpSurface", "RootLandingReport"]
