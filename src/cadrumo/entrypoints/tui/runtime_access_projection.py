"""Allowlisted public-session details for the runtime access screen."""

from __future__ import annotations

from ...application.user_profile.access_contracts import DisclosurePermission
from ...application.user_profile.access_projections import PublicAccessSession
from ...application.user_profile.automation_lifecycle import AutomationDenialReceipt
from ...core.i18n.render import tr
from ...core.period import Period


def session_rows(sessions: tuple[PublicAccessSession, ...]) -> str:
    """Show only allowlisted session facts, never a credential or custody key."""
    absent = tr("tui.automation_inventory.not_applicable")
    rows: list[str] = []
    for item in sorted(sessions, key=lambda item: item.session_id):
        rows.extend(_session_lines(item, absent))
    return "\n".join(rows)


def _session_lines(item: PublicAccessSession, absent: str) -> list[str]:
    scope = item.scope
    rows = [
        tr(
            "tui.runtime_access.session_details",
            session_id=str(item.session_id),
            client_id=str(item.client_id),
            parent_session_id=str(item.parent_session_id) if item.parent_session_id is not None else absent,
            grant_id=str(item.grant_id) if item.grant_id is not None else absent,
            key_id=str(item.key_id) if item.key_id is not None else absent,
            kind=item.kind.value,
            state=item.state.value,
            expires_at=item.expires_at.isoformat(),
        )
    ]
    rows.extend(
        _session_scope_lines(
            (
                ("operations", ", ".join(sorted(scope.operations))),
                ("actions", ", ".join(sorted(action.value for action in scope.actions))),
                ("disclosures", _disclosure_words(scope.disclosures)),
                ("periods", _period_words(scope.periods)),
                ("delegation", tr("flows.confirm.yes") if scope.allow_delegation else tr("flows.confirm.no")),
                (
                    "period_independent",
                    tr("flows.confirm.yes") if scope.allow_period_independent else tr("flows.confirm.no"),
                ),
            ),
            absent,
        )
    )
    return rows


def _session_scope_lines(values: tuple[tuple[str, str], ...], absent: str) -> list[str]:
    return [f"{tr(f'tui.automation_inventory.{label}')}: {value or absent}" for label, value in values]


def _period_words(periods: frozenset[Period] | None) -> str:
    if periods is None:
        return tr("tui.automation_inventory.all_periods")
    return ", ".join(str(period) for period in sorted(periods, key=str)) or tr("tui.automation_inventory.no_periods")


def _disclosure_words(disclosures: frozenset[DisclosurePermission]) -> str:
    permissions = sorted(
        disclosures,
        key=lambda permission: (
            str(permission.destination_id),
            str(permission.projection_id),
            permission.category.value,
        ),
    )
    return ", ".join(
        f"{permission.destination_id}/{permission.projection_id}/{permission.category.value}"
        for permission in permissions
    )


def denial_acknowledgement(receipt: AutomationDenialReceipt) -> str:
    """Render which revocation effects were confirmed and which cleanup remains pending."""
    return tr(
        "tui.runtime_access.denial_acknowledgement",
        access_denied=tr("flows.confirm.yes") if receipt.access_denied else tr("flows.confirm.no"),
        cleanup_pending=tr("flows.confirm.yes") if receipt.cleanup_pending else tr("flows.confirm.no"),
    )
