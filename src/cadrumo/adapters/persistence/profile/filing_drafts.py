"""Governed-persistence repository for filing drafts.

:class:`~domain.filing.ModeloDraft` records carry exact casilla
arithmetic and tax due values. They are stored as encrypted byte objects via
:class:`~adapters.persistence.storage.SecureObjectRepository` at
``FINANCIAL`` :class:`~adapters.persistence.storage.SensitivityClass` and
serialised through an :class:`~adapters.persistence.storage.Envelope` by
:class:`~adapters.persistence.storage.SecureBoundRepository`; no plaintext
draft JSON or envelope file lands on disk.

This concrete repository is the persistence adapter behind the
:class:`~domain.filing.ModeloDraftRepositoryProtocol` port. It lives in
the persistence adapter (not in :mod:`domain.filing`) because its
:class:`~adapters.persistence.storage.SecureBoundRepository` base is
SQL/crypto-coupled; the domain package owns only the typed
:class:`~domain.filing.ModeloDraft` payload and the narrow read/save
port that domain-facing service code depends on.

See Also:
    :class:`~domain.filing.ModeloDraft`
        Strict filing payload persisted by this repository.
    :class:`~adapters.persistence.storage.SecureBoundRepository`
        Generic encrypted-envelope repository base used for the draft store.
    :data:`adapters.persistence.storage.FILING_DRAFTS_NAMESPACE`
        Namespace, sensitivity, schema-version, object-key, and custody
        contract for draft secure objects.
    :mod:`application.filing`
        Application review flow that reads and updates persisted drafts.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, ClassVar, override

from ....core.classification.policies import SensitivityClass
from ....domain.filing.errors import FilingValidationError
from ....domain.filing.schema import ModeloDraft, compute_modelo_draft_id
from ..storage.envelope._secure_repository import SecureBoundRepository
from ..storage.runtime_repository import secure_object_repository_for_bucket
from ..storage.secure_object_namespaces import FILING_DRAFTS_NAMESPACE
from ..storage.sql import SecureObjectWrite
from ._filing_runtime import resolve_filing_repository_bucket_id

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ..storage.sql import SecureObjectRepository


class ModeloDraftRepository(SecureBoundRepository[ModeloDraft]):
    """Encrypted FINANCIAL repository for :class:`~domain.filing.ModeloDraft` payloads.

    The :class:`~adapters.persistence.storage.SecureBoundRepository`
    base wraps each draft in an
    :class:`~adapters.persistence.storage.Envelope` and writes it under
    :data:`adapters.persistence.storage.FILING_DRAFTS_NAMESPACE`. The
    draft id is the natural key, so list and iteration APIs expose draft
    aggregates rather than submission or amendment records. The namespace
    definition supplies the ``FINANCIAL``
    :class:`~adapters.persistence.storage.SensitivityClass`, schema
    version, object-key grammar, and custody contract.
    """

    # namespace/sensitivity/schema_version sourced from the sole registry authority
    namespace: ClassVar[str] = FILING_DRAFTS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = FILING_DRAFTS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = FILING_DRAFTS_NAMESPACE.schema_version

    def __init__(self, *, bucket_id: str | None = None, objects: SecureObjectRepository | None = None) -> None:
        """Bind the repository to a bucket, or to an explicit secure-object store for tests."""
        self._bucket_id = bucket_id.strip() if bucket_id is not None else None
        if objects is None:
            self._bucket_id = resolve_filing_repository_bucket_id(bucket_id)
            objects = secure_object_repository_for_bucket(self._bucket_id)
        super().__init__(objects=objects)

    @override
    @classmethod
    def payload_model(cls) -> type[ModeloDraft]:
        """Return the :class:`~domain.filing.ModeloDraft` encrypted payload model for filing drafts."""
        return ModeloDraft

    @property
    def bucket_id(self) -> str | None:
        """Return the profile bucket id when this repository resolved one."""
        return self._bucket_id

    @override
    def extract_identifier(self, payload: ModeloDraft) -> str:
        return payload.draft_id

    @override
    def save(self, payload: ModeloDraft) -> None:
        """Persist ``payload`` after confirming ``draft_id`` is its content address.

        :attr:`~domain.filing.ModeloDraft.draft_id` is documented as a hash over
        the draft's modelo, period, taxpayer, registry snapshot, casilla values,
        and binding values, and
        :func:`~domain.filing.compute_modelo_draft_id` is its sole canonical
        derivation — but nothing recomputed it, so an arbitrary, blank,
        whitespace, or stale id was persisted and reloaded unchanged and a
        stored draft could claim an identity that was not its own content. Two
        different drafts could then occupy one row, or one draft two rows.

        The check lives here rather than on the model because the id is a
        *durable* claim: an in-memory draft may legitimately carry a
        caller-chosen handle while its content is still being assembled, but
        once written it is the natural key this repository files it under and
        every later reader resolves it by.

        Args:
            payload: The :class:`ModeloDraft` aggregate to persist under its
                own content-addressed ``draft_id``.

        Raises:
            FilingValidationError: ``draft_id`` is not the content address the
                canonical helper derives for this draft.
        """
        self._validate_durable_content_address(payload)
        identifier, envelope = self._identified_envelope(payload)
        self._objects.save(
            namespace=self.namespace,
            object_key=identifier,
            classification=self.sensitivity,
            schema_version=self.schema_version,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json(
                context={"secure_modelo_binding_value": True},
            ).encode("utf-8"),
        )

    @staticmethod
    def _validate_durable_content_address(payload: ModeloDraft) -> None:
        """Refuse a draft whose durable identifier is not its content address."""
        derived = compute_modelo_draft_id(
            modelo=payload.modelo,
            period=payload.period,
            profile_tax_id=payload.profile_tax_id,
            snapshot_ref=payload.snapshot_ref,
            values=payload.values,
            binding_values=payload.binding_values,
        )
        if payload.draft_id != derived:
            raise FilingValidationError(
                f"refusing to persist draft_id {payload.draft_id!r}: it is not this draft's content "
                f"address; compute_modelo_draft_id derives {derived!r} from (modelo={payload.modelo!r}, "
                f"period={payload.period!r}, profile_tax_id={payload.profile_tax_id!r}, "
                f"snapshot_ref={payload.snapshot_ref.revision_id!r}, {len(payload.values)} values, "
                f"{len(payload.binding_values)} binding values)",
            )

    @override
    def to_secure_object_write(
        self,
        payload: ModeloDraft,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        """Prepare the same identity-preserving encrypted payload as :meth:`save`."""
        self._validate_durable_content_address(payload)
        identifier, envelope = self._identified_envelope(payload)
        return SecureObjectWrite(
            namespace=self.namespace,
            object_key=identifier,
            classification=self.sensitivity,
            schema_version=self.schema_version,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json(
                context={"secure_modelo_binding_value": True},
            ).encode("utf-8"),
            expected_revision_id=expected_revision_id,
        )

    def list_draft_ids(self) -> tuple[str, ...]:
        """Return every draft id persisted in this repository, in lexicographic order."""
        return tuple(sorted(self.iter_ids()))

    def iter_drafts(self) -> Iterator[ModeloDraft]:
        """Yield every persisted :class:`~domain.filing.ModeloDraft`, in lexicographic id order."""
        return iter(sorted(self.iter_records(), key=self.extract_identifier))


__all__ = [
    "ModeloDraftRepository",
]
