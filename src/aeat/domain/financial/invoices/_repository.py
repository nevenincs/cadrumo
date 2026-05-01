"""Governed-persistence repository for the invoice catalogue.

Wraps the substrate's :class:`Envelope[InvoiceCatalogue]` contract
behind a small, typed surface. Every read consults the envelope file
first; every write goes through ``save_encrypted_envelope`` at the
FINANCIAL sensitivity classification with an exclusive file lock for
the duration so concurrent writers serialise rather than race.

The repository is the only sanctioned read/write path for the invoice
catalogue. There is no plaintext fallback: every CLI command and
downstream consumer routes through this surface so the on-disk record
is always the encrypted envelope.

Storage imports are deferred behind the methods that consult them so
the financial subpackage does not pull ``aeat.storage`` (with its
Alembic plugin discovery) into every CLI command's import chain; this
preserves the json-pipe-safety contract.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ....core.logging import get_logger
from ._models import InvoiceCatalogue

_HKDF_CONTEXT_INVOICE_CATALOGUE = b"aeat.domain.financial.invoices.catalogue.v1"

_log = get_logger(__name__)

_INVOICE_CATALOGUE_VERSION = 1
_INVOICE_ENVELOPE_FILE_NAME = "invoices.envelope.json"
_INVOICE_LOCK_FILE_NAME = "invoices.lock"


class InvoiceCatalogueRepository:
    """Repository over the file-locked, envelope-backed invoice catalogue."""

    def __init__(self, *, store_dir: Path) -> None:
        """Bind the repository to a store directory.

        Args:
            store_dir: Directory containing the envelope file and the
                lock sidecar. Created on first write.
        """
        self._store_dir = Path(store_dir)

    @property
    def envelope_path(self) -> Path:
        """Return the canonical envelope file path."""
        return self._store_dir / _INVOICE_ENVELOPE_FILE_NAME

    @property
    def lock_target(self) -> Path:
        """Return the canonical lock sidecar path."""
        return self._store_dir / _INVOICE_LOCK_FILE_NAME

    def load(self) -> InvoiceCatalogue:
        """Return the persisted catalogue or an empty catalogue if absent.

        Raises:
            ClassificationError: If the on-disk envelope's class is not
                FINANCIAL.
            EnvelopeVersionError: If the envelope schema version is
                higher than the consumer supports.
        """
        from ....adapters.persistence.storage import (
            Envelope,
            SensitivityClass,
            load_encrypted_envelope,
        )
        from ....adapters.persistence.storage._encrypted_columns import _resolve_master_key_provider

        target = self.envelope_path
        if not target.exists():
            return InvoiceCatalogue()
        envelope = load_encrypted_envelope(
            target,
            Envelope[InvoiceCatalogue],
            expected_class=SensitivityClass.FINANCIAL,
            master_key_provider=_resolve_master_key_provider(),
            hkdf_context=_HKDF_CONTEXT_INVOICE_CATALOGUE,
            max_supported_version=_INVOICE_CATALOGUE_VERSION,
        )
        return envelope.payload

    def save(self, catalogue: InvoiceCatalogue) -> None:
        """Persist ``catalogue`` atomically under the file lock.

        The on-disk envelope is AES-256-GCM ciphertext at FINANCIAL
        class via the substrate's ``save_encrypted_envelope`` helper —
        no plaintext invoice row lands on disk.
        """
        from ....adapters.persistence.storage import (
            Envelope,
            SensitivityClass,
            exclusive_file_lock,
            save_encrypted_envelope,
        )
        from ....adapters.persistence.storage._encrypted_columns import _resolve_master_key_provider

        self._store_dir.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_target):
            envelope = Envelope[InvoiceCatalogue](
                schema_version=_INVOICE_CATALOGUE_VERSION,
                written_at=datetime.now(UTC),
                classification=SensitivityClass.FINANCIAL,
                payload=catalogue,
            )
            save_encrypted_envelope(
                envelope,
                self.envelope_path,
                master_key_provider=_resolve_master_key_provider(),
                hkdf_context=_HKDF_CONTEXT_INVOICE_CATALOGUE,
            )


__all__ = [
    "InvoiceCatalogueRepository",
]
