"""Governed-persistence repository for filing drafts.

Wraps the substrate's :class:`Envelope[FilingDraft]` contract behind a
small typed surface that the filing CLI and any future consumer can
call. Each draft is persisted as its own envelope file
(``<draft_id>.envelope.json``) under :attr:`aeat.config.AeatSettings.aeat_drafts_dir`,
so per-draft locking does not contend across the whole drafts directory.

The repository does NOT replace the legacy plaintext draft file format
(``<modelo>_<period>_<draft_id>.json``); the migration helper
:func:`migrate_legacy_drafts_to_repository` reads every legacy draft
JSON in a source directory and persists it through the repository.

Sensitivity classification: drafts carry per-line casilla arithmetic
that drives the exact tax due. Per the Wave-1 default policy table,
that is :class:`SensitivityClass.FINANCIAL`; the gate at
:func:`load_envelope` rejects payloads whose recorded class drifted.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..logging import get_logger
from ..storage import (
    Envelope,
    SensitivityClass,
    exclusive_file_lock,
    load_envelope,
    save_envelope,
)
from ..storage.errors import ClassificationError, EnvelopeVersionError
from ._schema import FilingDraft

_log = get_logger(__name__)

_DRAFT_ENVELOPE_VERSION = 1
_DRAFT_ENVELOPE_SUFFIX = ".envelope.json"
_DRAFT_LOCK_SUFFIX = ".lock"


class DraftMigrationSummary(BaseModel):
    """Frozen summary of one ``migrate_legacy_drafts_to_repository`` call.

    Attributes:
        imported: Number of legacy drafts persisted by this call.
        skipped: Number of legacy drafts that were already present in
            the destination repository (idempotency hit).
        errors: Number of legacy draft files the helper could not
            parse; counted but not re-raised so a partial migration
            can complete.
        store_dir: Resolved path to the repository's store directory.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    imported: int = Field(ge=0)
    skipped: int = Field(ge=0)
    errors: int = Field(default=0, ge=0)
    store_dir: str


class FilingDraftRepository:
    """Repository over the per-draft, file-locked, envelope-backed store."""

    def __init__(self, *, store_dir: Path) -> None:
        """Bind the repository to a store directory.

        Args:
            store_dir: Directory where the per-draft envelope files
                and lock sidecars live. Created on first write.
        """
        self._store_dir = Path(store_dir)

    @property
    def store_dir(self) -> Path:
        """Return the bound store directory."""
        return self._store_dir

    def envelope_path_for(self, draft_id: str) -> Path:
        """Return the canonical envelope path for ``draft_id``.

        Args:
            draft_id: The draft id (content-addressed hash from
                :func:`aeat.filing.compute_draft_id`).

        Returns:
            ``<store_dir>/<draft_id>.envelope.json``.
        """
        _validate_draft_id(draft_id)
        return self._store_dir / f"{draft_id}{_DRAFT_ENVELOPE_SUFFIX}"

    def lock_target_for(self, draft_id: str) -> Path:
        """Return the canonical lock-sidecar path for ``draft_id``."""
        _validate_draft_id(draft_id)
        return self._store_dir / f"{draft_id}{_DRAFT_LOCK_SUFFIX}"

    def load(self, draft_id: str) -> FilingDraft | None:
        """Return the persisted draft or ``None`` if absent.

        Args:
            draft_id: Draft id to load.

        Returns:
            The :class:`FilingDraft` payload, or ``None`` if the
            envelope file does not exist.

        Raises:
            ClassificationError: If the on-disk envelope's class is
                not FINANCIAL.
            EnvelopeVersionError: If the envelope schema version is
                higher than the consumer supports.
        """
        target = self.envelope_path_for(draft_id)
        if not target.exists():
            return None
        envelope = load_envelope(
            target,
            Envelope[FilingDraft],
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_DRAFT_ENVELOPE_VERSION,
        )
        return envelope.payload

    def save(self, draft: FilingDraft) -> None:
        """Persist ``draft`` atomically under its per-draft file lock."""
        self._store_dir.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_target_for(draft.draft_id)):
            envelope = Envelope[FilingDraft](
                schema_version=_DRAFT_ENVELOPE_VERSION,
                written_at=datetime.now(UTC),
                classification=SensitivityClass.FINANCIAL,
                payload=draft,
            )
            save_envelope(envelope, self.envelope_path_for(draft.draft_id))

    def delete(self, draft_id: str) -> bool:
        """Remove the envelope for ``draft_id``.

        Returns ``True`` when the envelope existed and was removed,
        ``False`` when nothing was on disk to begin with. The lock
        sidecar is left in place so concurrent ``save`` callers do
        not race against an unlink-then-recreate sequence.
        """
        target = self.envelope_path_for(draft_id)
        if not self._store_dir.exists():
            return False
        with exclusive_file_lock(self.lock_target_for(draft_id)):
            if not target.exists():
                return False
            target.unlink()
        return True

    def list_draft_ids(self) -> tuple[str, ...]:
        """Return every draft id persisted in this repository.

        The result is sorted lexicographically; callers that need
        chronological order should compare ``written_at`` after
        loading each envelope.
        """
        if not self._store_dir.exists():
            return ()
        ids: list[str] = []
        for path in self._store_dir.iterdir():
            if not path.is_file():
                continue
            name = path.name
            if not name.endswith(_DRAFT_ENVELOPE_SUFFIX):
                continue
            draft_id = name[: -len(_DRAFT_ENVELOPE_SUFFIX)]
            if not draft_id:
                continue
            ids.append(draft_id)
        ids.sort()
        return tuple(ids)

    def iter_drafts(self) -> Iterator[FilingDraft]:
        """Yield every persisted draft, in lexicographic id order."""
        for draft_id in self.list_draft_ids():
            payload = self.load(draft_id)
            if payload is not None:
                yield payload


def migrate_legacy_drafts_to_repository(
    legacy_dir: Path,
    *,
    repository: FilingDraftRepository,
    overwrite: bool = False,
) -> DraftMigrationSummary:
    """Move legacy plaintext draft JSONs into the governed repository.

    The legacy filing draft store wrote each draft as
    ``<modelo>_<period>_<draft_id>.json`` containing the JSON
    serialisation of one :class:`FilingDraft`. This helper reads every
    such file in ``legacy_dir`` and persists each through the
    repository (which writes the envelope under FINANCIAL class).

    The helper consults each per-draft lock for the duration of the
    save so concurrent migrations against the same destination
    serialise rather than race.

    Args:
        legacy_dir: Source directory containing legacy draft JSONs.
        repository: Destination repository.
        overwrite: When ``True``, replaces any draft already
            persisted in the repository. When ``False`` (default),
            already-persisted drafts are counted under ``skipped``.

    Returns:
        A frozen :class:`DraftMigrationSummary`.

    Raises:
        FileNotFoundError: If ``legacy_dir`` does not exist.
    """
    if not legacy_dir.exists():
        raise FileNotFoundError(legacy_dir)
    if not legacy_dir.is_dir():
        raise NotADirectoryError(legacy_dir)
    repository._store_dir.mkdir(parents=True, exist_ok=True)
    imported = 0
    skipped = 0
    errors = 0
    for path in sorted(legacy_dir.iterdir()):
        if not path.is_file():
            continue
        if path.suffix != ".json":
            continue
        if path.name.endswith(_DRAFT_ENVELOPE_SUFFIX):
            # Already an envelope file from a previous migration —
            # skip without raising so re-runs are idempotent.
            continue
        try:
            draft = FilingDraft.model_validate_json(path.read_text(encoding="utf-8"))
        except (ValidationError, OSError) as exc:
            _log.warning("skipping unreadable legacy draft %s: %s", path, exc)
            errors += 1
            continue
        with exclusive_file_lock(repository.lock_target_for(draft.draft_id)):
            target = repository.envelope_path_for(draft.draft_id)
            if not overwrite and target.exists():
                skipped += 1
                continue
            envelope = Envelope[FilingDraft](
                schema_version=_DRAFT_ENVELOPE_VERSION,
                written_at=datetime.now(UTC),
                classification=SensitivityClass.FINANCIAL,
                payload=draft,
            )
            save_envelope(envelope, target)
            imported += 1
    _log.info(
        "migrated legacy drafts from %s into %s: imported=%d skipped=%d errors=%d",
        legacy_dir,
        repository.store_dir,
        imported,
        skipped,
        errors,
    )
    return DraftMigrationSummary(
        imported=imported,
        skipped=skipped,
        errors=errors,
        store_dir=str(repository.store_dir.resolve()),
    )


def _validate_draft_id(draft_id: str) -> None:
    """Reject draft ids that would compose into an unsafe filename.

    The substrate's path-containment helpers already block traversal,
    but the per-draft envelope path is composed by string concatenation
    of ``<store_dir>/<draft_id>.envelope.json``. A draft id containing a
    path separator or starting with a dot would therefore land outside
    the store dir or shadow a hidden file. Treat that as a hard refusal
    rather than relying on the OS-level resolution to fail.
    """
    if not draft_id:
        raise ValueError("draft_id must be non-empty")
    if "/" in draft_id or "\\" in draft_id:
        raise ValueError(f"draft_id must not contain path separators: {draft_id!r}")
    if draft_id in {".", ".."} or draft_id.startswith("."):
        raise ValueError(f"draft_id must not be a relative-path token: {draft_id!r}")


__all__ = [
    "ClassificationError",
    "DraftMigrationSummary",
    "EnvelopeVersionError",
    "FilingDraftRepository",
    "migrate_legacy_drafts_to_repository",
]
