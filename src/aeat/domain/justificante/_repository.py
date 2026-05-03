"""Governed-persistence repository for parsed-justificante metadata.

Wraps the storage substrate's :class:`Envelope[Justificante]` contract
behind a small typed surface (:class:`JustificanteRepository`) that the
justificante parser and any future consumer can call. Each parsed
justificante's metadata is persisted as its own envelope file
(``<csv>.envelope.json``) under a caller-supplied store directory with
a per-record :func:`~aeat.adapters.persistence.storage.exclusive_file_lock`.

Sensitivity classification: the metadata captures the AEAT-assigned
CSV, the operator's NIF, the ``presented_at`` timestamp, and the
verification URL — auditable evidence with identity-bearing context,
hence :attr:`~aeat.adapters.persistence.storage.SensitivityClass.AUDIT`.

Out of scope: the PDF blob itself remains in
:attr:`aeat.core.config.AeatSettings.aeat_justificantes_dir` (operator-class
legal proof; the substrate already handles encrypted blobs via
:class:`aeat.adapters.persistence.storage.EncryptedBlobStore`). This
repository persists only the *parsed metadata* — so the CSV, NIF, and
URL pass through the classification gate at load time even when the
PDF is not co-located with the metadata.
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
from ._schema import Justificante

_HKDF_CONTEXT_JUSTIFICANTE = b"aeat.domain.justificante.metadata.v1"

_log = get_logger(__name__)

_JUSTIFICANTE_ENVELOPE_VERSION = 1
_JUSTIFICANTE_ENVELOPE_SUFFIX = ".envelope.json"
_JUSTIFICANTE_LOCK_SUFFIX = ".lock"


class JustificanteMigrationSummary(BaseModel):
    """Frozen summary of one :func:`migrate_legacy_justificantes_to_repository` call.

    Attributes:
        imported: Number of legacy metadata records persisted.
        skipped: Number already present in the destination repository.
        errors: Number of legacy files the helper could not parse.
        store_dir: Resolved path to the repository's store directory.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    imported: int = Field(ge=0)
    skipped: int = Field(ge=0)
    errors: int = Field(default=0, ge=0)
    store_dir: str


class JustificanteRepository:
    """Repository over the per-record, file-locked, envelope-backed store.

    Each justificante's parsed metadata is stored as its own
    encrypted-envelope file keyed by its
    :attr:`~aeat.domain.justificante.Justificante.csv` identifier under
    a single :attr:`store_dir`.
    """

    def __init__(self, *, store_dir: Path) -> None:
        """Bind the repository to a store directory.

        Args:
            store_dir: Directory where the per-record envelope files
                and lock sidecars live. Created on first write.
        """
        self._store_dir = Path(store_dir)

    @property
    def store_dir(self) -> Path:
        """Return the bound store directory."""
        return self._store_dir

    def envelope_path_for(self, csv: str) -> Path:
        """Return the canonical envelope path for a justificante CSV.

        Args:
            csv: Código Seguro de Verificación that keys the record.

        Returns:
            The fully-qualified path to the per-record envelope file.
        """
        safe_repository_id(csv, context="csv")
        return self._store_dir / f"{csv}{_JUSTIFICANTE_ENVELOPE_SUFFIX}"

    def lock_target_for(self, csv: str) -> Path:
        """Return the canonical lock-sidecar path for a justificante CSV.

        Args:
            csv: Código Seguro de Verificación that keys the record.

        Returns:
            The fully-qualified path to the per-record lock sidecar.
        """
        safe_repository_id(csv, context="csv")
        return self._store_dir / f"{csv}{_JUSTIFICANTE_LOCK_SUFFIX}"

    def load(self, csv: str) -> Justificante | None:
        """Return the persisted justificante metadata or ``None`` if absent.

        Args:
            csv: Código Seguro de Verificación to load.

        Returns:
            The deserialised :class:`~aeat.domain.justificante.Justificante`,
            or ``None`` when no envelope exists for ``csv``.

        Raises:
            :exc:`aeat.adapters.persistence.storage.errors.ClassificationError`:
                If the on-disk envelope's classification is not
                :attr:`~aeat.adapters.persistence.storage.SensitivityClass.AUDIT`.
            :exc:`aeat.adapters.persistence.storage.errors.EnvelopeVersionError`:
                If the envelope schema version is higher than the
                consumer supports.
        """
        target = self.envelope_path_for(csv)
        if not target.exists():
            return None
        envelope = load_encrypted_envelope(
            target,
            Envelope[Justificante],
            expected_class=SensitivityClass.AUDIT,
            master_key_provider=_resolve_master_key_provider(),
            hkdf_context=_HKDF_CONTEXT_JUSTIFICANTE,
            max_supported_version=_JUSTIFICANTE_ENVELOPE_VERSION,
        )
        return envelope.payload

    def save(self, justificante: Justificante) -> None:
        """Persist ``justificante`` atomically under its per-record file lock.

        The on-disk envelope is AES-256-GCM ciphertext at the
        :attr:`~aeat.adapters.persistence.storage.SensitivityClass.AUDIT`
        classification — no plaintext NIF, CSV, or verification URL
        lands on disk.

        Args:
            justificante: The :class:`~aeat.domain.justificante.Justificante`
                metadata record to persist.
        """
        self._store_dir.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_target_for(justificante.csv)):
            envelope = Envelope[Justificante](
                schema_version=_JUSTIFICANTE_ENVELOPE_VERSION,
                written_at=datetime.now(UTC),
                classification=SensitivityClass.AUDIT,
                payload=justificante,
            )
            save_encrypted_envelope(
                envelope,
                self.envelope_path_for(justificante.csv),
                master_key_provider=_resolve_master_key_provider(),
                hkdf_context=_HKDF_CONTEXT_JUSTIFICANTE,
            )
        _log.debug("saved justificante metadata for csv=%s", justificante.csv)

    def delete(self, csv: str) -> bool:
        """Remove the metadata envelope for ``csv``.

        Args:
            csv: Código Seguro de Verificación to delete.

        Returns:
            ``True`` if a record was removed; ``False`` if the store
            directory is missing or no envelope existed for ``csv``.
        """
        target = self.envelope_path_for(csv)
        if not self._store_dir.exists():
            return False
        with exclusive_file_lock(self.lock_target_for(csv)):
            if not target.exists():
                return False
            target.unlink()
        _log.debug("deleted justificante metadata for csv=%s", csv)
        return True

    def list_csvs(self) -> tuple[str, ...]:
        """Return every justificante CSV persisted in this repository.

        Returns:
            A lexicographically-sorted tuple of every Código Seguro de
            Verificación currently materialised in :attr:`store_dir`.
        """
        if not self._store_dir.exists():
            return ()
        ids: list[str] = []
        for path in self._store_dir.iterdir():
            if not path.is_file():
                continue
            name = path.name
            if not name.endswith(_JUSTIFICANTE_ENVELOPE_SUFFIX):
                continue
            csv = name[: -len(_JUSTIFICANTE_ENVELOPE_SUFFIX)]
            if not csv:
                continue
            ids.append(csv)
        ids.sort()
        return tuple(ids)

    def iter_justificantes(self) -> Iterator[Justificante]:
        """Yield every persisted justificante, in lexicographic CSV order.

        Yields:
            Each loaded :class:`~aeat.domain.justificante.Justificante`
            record. CSVs whose envelopes have vanished between the
            initial listing and the per-record load are silently
            skipped.
        """
        for csv in self.list_csvs():
            payload = self.load(csv)
            if payload is not None:
                yield payload


# TODO: remove after 2026-10-27 retention window.
def migrate_legacy_justificantes_to_repository(
    legacy_dir: Path,
    *,
    repository: JustificanteRepository,
    overwrite: bool = False,
) -> JustificanteMigrationSummary:
    """Move legacy plaintext justificante-metadata JSONs into the repository.

    Args:
        legacy_dir: Source directory containing legacy
            ``<csv>.json`` files (each is a JSON-serialised
            :class:`Justificante`).
        repository: Destination repository.
        overwrite: When ``True``, replaces any record already
            persisted in the repository. When ``False`` (default),
            already-persisted records are counted under ``skipped``.

    Returns:
        A frozen :class:`JustificanteMigrationSummary`.

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
        if path.name.endswith(_JUSTIFICANTE_ENVELOPE_SUFFIX):
            continue
        try:
            justificante = Justificante.model_validate_json(path.read_text(encoding="utf-8"))
        except (ValidationError, OSError):
            _log.warning("skipping unreadable legacy justificante %s", path, exc_info=True)
            errors += 1
            continue
        with exclusive_file_lock(repository.lock_target_for(justificante.csv)):
            target = repository.envelope_path_for(justificante.csv)
            if not overwrite and target.exists():
                skipped += 1
                continue
            envelope = Envelope[Justificante](
                schema_version=_JUSTIFICANTE_ENVELOPE_VERSION,
                written_at=datetime.now(UTC),
                classification=SensitivityClass.AUDIT,
                payload=justificante,
            )
            save_encrypted_envelope(
                envelope,
                target,
                master_key_provider=_resolve_master_key_provider(),
                hkdf_context=_HKDF_CONTEXT_JUSTIFICANTE,
            )
            imported += 1
    _log.info(
        "migrated legacy justificantes from %s into %s: imported=%d skipped=%d errors=%d",
        legacy_dir,
        repository.store_dir,
        imported,
        skipped,
        errors,
    )
    return JustificanteMigrationSummary(
        imported=imported,
        skipped=skipped,
        errors=errors,
        store_dir=str(repository.store_dir.resolve()),
    )


__all__ = [
    "ClassificationError",
    "EnvelopeVersionError",
    "JustificanteMigrationSummary",
    "JustificanteRepository",
    "migrate_legacy_justificantes_to_repository",
]
