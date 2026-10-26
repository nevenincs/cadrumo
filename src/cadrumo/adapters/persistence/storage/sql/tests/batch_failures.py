"""Own finite fixture projections over real domain and storage kernels."""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from sqlalchemy import bindparam, text

from ......core.classification.policies import SensitivityClass
from ...crypto.encrypted_columns import secure_object_key_digest
from ..orm import SecureObjectRow
from ..secure_object_records import SecureObjectBatchLoadItem
from ..secure_objects import SecureObjectRepository
from ..session import session_scope


def iter_many_with_failures(
    self: SecureObjectRepository,
    namespace: str,
    object_keys: Iterable[str],
    *,
    expected_class: SensitivityClass,
    max_supported_version: int,
) -> Iterator[SecureObjectBatchLoadItem]:
    """Yield readable/unreadable outcomes for requested natural object keys.

    Rows are selected by raw HMAC digests derived from ``object_keys`` and
    returned in stored digest order. Missing keys produce no item, matching
    :meth:`load` returning ``None``. Present rows use the same
    classification, schema-version, AEAD, and revision-lineage checks as
    namespace scans. ``expected_class`` is the :class:`SensitivityClass`
    every yielded row must be classified under; a mismatch fails closed.
    """
    self._check_session_freshness(namespace)
    namespace_definition = self._enforce_registered_read_policy(namespace=namespace, expected_class=expected_class)
    object_key_digests = tuple(dict.fromkeys(secure_object_key_digest(object_key) for object_key in object_keys))
    if not object_key_digests:
        return
    with session_scope(self._engine) as session:
        stmt = (
            text(
                "SELECT id, object_key, classification, schema_version, written_at, payload, revision_id, previous_revision_id, payload_hash, ciphertext_hash, previous_payload_hash FROM secure_objects WHERE namespace = :namespace AND object_key IN :object_keys ORDER BY object_key"
            )
            .bindparams(
                bindparam("namespace", value=namespace),
                bindparam("object_keys", value=object_key_digests, expanding=True),
            )
            .columns(
                id=SecureObjectRow.__table__.c.id.type,
                object_key=SecureObjectRow.__table__.c.object_key.type,
                classification=SecureObjectRow.__table__.c.classification.type,
                schema_version=SecureObjectRow.__table__.c.schema_version.type,
                written_at=SecureObjectRow.__table__.c.written_at.type,
            )
        )
        for raw in session.execute(stmt):
            yield self._list_item_from_raw_row(
                raw,
                namespace=namespace,
                expected_class=expected_class,
                max_supported_version=max_supported_version,
                namespace_definition=namespace_definition,
            )
