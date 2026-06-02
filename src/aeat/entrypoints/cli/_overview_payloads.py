"""Typed ``--json`` payload schemas for overview CLI commands.

Each class declared here is a strict :class:`OutputSchema` subclass and is
decorated with :func:`register_schema` so the JSON-contract test suite can
enumerate every overview-command surface this module covers.

Field sets match the production payload dicts constructed in ``_overview.py``
at their emit sites. All sequence fields use ``list`` rather than ``tuple``
because ``model_dump(mode='json')`` serialises pydantic tuples as JSON arrays,
and the strict ``OutputSchema`` base does not coerce lists to tuples on
re-validation.
"""

from __future__ import annotations

from ._schemas import OutputSchema, register_schema

# ---------------------------------------------------------------------------
# Shared sub-models (not registered — used as nested types)
# ---------------------------------------------------------------------------


class OverviewDraftPayload(OutputSchema):
    """One draft row nested in a period-scoped status result."""

    draft_id: str
    modelo: str
    status: str


class OverviewCalendarEntryPayload(OutputSchema):
    """One calendar entry nested in a calendar result."""

    modelo: str
    period: str
    user_state: str
    opens_on: str
    closes_on: str
    adjusted_closes_on: str
    shift_reason: str | None = None


class OverviewCalendarWarningPayload(OutputSchema):
    """One calendar warning nested in a calendar result."""

    code: str
    message: str
    fix_command: str


class OverviewAgendaEntryPayload(OutputSchema):
    """One agenda entry (next_due / due_today / due_soon / overdue)."""

    modelo: str
    period: str
    adjusted_closes_on: str


# ---------------------------------------------------------------------------
# Registered schemas
# ---------------------------------------------------------------------------


@register_schema("overview.status")
class OverviewStatusResult(OutputSchema):
    """JSON envelope for ``aeat app overview status``."""

    # Period-scoped branch fields
    period: str | None = None
    # The period-scoped branch emits a list of draft payloads; the
    # full-status passthrough branch emits an ``int`` count derived from
    # ``OverviewStatusReport.drafts``. Both shapes share the JSON key.
    drafts: int | list[OverviewDraftPayload] | None = None
    verbose: bool | None = None

    # Full status-report passthrough (model_dump of OverviewStatusReport).
    # The status report is an application-layer pydantic model; the full
    # shape is forwarded as-is. We accept extra fields so any new keys
    # the application model adds don't break the conformance gate.
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class-variable assignment triggers mypy
    # [assignment]; suppression is the only escape without a mypy plugin upgrade.
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("overview.calendar")
class OverviewCalendarResult(OutputSchema):
    """JSON envelope for ``aeat app overview calendar``.

    Covers both the single-profile mode (``entries``/``warnings``/
    ``suppressed_entries`` populated) and the ``--all-profiles`` mode
    (``profiles`` populated, single-profile fields empty). The same
    envelope key serves the leaf so the JSON-contract registry holds
    exactly one schema per CLI leaf; the populated field set tells the
    consumer which branch produced the payload.
    """

    from_date: str | None = None
    to_date: str | None = None
    entries: list[dict] = []
    warnings: list[dict] = []
    suppressed_entries: list[dict] = []
    profiles: list[dict] = []
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class-variable assignment triggers mypy
    # [assignment]; suppression is the only escape without a mypy plugin upgrade.
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("overview.agenda")
class OverviewAgendaResult(OutputSchema):
    """JSON envelope for ``aeat app overview agenda``."""

    as_of: str | None = None
    horizon_days: int | None = None
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class-variable assignment triggers mypy
    # [assignment]; suppression is the only escape without a mypy plugin upgrade.
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("overview.backlog")
class OverviewBacklogResult(OutputSchema):
    """JSON envelope for ``aeat app overview backlog``."""

    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class-variable assignment triggers mypy
    # [assignment]; suppression is the only escape without a mypy plugin upgrade.
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("overview.explain")
class OverviewExplainResult(OutputSchema):
    """JSON envelope for ``aeat app overview explain``."""

    modelo: str | None = None
    year: int | None = None
    applicable: bool | None = None
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class-variable assignment triggers mypy
    # [assignment]; suppression is the only escape without a mypy plugin upgrade.
    model_config = {"extra": "allow"}  # type: ignore[assignment]
