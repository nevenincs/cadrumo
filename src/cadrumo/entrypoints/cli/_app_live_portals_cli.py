"""Portal registry command registration for ``aeat app live portals``.

The list verb accepts :class:`PortalCategory` filters and projects local
:class:`PortalMetadata` records from :data:`PORTAL_REGISTRY` into
:class:`PortalEntryPayload` envelopes. The view verb resolves one
:class:`Portal` through :func:`get_portal` and emits :class:`PortalsViewResult`.
"""

from __future__ import annotations

from typing import Annotated, TypedDict

import typer

from ...core.errors import resolve_error_message
from ...core.i18n import tr
from ...domain.portals import PortalCategory
from ._app_execution_policies import METADATA, declare_metadata_group
from ._command_policy import command_execution_policy
from ._common import MODELO_CODE_CHOICE_ALL, _emit_envelope


class _PortalRow(TypedDict):
    portal: str
    category: str
    subdomain: str
    url: str
    auth_methods: str
    url_stability: str
    label: str
    purpose: str
    active: bool


portals_app = typer.Typer(
    name="portals",
    help=tr("cli.app.live.portals.app_help", default="Local AEAT portal registry catalogue (read-only)."),
    no_args_is_help=True,
    add_completion=False,
)
declare_metadata_group(portals_app)


def register_portals_commands(app: typer.Typer) -> None:
    """Mount local portal-registry commands on the live app."""
    app.add_typer(portals_app, name="portals")


def _portal_row(metadata) -> _PortalRow:
    from ...domain.portals import portal_host_name

    # `metadata.label` and `metadata.purpose` are Translatable
    # translation keys (e.g. `entries.portal_sede_root.label`). A bare
    # `str()` dumps the raw key path at the operator; route them
    # through `tr()` so the resolved label is emitted instead.
    return _PortalRow(
        portal=metadata.portal.value,
        category=metadata.category.value,
        subdomain=portal_host_name(metadata.subdomain),
        url=str(metadata.url),
        auth_methods=",".join(sorted(method.value for method in metadata.auth_methods)),
        url_stability=metadata.url_stability.value,
        label=tr(str(metadata.label)),
        purpose=tr(str(metadata.purpose)),
        active=metadata.active,
    )


@portals_app.command(
    "list",
    help=tr("cli.app.live.portals.list_help", default="List portal-registry entries (optionally filtered)."),
)
def portals_list(
    ctx: typer.Context,
    category: Annotated[
        PortalCategory | None,
        typer.Option(
            "--category",
            help=tr("cli.app.live.portals.category_help", default="Filter to one PortalCategory value."),
        ),
    ] = None,
    modelo: Annotated[
        str | None,
        typer.Option(
            "--modelo",
            click_type=MODELO_CODE_CHOICE_ALL,
            help=tr(
                "cli.app.live.portals.modelo_help",
                default="Filter to portals bound to one modelo code (e.g. 303).",
            ),
        ),
    ] = None,
) -> None:
    """List local AEAT portal registry entries, optionally filtered by category or modelo.

    The ``category`` option is parsed as :class:`PortalCategory` and passed to
    :func:`portals_by_category`; ``--modelo`` uses :func:`portals_for_modelo`.
    All rows are :class:`PortalEntryPayload` projections emitted through
    :class:`PortalsListResult`.
    """
    from ...domain.portals import PORTAL_REGISTRY, portals_by_category, portals_for_modelo

    if category and modelo:
        raise typer.BadParameter(tr("cli.app.live.portals.category_modelo_exclusive"))
    if category:
        entries = portals_by_category(category)
    elif modelo:
        entries = portals_for_modelo(modelo)
    else:
        entries = tuple(PORTAL_REGISTRY.values())

    rows = [_portal_row(m) for m in entries]
    from ._app_live_payloads import PortalEntryPayload, PortalsListResult

    result = PortalsListResult(
        count=len(rows),
        rows=[PortalEntryPayload(**row) for row in rows],
    )
    lines = [f"count\t{len(rows)}"]
    for row in rows:
        lines.append(f"{row['portal']}\t{row['category']}\t{row['url_stability']}\t{row['label']}")
    _emit_envelope(ctx, command="app.live.portals.list", result=result, lines=lines)


@portals_app.command(
    "view",
    help=tr("cli.app.live.portals.view_help", default="View one portal-registry entry by Portal id."),
)
def portals_show(
    ctx: typer.Context,
    portal_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.live.portals.portal_id_help", default="Portal enum value.")),
    ],
) -> None:
    """Show one portal-registry entry by its :class:`Portal` id.

    The id resolves through :func:`get_portal` and emits the local
    :class:`PortalEntryPayload` projection as :class:`PortalsViewResult`.
    """
    from ...domain.portals import UnknownPortalError, get_portal

    try:
        metadata = get_portal(portal_id)
    except UnknownPortalError as exc:
        raise typer.BadParameter(resolve_error_message(exc)) from exc
    payload = _portal_row(metadata)
    from ._app_live_payloads import PortalsViewResult

    result = PortalsViewResult(**payload)
    lines = [f"{key}\t{value}" for key, value in payload.items() if value != ""]
    _emit_envelope(ctx, command="app.live.portals.view", result=result, lines=lines)


for _callback in (portals_list, portals_show):
    command_execution_policy(METADATA)(_callback)


# ─────────────────────────────────────────────────────────────────────────
