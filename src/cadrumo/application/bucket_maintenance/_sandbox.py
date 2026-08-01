"""Sandbox workspace lifecycle: create, activate, and discard an isolated bucket.

A sandbox is an ordinary profile bucket distinguished only by a reserved
operator-visible label prefix (:data:`SANDBOX_LABEL_PREFIX`). It rides the
exact same encrypted per-bucket storage substrate every profile uses
(:class:`~adapters.persistence.storage.SecureObjectRepository` via the
bucket-scoped runtime wrapper): there is no plaintext scratch directory and no
parallel storage backend. Isolation is the pre-existing per-bucket engine
guarantee (see
:mod:`~application.workflow.tests.test_per_bucket_engine_isolation`);
this module adds nothing to that guarantee, it only composes the existing
single-writer primitives behind an experiment-lifecycle vocabulary.

The service delegates every write to an existing primitive
(``composition-service-no-parallel-write-path``):

- :func:`~application.user_profile.register_active_profile` (via the
  ``config profile create`` / ``duplicate`` atomic-create span) provisions
  the sandbox bucket, optionally seeded from a source profile's live facts —
  exactly the same fork ``config profile duplicate`` already performs. The
  source bucket is opened read-only (a lifecycle-service ``read``) and is
  never written to, so seeding cannot mutate main state.
- :func:`~application.user_profile.select_profile_with_lifecycle_span`
  activates a named sandbox as the current session (``config login``'s
  primitive).
- :class:`~application.bucket_maintenance.BucketMaintenanceService`.delete
  composes the existing soft-tombstone-then-hard-erase primitives to discard
  the sandbox bucket entirely.
- :class:`~application.bucket_maintenance.BucketMaintenanceService`.archive
  composes the soft-tombstone-only primitive to move a sandbox into reversible
  dormancy (the bucket directory, manifest, and encrypted record survive
  intact); :meth:`~application.bucket_maintenance.BucketMaintenanceService`.restore
  is its symmetric inverse.
- :class:`~application.bucket_maintenance.BucketMaintenanceService`.browse
  (via a read-only lifecycle session, not the active bucket) backs
  :func:`preview_discard_sandbox`, so an operator can see what a discard would
  remove before confirming it.

:func:`list_sandboxes` is the read-only enumeration shared by ``sandbox list``
and ``sandbox prune`` — the composition-verb pattern this module follows: a
bulk verb composes the same single-bucket primitives per row rather than
re-implementing bucket erasure.

The destructive-action protocol mirrors
:class:`~application.bucket_maintenance.DeleteBucketCommand`: a discard
requires ``confirmed=True``, refuses the active bucket (the operator switches
away first — the existing ``BucketMaintenanceService.delete`` contract), and
additionally refuses to discard any bucket whose label is not sandbox-tagged
unless the caller explicitly acknowledges bypassing that guard — so an
operator (or an LLM agent driving the CLI) cannot accidentally erase a real
profile through the sandbox verb.

See Also:
    :mod:`~application.bucket_maintenance`
        Public facade that exports the sandbox lifecycle commands and results.
    :class:`~application.bucket_maintenance.BucketMaintenanceService`
        Existing bucket-maintenance service composed for discard, archive,
        restore, browse, and disk-usage operations.
    :func:`~application.user_profile.register_active_profile`
        Profile-create primitive used when a sandbox bucket is provisioned.
    :func:`~application.user_profile.select_profile_with_lifecycle_span`
        Profile-switch primitive used when a sandbox becomes active.
    :mod:`~entrypoints.cli._config._sandbox`
        CLI command surface that translates operator input into these command
        models.
    :class:`~domain.transactions.TransactionCatalogue`
        Ledger catalogue promoted by sandbox merges when ``ledger`` scope is
        selected.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...core import STRICT_FROZEN_CONFIG, resolve_active_bucket_id
from ...core.external_constants import SANDBOX_LABEL_PREFIX as _SANDBOX_LABEL_PREFIX
from ...core.identity import BucketId
from ...core.time import now
from ...domain.buckets import (
    BucketEvent,
    BucketEventObjectType,
    BucketEventType,
    BucketRestoreRefusedError,
    append_bucket_event,
    derive_bucket_event_id,
)
from ...domain.modelos import upsert_calculation_revision, upsert_filing_record, upsert_work_unit
from ...domain.transactions import Transaction, TransactionCatalogue
from ...domain.user_profile import ProfileNotFoundError, UserProfileFact, UserProfileStatus, new_profile_id
from ..user_profile import (
    ProfileAlreadyRegisteredError,
    build_lifecycle_service,
    profile_create_storage_span,
    profile_storage_session,
    register_active_profile,
)
from ..workflow import (
    ProfileLabelAmbiguousError,
    list_profile_buckets,
    read_profile_bucket,
    read_profile_bucket_by_id,
    workflow_state_repository,
)
from ._contracts import (
    ArchiveBucketCommand,
    BrowseBucketCommand,
    BucketNamespaceInventoryRow,
    DeleteBucketCommand,
    RestoreBucketCommand,
)
from ._service import BucketMaintenanceService

#: Reserved operator-visible label prefix identifying a sandbox bucket.
#:
#: A profile whose label starts with this prefix is a sandbox: created through
#: :func:`create_sandbox`, safe to discard without the non-sandbox confirmation
#: escalation. :func:`create_sandbox` is the only path this module exposes for
#: minting one, and :func:`discard_sandbox` (via :func:`is_sandbox_label`)
#: decides whether a bucket may be discarded without the extra confirmation.
#: The token itself is declared in the light :mod:`cadrumo.core.external_constants`
#: layer so the state-free CLI surface can read it without importing this heavy
#: module; it is re-exported here as the canonical application-facing name.
SANDBOX_LABEL_PREFIX = _SANDBOX_LABEL_PREFIX


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


class SandboxNotArchivedError(Exception):
    """Raised when ``restore_sandbox`` targets a sandbox that is not currently archived."""

    def __init__(self, bucket_id: str) -> None:
        super().__init__(f"bucket {bucket_id!r} is not archived; there is nothing to restore")
        self.bucket_id = bucket_id


class SandboxMergeRefusedError(Exception):
    """Raised when ``merge_sandbox`` is refused (missing confirmation, unknown scope target)."""


class SandboxMergeScope(StrEnum):
    """Closed axis of promotable data categories a sandbox merge may select.

    ``LEDGER`` promotes ledger transactions only (the manual/imported
    :class:`~domain.transactions.Transaction` catalogue, which already
    carries classification decisions on each row). ``MODELO`` promotes the
    modelo work-unit, calculation-revision, and filing-record catalogues.
    ``ALL`` promotes every one of the above in one call.

    Ledger promotion reads the sandbox
    :class:`~domain.transactions.TransactionCatalogue` through the concrete
    :class:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository`
    and upserts the rows into the target bucket.
    """

    LEDGER = "ledger"
    MODELO = "modelo"
    ALL = "all"


class PreviewDiscardSandboxCommand(BaseModel):
    """Operator request to preview what a sandbox discard would remove.

    Read-only counterpart to :class:`DiscardSandboxCommand`: it never opens
    the target bucket for write and never calls
    :meth:`~application.bucket_maintenance.BucketMaintenanceService`.delete.
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
    :meth:`~application.bucket_maintenance.BucketMaintenanceService`.browse
    returns for the active bucket, computed here for a bucket that need not
    be active. ``is_active`` flags whether the target is the current session
    — a real discard of it would be refused until the operator switches away.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    label: str
    is_active: bool
    namespaces: tuple[BucketNamespaceInventoryRow, ...]


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
    :class:`~application.bucket_maintenance.DeleteBucketCommand`.
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


class ArchiveSandboxCommand(BaseModel):
    """Operator request to move a sandbox into reversible dormancy.

    Unlike :class:`DiscardSandboxCommand`, ``archive`` never removes the
    sandbox bucket: it composes
    :meth:`~application.bucket_maintenance.BucketMaintenanceService`.archive
    (soft tombstone only), so the bucket directory, manifest, and
    encrypted record all survive intact and :func:`restore_sandbox` can
    bring the same sandbox back. ``confirmed=True`` mirrors
    :class:`DiscardSandboxCommand`'s boundary contract.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    confirmed: bool = False
    allow_non_sandbox: bool = False


class ArchiveSandboxResult(BaseModel):
    """Outcome of a successful sandbox archive."""

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    label: str
    occurred_at: datetime


class RestoreSandboxCommand(BaseModel):
    """Operator request to bring an archived sandbox back to active status.

    Symmetric inverse of :class:`ArchiveSandboxCommand`. Refuses when the
    target is not currently archived (tombstoned).
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    allow_non_sandbox: bool = False


class RestoreSandboxResult(BaseModel):
    """Outcome of a successful sandbox restore."""

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    label: str
    occurred_at: datetime


class MergeSandboxCommand(BaseModel):
    """Operator request to promote one data scope from a sandbox into a target profile.

    ``source_bucket_id`` must carry the reserved sandbox label (the
    ``allow_non_sandbox`` escape hatch mirrors every other sandbox verb's
    non-sandbox guard). ``target_bucket_id`` names the profile bucket the
    scope is merged INTO — ordinarily the operator's main profile, resolved
    by the CLI layer before this command is built, never the sandbox itself.
    ``confirmed=True`` is required because the merge mutates the target
    profile's real records.
    """

    model_config = STRICT_FROZEN_CONFIG

    source_bucket_id: BucketId
    target_bucket_id: BucketId
    scope: SandboxMergeScope
    confirmed: bool = False
    allow_non_sandbox: bool = False


class MergeSandboxResult(BaseModel):
    """Outcome of a successful sandbox merge.

    ``merged_counts`` reports, per merged typed category, how many rows the
    merge upserted into the target bucket (a re-run against unchanged sandbox
    content upserts the same content-addressed ids again — an idempotent
    no-op write, never a duplicate row).
    """

    model_config = STRICT_FROZEN_CONFIG

    source_bucket_id: BucketId
    target_bucket_id: BucketId
    scope: SandboxMergeScope
    merged_counts: dict[str, int]
    occurred_at: datetime


def create_sandbox(command: CreateSandboxCommand) -> CreateSandboxResult:
    """Fork a fresh, isolated sandbox bucket and make it the active profile.

    Composes the canonical atomic-create span
    (:func:`~application.user_profile.profile_create_storage_span` +
    :func:`~application.user_profile.register_active_profile`) — the
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
    lifecycle session (:func:`~application.user_profile.profile_storage_session`)
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
        namespaces=browsed.rows,
    )


def list_sandboxes() -> tuple[tuple[BucketId, str], ...]:
    """Return every ``(bucket_id, label)`` pair currently carrying the sandbox prefix.

    Read-only enumeration shared by ``sandbox list`` and ``sandbox prune``.
    """
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

    Composes :class:`~application.bucket_maintenance.BucketMaintenanceService`.delete
    — the same soft-tombstone-then-hard-directory-removal primitive
    ``config profile delete`` uses — after confirming the target either
    carries the reserved sandbox label or the caller explicitly set
    ``allow_non_sandbox=True``. Refuses (via the composed service) to
    discard the currently active bucket; the operator must switch away
    first. For a reversible alternative that never erases the bucket, see
    :func:`archive_sandbox`.

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
    if outcome.previous_label is None:
        raise SandboxNotFoundError(command.bucket_id)
    return DiscardSandboxResult(
        bucket_id=outcome.bucket_id,
        previous_label=outcome.previous_label,
        occurred_at=outcome.occurred_at,
    )


def archive_sandbox(command: ArchiveSandboxCommand) -> ArchiveSandboxResult:
    """Move the sandbox bucket identified by ``command.bucket_id`` into reversible dormancy.

    Composes :class:`~application.bucket_maintenance.BucketMaintenanceService`.archive
    — the same soft-tombstone-only primitive that leaves the bucket
    directory, manifest, and encrypted record intact — after confirming
    the target either carries the reserved sandbox label or the caller
    explicitly set ``allow_non_sandbox=True``. Refuses (via the composed
    service) to archive the currently active bucket; the operator must
    switch away first. Unlike :func:`discard_sandbox`, the archived
    sandbox can be brought back with :func:`restore_sandbox`.

    Returns:
        :class:`ArchiveSandboxResult` describing the archived sandbox.
    """
    pointer = read_profile_bucket_by_id(command.bucket_id)
    if pointer is None:
        raise SandboxNotFoundError(command.bucket_id)
    if not is_sandbox_label(pointer.label) and not command.allow_non_sandbox:
        raise SandboxDiscardRefusedError(
            f"bucket {command.bucket_id!r} (label {pointer.label!r}) is not a sandbox; "
            "pass allow_non_sandbox=True to archive a non-sandbox profile",
        )
    outcome = BucketMaintenanceService().archive(
        ArchiveBucketCommand(bucket_id=command.bucket_id, confirmed=command.confirmed),
    )
    return ArchiveSandboxResult(bucket_id=outcome.bucket_id, label=outcome.label, occurred_at=outcome.occurred_at)


def restore_sandbox(command: RestoreSandboxCommand) -> RestoreSandboxResult:
    """Bring the archived sandbox bucket identified by ``command.bucket_id`` back to active.

    Composes :class:`~application.bucket_maintenance.BucketMaintenanceService`.restore
    — the symmetric inverse of :func:`archive_sandbox` — after confirming
    the target either carries the reserved sandbox label or the caller
    explicitly set ``allow_non_sandbox=True``. Refuses when the target is
    not currently archived.

    Returns:
        :class:`RestoreSandboxResult` describing the restored sandbox.
    """
    pointer = read_profile_bucket_by_id(command.bucket_id)
    if pointer is None:
        raise SandboxNotFoundError(command.bucket_id)
    if not is_sandbox_label(pointer.label) and not command.allow_non_sandbox:
        raise SandboxDiscardRefusedError(
            f"bucket {command.bucket_id!r} (label {pointer.label!r}) is not a sandbox; "
            "pass allow_non_sandbox=True to restore a non-sandbox profile",
        )
    try:
        outcome = BucketMaintenanceService().restore(RestoreBucketCommand(bucket_id=command.bucket_id))
    except BucketRestoreRefusedError as exc:
        raise SandboxNotArchivedError(command.bucket_id) from exc
    return RestoreSandboxResult(bucket_id=outcome.bucket_id, label=outcome.label, occurred_at=outcome.occurred_at)


def merge_sandbox(command: MergeSandboxCommand) -> MergeSandboxResult:
    """Promote ``command.scope`` from a sandbox bucket into ``command.target_bucket_id``.

    Composes the SAME typed-catalogue repositories and domain upsert
    primitives the portable-bundle import path
    (:func:`~application.user_profile.deserialize_profile_bundle`) uses
    for ledger/work-unit/calculation-revision/filing-record restore
    (``composition-service-no-parallel-write-path``): this function does not
    reimplement a write path, it selects which of those existing upserts to
    run for the requested scope. Every upsert keys on the row's own
    content-addressed or natural id, so re-running a merge against unchanged
    sandbox content is an idempotent no-op write (the target ends up with the
    identical row it already had, never a duplicate).

    Refuses unless ``command.confirmed`` is ``True``. Refuses when
    ``command.source_bucket_id`` is not sandbox-labelled unless the caller
    explicitly sets ``command.allow_non_sandbox``, mirroring every other
    sandbox verb's non-sandbox guard. Refuses when the source and target
    buckets are identical (nothing to promote).

    Returns:
        :class:`MergeSandboxResult` reporting the per-category row counts
        merged into the target bucket.
    """
    if not command.confirmed:
        raise SandboxMergeRefusedError(
            "sandbox merge requires explicit confirmation (confirmed=True); "
            "pass --yes at the CLI boundary to promote sandbox data into the target profile",
        )
    if command.source_bucket_id == command.target_bucket_id:
        raise SandboxMergeRefusedError(
            f"source and target bucket are the same ({command.source_bucket_id!r}); nothing to merge",
        )
    source_pointer = read_profile_bucket_by_id(command.source_bucket_id)
    if source_pointer is None:
        raise SandboxNotFoundError(command.source_bucket_id)
    if not is_sandbox_label(source_pointer.label) and not command.allow_non_sandbox:
        raise SandboxDiscardRefusedError(
            f"bucket {command.source_bucket_id!r} (label {source_pointer.label!r}) is not a sandbox; "
            "pass allow_non_sandbox=True to merge from a non-sandbox profile",
        )
    target_pointer = read_profile_bucket_by_id(command.target_bucket_id)
    if target_pointer is None:
        raise SandboxNotFoundError(command.target_bucket_id)

    merged_counts: dict[str, int] = {}

    if command.scope in (SandboxMergeScope.LEDGER, SandboxMergeScope.ALL):
        with profile_storage_session(command.source_bucket_id):
            source_transactions = tuple(TransactionCatalogueRepository(bucket_id=command.source_bucket_id).load())
        if source_transactions:
            with profile_storage_session(command.target_bucket_id):
                target_repo = TransactionCatalogueRepository(bucket_id=command.target_bucket_id)
                existing = target_repo.load()
                merged: dict[str, Transaction] = dict(existing.transactions)
                for transaction in source_transactions:
                    merged[transaction.transaction_id] = transaction
                target_repo.save(TransactionCatalogue(transactions=merged))
        merged_counts["ledger_transactions"] = len(source_transactions)

    if command.scope in (SandboxMergeScope.MODELO, SandboxMergeScope.ALL):
        with profile_storage_session(command.source_bucket_id):
            source_work_units = tuple(WorkUnitCatalogueRepository(bucket_id=command.source_bucket_id).load())
            source_revisions = tuple(
                CalculationRevisionCatalogueRepository(bucket_id=command.source_bucket_id).load(),
            )
            source_filing_records = tuple(ModeloRecordCatalogueRepository(bucket_id=command.source_bucket_id).load())

        with profile_storage_session(command.target_bucket_id):
            if source_work_units:
                work_unit_repo = WorkUnitCatalogueRepository(bucket_id=command.target_bucket_id)
                catalogue = work_unit_repo.load()
                for unit in source_work_units:
                    catalogue = upsert_work_unit(catalogue, unit)
                work_unit_repo.save(catalogue)
            if source_revisions:
                revision_repo = CalculationRevisionCatalogueRepository(bucket_id=command.target_bucket_id)
                revision_catalogue = revision_repo.load()
                for revision in source_revisions:
                    revision_catalogue = upsert_calculation_revision(revision_catalogue, revision)
                revision_repo.save(revision_catalogue)
            if source_filing_records:
                filing_repo = ModeloRecordCatalogueRepository(bucket_id=command.target_bucket_id)
                filing_catalogue = filing_repo.load()
                for record in source_filing_records:
                    filing_catalogue = upsert_filing_record(filing_catalogue, record)
                filing_repo.save(filing_catalogue)

        merged_counts["work_units"] = len(source_work_units)
        merged_counts["calculation_revisions"] = len(source_revisions)
        merged_counts["filing_records"] = len(source_filing_records)

    occurred_at = now()
    payload = {
        "source_bucket_id": command.source_bucket_id,
        "source_label": source_pointer.label,
        "scope": command.scope.value,
        **{f"merged.{category}": str(count) for category, count in merged_counts.items()},
    }
    event = BucketEvent(
        event_id=derive_bucket_event_id(
            bucket_id=command.target_bucket_id,
            event_type=BucketEventType.BUCKET_MERGED,
            occurred_at=occurred_at,
            actor="bucket-maintenance",
            object_type=BucketEventObjectType.BUCKET,
            object_id=command.target_bucket_id,
            payload=payload,
        ),
        bucket_id=command.target_bucket_id,
        event_type=BucketEventType.BUCKET_MERGED,
        occurred_at=occurred_at,
        actor="bucket-maintenance",
        object_type=BucketEventObjectType.BUCKET,
        object_id=command.target_bucket_id,
        payload_version=1,
        payload=payload,
    )
    with profile_storage_session(command.target_bucket_id):
        event_repository = BucketMaintenanceService._event_repository_for_bucket(command.target_bucket_id)
        event_repository.save(append_bucket_event(event_repository.load(), event))

    return MergeSandboxResult(
        source_bucket_id=command.source_bucket_id,
        target_bucket_id=command.target_bucket_id,
        scope=command.scope,
        merged_counts=merged_counts,
        occurred_at=occurred_at,
    )


__all__ = [
    "SANDBOX_LABEL_PREFIX",
    "ArchiveSandboxCommand",
    "ArchiveSandboxResult",
    "CreateSandboxCommand",
    "CreateSandboxResult",
    "DiscardSandboxCommand",
    "DiscardSandboxResult",
    "MergeSandboxCommand",
    "MergeSandboxResult",
    "PreviewDiscardSandboxCommand",
    "PreviewDiscardSandboxResult",
    "RestoreSandboxCommand",
    "RestoreSandboxResult",
    "SandboxAlreadyExistsError",
    "SandboxDiscardRefusedError",
    "SandboxMergeRefusedError",
    "SandboxMergeScope",
    "SandboxNotArchivedError",
    "SandboxNotFoundError",
    "SandboxSourceNotFoundError",
    "archive_sandbox",
    "create_sandbox",
    "discard_sandbox",
    "is_sandbox_label",
    "list_sandboxes",
    "merge_sandbox",
    "preview_discard_sandbox",
    "restore_sandbox",
    "sandbox_label",
]
