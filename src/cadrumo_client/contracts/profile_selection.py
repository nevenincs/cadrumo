"""Which profile a frontend means: the runtime's answers to questions asked before any profile session.

Both requests are answered on a verified connection that holds no session.
They open no worker, read no keychain and grant nothing: a frontend still signs
in by presenting a proof, attending a held sign-in or configuring a key. The
runtime reads the selection and the profiles it serves, so no frontend reads
the selection itself.
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, StringConstraints, model_validator

from cadrumo.core.identity.profile_label import ProfileLabel
from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG

from .sign_in import SignInPresence

type ProfileTargetText = Annotated[str, StringConstraints(min_length=1, max_length=512)]
"""What the operator typed to name a profile: its identifier or its exact label."""


class ActiveProfileRequest(BaseModel):
    """Ask which profile is selected and which holds the live sign-in.

    ``watch`` also asks for a ``sign_in_changed`` cue on this connection
    whenever a sign-in or the selection may have changed, until the connection
    closes. A cue is only a reason to ask again.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["active_profile"] = "active_profile"
    request_id: UUID
    watch: bool = False


class ActiveProfileReply(BaseModel):
    """The selected profile and the live sign-in, as the runtime observed them now.

    ``presence`` is the sign-in's presence for the selected profile:
    ``present`` names it in ``signed_in_profile_id``, ``absent`` means no
    profile is signed in, and ``unknown`` means the runtime could not tell,
    which never reads as signed out. With no selected profile nothing is
    signed in.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["active_profile"] = "active_profile"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    selected_profile_id: UUID | None
    signed_in_profile_id: UUID | None
    presence: SignInPresence

    @model_validator(mode="after")
    def _sign_in_follows_presence(self) -> ActiveProfileReply:
        if (self.presence is SignInPresence.PRESENT) != (self.signed_in_profile_id is not None):
            raise ValueError("a signed-in profile is named exactly when a sign-in is present")
        if self.signed_in_profile_id is not None and self.signed_in_profile_id != self.selected_profile_id:
            raise ValueError("the signed-in profile is the selected one")
        return self


class LoginTargetRequest(BaseModel):
    """Ask which profile the operator's text names, before signing in to it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["login_target"] = "login_target"
    request_id: UUID
    name: ProfileTargetText


class LoginTargetReply(BaseModel):
    """The profile the text names by identifier or exact label, or none when it names no live profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["login_target"] = "login_target"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    profile_id: UUID | None
    label: ProfileLabel | None

    @model_validator(mode="after")
    def _label_follows_profile(self) -> LoginTargetReply:
        if (self.profile_id is None) != (self.label is None):
            raise ValueError("a resolved profile carries its label, and only a resolved one")
        return self
