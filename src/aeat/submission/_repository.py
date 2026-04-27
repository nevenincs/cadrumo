"""Governed-persistence repository for submitted-filing audit records.

Wraps the substrate's :class:`Envelope[SubmittedFiling]` contract behind
a small typed surface that the submission engine and any future consumer
can call. Each submission is persisted as its own envelope file
(``<submission_id>.envelope.json``) under
:attr:`aeat.config.AeatSettings.aeat_submissions_dir` with a per-record
exclusive_file_lock so concurrent writers serialise per-record but never
across the whole directory.

Sensitivity classification: a submission record captures the exact bytes
Kent uploaded plus AEAT's response. That is auditable evidence with
identity-bearing context — :class:`SensitivityClass.AUDIT` per the
default policy table.

The repository does NOT replace the existing
:meth:`aeat.submission._engine.SubmissionEngine._persist` writer; the
migration helper :func:`migrate_legacy_submissions_to_repository` reads
every legacy ``<submission_id>.json`` and persists each through the
repository's envelope contract.
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
from ._models import SubmittedFiling

_log = get_logger(__name__)

_SUBMISSION_ENVELOPE_VERSION = 1
_SUBMISSION_ENVELOPE_SUFFIX = ".envelope.json"
_SUBMISSION_LOCK_SUFFIX = ".lock"


class SubmissionMigrationSummary(BaseModel):
    """Frozen summary of one ``migrate_legacy_submissions_to_repository`` call.

    Attributes:
        imported: Number of legacy submissions persisted by this call.
        skipped: Number of legacy submissions already present in the
            destination repository (idempotency hit).
        errors: Number of legacy submission files the helper could not
            parse; counted but not re-raised so a partial migration can
            complete.
        store_dir: Resolved path to the repository's store directory.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    imported: int = Field(ge=0)
    skipped: int = Field(ge=0)
    errors: int = Field(default=0, ge=0)
    store_dir: str


class SubmissionRepository:
    """Repository over the per-submission, file-locked, envelope-backed store."""

    def __init__(self, *, store_dir: Path) -> None:
        """Bind the repository to a store directory.

        Args:
            store_dir: Directory where the per-submission envelope
                files and lock sidecars live. Created on first write.
        """
        self._store_dir = Path(store_dir)

    @property
    def store_dir(self) -> Path:
        """Return the bound store directory."""
        return self._store_dir

    def envelope_path_for(self, submission_id: str) -> Path:
        """Return the canonical envelope path for ``submission_id``.

        Args:
            submission_id: The submission identifier
                (:func:`aeat.submission._models.make_submission_id`).

        Returns:
            ``<store_dir>/<submission_id>.envelope.json``.
        """
        _validate_submission_id(submission_id)
        return self._store_dir / f"{submission_id}{_SUBMISSION_ENVELOPE_SUFFIX}"

    def lock_target_for(self, submission_id: str) -> Path:
        """Return the canonical lock-sidecar path for ``submission_id``."""
        _validate_submission_id(submission_id)
        return self._store_dir / f"{submission_id}{_SUBMISSION_LOCK_SUFFIX}"

    def load(self, submission_id: str) -> SubmittedFiling | None:
        """Return the persisted submission or ``None`` if absent.

        Raises:
            ClassificationError: If the on-disk envelope's class is not
                AUDIT.
            EnvelopeVersionError: If the envelope schema version is
                higher than the consumer supports.
        """
        target = self.envelope_path_for(submission_id)
        if not target.exists():
            return None
        envelope = load_envelope(
            target,
            Envelope[SubmittedFiling],
            expected_class=SensitivityClass.AUDIT,
            max_supported_version=_SUBMISSION_ENVELOPE_VERSION,
        )
        return envelope.payload

    def save(self, filing: SubmittedFiling) -> None:
        """Persist ``filing`` atomically under its per-submission file lock."""
        self._store_dir.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_target_for(filing.submission_id)):
            envelope = Envelope[SubmittedFiling](
                schema_version=_SUBMISSION_ENVELOPE_VERSION,
                written_at=datetime.now(UTC),
                classification=SensitivityClass.AUDIT,
                payload=filing,
            )
            save_envelope(envelope, self.envelope_path_for(filing.submission_id))

    def delete(self, submission_id: str) -> bool:
        """Remove the envelope for ``submission_id``.

        Returns ``True`` when the envelope existed and was removed,
        ``False`` when nothing was on disk to begin with.
        """
        target = self.envelope_path_for(submission_id)
        if not self._store_dir.exists():
            return False
        with exclusive_file_lock(self.lock_target_for(submission_id)):
            if not target.exists():
                return False
            target.unlink()
        return True

    def list_submission_ids(self) -> tuple[str, ...]:
        """Return every submission id persisted in this repository."""
        if not self._store_dir.exists():
            return ()
        ids: list[str] = []
        for path in self._store_dir.iterdir():
            if not path.is_file():
                continue
            name = path.name
            if not name.endswith(_SUBMISSION_ENVELOPE_SUFFIX):
                continue
            submission_id = name[: -len(_SUBMISSION_ENVELOPE_SUFFIX)]
            if not submission_id:
                continue
            ids.append(submission_id)
        ids.sort()
        return tuple(ids)

    def iter_submissions(self) -> Iterator[SubmittedFiling]:
        """Yield every persisted submission, in lexicographic id order."""
        for submission_id in self.list_submission_ids():
            payload = self.load(submission_id)
            if payload is not None:
                yield payload


def migrate_legacy_submissions_to_repository(
    legacy_dir: Path,
    *,
    repository: SubmissionRepository,
    overwrite: bool = False,
) -> SubmissionMigrationSummary:
    """Move legacy plaintext submission JSONs into the governed repository.

    The legacy submission engine writes each submission as
    ``<submission_id>.json`` containing the JSON serialisation of one
    :class:`SubmittedFiling`. This helper reads every such file in
    ``legacy_dir`` and persists each through the repository (which writes
    the envelope under AUDIT class).

    Args:
        legacy_dir: Source directory containing legacy submission JSONs.
            Sub-directories (e.g. ``amendment-results/``) are skipped;
            those carry a different payload type.
        repository: Destination repository.
        overwrite: When ``True``, replaces any submission already
            persisted in the repository. When ``False`` (default),
            already-persisted submissions are counted under ``skipped``.

    Returns:
        A frozen :class:`SubmissionMigrationSummary`.

    Raises:
        FileNotFoundError: If ``legacy_dir`` does not exist.
        NotADirectoryError: If ``legacy_dir`` is not a directory.
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
        if path.name.endswith(_SUBMISSION_ENVELOPE_SUFFIX):
            continue
        try:
            filing = SubmittedFiling.model_validate_json(path.read_text(encoding="utf-8"))
        except (ValidationError, OSError) as exc:
            _log.warning("skipping unreadable legacy submission %s: %s", path, exc)
            errors += 1
            continue
        with exclusive_file_lock(repository.lock_target_for(filing.submission_id)):
            target = repository.envelope_path_for(filing.submission_id)
            if not overwrite and target.exists():
                skipped += 1
                continue
            envelope = Envelope[SubmittedFiling](
                schema_version=_SUBMISSION_ENVELOPE_VERSION,
                written_at=datetime.now(UTC),
                classification=SensitivityClass.AUDIT,
                payload=filing,
            )
            save_envelope(envelope, target)
            imported += 1
    _log.info(
        "migrated legacy submissions from %s into %s: imported=%d skipped=%d errors=%d",
        legacy_dir,
        repository.store_dir,
        imported,
        skipped,
        errors,
    )
    return SubmissionMigrationSummary(
        imported=imported,
        skipped=skipped,
        errors=errors,
        store_dir=str(repository.store_dir.resolve()),
    )


def _validate_submission_id(submission_id: str) -> None:
    """Reject submission ids that would compose into an unsafe filename."""
    if not submission_id:
        raise ValueError("submission_id must be non-empty")
    if "/" in submission_id or "\\" in submission_id:
        raise ValueError(f"submission_id must not contain path separators: {submission_id!r}")
    if submission_id in {".", ".."} or submission_id.startswith("."):
        raise ValueError(f"submission_id must not be a relative-path token: {submission_id!r}")


__all__ = [
    "ClassificationError",
    "EnvelopeVersionError",
    "SubmissionMigrationSummary",
    "SubmissionRepository",
    "migrate_legacy_submissions_to_repository",
]
