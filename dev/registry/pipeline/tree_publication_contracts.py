"""Canonical records and transaction identities for generated export publication."""

from __future__ import annotations

import os
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from cadrumo.core.hashing import hash_file
from cadrumo.core.link_safety import is_link_like
from cadrumo.core.locks import exclusive_file_lock
from cadrumo.core.locks_errors import LockAcquisitionError
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.ids import ModeloId, RevisionId

from ..compiler.export_fragment_grammar import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from ._tree_validation import (
    GeneratedExportTreeValidationContext,
    ValidatedGeneratedExportTree,
    ValidatedHistoricalStaticGeneratedExportTree,
)
from .export_fragment_provenance import (
    SHA256_PATTERN,
    ExportFragmentOutputDigest,
    collect_export_fragment_output_digests,
)

_JOURNAL_SCHEMA_VERSION: Final[Literal[1]] = 1


_MODELO_ID_ADAPTER: Final[TypeAdapter[ModeloId]] = TypeAdapter(ModeloId)


_REVISION_ID_ADAPTER: Final[TypeAdapter[RevisionId]] = TypeAdapter(RevisionId)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class GeneratedExportPublicationJournal(_StrictModel):
    """Crash-recovery facts for an export swap or pinned revision-bundle cutover."""

    schema_version: Literal[1]
    state: Literal["intent", "backup_staged", "candidate_live", "committed"]
    modelo: ModeloId
    revision_id: RevisionId
    candidate_export: str = Field(min_length=1)
    backup_export: str = Field(min_length=1)
    candidate_manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    candidate_revision_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    superseded_layout_id: str | None = Field(default=None, min_length=1)
    generated_layout_id: str | None = Field(default=None, min_length=1)
    superseded_construct_references: int | None = Field(default=None, ge=0)
    supersession_source_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    cleanup_started: bool | None = None

    @field_validator("modelo", "revision_id")
    @classmethod
    def _identities_are_single_path_components(cls, value: str) -> str:
        _require_single_path_component(value, subject="generated publication journal identity")
        return value

    @property
    def is_supersession(self) -> bool:
        """Whether this transaction replaces a reviewed manual layout as a bundle."""
        return self.superseded_layout_id is not None


@dataclass(frozen=True, slots=True)
class GeneratedExportTreePublicationContext:
    """Explicit caller roots, validated candidate and optional reviewed supersession pin."""

    validation: GeneratedExportTreeValidationContext
    temporary_root: Path
    target_root: Path
    target_export_root: Path
    expected_target_state: GeneratedExportTreeTargetStateReceipt | None = None
    supersession: GeneratedExportSupersession | None = None
    final_live_validator: Callable[[], None] | None = None
    #: Replaces one export directory with another for cutover, rollback and
    #: recovery. A caller proving the rollback path supplies a replacement that
    #: refuses one specific swap; publication itself always uses ``os.replace``.
    replace_export_directory: Callable[[Path, Path], None] = os.replace


@dataclass(frozen=True, slots=True)
class GeneratedExportTreeTargetStateReceipt:
    """The target state a read-only check observed before publication."""

    manifest_sha256: str | None
    output_files: tuple[ExportFragmentOutputDigest, ...]
    supersession_source_sha256: str | None = None

    @classmethod
    def observe(
        cls,
        export_root: Path,
        *,
        supersession_source_sha256: str | None = None,
    ) -> GeneratedExportTreeTargetStateReceipt:
        """Capture the exact manifest and output digests currently at this root."""
        if not export_root.exists():
            return cls(
                manifest_sha256=None,
                output_files=(),
                supersession_source_sha256=supersession_source_sha256,
            )
        return cls(
            manifest_sha256=export_provenance_file_sha256(export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME),
            output_files=collect_export_fragment_output_digests(export_root),
            supersession_source_sha256=supersession_source_sha256,
        )


@dataclass(frozen=True, slots=True)
class GeneratedExportSupersession:
    """Reviewed source pin for retiring one manual layout during export publication."""

    superseded_layout_id: str
    generated_layout_id: str
    expected_construct_references: int
    source_state_sha256: str
    source_ref: str | None = None
    source_sha256: str | None = None
    manual_source_sha256: str | None = None
    manual_origin_revision: str | None = None


@dataclass(frozen=True, slots=True)
class PublishedGeneratedExportTree:
    """The precise generated export tree selected through the loader boundary and cut over."""

    validated: ValidatedGeneratedExportTree | ValidatedHistoricalStaticGeneratedExportTree | None
    export_root: Path
    provenance_manifest_path: Path


@dataclass(frozen=True, slots=True)
class GeneratedExportTransactionPaths:
    """The bounded files/directories one modelo/revision export transaction owns.

    The journal and lock identity are fixed per target in the registry
    directory's parent, outside compiler inputs. Ordinary export staging and
    rollback paths remain transaction-prefixed children of the registry root.
    Supersession revision bundles use separate prefixed siblings in the parent
    because live-root compilation must see only the cutover revision.
    """

    target_root: Path
    modelo: str
    revision_id: str

    @classmethod
    def for_context(cls, context: GeneratedExportTreePublicationContext) -> GeneratedExportTransactionPaths:
        """The transaction paths under a publication context's resolved target root."""
        return cls(
            target_root=context.target_root.resolve(),
            modelo=str(context.validation.target.modelo),
            revision_id=str(context.validation.target.revision_id),
        )

    @property
    def lock_identity(self) -> Path:
        """The identity whose ``.lock`` sidecar serialises this transaction."""
        return self.target_root.parent / (
            f".{self.target_root.name}-generated-export-transaction-{self.modelo}-{self.revision_id}"
        )

    @property
    def journal(self) -> Path:
        """The crash-recovery journal beside the lock identity."""
        return self.transaction_root / f"{self.lock_identity.name}.json"

    @property
    def transaction_root(self) -> Path:
        """The same-volume parent used for transaction bookkeeping and bundle trees."""
        return self.target_root.parent

    @property
    def legacy_lock_identity(self) -> Path:
        """The previous in-root lock identity retained for migration detection."""
        return self.target_root / f".generated-export-transaction-{self.modelo}-{self.revision_id}"

    @property
    def legacy_journal(self) -> Path:
        """The previous in-root journal path, which must not be mistaken for new state."""
        return self.target_root / f"{self.legacy_lock_identity.name}.json"

    @property
    def backup_prefix(self) -> str:
        """The name prefix every rollback backup sibling of this transaction carries."""
        return f".generated-export-backup-{self.modelo}-{self.revision_id}-"

    @property
    def staging_prefix(self) -> str:
        """The name prefix every same-volume staging sibling of this transaction carries."""
        return f".generated-export-stage-{self.modelo}-{self.revision_id}-"

    @property
    def bundle_backup_prefix(self) -> str:
        """Name prefix for an opaque whole-revision backup in ``transaction_root``."""
        return f".{self.target_root.name}-generated-export-bundle-backup-{self.modelo}-{self.revision_id}-"

    @property
    def bundle_staging_prefix(self) -> str:
        """Name prefix for an opaque whole-revision candidate in ``transaction_root``."""
        return f".{self.target_root.name}-generated-export-bundle-stage-{self.modelo}-{self.revision_id}-"

    def new_backup_sibling(self) -> Path:
        """Return a fresh rollback backup sibling that does not exist yet."""
        backup = self.target_root / f"{self.backup_prefix}{secrets.token_hex(16)}"
        if backup.exists() or is_link_like(backup):
            raise RegistryValidationError(f"generated export rollback sibling unexpectedly exists: {backup}")
        return backup

    def new_staging_sibling(self) -> Path:
        """Return a fresh same-volume staging sibling that does not exist yet.

        It lives beside ``modelos/`` at the registry root, never inside the revision
        directory: ``load_modelo_directory`` recursively validates every file under
        a revision directory and refuses a staging sibling parked next to ``export/``.
        """
        staging = self.target_root / f"{self.staging_prefix}{secrets.token_hex(16)}"
        if staging.exists() or is_link_like(staging):
            raise RegistryValidationError(f"generated export staging sibling unexpectedly exists: {staging}")
        return staging

    def new_bundle_backup_sibling(self) -> Path:
        """Return a fresh whole-revision rollback sibling outside compiler inputs."""
        backup = self.transaction_root / f"{self.bundle_backup_prefix}{secrets.token_hex(16)}"
        if backup.exists() or is_link_like(backup):
            raise RegistryValidationError(f"generated export rollback sibling unexpectedly exists: {backup}")
        return backup

    def new_bundle_staging_sibling(self) -> Path:
        """Return a fresh whole-revision candidate sibling outside compiler inputs."""
        staging = self.transaction_root / f"{self.bundle_staging_prefix}{secrets.token_hex(16)}"
        if staging.exists() or is_link_like(staging):
            raise RegistryValidationError(f"generated export staging sibling unexpectedly exists: {staging}")
        return staging


def _require_no_legacy_transaction(transaction_paths: GeneratedExportTransactionPaths) -> None:
    """Refuse old in-root journals and detect an active holder without deleting sidecars."""
    if transaction_paths.legacy_journal.exists():
        raise RegistryValidationError(
            "legacy generated export journal requires recovery at its original location; "
            f"preserved journal: {transaction_paths.legacy_journal}",
        )
    try:
        with exclusive_file_lock(transaction_paths.legacy_lock_identity, timeout=0):
            pass
    except LockAcquisitionError as exc:
        raise RegistryValidationError(
            "legacy generated export transaction is active at its original lock; retry after it finishes: "
            f"{transaction_paths.legacy_lock_identity}.lock",
        ) from exc
    if transaction_paths.legacy_journal.exists():
        raise RegistryValidationError(
            "legacy generated export journal appeared during transaction admission; "
            f"preserved journal: {transaction_paths.legacy_journal}",
        )


def _require_single_path_component(value: str, *, subject: str) -> None:
    """Reject drive-relative or multi-component identifiers before path use."""
    posix_component = PurePosixPath(value)
    windows_component = PureWindowsPath(value)
    if (
        value in {".", ".."}
        or posix_component.is_absolute()
        or posix_component.parts != (value,)
        or windows_component.is_absolute()
        or windows_component.drive
        or windows_component.parts != (value,)
    ):
        raise ValueError(f"{subject} must be one relative path component")


def export_provenance_file_sha256(path: Path) -> str:
    """Return the SHA-256 of one regular, non-linked export provenance file."""
    if is_link_like(path) or not path.is_file():
        raise RegistryValidationError(f"generated export provenance path must be a regular file: {path}")
    digest, _byte_count = hash_file(path)
    return digest
