"""Typed ``--json`` payload schemas for census config CLI commands.

Each class declared here is a strict :class:`OutputSchema` subclass and is
decorated with :func:`register_schema` so the JSON-contract test suite can
enumerate every census command surface this module covers.

Field sets match the production payload dicts constructed in
``_profile_census.py`` at their emit sites.
"""

from __future__ import annotations

from .._schemas import OutputSchema, register_schema


@register_schema("config.profile.census.refresh")
class CensusRefreshResult(OutputSchema):
    """JSON envelope for ``aeat config profile census refresh``."""

    snapshot_id: str
    profile_id: str
    captured_at: str
    facts: dict = {}


@register_schema("config.profile.census.show")
class CensusShowResult(OutputSchema):
    """JSON envelope for ``aeat config profile census show``."""

    snapshot_id: str
    profile_id: str
    captured_at: str
    source_url: str
    state: str
    facts: dict = {}


@register_schema("config.profile.census.compare")
class CensusCompareResult(OutputSchema):
    """JSON envelope for ``aeat config profile census compare``."""

    snapshot_id: str | None = None
    diverging: list[dict] = []
    census_only: list[dict] = []
    profile_only: list[dict] = []
    rows: list[dict] = []
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("config.profile.census.apply")
class CensusApplyResult(OutputSchema):
    """JSON envelope for ``aeat config profile census apply``."""

    snapshot_id: str
    written_paths: list[str] = []
    unchanged_paths: list[str] = []
    model_config = {"extra": "allow"}  # type: ignore[assignment]
