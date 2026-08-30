"""The decrypted-envelope document shape read by the unsecured-profile guard.

What survives of a module that also modelled the deleted on-disk key store.
The parameter and version-gate records for that store's ``master.kdf`` sidecar
were deleted with it; nothing wrote or read either by then. The envelope
document below is unrelated to that store and is live: the unsecured-provider
tax-id refusal parses a decrypted profile envelope through it to prove the
active profile is synthetic before a published deterministic key is admitted.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .....core.models import STRICT_FROZEN_CONFIG


class _EnvelopeFact(BaseModel):
    """A single fact entry within an :class:`EnvelopeDocument` payload."""

    model_config = STRICT_FROZEN_CONFIG

    path: str
    value: object = None


class _EnvelopePayload(BaseModel):
    """The ``payload`` dict inside an :class:`EnvelopeDocument`."""

    model_config = STRICT_FROZEN_CONFIG

    facts: list[_EnvelopeFact] = Field(default_factory=list)


class EnvelopeDocument(BaseModel):
    """Typed representation of a decrypted user-profile envelope JSON document."""

    model_config = STRICT_FROZEN_CONFIG

    payload: _EnvelopePayload | None = None
