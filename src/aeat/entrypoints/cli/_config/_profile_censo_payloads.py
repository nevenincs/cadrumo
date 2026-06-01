"""Typed ``--json`` payload schemas for censo config CLI commands.

Each class declared here is a strict :class:`OutputSchema` subclass and is
decorated with :func:`register_schema` so the JSON-contract test suite can
enumerate every censo command surface this module covers.

Field sets match the production payload dicts constructed in
``_profile_censo.py`` at their emit sites.
"""

from __future__ import annotations

from .._schemas import OutputSchema, register_schema


@register_schema("config.profile.censo.refresh")
class CensoRefreshResult(OutputSchema):
    """JSON envelope for ``aeat config profile censo refresh``."""

    snapshot_id: str
    profile_id: str
    captured_at: str
    facts: dict = {}


@register_schema("config.profile.censo.show")
class CensoShowResult(OutputSchema):
    """JSON envelope for ``aeat config profile censo show``."""

    snapshot_id: str
    profile_id: str
    captured_at: str
    source_url: str
    state: str
    facts: dict = {}


@register_schema("config.profile.censo.compare")
class CensoCompareResult(OutputSchema):
    """JSON envelope for ``aeat config profile censo compare``."""

    snapshot_id: str | None = None
    diverging: list[dict] = []
    censo_only: list[dict] = []
    profile_only: list[dict] = []
    rows: list[dict] = []
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR: pydantic v2 model_config class var shadows ConfigDict descriptor; mypy assignment check incorrect.
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("config.profile.censo.apply")
class CensoApplyResult(OutputSchema):
    """JSON envelope for ``aeat config profile censo apply``."""

    snapshot_id: str
    written_paths: list[str] = []
    unchanged_paths: list[str] = []
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR: pydantic v2 model_config class var shadows ConfigDict descriptor; mypy assignment check incorrect.
    model_config = {"extra": "allow"}  # type: ignore[assignment]
