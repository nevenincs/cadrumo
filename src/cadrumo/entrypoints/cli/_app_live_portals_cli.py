"""Portal registry behavior handlers for ``aeat app live portals``.

The list verb accepts :class:`PortalCategory` filters and projects local
:class:`PortalMetadata` records from :data:`PORTAL_REGISTRY` into
:class:`PortalEntryPayload` envelopes. The view verb resolves one
:class:`Portal` through :func:`get_portal` and emits :class:`PortalsViewResult`.
"""

from __future__ import annotations

from typing import TypedDict

import typer

from ...core.i18n.render import tr
from ...domain.portals.categories import PortalCategory
from ...domain.portals.errors import PortalRegistryError
from ._common import emit_envelope


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


def _project_portal_refusal(error: PortalRegistryError) -> PortalRegistryError:
    """Attach the application-owned no-action projection to one domain refusal."""
    from ...application.operator_actions.preconditions import no_action_precondition_verdict
    from ._common import attach_cli_policy_verdict

    failure = error.portal_failure
    assert failure is not None, "portal registry refusals must carry a closed domain classification"
    verdict = no_action_precondition_verdict(
        condition_id=failure.condition.value,
        facts=failure.facts,
        provenance=failure.provenance,
        outcome=failure.outcome,
    )
    return attach_cli_policy_verdict(error, verdict=verdict)


def _portal_row(metadata) -> _PortalRow:
    from ...domain.portals.hosts import portal_host_name

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


def portals_list(
    ctx: typer.Context,
    category: PortalCategory | None = None,
    modelo: str | None = None,
) -> None:
    """List local AEAT portal registry entries, optionally filtered by category or modelo.

    The ``category`` option is parsed as :class:`PortalCategory` and passed to
    :func:`portals_by_category`; ``--modelo`` uses :func:`portals_for_modelo`.
    All rows are :class:`PortalEntryPayload` projections emitted through
    :class:`PortalsListResult`.
    """
    try:
        from ...domain.portals.registry import PORTAL_REGISTRY, portals_by_category, portals_for_modelo

        if category and modelo:
            raise typer.BadParameter(tr("cli.app.live.portals.category_modelo_exclusive"))
        if category:
            entries = portals_by_category(category)
        elif modelo:
            entries = portals_for_modelo(modelo)
        else:
            entries = tuple(PORTAL_REGISTRY.values())
    except PortalRegistryError as exc:
        raise _project_portal_refusal(exc) from exc

    rows = [_portal_row(m) for m in entries]
    from ._app_live_portals_payloads import PortalEntryPayload, PortalsListResult

    result = PortalsListResult(
        count=len(rows),
        rows=[PortalEntryPayload(**row) for row in rows],
    )
    lines = [f"count\t{len(rows)}"]
    for row in rows:
        lines.append(f"{row['portal']}\t{row['category']}\t{row['url_stability']}\t{row['label']}")
    emit_envelope(ctx, command="app.live.portals.list", result=result, lines=lines)


def portals_show(
    ctx: typer.Context,
    portal_id: str,
) -> None:
    """Show one portal-registry entry by its :class:`Portal` id.

    The id resolves through :func:`get_portal` and emits the local
    :class:`PortalEntryPayload` projection as :class:`PortalsViewResult`.
    """
    try:
        from ...domain.portals.registry import get_portal

        metadata = get_portal(portal_id)
    except PortalRegistryError as exc:
        raise _project_portal_refusal(exc) from exc
    payload = _portal_row(metadata)
    from ._app_live_portals_payloads import PortalsViewResult

    result = PortalsViewResult(**payload)
    lines = [f"{key}\t{value}" for key, value in payload.items() if value != ""]
    emit_envelope(ctx, command="app.live.portals.view", result=result, lines=lines)


__all__ = ["portals_list", "portals_show"]


# ─────────────────────────────────────────────────────────────────────────
