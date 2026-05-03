"""Governed-persistence repository for filing-history records.

Wraps the encrypted-envelope substrate's
:class:`aeat.adapters.persistence.storage.Envelope` of
:class:`aeat.domain.sync.WireFilingHistory` behind a small typed
surface for the sync runner and any future consumer. Each modelo's
filing history is persisted as its own envelope file
(``<modelo>.envelope.json``) under
:attr:`aeat.core.config.AeatSettings.aeat_filing_history_dir`, guarded
by a per-modelo :func:`aeat.adapters.persistence.storage.exclusive_file_lock`.

Sensitivity classification: a filing-history payload captures the
sequence of submitted filings (modelo, period, submitted_at, status)
the operator has on AEAT — auditable evidence with identity-bearing
context, hence
:attr:`aeat.adapters.persistence.storage.SensitivityClass.AUDIT`.

Out of scope: the optional HTML page archive remains in
``aeat_filing_history_dir / pages/``. That artefact is an
operator-visible legal record and is owned by the page-archive
subsystem; the repository governs only the *structured* filing-history
shape so the modelo / period / submitted_at / status fields pass
through the classification gate at load time.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ...adapters.persistence.storage import (
    Envelope,
    SensitivityClass,
    exclusive_file_lock,
    load_encrypted_envelope,
    safe_repository_id,
    save_encrypted_envelope,
)
from ...adapters.persistence.storage.crypto._encrypted_columns import _resolve_master_key_provider
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...core.logging import get_logger
from ...domain.sync import WireFilingHistory

_HKDF_CONTEXT_FILING_HISTORY = b"aeat.application.filing.history.v1"

_log = get_logger(__name__)

_HISTORY_ENVELOPE_VERSION = 1
_HISTORY_ENVELOPE_SUFFIX = ".envelope.json"
_HISTORY_LOCK_SUFFIX = ".lock"


class HistoryMigrationSummary(BaseModel):
    """Frozen summary of one :func:`migrate_legacy_filing_history_to_repository` call.

    Attributes:
        imported: Number of legacy modelo histories persisted by this
            call.
        skipped: Number already present in the destination repository.
        errors: Number of legacy files the helper could not parse.
        store_dir: Resolved path to the repository's store directory.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    imported: int = Field(ge=0)
    skipped: int = Field(ge=0)
    errors: int = Field(default=0, ge=0)
    store_dir: str


class FilingHistoryRepository:
    """Repository over the per-modelo, file-locked, envelope-backed store.

    Every persisted record passes through the encrypted-envelope
    substrate so the on-disk artefact is always AES-256-GCM
    ciphertext at
    :attr:`aeat.adapters.persistence.storage.SensitivityClass.AUDIT`.
    """

    def __init__(self, *, store_dir: Path) -> None:
        """Bind the repository to a store directory.

        Args:
            store_dir: Directory where the per-modelo envelope files
                and lock sidecars live. Created on first write.
        """
        self._store_dir = Path(store_dir)

    @property
    def store_dir(self) -> Path:
        """Return the bound store directory."""
        return self._store_dir

    def envelope_path_for(self, modelo: str) -> Path:
        """Return the canonical envelope path for ``modelo``."""
        safe_repository_id(modelo, context="modelo")
        return self._store_dir / f"{modelo}{_HISTORY_ENVELOPE_SUFFIX}"

    def lock_target_for(self, modelo: str) -> Path:
        """Return the canonical lock-sidecar path for ``modelo``."""
        safe_repository_id(modelo, context="modelo")
        return self._store_dir / f"{modelo}{_HISTORY_LOCK_SUFFIX}"

    def load(self, modelo: str) -> WireFilingHistory | None:
        """Return the persisted filing history for ``modelo`` or ``None``.

        Args:
            modelo: Modelo identifier (e.g. ``"130"``).

        Returns:
            The decrypted :class:`aeat.domain.sync.WireFilingHistory`
            payload, or ``None`` when no envelope is persisted.

        Raises:
            :exc:`aeat.adapters.persistence.storage.errors.ClassificationError`:
                When the on-disk envelope's class is not ``AUDIT``.
            :exc:`aeat.adapters.persistence.storage.errors.EnvelopeVersionError`:
                When the envelope schema version is higher than this
                consumer supports.
        """
        target = self.envelope_path_for(modelo)
        if not target.exists():
            return None
        envelope = load_encrypted_envelope(
            target,
            Envelope[WireFilingHistory],
            expected_class=SensitivityClass.AUDIT,
            master_key_provider=_resolve_master_key_provider(),
            hkdf_context=_HKDF_CONTEXT_FILING_HISTORY,
            max_supported_version=_HISTORY_ENVELOPE_VERSION,
        )
        return envelope.payload

    def save(self, modelo: str, history: WireFilingHistory) -> None:
        """Persist ``history`` for ``modelo`` atomically under the per-modelo lock.

        The on-disk envelope is AES-256-GCM ciphertext at
        :attr:`aeat.adapters.persistence.storage.SensitivityClass.AUDIT`
        — no plaintext filing-state row lands on disk.

        Args:
            modelo: Modelo identifier (e.g. ``"130"``).
            history: The :class:`aeat.domain.sync.WireFilingHistory`
                payload to persist.
        """
        safe_repository_id(modelo, context="modelo")
        self._store_dir.mkdir(parents=True, exist_ok=True)
        try:
            with exclusive_file_lock(self.lock_target_for(modelo)):
                envelope = Envelope[WireFilingHistory](
                    schema_version=_HISTORY_ENVELOPE_VERSION,
                    written_at=datetime.now(UTC),
                    classification=SensitivityClass.AUDIT,
                    payload=history,
                )
                save_encrypted_envelope(
                    envelope,
                    self.envelope_path_for(modelo),
                    master_key_provider=_resolve_master_key_provider(),
                    hkdf_context=_HKDF_CONTEXT_FILING_HISTORY,
                )
        except OSError:
            _log.error("failed to save filing history modelo=%s", modelo, exc_info=True)
            raise
        _log.debug("saved filing history modelo=%s", modelo)

    def delete(self, modelo: str) -> bool:
        """Remove the filing-history envelope for ``modelo``.

        Args:
            modelo: Modelo identifier (e.g. ``"130"``).

        Returns:
            ``True`` when the envelope was deleted, ``False`` when no
            envelope existed.
        """
        target = self.envelope_path_for(modelo)
        if not self._store_dir.exists():
            return False
        try:
            with exclusive_file_lock(self.lock_target_for(modelo)):
                if not target.exists():
                    return False
                target.unlink()
        except OSError:
            _log.error("failed to delete filing history modelo=%s", modelo, exc_info=True)
            raise
        _log.info("deleted filing history modelo=%s", modelo)
        return True

    def list_modelos(self) -> tuple[str, ...]:
        """Return every modelo persisted in this repository, sorted."""
        if not self._store_dir.exists():
            return ()
        ids: list[str] = []
        for path in self._store_dir.iterdir():
            if not path.is_file():
                continue
            name = path.name
            if not name.endswith(_HISTORY_ENVELOPE_SUFFIX):
                continue
            modelo = name[: -len(_HISTORY_ENVELOPE_SUFFIX)]
            if not modelo:
                continue
            ids.append(modelo)
        ids.sort()
        return tuple(ids)

    def iter_histories(self) -> Iterator[tuple[str, WireFilingHistory]]:
        """Yield ``(modelo, history)`` tuples for every persisted modelo."""
        for modelo in self.list_modelos():
            payload = self.load(modelo)
            if payload is None:
                _log.debug("iter_histories: envelope for modelo=%s returned no payload; skipping", modelo)
                continue
            yield modelo, payload


def migrate_legacy_filing_history_to_repository(
    legacy_dir: Path,
    *,
    repository: FilingHistoryRepository,
    overwrite: bool = False,
) -> HistoryMigrationSummary:
    """Move legacy plaintext filing-history JSONs into the encrypted repository.

    The legacy filing-history store wrote each modelo's history as
    ``<modelo>.json`` containing the JSON serialisation of one
    :class:`aeat.domain.sync.WireFilingHistory`. This helper reads
    every such file in ``legacy_dir`` and persists each through the
    repository under
    :attr:`aeat.adapters.persistence.storage.SensitivityClass.AUDIT`.

    Sub-directories (notably ``pages/``, which carries archived HTML
    detail pages owned by a different subsystem) are skipped via the
    ``is_file`` guard.

    Args:
        legacy_dir: Source directory containing legacy
            ``<modelo>.json`` files.
        repository: Destination :class:`FilingHistoryRepository`.
        overwrite: When ``True``, replaces any modelo's history
            already persisted in the repository. When ``False``
            (default), already-persisted modelos are counted under
            :attr:`HistoryMigrationSummary.skipped`.

    Returns:
        A frozen :class:`HistoryMigrationSummary`.

    Raises:
        FileNotFoundError: When ``legacy_dir`` does not exist.
        NotADirectoryError: When ``legacy_dir`` is not a directory.
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
        if path.name.endswith(_HISTORY_ENVELOPE_SUFFIX):
            continue
        # Filename is <modelo>.json — derive modelo from the stem.
        modelo = path.stem
        try:
            history = WireFilingHistory.model_validate_json(path.read_text(encoding="utf-8"))
        except (ValidationError, OSError):
            _log.warning("skipping unreadable legacy filing history %s", path, exc_info=True)
            errors += 1
            continue
        try:
            safe_repository_id(modelo, context="modelo")
        except ValueError:
            _log.warning("skipping unsafe modelo filename %s", path, exc_info=True)
            errors += 1
            continue
        try:
            with exclusive_file_lock(repository.lock_target_for(modelo)):
                target = repository.envelope_path_for(modelo)
                if not overwrite and target.exists():
                    skipped += 1
                    continue
                envelope = Envelope[WireFilingHistory](
                    schema_version=_HISTORY_ENVELOPE_VERSION,
                    written_at=datetime.now(UTC),
                    classification=SensitivityClass.AUDIT,
                    payload=history,
                )
                save_encrypted_envelope(
                    envelope,
                    target,
                    master_key_provider=_resolve_master_key_provider(),
                    hkdf_context=_HKDF_CONTEXT_FILING_HISTORY,
                )
                imported += 1
        except OSError:
            _log.error("failed to migrate filing history for modelo=%s path=%s", modelo, path, exc_info=True)
            errors += 1
            continue
    _log.info(
        "migrated legacy filing history from %s into %s: imported=%d skipped=%d errors=%d",
        legacy_dir,
        repository.store_dir,
        imported,
        skipped,
        errors,
    )
    return HistoryMigrationSummary(
        imported=imported,
        skipped=skipped,
        errors=errors,
        store_dir=str(repository.store_dir.resolve()),
    )


__all__ = [
    "ClassificationError",
    "EnvelopeVersionError",
    "FilingHistoryRepository",
    "HistoryMigrationSummary",
    "migrate_legacy_filing_history_to_repository",
]
