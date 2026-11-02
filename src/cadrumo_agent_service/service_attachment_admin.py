"""The person's attachment decisions, answered for the administration surface.

None of these touches the agent tree's lifecycle: they read and settle disclosure
grants and release requests held by the service.
"""

from __future__ import annotations

from typing import Any

from .providers.application.attachment_releases import AttachmentReleases, ReleaseScope


def answer_attachment_admin(
    releases: AttachmentReleases,
    *,
    closing: bool,
    action: str,
    run_id: str | None,
    request_id: str | None,
    scope: str | None,
    grant_id: str | None,
    conversation_id: str | None,
) -> dict[str, Any]:
    """Answer one attachment administration action, refusing while the service is stopping."""
    if closing:
        return {"kind": "refused", "code": "service_stopping"}
    if action == "attachment_grants":
        return releases.grants()
    if action == "attachment_grant_revoke" and grant_id is not None:
        return releases.revoke(grant_id)
    if action == "attachment_conversation_forget" and conversation_id is not None:
        return releases.forget_conversation(conversation_id)
    return _answer_request_action(releases, action, run_id, request_id, scope)


def _answer_request_action(
    releases: AttachmentReleases, action: str, run_id: str | None, request_id: str | None, scope: str | None
) -> dict[str, Any]:
    if run_id is None or request_id is None:
        return {"kind": "refused", "code": "invalid_request"}
    if action == "attachment_card":
        return releases.card(run_id, request_id)
    if action == "attachment_release":
        return releases.release(run_id, request_id, None if scope is None else ReleaseScope(scope))
    return {"kind": "refused", "code": "invalid_request"}
