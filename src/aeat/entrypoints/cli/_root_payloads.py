"""Typed ``--json`` payload schemas for root CLI group callbacks.

The root callbacks in :mod:`aeat.entrypoints.cli` are not ordinary leaf
commands, but they still emit :class:`~aeat.entrypoints.cli._schemas.SchemaEnvelope`
documents through :func:`aeat.entrypoints.cli._common._emit_envelope`.
Each class declared here is a strict :class:`OutputSchema` subclass and is
decorated with :func:`register_schema` so the JSON-contract and CLI-reference
conformance gates can enumerate these group-callback surfaces alongside normal
command leaves.

Field sets match the production payload dicts constructed in
:mod:`aeat.entrypoints.cli` at the ``root.status`` and ``root.app`` emit sites.
The concrete application shape depends on the callback branch:
:class:`~aeat.application.operator_surface.HelpDocument`,
:class:`~aeat.application.operator_surface.RootLandingReport`, or
:class:`~aeat.application.overview.OverviewStatusReport`.
"""

from __future__ import annotations

from ._schemas import OutputSchema, register_schema


@register_schema("root.status")
class RootStatusResult(OutputSchema):
    """JSON envelope for the bare ``aeat`` (or ``aeat --help``) invocation.

    The root callback validates one of three application-layer payloads:
    :class:`~aeat.application.operator_surface.HelpDocument` for ``aeat --help``,
    :class:`~aeat.application.operator_surface.RootLandingReport` for the
    cold-start / no-session landing, or
    :class:`~aeat.application.overview.OverviewStatusReport` when an active
    session can render the full overview. These shapes vary significantly, so
    the schema accepts extra fields while still registering the stable
    ``root.status`` envelope key.
    """

    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class var shadows ConfigDict descriptor;
    # mypy assignment check is incorrect.
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("root.app")
class AppRootResult(OutputSchema):
    """JSON envelope for the bare ``aeat app`` (or ``aeat app --help``) invocation.

    The app group callback wraps
    :class:`~aeat.application.operator_surface.HelpDocument` under the stable
    ``root.app`` group-callback key. Like :class:`RootStatusResult`, the schema
    allows the application-owned help fields to pass through without modelling
    every help-section variant in the CLI layer.
    """

    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class var shadows ConfigDict descriptor;
    # mypy assignment check is incorrect.
    model_config = {"extra": "allow"}  # type: ignore[assignment]
