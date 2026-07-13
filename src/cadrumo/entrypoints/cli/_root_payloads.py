"""Typed ``--json`` payload schemas for root CLI group callbacks.

The root callbacks are not ordinary leaf commands, but they still emit
:class:`SchemaEnvelope` documents through :func:`_emit_envelope`. Each class is
a strict :class:`OutputSchema` subclass. :func:`register_schema` registers it
so the JSON-contract and CLI-reference conformance gates can enumerate these
group-callback surfaces alongside normal command leaves.

Field sets match the production payload dicts constructed in
the root callback at the ``root.status`` and ``root.app`` emit sites. The
concrete application shape depends on the callback branch:
:class:`HelpDocument`, :class:`RootLandingReport`, or
:class:`OverviewStatusReport`.

See Also:
    :func:`build_help_document`
        Builds the root and app help documents wrapped by these group-callback
        payload schemas.
    :func:`build_root_landing_report`
        Builds the cold-start / no-session landing DTO carried by
        ``root.status``.
    :func:`build_overview_status_report`
        Builds the active-session overview DTO also accepted by
        ``root.status``.
"""

from __future__ import annotations

from ._schemas import OutputSchema, register_schema


@register_schema("root.status")
class RootStatusResult(OutputSchema):
    """JSON envelope for the bare ``cadrumo`` (or ``aeat --help``) invocation.

    The root callback validates one of three application-layer payloads:
    :class:`HelpDocument` for ``aeat --help``, :class:`RootLandingReport` for the
    cold-start / no-session landing, or :class:`OverviewStatusReport` when an
    active session can render the full overview. These shapes vary
    significantly, so the schema accepts extra fields while still registering
    the stable ``root.status`` envelope key.

    The text half of the landing branch is rendered by
    :func:`render_cli_root_landing_lines`; JSON mode keeps the application DTO
    fields intact inside :class:`SchemaEnvelope`.
    """

    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class var shadows ConfigDict descriptor;
    # mypy assignment check is incorrect.
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("root.app")
class AppRootResult(OutputSchema):
    """JSON envelope for the bare ``aeat app`` (or ``aeat app --help``) invocation.

    The app group callback wraps :class:`HelpDocument` under the stable
    ``root.app`` group-callback key. Like :class:`RootStatusResult`, the schema
    allows the application-owned help fields to pass through without modelling
    every help-section variant in the CLI layer.

    The document is produced by :func:`build_help_document` for the ``app`` help
    surface and emitted through :class:`SchemaEnvelope`.
    """

    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class var shadows ConfigDict descriptor;
    # mypy assignment check is incorrect.
    model_config = {"extra": "allow"}  # type: ignore[assignment]
