"""Masked status, typed refusals and action results for provider settings.

These are the values every frontend may show. None of them carries a secret or
a fingerprint of one: a status entry names the provider, its catalog facts, the
person's chosen mode, whether a credential is available and from where, and the
row revision an action must send back as its guard. The revision hashes the
record's ciphertext, so it changes on every write and cannot confirm a guessed
key.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from cadrumo.core.errors.hierarchy import pydantic_validation_boundary
from cadrumo.core.hex import is_hex64
from cadrumo.core.json_contract import OutputSchema
from cadrumo.core.models import STRICT_FROZEN_CONFIG

from ..domain.catalog import LaneId, ProviderAuthKind, ProviderConsumer, ProviderId, ProviderTransport
from ..domain.record import ModelId

ProviderSettingsRevision = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
"""A status revision: the stored row's opaque revision, or all zeros when no record exists."""


def is_provider_settings_revision(value: str) -> bool:
    """Return whether ``value`` is a well-formed revision token."""
    return is_hex64(value)


class ProviderSettingsMode(StrEnum):
    """The person's chosen mode for one provider."""

    KEY = "key"
    OAUTH = "oauth_token"
    PROVIDER_SIGN_IN = "provider_sign_in"
    DISABLED = "disabled"
    UNSET = "unset"


class ProviderCredentialSource(StrEnum):
    """Where the credential a consumer would use comes from."""

    PROFILE = "profile"
    NONE = "none"


class ProviderReadiness(StrEnum):
    """How ready the provider is for use.

    ``ready`` is reserved for a credential a consumer has used successfully;
    storing a key alone never produces it.
    """

    READY = "ready"
    NOT_VERIFIED = "not_verified"
    MISSING = "missing"
    DISABLED = "disabled"
    SIGN_IN_REQUIRED = "sign_in_required"
    UNUSABLE = "unusable"


class ProviderStatusReason(StrEnum):
    """Why a provider is not usable; ``None`` when it is usable."""

    NOT_CONFIGURED = "not_configured"
    TURNED_OFF = "turned_off"
    SIGN_IN_WITH_PROVIDER_TOOL = "sign_in_with_provider_tool"
    RECORD_UNREADABLE = "record_unreadable"


class CliState(StrEnum):
    """What Cadrumo knows about a cli lane's program on this machine.

    ``unknown`` is reported whenever Cadrumo has not established the state
    without reading a provider-owned credential file.
    """

    INSTALLED_SIGNED_IN = "installed_signed_in"
    INSTALLED_SIGNED_OUT = "installed_signed_out"
    NOT_INSTALLED = "not_installed"
    UNKNOWN = "unknown"


HelperCause = Literal[
    "profile_missing",
    "unsupported_method",
    "host_input_invalid",
    "host_disconnected",
    "login_already_running",
    "timed_out",
    "home_in_git_project",
    "home_unavailable",
    "cli_not_found",
    "browser_relay_unavailable",
    "cli_start_failed",
    "cli_exited_early",
    "cli_protocol_mismatch",
    "cli_reported_error",
    "login_not_completed",
    "cleanup_unconfirmed",
    "internal_error",
]
"""The helper's closed words for why a terminal event is not a success."""

ServiceCause = Literal[
    "helper_start_failed",
    "helper_output_invalid",
    "helper_ended_without_result",
    "helper_exit_nonzero",
    "agent_stop_failed",
    "status_not_confirmed",
]
"""The closed words the service adds when it, not the helper, settles an attempt."""


class CliStateCause(StrEnum):
    """Why a cli lane's state is not established or not signed in; one closed word, never provider output."""

    CLI_NOT_FOUND = "cli_not_found"
    HOME_IN_GIT_PROJECT = "home_in_git_project"
    HOME_UNAVAILABLE = "home_unavailable"
    PROBE_START_FAILED = "probe_start_failed"
    PROBE_TIMED_OUT = "probe_timed_out"
    PROBE_OUTPUT_UNREADABLE = "probe_output_unreadable"
    PROBE_CLEANUP_UNCONFIRMED = "probe_cleanup_unconfirmed"
    STATUS_READ_FAILED = "status_read_failed"
    """The service could not read the agent's status: a nonzero exit, a refused runner or an operating-system error."""
    STATUS_UNREADABLE = "status_unreadable"
    """The agent's status answer was not valid JSON of the declared schema."""
    STATUS_CONTEXT_UNAVAILABLE = "status_context_unavailable"
    """No live profile authority could back a status read."""


class NextStep(StrEnum):
    """What a person can do about a sign-in that did not complete; one closed word."""

    RETRY = "retry"
    INSTALL_CLI = "install_cli"
    MOVE_PROFILE_OUTSIDE_GIT = "move_profile_outside_git"
    CLOSE_OTHER_SIGN_IN = "close_other_sign_in"
    CONSOLE_SIGN_IN = "console_sign_in"
    UPDATE_APP = "update_app"


@dataclass(frozen=True, slots=True)
class CliObservation:
    """One cli lane's observed state with the cause when it is not signed in or not established."""

    state: CliState
    cause: CliStateCause | None = None


class ProviderStatusEntry(OutputSchema):
    """Masked status of one provider."""

    id: LaneId
    """The lane id every change addresses."""
    provider: ProviderId
    """The provider identity the lane reaches; frontends key icons by it."""
    transport: ProviderTransport
    display_name: str
    auth_kind: ProviderAuthKind
    consumers: tuple[ProviderConsumer, ...]
    mode: ProviderSettingsMode
    credential_saved: bool
    """Whether a direct credential is stored for the lane, whatever the mode; never the credential itself."""
    available: bool
    source: ProviderCredentialSource
    readiness: ProviderReadiness
    reason: ProviderStatusReason | None
    base_url: str | None
    """The person's stored base URL only; never the catalog default."""
    default_base_url: str | None
    cli_state: CliState | None
    """Whether a cli lane's program is installed and signed in; ``None`` for an api lane."""
    cli_state_cause: CliStateCause | None = None
    """Why a cli lane is not established or not signed in, when the probe says; never provider output."""
    next_step: NextStep | None = None
    """What the person can do about ``cli_state_cause``; ``None`` when no step is declared for it."""
    revision: ProviderSettingsRevision


class ProviderSettingsStatus(OutputSchema):
    """Masked status of every catalogued provider, in catalog order."""

    providers: tuple[ProviderStatusEntry, ...] = Field(min_length=1)


class ProviderSettingsRefusalCode(StrEnum):
    """Closed refusal codes for every provider-settings read and change."""

    NOT_SIGNED_IN = "not_signed_in"
    PROFILE_LOCKED = "profile_locked"
    INVALID_KEY_FORMAT = "invalid_key_format"
    BASE_URL_REJECTED = "base_url_rejected"
    REVISION_CONFLICT = "revision_conflict"
    COMMITTED_READBACK_FAILED = "committed_readback_failed"
    CATALOG_UNAVAILABLE = "catalog_unavailable"
    """cadrumo-agent could not report its providers, so there is nothing to read or change."""
    RUNTIME_UNAVAILABLE = "runtime_unavailable"
    """No runtime took the request, so nothing was read or changed; produced at the frontend, never by the service."""
    PERSON_ACT_REQUIRED = "person_act_required"
    """Produced at dispatch for a frontend that may not change credentials, never by the service."""
    MODEL_LIST_FULL = "model_list_full"
    """The local model list already holds as many added models as it keeps."""
    UNKNOWN = "unknown"


class ProviderSettingsRefusal(BaseModel):
    """A typed refusal carrying no secret and no storage detail."""

    model_config = STRICT_FROZEN_CONFIG

    code: ProviderSettingsRefusalCode


class ProviderSettingsActionAccepted(BaseModel):
    """A committed action, with the provider's status read back after commit."""

    model_config = STRICT_FROZEN_CONFIG

    entry: ProviderStatusEntry


type ProviderSettingsActionResult = ProviderSettingsActionAccepted | ProviderSettingsRefusal


class LocalModelListEntry(OutputSchema):
    """One lane and one of its models: a model added to a local lane's list, or the model read with."""

    lane: LaneId
    """The catalogue lane id the model is listed on."""
    model: ModelId


class LocalModelListStatus(OutputSchema):
    """The models the person added to local lanes' lists, in the order added, with the record's guard.

    A lane's recommended models are the catalogue's and are not listed here.
    ``reading`` is the lane and model the person selected to read documents
    with, or ``None`` when none is stored. ``local_lanes`` are the catalogue's
    local lane ids, whose models a picker offers from their lists; none when
    the catalogue cannot be read. ``unreadable`` means a stored list
    record cannot be read. Then no model is listed or selected, because
    nothing is known, and ``revision`` guards the reset that removes the
    record. Every state carries a revision, so an unreadable record always
    has a reset route.
    """

    unreadable: bool
    models: tuple[LocalModelListEntry, ...]
    reading: LocalModelListEntry | None
    local_lanes: tuple[LaneId, ...]
    revision: ProviderSettingsRevision

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _models_follow_readability(self) -> Self:
        if self.unreadable and (self.models or self.reading is not None):
            raise ValueError("an unreadable record lists and selects no model")
        return self


type LocalModelListResult = LocalModelListStatus | ProviderSettingsRefusal


__all__ = [
    "CliState",
    "LocalModelListEntry",
    "LocalModelListResult",
    "LocalModelListStatus",
    "ProviderCredentialSource",
    "ProviderReadiness",
    "ProviderSettingsActionAccepted",
    "ProviderSettingsActionResult",
    "ProviderSettingsMode",
    "ProviderSettingsRefusal",
    "ProviderSettingsRefusalCode",
    "ProviderSettingsRevision",
    "ProviderSettingsStatus",
    "ProviderStatusEntry",
    "ProviderStatusReason",
    "is_provider_settings_revision",
]
