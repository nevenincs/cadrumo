"""Typed ``--json`` payload schemas for app live CLI commands.

Each class declared here is a strict :class:`OutputSchema` subclass and is
decorated with :func:`register_schema` so the JSON-contract test suite can
enumerate every live-command surface this module covers.

Field sets match the production payload dicts constructed in ``_app_live.py``
at their emit sites.  All sequence fields use ``list`` rather than ``tuple``
because ``model_dump(mode='json')`` serialises pydantic tuples as JSON arrays,
and the strict ``OutputSchema`` base does not coerce lists to tuples on
re-validation.
"""

from __future__ import annotations

from ._schemas import OutputSchema, register_schema

# ---------------------------------------------------------------------------
# Shared sub-models (not registered — used as nested types)
# ---------------------------------------------------------------------------


class FiledListingRowPayload(OutputSchema):
    """One filed declaration row in a filed-list result."""

    modelo: str
    year: int
    period: str
    expediente_id: str
    status: str
    presented_at: str
    has_submitted_file: bool
    has_declaration_copy: bool
    has_justificante: bool


# ---------------------------------------------------------------------------
# Registered schemas
# ---------------------------------------------------------------------------


@register_schema("app.live.filed.list")
class FiledListResult(OutputSchema):
    """Payload for ``aeat app live filed list``."""

    modelo_filter: str | None
    year_from: int
    year_to: int
    row_count: int
    rows: list[FiledListingRowPayload]


@register_schema("app.live.filed.capture")
class FiledCaptureResult(OutputSchema):
    """Payload for ``aeat app live filed capture``."""

    output_root: str
    modelo: str
    year: int
    captured_count: int
    observation_paths: list[str]
    artefact_refs: list[str]
    casilla_count: int
    calculation_observation_count: int
    calculation_observation_keys: list[str]


@register_schema("app.live.filed.capture.sources")
class FiledCaptureSourcesResult(OutputSchema):
    """Payload for ``aeat app live filed capture-sources``."""

    output_root: str
    target_modelo: str
    target_year: int
    target_period: str
    captured_count: int
    observation_paths: list[str]
    artefact_refs: list[str]
    casilla_count: int
    calculation_observation_count: int
    calculation_observation_keys: list[str]
