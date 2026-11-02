"""The automation access a person is asked to approve: the kind of change and the reviewed proposal.

A proposal is the consent operand an automation or a frontend submits through
the ephemeral channel. It names a scope and bounds, never a credential, and the
runtime decides whether to grant it.
"""

from __future__ import annotations

import unicodedata
from datetime import timedelta
from enum import StrEnum
from typing import Annotated, Final
from uuid import UUID

from pydantic import AfterValidator, BaseModel, StringConstraints, model_validator

from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from cadrumo.core.time.utc import UtcInstant

from .access_vocabulary import AccessScope

_GRANT_DEFAULT_VALIDITY_DAYS: Final = 365

GRANT_DEFAULT_VALIDITY: Final = timedelta(days=_GRANT_DEFAULT_VALIDITY_DAYS)
"""How long a proposed grant lasts when its proposer names no shorter validity."""


GRANT_LABEL_MAXIMUM_LENGTH: Final = 64
"""The longest name a person can give a key at issue."""


def _require_printable_label(value: str) -> str:
    if any(unicodedata.category(character).startswith("C") for character in value):
        raise ValueError("a key label holds printable characters only")
    return value


type GrantLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=GRANT_LABEL_MAXIMUM_LENGTH),
    AfterValidator(_require_printable_label),
]
"""A person's non-secret name for a key; it names the key in the inventory and authenticates nothing."""


class EnrollmentKind(StrEnum):
    """Exactly reviewed grant changes; a rotation never extends grant validity."""

    ENROLL = "enroll"
    ROTATE = "rotate"
    RENEW = "renew"
    CHANGE_SCOPE = "change_scope"

    @property
    def issues_a_key(self) -> bool:
        """Whether approving this kind creates a key, which is then the one the receipt names."""
        return self in {EnrollmentKind.ENROLL, EnrollmentKind.ROTATE}


class EnrollmentProposal(BaseModel):
    """Private consent operand, submitted only through the ephemeral channel."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: EnrollmentKind
    scope: AccessScope
    expires_at: UtcInstant
    key_expires_at: UtcInstant | None
    unattended: bool
    allow_os_lock: bool
    target_grant_id: UUID | None = None
    target_key_id: UUID | None = None
    label: GrantLabel | None = None

    @model_validator(mode="after")
    def _targets(self) -> EnrollmentProposal:
        if self.label is not None and self.kind is not EnrollmentKind.ENROLL:
            raise ValueError("a key is named only when it is issued")
        if (self.kind is EnrollmentKind.ENROLL) != (self.target_grant_id is None):
            raise ValueError("grant target does not match enrollment kind")
        if (self.kind is EnrollmentKind.ROTATE) != (self.target_key_id is not None):
            raise ValueError("key target does not match enrollment kind")
        if self.kind.issues_a_key != (self.key_expires_at is not None):
            raise ValueError("key validity must match the reviewed key change")
        if (self.key_expires_at is not None and self.key_expires_at > self.expires_at) or (
            self.allow_os_lock and not self.unattended
        ):
            raise ValueError("invalid enrollment bounds")
        return self
