"""Sandbox workspace lifecycle: create, activate, and discard an isolated bucket.

A sandbox is an ordinary profile bucket distinguished only by a reserved
operator-visible label prefix (:data:`SANDBOX_LABEL_PREFIX`). It rides the
exact same encrypted per-bucket storage substrate every profile uses
(:class:`~aeat.adapters.persistence.storage.SecureObjectRepository` via the
bucket-scoped runtime wrapper): there is no plaintext scratch directory and no
parallel storage backend. Isolation is the pre-existing per-bucket engine
guarantee (see
:mod:`~aeat.application.workflow.tests.test_per_bucket_engine_isolation`);
this module adds nothing to that guarantee, it only composes the existing
single-writer primitives behind an experiment-lifecycle vocabulary.

The service delegates every write to an existing primitive
(``composition-service-no-parallel-write-path``):

- :func:`~aeat.application.user_profile.register_active_profile` (via the
  ``config profile create`` / ``duplicate`` atomic-create span) provisions
  the sandbox bucket, optionally seeded from a source profile's live facts —
  exactly the same fork ``config profile duplicate`` already performs. The
  source bucket is opened read-only (a lifecycle-service ``read``) and is
  never written to, so seeding cannot mutate main state.
- :func:`~aeat.application.user_profile.select_profile_with_lifecycle_span`
  activates a named sandbox as the current session (``config switch``'s
  primitive).
- :class:`~aeat.application.bucket_maintenance.BucketMaintenanceService`.delete
  composes the existing soft-tombstone-then-hard-erase primitives to discard
  the sandbox bucket entirely.
- :class:`~aeat.application.bucket_maintenance.BucketMaintenanceService`.browse
  (via a read-only lifecycle session, not the active bucket) backs
  :func:`preview_discard_sandbox`, so an operator can see what a discard would
  remove before confirming it.

:func:`list_sandboxes` is the read-only enumeration shared by ``sandbox list``
and ``sandbox prune`` — the composition-verb pattern this module follows: a
bulk verb composes the same single-bucket primitives per row rather than
re-implementing bucket erasure.

The destructive-action protocol mirrors
:class:`~aeat.application.bucket_maintenance.DeleteBucketCommand`: a discard
requires ``confirmed=True``, refuses the active bucket (the operator switches
away first — the existing ``BucketMaintenanceService.delete`` contract), and
additionally refuses to discard any bucket whose label is not sandbox-tagged
unless the caller explicitly acknowledges bypassing that guard — so an
operator (or an LLM agent driving the CLI) cannot accidentally erase a real
profile through the sandbox verb.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG
from ...core.identity import BucketId
from ..workflow import read_profile_bucket_by_id
from ._contracts import DeleteBucketCommand
from ._service import BucketMaintenanceService

SANDBOX_LABEL_PREFIX = "sandbox:"
"""Reserved operator-visible label prefix identifying a sandbox bucket.

A profile whose label starts with this prefix is a sandbox: created through
:func:`create_sandbox`, safe to discard without the non-sandbox confirmation
escalation. :func:`create_sandbox` is the only path this module exposes for
minting one, and :func:`discard_sandbox` (via :func:`is_sandbox_label`)
decides whether a bucket may be discarded without the extra confirmation.
"""


def is_sandbox_label(label: str) -> bool:
    """Return whether ``label`` carries the reserved sandbox prefix."""
    return label.startswith(SANDBOX_LABEL_PREFIX)


def sandbox_label(name: str) -> str:
    """Return the reserved sandbox label for operator-chosen ``name``."""
    return f"{SANDBOX_LABEL_PREFIX}{name}"


class SandboxAlreadyExistsError(Exception):
    """Raised when ``create_sandbox`` targets a name that already has a manifest."""

    def __init__(self, label: str) -> None:
        super().__init__(f"a sandbox labelled {label!r} already exists")
        self.label = label


class SandboxSourceNotFoundError(Exception):
    """Raised when ``create_sandbox``'s seed source names an unknown or non-live profile."""

    def __init__(self, name: str) -> None:
        super().__init__(f"no live profile named {name!r} to seed the sandbox from")
        self.name = name


class SandboxNotFoundError(Exception):
    """Raised when a sandbox lookup targets an unknown bucket."""

    def __init__(self, bucket_id: str) -> None:
        super().__init__(f"no bucket registered with id {bucket_id!r}")
        self.bucket_id = bucket_id


class SandboxDiscardRefusedError(Exception):
    """Raised when discarding a bucket is refused by the sandbox destructive-action gate."""


class PreviewDiscardSandboxCommand(BaseModel):
    """Operator request to preview what a sandbox discard would remove.

    Read-only counterpart to :class:`DiscardSandboxCommand`: it never opens
    the target bucket for write and never calls
    :meth:`~aeat.application.bucket_maintenance.BucketMaintenanceService`.delete.
    ``allow_non_sandbox`` mirrors the discard command's escape hatch so a
    preview against a non-sandbox bucket reports the same "not a sandbox"
    refusal a real discard would, rather than silently previewing an erase
    the real verb would never allow.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    allow_non_sandbox: bool = False


class PreviewDiscardSandboxResult(BaseModel):
    """Read-only preview of what discarding a sandbox would remove.

    ``namespaces`` is the same per-namespace row-count inventory
    :meth:`~aeat.application.bucket_maintenance.BucketMaintenanceService`.browse
    returns for the active bucket, computed here for a bucket that need not
    be active. ``is_active`` flags whether the target is the current session
    — a real discard of it would be refused until the operator switches away.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    label: str
    is_active: bool
    namespaces: tuple[SandboxNamespaceInventoryRow, ...]


class SandboxNamespaceInventoryRow(BaseModel):
    """One namespace row in a sandbox discard preview."""

    model_config = STRICT_FROZEN_CONFIG

    namespace: str = Field(min_length=1)
    row_count: int = Field(ge=0)


class CreateSandboxCommand(BaseModel):
    """Operator request to fork an isolated, discardable sandbox bucket.

    ``name`` is the operator-chosen sandbox name (rendered as
    ``sandbox:<name>``); ``from_profile`` optionally names a live profile
    whose facts seed the sandbox (an experiment that needs realistic profile
    data without touching the source). A sandbox is a real profile bucket
    underneath, so it is bound by the same profile-schema required-field
    validation ``config profile create`` enforces: creating one with no
    ``from_profile`` and no facts fails that validation exactly as an
    empty ``config profile create`` would. Seed from an existing profile
    to get a realistic, immediately-usable sandbox.
    """

    model_config = STRICT_FROZEN_CONFIG

    name: str = Field(min_length=1, max_length=120)
    from_profile: str | None = Field(default=None, min_length=1, max_length=160)


class CreateSandboxResult(BaseModel):
    """Outcome of a successful sandbox creation. The sandbox becomes the active bucket."""

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    label: str
    seeded_from: str | None = None


class DiscardSandboxCommand(BaseModel):
    """Operator request to permanently erase a sandbox bucket.

    ``confirmed=True`` is required, mirroring
    :class:`~aeat.application.bucket_maintenance.DeleteBucketCommand`.
    ``allow_non_sandbox`` must be explicitly set to erase a bucket whose
    label does NOT carry the reserved sandbox prefix — the default refuses,
    so a mistaken discard of a real profile is not silently possible.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    confirmed: bool = False
    allow_non_sandbox: bool = False


class DiscardSandboxResult(BaseModel):
    """Outcome of a successful sandbox discard."""

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    previous_label: str
    occurred_at: datetime


def create_sandbox(command: CreateSandboxCommand) -> CreateSandboxResult:
    """Fork a fresh, isolated sandbox bucket and make it the active profile.

    Composes the canonical atomic-create span
    (:func:`~aeat.application.user_profile.profile_create_storage_span` +
    :func:`~aeat.application.user_profile.register_active_profile`) — the
    exact primitive ``config profile create`` and ``config profile
    duplicate`` already use — so the sandbox bucket, its manifest, its
    encrypted record, and the active-profile pointer land in one
    all-or-nothing unit of work. When ``command.from_profile`` is supplied,
    the source profile's live facts are read through a read-only lifecycle
    session (the source bucket is never opened for write), so seeding cannot
    mutate main state.

    Returns:
        :class:`CreateSandboxResult` describing the new sandbox bucket, which
        is now the active profile.
    """
    from ...domain.user_profile import ProfileNotFoundError, UserProfileFact, UserProfileStatus, new_profile_id
    from ..user_profile import (
        ProfileAlreadyRegisteredError,
        build_lifecycle_service,
        profile_create_storage_span,
        profile_storage_session,
        register_active_profile,
    )
    from ..workflow import ProfileLabelAmbiguousError, read_profile_bucket, workflow_state_repository

    label = sandbox_label(command.name)
    if read_profile_bucket(label) is not None:
        raise SandboxAlreadyExistsError(label)

    facts: tuple[UserProfileFact, ...] = ()
    if command.from_profile is not None:
        try:
            source_pointer = read_profile_bucket(command.from_profile)
        except ProfileLabelAmbiguousError as exc:
            raise SandboxSourceNotFoundError(command.from_profile) from exc
        if source_pointer is None:
            raise SandboxSourceNotFoundError(command.from_profile)
        try:
            with profile_storage_session(source_pointer.bucket_id):
                source_record = build_lifecycle_service(bucket_id=source_pointer.bucket_id).read(
                    source_pointer.bucket_id,
                )
        except ProfileNotFoundError as exc:
            raise SandboxSourceNotFoundError(command.from_profile) from exc
        if source_record.status is not UserProfileStatus.ACTIVE:
            raise SandboxSourceNotFoundError(command.from_profile)
        facts = source_record.facts

    profile_id = new_profile_id()
    try:
        with profile_create_storage_span(profile_id) as routing_profile_id:
            workflow_state_repository().update(
                lambda current: register_active_profile(
                    current,
                    profile_id=profile_id,
                    display_name=label,
                    facts=facts,
                    # A sandbox seeded from a real profile legitimately
                    # reproduces that profile's tax id; the duplicate-tax-id
                    # refusal applies to a fresh, unseeded creation only.
                    enforce_unique_tax_id=command.from_profile is None,
                    routing_profile_id=routing_profile_id,
                ),
            )
    except ProfileAlreadyRegisteredError as exc:
        raise SandboxAlreadyExistsError(label) from exc

    return CreateSandboxResult(bucket_id=profile_id, label=label, seeded_from=command.from_profile)


def preview_discard_sandbox(command: PreviewDiscardSandboxCommand) -> PreviewDiscardSandboxResult:
    """Report what discarding ``command.bucket_id`` would remove, without removing it.

    Reads the target bucket's namespace inventory through a read-only
    lifecycle session (:func:`~aeat.application.user_profile.profile_storage_session`)
    — the identical read-only pattern :func:`create_sandbox` already uses to
    seed from a non-active source profile — so a sandbox need not be the
    active bucket to be previewed. No write primitive is invoked; the target
    bucket, its manifest, and its records are untouched.

    Applies the same non-sandbox refusal :func:`discard_sandbox` applies, so
    a preview can never suggest an erase the real verb would refuse.

    Returns:
        :class:`PreviewDiscardSandboxResult` describing the bucket's current
        contents.
    """
    from ...core import resolve_active_bucket_id
    from ..user_profile import profile_storage_session
    from ._contracts import BrowseBucketCommand
    from ._service import BucketMaintenanceService

    pointer = read_profile_bucket_by_id(command.bucket_id)
    if pointer is None:
        raise SandboxNotFoundError(command.bucket_id)
    if not is_sandbox_label(pointer.label) and not command.allow_non_sandbox:
        raise SandboxDiscardRefusedError(
            f"bucket {command.bucket_id!r} (label {pointer.label!r}) is not a sandbox; "
            "pass allow_non_sandbox=True to preview a non-sandbox profile",
        )

    with profile_storage_session(command.bucket_id):
        browsed = BucketMaintenanceService().browse(BrowseBucketCommand(bucket_id=command.bucket_id))

    return PreviewDiscardSandboxResult(
        bucket_id=command.bucket_id,
        label=pointer.label,
        is_active=resolve_active_bucket_id() == command.bucket_id,
        namespaces=tuple(
            SandboxNamespaceInventoryRow(namespace=row.namespace, row_count=row.row_count) for row in browsed.rows
        ),
    )


def list_sandboxes() -> tuple[tuple[BucketId, str], ...]:
    """Return every ``(bucket_id, label)`` pair currently carrying the sandbox prefix.

    Read-only enumeration shared by ``sandbox list`` and ``sandbox prune``.
    """
    from ..workflow import list_profile_buckets

    return tuple(
        sorted(
            (
                (pointer.bucket_id, pointer.label)
                for pointer in list_profile_buckets().values()
                if is_sandbox_label(pointer.label)
            ),
            key=lambda row: row[1].casefold(),
        ),
    )


def discard_sandbox(command: DiscardSandboxCommand) -> DiscardSandboxResult:
    """Permanently erase the sandbox bucket identified by ``command.bucket_id``.

    Composes :class:`~aeat.application.bucket_maintenance.BucketMaintenanceService`.delete
    — the same soft-tombstone-then-hard-directory-removal primitive
    ``config profile delete`` / ``config profile archive`` use — after
    confirming the target either carries the reserved sandbox label or the
    caller explicitly set ``allow_non_sandbox=True``. Refuses (via the
    composed service) to discard the currently active bucket; the operator
    must switch away first.

    Returns:
        :class:`DiscardSandboxResult` describing the erased sandbox.
    """
    pointer = read_profile_bucket_by_id(command.bucket_id)
    if pointer is None:
        raise SandboxNotFoundError(command.bucket_id)
    if not is_sandbox_label(pointer.label) and not command.allow_non_sandbox:
        raise SandboxDiscardRefusedError(
            f"bucket {command.bucket_id!r} (label {pointer.label!r}) is not a sandbox; "
            "pass allow_non_sandbox=True to discard a non-sandbox profile",
        )
    outcome = BucketMaintenanceService().delete(
        DeleteBucketCommand(bucket_id=command.bucket_id, confirmed=command.confirmed),
    )
    return DiscardSandboxResult(
        bucket_id=outcome.bucket_id,
        previous_label=outcome.previous_label,
        occurred_at=outcome.occurred_at,
    )


__all__ = [
    "SANDBOX_LABEL_PREFIX",
    "CreateSandboxCommand",
    "CreateSandboxResult",
    "DiscardSandboxCommand",
    "DiscardSandboxResult",
    "PreviewDiscardSandboxCommand",
    "PreviewDiscardSandboxResult",
    "SandboxAlreadyExistsError",
    "SandboxDiscardRefusedError",
    "SandboxNamespaceInventoryRow",
    "SandboxNotFoundError",
    "SandboxSourceNotFoundError",
    "create_sandbox",
    "discard_sandbox",
    "is_sandbox_label",
    "list_sandboxes",
    "preview_discard_sandbox",
    "sandbox_label",
]
