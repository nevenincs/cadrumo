"""Strict public result contracts for profile sign-in custody commands.

:class:`OutputSchema` defines the public result envelope.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from ....application.runtime.sign_in import SignInStatus
from ....core.identity.bucket import BucketId
from ....core.json_contract import OutputSchema


class ConfigLoginResult(OutputSchema):
    """JSON envelope for ``aeat config login``.

    Reports the authenticated profile's immutable identity, its operator
    label and the two session deadlines. ``session_persisted`` is ``False`` on a host with no
    usable OS keychain, where the login is process-scoped only.
    ``already_authenticated`` marks the idempotent no-op that resumed a
    still-valid session without re-prompting, and
    ``closed_previous_profile`` names the profile a cross-profile handover
    signed out. No passphrase, key material, or session-key bytes enter
    this payload.
    """

    profile_id: BucketId
    active_profile: str
    authenticated_at: datetime
    idle_deadline: datetime
    absolute_deadline: datetime
    session_persisted: bool
    already_authenticated: bool
    closed_previous_profile: str | None = None


class ConfigSignInStatusResult(OutputSchema):
    """Non-authoritative active-profile sign-in observation, without a session bearer."""

    profile_id: BucketId | None
    status: SignInStatus


class ConfigLogoutResult(OutputSchema):
    """Global human sign-out; automation and receipt cleanup remain explicit."""

    logged_out_profile: str | None = None
    already_logged_out: bool
    scope: Literal["profile_human_access"] = "profile_human_access"
    human_receipt_revoked: bool
    receipt_removed: bool | None = None
    keychain_removed: bool | None = None
    automation_enabled: bool | None = None
    automation_revoked: Literal[False] = False
