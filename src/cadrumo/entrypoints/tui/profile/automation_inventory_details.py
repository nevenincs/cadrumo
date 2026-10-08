"""Render public automation inventory facts for the TUI."""

from __future__ import annotations

from ....application.user_profile.automation_enrollment import (
    AutomationGrantProjection,
    AutomationKeyProjection,
    AutomationReviewProjection,
    AutomationScopeProjection,
)
from ....core.i18n.render import tr


def _value(value: object) -> str:
    if isinstance(value, bool):
        return tr("flows.confirm.yes") if value else tr("flows.confirm.no")
    return str(value)


def _detail(label: str, value: object) -> str:
    return f"{tr(f'tui.automation_inventory.{label}')}: {_value(value)}"


def _scope(scope: AutomationScopeProjection) -> tuple[str, ...]:
    disclosures = tuple(
        f"{item.destination_id}/{item.projection_id}/{item.category.value}" for item in scope.disclosures
    )
    if scope.periods is None:
        periods = tr("tui.automation_inventory.all_periods")
    elif not scope.periods:
        periods = tr("tui.automation_inventory.no_periods")
    else:
        periods = ", ".join(f"{item.filing_year}/{item.code}" for item in scope.periods)
    return (
        _detail("operations", ", ".join(scope.operations)),
        _detail("actions", ", ".join(item.value for item in scope.actions)),
        _detail("disclosures", ", ".join(disclosures)),
        _detail("periods", periods),
        _detail("delegation", scope.allow_delegation),
        _detail("period_independent", scope.allow_period_independent),
    )


def _grant_detail(item: AutomationGrantProjection) -> str:
    return "\n".join(
        (
            _detail("id", item.grant_id),
            _detail("client", item.client_id),
            _detail("state", item.state.value),
            _detail("expires", item.expires_at.isoformat()),
            *_scope(item.scope),
            _detail("unattended", item.unattended),
            *((tr("tui.automation_inventory.unattended_notice"),) if item.unattended else ()),
            _detail("os_lock", item.allow_os_lock),
        )
    )


def _key_detail(item: AutomationKeyProjection) -> str:
    return "\n".join(
        (
            _detail("id", item.key_id),
            _detail("grant", item.grant_id),
            _detail("state", item.state.value),
            _detail("expires", item.expires_at.isoformat()),
            _detail("last_used", item.last_used_at.isoformat() if item.last_used_at is not None else ""),
        )
    )


def _request_detail(item: AutomationReviewProjection) -> str:
    return "\n".join(
        (
            _detail("profile", item.receipt.profile_id),
            _detail("id", item.receipt.request_id),
            _detail("review_digest", item.receipt.review_digest),
            _detail("client", item.client_id),
            _detail("destination", item.destination_id),
            _detail("state", item.receipt.stage.value),
            _detail("expires", item.expires_at.isoformat()),
            _detail("kind", item.proposal.kind.value),
            _detail("grant_expires", item.proposal.expires_at.isoformat()),
            _detail(
                "key_expires",
                item.proposal.key_expires_at.isoformat() if item.proposal.key_expires_at is not None else "",
            ),
            _detail("target_grant", item.proposal.target_grant_id or ""),
            _detail("target_key", item.proposal.target_key_id or ""),
            *_scope(item.proposal.scope),
            _detail("unattended", item.proposal.unattended),
            *((tr("tui.automation_inventory.unattended_notice"),) if item.proposal.unattended else ()),
            _detail("os_lock", item.proposal.allow_os_lock),
        )
    )
