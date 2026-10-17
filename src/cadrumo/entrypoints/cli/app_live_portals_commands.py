"""Portal registry behavior handlers for ``aeat app live portals``.

The list verb accepts :class:`PortalCategory` filters and the view verb resolves
one :class:`Portal` by id; both read the portal catalogue through the shared
reference-catalogue service and emit its typed results.
"""

from __future__ import annotations

import typer

from ...application.reference_catalogue import PortalFilterConflictError, list_portals, view_portal
from ...core.modelo import Modelo
from ...domain.portals.categories import PortalCategory
from ...domain.portals.errors import PortalRegistryError
from .common import emit_envelope


def _project_portal_refusal(error: PortalRegistryError) -> PortalRegistryError:
    """Attach the application-owned no-action projection to one domain refusal."""
    from ...application.operator_actions.preconditions import no_action_precondition_verdict
    from .common import attach_cli_policy_verdict

    failure = error.portal_failure
    if failure is None:
        # A refusal carrying no closed classification cannot be projected into an
        # operator action. Surface it as raised: replacing the operator's portal
        # refusal with an internal error about the projection would lose the
        # refusal they need to read.
        return error
    verdict = no_action_precondition_verdict(
        condition_id=failure.condition.value,
        facts=failure.facts,
        provenance=failure.provenance,
        outcome=failure.outcome,
    )
    return attach_cli_policy_verdict(error, verdict=verdict)


def portals_list(
    ctx: typer.Context,
    category: PortalCategory | None = None,
    modelo: Modelo | None = None,
) -> None:
    """List local AEAT portals, optionally filtered by :class:`PortalCategory` or modelo."""
    try:
        result = list_portals(category=category, modelo=modelo)
    except PortalFilterConflictError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except PortalRegistryError as exc:
        raise _project_portal_refusal(exc) from exc

    lines = [f"count\t{result.count}"]
    for row in result.rows:
        lines.append(f"{row.portal}\t{row.category}\t{row.url_stability}\t{row.label}")
    emit_envelope(ctx, command="app.live.portals.list", result=result, lines=lines)


def portals_show(
    ctx: typer.Context,
    portal_id: str,
) -> None:
    """Show one portal-registry entry by its :class:`Portal` id."""
    try:
        result = view_portal(portal_id)
    except PortalRegistryError as exc:
        raise _project_portal_refusal(exc) from exc
    lines = [f"{key}\t{value}" for key, value in result.model_dump().items() if value != ""]
    emit_envelope(ctx, command="app.live.portals.view", result=result, lines=lines)


__all__ = ["portals_list", "portals_show"]


# ─────────────────────────────────────────────────────────────────────────
