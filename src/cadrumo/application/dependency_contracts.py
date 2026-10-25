"""The closed vocabulary every surface renders for a setup item.

Cadrumo depends on two outside pieces of software to work: the browser that
reads the tax agency's website, and the local AI -- the program that runs
models on this computer together with every model the catalogue roles read
with. Each is one setup item, set up once for the whole installation. The
native component engine decides each item's state, plans and performs its
setup and reports them as closed codes; the Python surfaces decode those codes
into the types here and word them.

Nothing here is presentation text. The wording owner maps each closed value to
one sentence and one action in the canonical locale catalogues, so a surface
that shows a category, an operation id or an internal term is wrong by
construction rather than by review.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final

from pydantic import BaseModel, NonNegativeInt, StringConstraints, model_validator

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ..core.errors.hierarchy import pydantic_validation_boundary
from ..core.identifier_grammar import NamespacedId
from ..core.models import STRICT_FROZEN_CONFIG

__all__ = [
    "DEPENDENCY_SETUP_RECOVERIES",
    "DependencyBlockedReason",
    "DependencyCheckMode",
    "DependencyHostName",
    "DependencyItemDeclaration",
    "DependencyItemId",
    "DependencyItemKind",
    "DependencyNote",
    "DependencyRecoveryAction",
    "DependencySetupStep",
    "DependencyStaleReason",
    "DependencyState",
    "DependencyStatusRow",
    "dependency_item_kind",
]


class DependencyItemKind(StrEnum):
    """The two setup items; each kind is exactly one item.

    ``local_ai`` is the local AI as a whole: the program that runs models and
    the model every catalogue role reads with. It is planned, set up, checked
    and shown as one item; its program and models are parts of its plan, never
    items of their own.
    """

    BROWSER = "browser"
    LOCAL_AI = "local_ai"


type DependencyItemId = Annotated[
    str,
    StringConstraints(pattern=r"^(?:browser|local_ai)$", min_length=7, max_length=64),
]
"""Stable setup item identity, which is its kind.

The identity doubles as the progress subject and as a segment of every setup
phase code, so its grammar is a subset of the operation event-code grammar.
"""


def dependency_item_kind(item_id: str) -> DependencyItemKind:
    """Return the kind an item identity names, refusing an identity outside the grammar."""
    return DependencyItemKind(item_id)


type DependencyHostName = Annotated[
    str,
    StringConstraints(
        max_length=253,
        pattern=r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$",
    ),
]
"""Lowercase fully qualified host a setup item downloads from or signs in through."""


class DependencyState(StrEnum):
    """The one state each setup item is in at a time.

    ``unknown`` means a probe could not read; it is never shown as absent or
    ready. Cadrumo is set up when every item is ``ready`` or ``stale``.
    """

    ABSENT = "absent"
    PROVISIONING = "provisioning"
    VERIFYING = "verifying"
    READY = "ready"
    STALE = "stale"
    FAILED = "failed"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class DependencyBlockedReason(StrEnum):
    """Why an item cannot be set up right now.

    ``needs_person`` covers an approval or an outside install;
    ``hardware`` is a computer below the model floor, which is reported as a
    limit of this computer rather than as a failure the person can fix.
    """

    OFFLINE = "offline"
    NEEDS_PERSON = "needs_person"
    HARDWARE = "hardware"
    NOT_IN_THIS_BUILD = "not_in_this_build"


class DependencyStaleReason(StrEnum):
    """How a usable item differs from what this version requires or was tested with."""

    OLDER_REVISION = "older_revision"
    DIFFERENT_MODEL_VERSION = "different_model_version"
    PROGRAM_TOO_OLD = "program_too_old"


class DependencyNote(StrEnum):
    """Secondary fact a ready item can carry without changing its state."""

    DOWNLOADED_NOT_LOADED = "downloaded_not_loaded"
    OWN_NETWORK_SETTINGS = "own_network_settings"


class DependencyRecoveryAction(StrEnum):
    """The single button a surface offers for an item's current state."""

    SET_UP = "set_up"
    UPDATE = "update"
    TRY_AGAIN = "try_again"
    RESUME = "resume"
    CHECK_AGAIN = "check_again"


DEPENDENCY_SETUP_RECOVERIES: Final = frozenset(
    {
        DependencyRecoveryAction.SET_UP,
        DependencyRecoveryAction.UPDATE,
        DependencyRecoveryAction.TRY_AGAIN,
        DependencyRecoveryAction.RESUME,
    }
)
"""The recovery buttons that run the setup operation for their row's item.

A surface offers an item's setup only while its row's button is one of these;
any other row, a blocked one included, says its sentence and offers no setup.
"""


class DependencyCheckMode(StrEnum):
    """Quick checks read local facts only; full checks also reach the network and exercise the item."""

    QUICK = "quick"
    FULL = "full"


class DependencySetupStep(StrEnum):
    """Ordered steps of one item's setup, published as ``dependencies.setup.<item>.<step>``."""

    PLAN = "plan"
    PREFLIGHT = "preflight"
    DOWNLOAD = "download"
    INSTALL = "install"
    VERIFY = "verify"
    CLEANUP = "cleanup"


class DependencyItemDeclaration(BaseModel):
    """How the surfaces name one setup item and which operator action sets it up.

    ``display_key`` and ``recovery_action_id`` are identities, not text: the
    first names the plain item name in the locale catalogues, the second the
    operator action a refusal for this item offers as its recovery.
    """

    model_config = STRICT_FROZEN_CONFIG

    item_id: DependencyItemId
    kind: DependencyItemKind
    display_key: NamespacedId
    recovery_action_id: NamespacedId

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_kind(self) -> DependencyItemDeclaration:
        if dependency_item_kind(self.item_id) is not self.kind:
            raise ValueError("setup item identity does not name its declared kind")
        return self


class DependencyStatusRow(BaseModel):
    """The derived, renderer-neutral status of one setup item.

    Every surface renders this row and nothing else: the state, exactly the
    reason that state requires, an optional note, and the one recovery button.
    """

    model_config = STRICT_FROZEN_CONFIG

    item_id: DependencyItemId
    kind: DependencyItemKind
    mode: DependencyCheckMode
    state: DependencyState
    stale_reason: DependencyStaleReason | None = None
    blocked_reason: DependencyBlockedReason | None = None
    failure_category: DependencyFailureCategory | None = None
    note: DependencyNote | None = None
    version: Annotated[str, StringConstraints(min_length=1, max_length=128)] | None = None
    size_estimate_bytes: NonNegativeInt | None = None
    recovery: DependencyRecoveryAction | None = None
    recovery_action_id: NamespacedId | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_state_reason(self) -> DependencyStatusRow:
        if dependency_item_kind(self.item_id) is not self.kind:
            raise ValueError("status row identity does not name its kind")
        _require_only(
            stale=self.state is DependencyState.STALE,
            blocked=self.state is DependencyState.BLOCKED,
            failed=self.state is DependencyState.FAILED,
            stale_reason=self.stale_reason,
            blocked_reason=self.blocked_reason,
            failure_category=self.failure_category,
        )
        if self.note is not None and self.state not in {DependencyState.READY, DependencyState.STALE}:
            raise ValueError("only a usable item carries a note")
        if (self.recovery is None) != (self.recovery_action_id is None):
            raise ValueError("a recovery button and its operator action are offered together")
        return self


def _require_only(
    *,
    stale: bool,
    blocked: bool,
    failed: bool,
    stale_reason: DependencyStaleReason | None,
    blocked_reason: DependencyBlockedReason | None,
    failure_category: DependencyFailureCategory | None,
) -> None:
    if stale != (stale_reason is not None):
        raise ValueError("a stale reason is carried exactly when the item differs from what is required")
    if blocked != (blocked_reason is not None):
        raise ValueError("a blocked reason is carried exactly when the item is blocked")
    if failed != (failure_category is not None):
        raise ValueError("a failure category is carried exactly when the item failed")
