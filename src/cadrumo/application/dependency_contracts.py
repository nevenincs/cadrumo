"""Typed contracts shared by every setup item: states, readings, plans and the provisioner ports.

Cadrumo depends on two outside pieces of software to work: the browser that
reads the tax agency's website, and the local AI -- the program that runs
models on this computer together with every model the catalogue roles read
with. Each is one setup item, set up once for the whole installation. The
person's Google account is not software and is not a setup item: it belongs
to the profile and is signed into on its own. This module owns the closed
vocabulary every surface renders for an item -- its state, the reason it is
blocked, the category a failure falls into, the action that recovers it -- and
the shapes a setup plan and its approval digest take.

Nothing here is presentation text. The wording owner maps each closed value to
one sentence and one action in the canonical locale catalogues, so a surface
that shows a category, an operation id or an internal term is wrong by
construction rather than by review.

State is never stored. :func:`~cadrumo.application.dependency_registry.derive_dependency_row`
computes it from a probe reading, any running setup step and the last settled
setup failure. A receipt is evidence a probe may compare against, never a
reading on its own, so no receipt can make an item ready.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from contextlib import AbstractAsyncContextManager
from enum import StrEnum
from typing import Annotated, Final, Protocol, runtime_checkable

from pydantic import BaseModel, Field, NonNegativeInt, PositiveFloat, StringConstraints, model_validator

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ..core.errors.hierarchy import pydantic_validation_boundary
from ..core.hashing import content_hash_hex
from ..core.identifier_grammar import NamespacedId
from ..core.identity.digest import ContentDigest
from ..core.model_catalogue import ModelSelectionAdvisory
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.storage_taxonomy import StorageCategory
from .provisioning_contracts import ProvisioningFactValue

__all__ = [
    "DEPENDENCY_FULL_CHECK_ITEM_BUDGET_S",
    "DEPENDENCY_PLAN_CONTRACT_VERSION",
    "DEPENDENCY_PROGRESS_UNIT_CODE",
    "DEPENDENCY_QUICK_CHECK_BUDGET_S",
    "DEPENDENCY_SETUP_RECOVERIES",
    "DEPENDENCY_SPACE_HEADROOM_BYTES",
    "DependencyActivity",
    "DependencyBlockedReason",
    "DependencyCheckMode",
    "DependencyHostName",
    "DependencyItemChecker",
    "DependencyItemDeclaration",
    "DependencyItemFinisher",
    "DependencyItemId",
    "DependencyItemKind",
    "DependencyItemProvisioner",
    "DependencyNote",
    "DependencyPartId",
    "DependencyPlanEntry",
    "DependencyPlanPart",
    "DependencyProbeOutcome",
    "DependencyProbeReading",
    "DependencyProvisionResult",
    "DependencyRecoveryAction",
    "DependencySetupEvents",
    "DependencySetupPlan",
    "DependencySetupStep",
    "DependencySpaceCheck",
    "DependencyStaleReason",
    "DependencyState",
    "DependencyStatusRow",
    "combine_plan_parts",
    "dependency_item_kind",
    "dependency_phase_code",
    "dependency_plan_digest",
    "dependency_progress_subject",
    "dependency_retry_notice_code",
    "known_download_bytes_of",
    "known_part_bytes_of",
    "parse_dependency_retry_notice",
    "required_free_bytes",
    "shared_download_key",
]

DEPENDENCY_QUICK_CHECK_BUDGET_S: Final = 2.0
"""Wall-clock bound for one quick check of every item together.

The quick check answers startup, the status indicator and every surface's
status row, so it moves no network traffic and loads no model; an item whose
probe has not answered inside the bound reads as unknown rather than holding
every other row back.
"""

DEPENDENCY_FULL_CHECK_ITEM_BUDGET_S: Final = 60.0
"""Wall-clock bound for one item's full check, which may launch, refresh or generate."""

DEPENDENCY_SPACE_HEADROOM_BYTES: Final = 1024**3
"""Fixed free space kept beyond the planned download, on top of the 20 % margin."""

DEPENDENCY_PLAN_CONTRACT_VERSION: Final = 1
"""Version folded into every plan digest so a plan-shape change can never reuse an approval."""

DEPENDENCY_PROGRESS_UNIT_CODE: Final = "bytes"
"""Progress unit for setup transfers; a transfer of unknown size publishes its step only."""


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


def dependency_phase_code(item_id: str, step: DependencySetupStep) -> str:
    """Return the operation phase code for one item's setup step."""
    dependency_item_kind(item_id)
    return f"dependencies.setup.{item_id}.{step.value}"


def dependency_progress_subject(item_id: str) -> str:
    """Return the progress ``subject_code`` naming the item a byte figure belongs to."""
    dependency_item_kind(item_id)
    return item_id


def required_free_bytes(download_bytes: int) -> int:
    """Return the free space a download needs: its size plus 20 %, plus a fixed 1 GiB."""
    if download_bytes < 0:
        raise ValueError("a download size cannot be negative")
    return -(-download_bytes * 6 // 5) + DEPENDENCY_SPACE_HEADROOM_BYTES


class DependencyItemDeclaration(BaseModel):
    """What the registry knows about one setup item before anything is probed.

    ``display_key`` and ``recovery_action_id`` are identities, not text: the
    first names the plain item name in the locale catalogues, the second the
    operator action a refusal for this item offers as its recovery.
    ``network_host_group`` names the item's host list among the declared
    external constants. ``full_check_budget_s`` bounds the item's full check:
    an item made of several parts checks every part, so its bound covers them
    all.
    """

    model_config = STRICT_FROZEN_CONFIG

    item_id: DependencyItemId
    kind: DependencyItemKind
    display_key: NamespacedId
    network_host_group: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$", max_length=64)]
    storage_category: StorageCategory
    size_estimate_bytes: NonNegativeInt | None = None
    recovery_action_id: NamespacedId
    installs_outside_program: bool = False
    full_check_budget_s: PositiveFloat = DEPENDENCY_FULL_CHECK_ITEM_BUDGET_S

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_kind(self) -> DependencyItemDeclaration:
        if dependency_item_kind(self.item_id) is not self.kind:
            raise ValueError("setup item identity does not name its declared kind")
        return self


class DependencyProbeOutcome(StrEnum):
    """What one probe observed, before state derivation applies running work and past failures.

    ``present`` and ``differs`` must rest on something the probe observed on
    this computer (an executable, an inventory entry, a token row); a receipt
    or a marker on its own is not presence.
    """

    PRESENT = "present"
    DIFFERS = "differs"
    ABSENT = "absent"
    UNREADABLE = "unreadable"
    BLOCKED = "blocked"
    FAILED = "failed"


class DependencyProbeReading(BaseModel):
    """One item's probe answer, with exactly the reason its outcome requires."""

    model_config = STRICT_FROZEN_CONFIG

    item_id: DependencyItemId
    mode: DependencyCheckMode
    outcome: DependencyProbeOutcome
    stale_reason: DependencyStaleReason | None = None
    blocked_reason: DependencyBlockedReason | None = None
    failure_category: DependencyFailureCategory | None = None
    note: DependencyNote | None = None
    version: Annotated[str, StringConstraints(min_length=1, max_length=128)] | None = None
    facts: Mapping[str, ProvisioningFactValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_reason_matches_outcome(self) -> DependencyProbeReading:
        _require_only(
            stale=self.outcome is DependencyProbeOutcome.DIFFERS,
            blocked=self.outcome is DependencyProbeOutcome.BLOCKED,
            failed=self.outcome is DependencyProbeOutcome.FAILED,
            stale_reason=self.stale_reason,
            blocked_reason=self.blocked_reason,
            failure_category=self.failure_category,
        )
        if self.note is not None and self.outcome not in {
            DependencyProbeOutcome.PRESENT,
            DependencyProbeOutcome.DIFFERS,
        }:
            raise ValueError("only a usable item carries a note")
        return self


class DependencyActivity(BaseModel):
    """The step a running setup operation has reached for one item."""

    model_config = STRICT_FROZEN_CONFIG

    item_id: DependencyItemId
    step: DependencySetupStep


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


type DependencyPartId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$", min_length=1, max_length=64)]
"""One part of an item's plan: ``program`` for the local AI program, or the catalogue role a model serves."""

type _TargetVersion = Annotated[str, StringConstraints(min_length=1, max_length=128)]


class DependencyPlanPart(BaseModel):
    """One piece of an item's plan: the local AI program, or the model one catalogue role reads with.

    ``target_version`` names a model and its pinned digest. Parts with the same
    destination and target fetch the same bytes -- several roles resolved to
    one model -- so the item counts that download once and the later part
    moves no byte. ``download_bytes`` is ``None`` when the source does not say
    in advance.
    """

    model_config = STRICT_FROZEN_CONFIG

    part_id: DependencyPartId
    download_bytes: NonNegativeInt | None
    source_hosts: tuple[DependencyHostName, ...] = Field(min_length=1)
    destination: StorageCategory | None
    installs_outside_program: bool = False
    target_version: _TargetVersion | None = None
    advisories: tuple[ModelSelectionAdvisory, ...] = ()

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_part(self) -> DependencyPlanPart:
        if len(set(self.source_hosts)) != len(self.source_hosts):
            raise ValueError("a plan part names each source host once")
        if self.destination is None and not self.installs_outside_program:
            raise ValueError("a plan part names where it stores what it downloads")
        return self


def _part_download_key(part: DependencyPlanPart) -> tuple[str, str] | None:
    if part.target_version is None or part.destination is None:
        return None
    return part.destination.value, part.target_version


def known_part_bytes_of(parts: Iterable[DependencyPlanPart]) -> int:
    """Sum the known sizes of ``parts``, counting each shared download once."""
    seen: set[tuple[str, str]] = set()
    total = 0
    for part in parts:
        if part.download_bytes is None:
            continue
        key = _part_download_key(part)
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
        total += part.download_bytes
    return total


class DependencyPlanEntry(BaseModel):
    """What setting up one item will do: how much, from where, to where, and whether a program is installed.

    ``download_bytes`` is ``None`` when the source does not say in advance; the
    plan then shows the size as unknown and its free-space check covers only
    the known part. ``advisories`` are the licence notices a person must see
    before a model is downloaded; they are part of what an approval binds.

    The local AI's entry lists its ``parts`` -- the program, then the model of
    each role that needs one -- and is their sum: its ``download_bytes`` is the
    known size of its parts, and its hosts, licence notices and program
    install are theirs. A part of unknown size leaves the plan's size partly
    unknown. An approval binds every part, so a changed part needs a new one.
    """

    model_config = STRICT_FROZEN_CONFIG

    item_id: DependencyItemId
    download_bytes: NonNegativeInt | None
    source_hosts: tuple[DependencyHostName, ...] = Field(min_length=1)
    destination: StorageCategory | None
    installs_outside_program: bool = False
    target_version: _TargetVersion | None = None
    advisories: tuple[ModelSelectionAdvisory, ...] = ()
    parts: tuple[DependencyPlanPart, ...] = ()

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_entry(self) -> DependencyPlanEntry:
        kind = dependency_item_kind(self.item_id)
        if len(set(self.source_hosts)) != len(self.source_hosts):
            raise ValueError("a plan entry names each source host once")
        if self.destination is None and not self.installs_outside_program:
            raise ValueError("a plan entry names where it stores what it downloads")
        if self.advisories and kind is not DependencyItemKind.LOCAL_AI:
            raise ValueError("only the local AI carries a licence notice")
        if self.parts and kind is not DependencyItemKind.LOCAL_AI:
            raise ValueError("only the local AI is planned in parts")
        if self.parts:
            _require_parts_summed(self)
        return self

    @property
    def has_unknown_size(self) -> bool:
        """Whether the entry, or any of its parts, downloads an amount its source does not state."""
        return self.download_bytes is None or any(part.download_bytes is None for part in self.parts)


def _require_parts_summed(entry: DependencyPlanEntry) -> None:
    parts = entry.parts
    if len({part.part_id for part in parts}) != len(parts):
        raise ValueError("an item's plan names each part once")
    if entry.target_version is not None:
        raise ValueError("an item planned in parts names its versions in its parts")
    if entry.download_bytes != known_part_bytes_of(parts):
        raise ValueError("an item's planned size is the known size of its parts")
    if entry.installs_outside_program != any(part.installs_outside_program for part in parts):
        raise ValueError("an item installs a program exactly when one of its parts does")
    if entry.source_hosts != tuple(dict.fromkeys(host for part in parts for host in part.source_hosts)):
        raise ValueError("an item's hosts are its parts' hosts")
    if entry.advisories != tuple(sorted({advisory for part in parts for advisory in part.advisories})):
        raise ValueError("an item's licence notices are its parts'")


def combine_plan_parts(
    item_id: str, parts: tuple[DependencyPlanPart, ...], *, destination: StorageCategory | None
) -> DependencyPlanEntry:
    """Return the one plan entry of an item made of ``parts``, summing what they do."""
    return DependencyPlanEntry(
        item_id=item_id,
        download_bytes=known_part_bytes_of(parts),
        source_hosts=tuple(dict.fromkeys(host for part in parts for host in part.source_hosts)),
        destination=destination,
        installs_outside_program=any(part.installs_outside_program for part in parts),
        advisories=tuple(sorted({advisory for part in parts for advisory in part.advisories})),
        parts=parts,
    )


class DependencySpaceCheck(BaseModel):
    """Free space measured on the storage volume against what the plan needs.

    ``free_bytes`` is ``None`` when the volume could not be measured, which is
    never read as enough.
    """

    model_config = STRICT_FROZEN_CONFIG

    free_bytes: NonNegativeInt | None
    required_bytes: NonNegativeInt

    @property
    def sufficient(self) -> bool:
        """Whether the measured free space covers the plan."""
        return self.free_bytes is not None and self.free_bytes >= self.required_bytes


class DependencySetupPlan(BaseModel):
    """The ordered plan a person approves before any byte moves.

    The approval binds :func:`dependency_plan_digest`, which covers the entries
    and not the free-space measurement: free space changes by the second, and
    an approval is for what will be downloaded and where, not for a volume
    reading. The space check is re-run before the transfer starts.
    """

    model_config = STRICT_FROZEN_CONFIG

    entries: tuple[DependencyPlanEntry, ...] = Field(min_length=1)
    space: DependencySpaceCheck

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_plan(self) -> DependencySetupPlan:
        identities = [entry.item_id for entry in self.entries]
        if len(set(identities)) != len(identities):
            raise ValueError("a setup plan names each item once")
        if self.space.required_bytes != required_free_bytes(self.known_download_bytes):
            raise ValueError("the plan's space requirement does not follow from its download size")
        return self

    @property
    def known_download_bytes(self) -> int:
        """Bytes the known-size entries download, counting each shared download once."""
        return known_download_bytes_of(self.entries)

    @property
    def has_unknown_size(self) -> bool:
        """Whether any entry's or part's size is unknown until its transfer starts."""
        return any(entry.has_unknown_size for entry in self.entries)

    @property
    def installs_outside_program(self) -> bool:
        """Whether approving the plan installs a program outside Cadrumo's storage."""
        return any(entry.installs_outside_program for entry in self.entries)


def shared_download_key(entry: DependencyPlanEntry) -> tuple[str, str] | None:
    """Return what makes two entries one download, or ``None`` when the entry is its own.

    Entries with the same destination and the same target version fetch the
    same bytes, so the plan counts that download once. An entry without a target version is never
    merged, because nothing proves it shares bytes with another.
    """
    if entry.target_version is None or entry.destination is None:
        return None
    return entry.destination.value, entry.target_version


def known_download_bytes_of(entries: Iterable[DependencyPlanEntry]) -> int:
    """Sum the known sizes of ``entries``, counting each shared download once."""
    seen: set[tuple[str, str]] = set()
    total = 0
    for entry in entries:
        if entry.download_bytes is None:
            continue
        key = shared_download_key(entry)
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
        total += entry.download_bytes
    return total


def dependency_retry_notice_code(item_id: str, *, attempt: int, delay_s: float) -> str:
    """Return the NOTICE code announcing retry ``attempt`` of one item after ``delay_s`` seconds.

    The attempt number and the whole seconds of the wait are the code's last
    two segments, so every surface can render "trying again in N seconds,
    attempt M" from the code alone.
    """
    dependency_item_kind(item_id)
    if attempt < 2:
        raise ValueError("a retry is the second attempt or later")
    return f"dependencies.setup.{item_id}.retry.{attempt}.{max(1, math.ceil(delay_s))}"


def parse_dependency_retry_notice(code: str) -> tuple[str, int, int] | None:
    """Return ``(item_id, attempt, delay_seconds)`` from a retry NOTICE code, or ``None`` for any other code."""
    prefix = "dependencies.setup."
    if not code.startswith(prefix):
        return None
    head, separator, tail = code.removeprefix(prefix).rpartition(".retry.")
    if not separator:
        return None
    attempt, dot, delay = tail.partition(".")
    if not dot or not attempt.isdigit() or not delay.isdigit():
        return None
    try:
        dependency_item_kind(head)
    except ValueError:
        return None
    return head, int(attempt), int(delay)


def dependency_plan_digest(plan: DependencySetupPlan) -> ContentDigest:
    """Return the digest an approval of ``plan`` binds.

    The digest covers the contract version and every entry in order, so a
    changed size, host, destination, version or item set needs a new approval,
    while a re-measured free space does not.
    """
    return content_hash_hex(
        {
            "contract_version": DEPENDENCY_PLAN_CONTRACT_VERSION,
            "entries": [entry.model_dump(mode="json") for entry in plan.entries],
        }
    )


class DependencyProvisionResult(BaseModel):
    """What one item's provisioner did, before the independent full check decides readiness.

    ``changed`` records whether anything was written, so a failure after
    partial writes is reported as a partial effect rather than as no effect.
    A provisioner never claims readiness: the setup operation always runs the
    item's full check afterwards.
    """

    model_config = STRICT_FROZEN_CONFIG

    item_id: DependencyItemId
    changed: bool
    failure_category: DependencyFailureCategory | None = None
    transferred_bytes: NonNegativeInt = 0
    facts: Mapping[str, ProvisioningFactValue] = Field(default_factory=dict)


@runtime_checkable
class DependencySetupEvents(Protocol):
    """Per-item event port the setup operation hands to a provisioner.

    The operation binds the item identity, the phase codes, progress
    throttling and the journal; a provisioner reports only what it is doing.
    """

    async def step(self, step: DependencySetupStep) -> None:
        """Report that the item entered ``step``."""
        ...

    async def transferred(self, *, completed: int, total: int | None) -> None:
        """Report bytes moved so far; ``total`` is ``None`` while the size is unknown."""
        ...

    async def retrying(self, *, attempt: int, delay_s: float) -> None:
        """Report that a transient failure will be retried as ``attempt`` after ``delay_s`` seconds."""
        ...

    @property
    def cancellation_requested(self) -> bool:
        """Whether the person asked to cancel; checked between transfer chunks."""
        ...

    def irreversible(self) -> AbstractAsyncContextManager[None]:
        """Enter the short section that replaces a verified older install, where cancel is refused."""
        ...


@runtime_checkable
class DependencyItemChecker(Protocol):
    """Read-only port every setup item implements: its declaration and its quick and full checks.

    A check never downloads or installs. A quick check reads local facts only;
    a full check may reach the network and exercise the item. A check that
    cannot read returns ``unreadable`` instead of raising.
    """

    @property
    def declaration(self) -> DependencyItemDeclaration:
        """The registry declaration this checker answers for."""
        ...

    async def check(self, mode: DependencyCheckMode) -> DependencyProbeReading:
        """Return the item's probe reading in ``mode``."""
        ...


@runtime_checkable
class DependencyItemFinisher(Protocol):
    """Optional port: work an item does only once the setup's own full check found it usable.

    Writing the receipt and removing superseded installs belong here, never at
    the end of :meth:`DependencyItemProvisioner.provision`: until the
    independent check passes, nothing proves the new install is the one to
    keep. The setup runs it inside the irreversible section, so a cancel
    cannot stop it halfway, and skips it when the person already cancelled.
    """

    async def after_verified(self, entry: DependencyPlanEntry) -> None:
        """Finish ``entry`` after it verified."""
        ...


@runtime_checkable
class DependencyItemProvisioner(DependencyItemChecker, Protocol):
    """Port an item set up by the registered setup operation implements on top of its checks."""

    async def plan(self, *, model_name: str | None) -> DependencyPlanEntry:
        """Return what setting the item up would do, without moving any byte."""
        ...

    async def provision(self, entry: DependencyPlanEntry, events: DependencySetupEvents) -> DependencyProvisionResult:
        """Carry out exactly ``entry``, which the person approved, reporting through ``events``."""
        ...
