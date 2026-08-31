"""Encrypted persistence adapter for Modelo edit mutation result receipts.

:class:`ModeloEditReceiptRepository` persists one
:class:`~application.modelo._edit_models.ModeloEditMutationResultReceiptV1` per encrypted
row, keyed by its own content-addressed ``receipt_id``, through
:class:`~adapters.persistence.storage.SecureBoundRepository` at ``FINANCIAL``
:class:`~adapters.persistence.storage.SensitivityClass`. Each receipt is its
own row rather than one whole-catalogue singleton blob, so a lookup by
``receipt_id`` is one atomic encrypted-SQL read -- the domain proof a guarded
compare-and-swap edit committed must be recoverable after a crash without
decrypting every receipt a bucket has ever produced.

See Also:
    :class:`~application.modelo._edit_models.ModeloEditMutationResultReceiptV1`
        The strict receipt payload this repository stores.
    :data:`~adapters.persistence.storage.MODELO_EDIT_RECEIPT_NAMESPACE`
        Central namespace, sensitivity, and schema-version contract for these
        secure objects.
    :class:`~adapters.persistence.storage.SecureBoundRepository`
        Shared per-record Envelope-wrapped encrypted repository kernel this
        class binds to one payload family; exposes ``to_secure_object_write``
        for the guarded co-commit the calculation-revision persistence writer
        composes this repository into.
"""

from __future__ import annotations

from typing import override

from ....application.modelo.edit_contract import ModeloEditMutationResultReceiptV1
from ..storage.envelope._secure_repository import SecureBoundRepository
from ..storage.secure_object_namespaces import MODELO_EDIT_RECEIPT_NAMESPACE


class ModeloEditReceiptRepository(SecureBoundRepository[ModeloEditMutationResultReceiptV1]):
    """Store one bucket's Modelo edit mutation result receipts, one row each."""

    namespace = MODELO_EDIT_RECEIPT_NAMESPACE.namespace
    sensitivity = MODELO_EDIT_RECEIPT_NAMESPACE.sensitivity
    schema_version = MODELO_EDIT_RECEIPT_NAMESPACE.schema_version
    payload_type = ModeloEditMutationResultReceiptV1

    @override
    def extract_identifier(self, payload: ModeloEditMutationResultReceiptV1) -> str:
        """Return the receipt's own content-addressed identity."""
        return payload.receipt_id


__all__ = ["ModeloEditReceiptRepository"]
