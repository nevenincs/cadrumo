"""Generic SQL-backed :class:`Envelope` repository built on :class:`SecureObjectRepository`.

The 8 domain repositories that wrap :class:`SecureObjectRepository`
(filing drafts, submissions, filing history, complementaria,
justificantes, observations, assets, inventory) all share the same
boilerplate: namespace + sensitivity + schema-version + Pydantic payload
type + a function that extracts the natural id from the payload.

This module provides :class:`SecureBoundRepository`, a generic base
class that captures that shared shape exactly once. Concrete subclasses
override the four class-level descriptors (`namespace`, `payload_type`,
`sensitivity`, `schema_version`) and implement `extract_identifier`;
they inherit `envelope_path_for`, `lock_target_for`, `load`, `save`,
`delete`, `iter_ids`, and `iter_records` for free.

The base class does NOT replace :class:`SecureObjectRepository`; it
composes one.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar, cast

from pydantic import BaseModel

from .....core.classification import SensitivityClass
from .....core.config import Settings
from .....core.logging import get_logger
from .....core.time import now
from .._path_safety import safe_repository_id
from ..errors import ClassificationError, EnvelopeVersionError, RepositorySetupError
from ..runtime_repository import (
    secure_object_repository_for_active_bucket_or_default_route,
    secure_object_repository_for_bucket,
)
from ..sql import SecureObjectRepository
from ._envelope import Envelope

_log = get_logger(__name__)


def _active_bucket_objects_or_default(settings: Settings | None = None) -> SecureObjectRepository:
    """Return active-bucket storage when selected, otherwise the process default.

    When an active profile bucket is available the repository is backed by
    the bucket's own encrypted database, resolved through
    :func:`~aeat.adapters.persistence.storage.runtime_repository.secure_object_repository_for_active_bucket_or_default_route`
    so the URL is derived from the live bucket path rather than the
    settings-override snapshot captured at test-fixture construction time.
    A missing active bucket uses the process-default route for explicit
    test harnesses and bootstrap-adjacent callers. Once a bucket is
    selected, route/session failures are not swallowed.
    """
    return secure_object_repository_for_active_bucket_or_default_route(settings)


class SecureBoundRepository[T: BaseModel]:
    """Generic repository over encrypted SQL-backed envelopes for one payload type.

    Subclasses MUST set class attributes:

    - :attr:`namespace`: the :class:`SecureObjectRepository` namespace
      string for this payload family (e.g. ``"aeat.domain.filing.drafts"``).
    - :attr:`payload_type`: the typed Pydantic model class wrapped by the
      envelope.
    - :attr:`sensitivity`: the :class:`SensitivityClass` that every row
      in this namespace MUST carry; mismatches raise
      :class:`ClassificationError`.
    - :attr:`schema_version`: the current envelope schema version this
      consumer expects; rows whose version differs from it raise
      :class:`EnvelopeVersionError`.

    Subclasses MUST implement :meth:`extract_identifier` so that
    :meth:`save` and :meth:`iter_ids` can recover the natural id from
    the decrypted payload.
    """

    namespace: ClassVar[str]
    sensitivity: ClassVar[SensitivityClass]
    schema_version: ClassVar[int]
    payload_type: ClassVar[type[BaseModel]]

    def __init__(
        self,
        *,
        bucket_id: str | None = None,
        objects: SecureObjectRepository | None = None,
        settings: Settings | None = None,
    ) -> None:
        if objects is not None:
            self._objects = objects
        elif bucket_id is not None:
            self._objects = secure_object_repository_for_bucket(
                safe_repository_id(bucket_id, context="bucket_id"),
                settings,
            )
        else:
            self._objects = _active_bucket_objects_or_default(settings)
        cls = type(self)
        for attr in ("namespace", "sensitivity", "schema_version"):
            if not hasattr(cls, attr) or getattr(cls, attr, None) is None:
                raise RepositorySetupError(
                    f"{cls.__name__} must set class attribute {attr!r} before instantiating SecureBoundRepository",
                )
        cls.payload_model()

    # ------------------------------------------------------------------
    # Subclass extension point
    # ------------------------------------------------------------------

    def extract_identifier(self, payload: T) -> str:
        """Return the natural id for ``payload`` (used as the SQL object key).

        Subclasses MUST override. The base implementation raises
        :class:`NotImplementedError`.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must override extract_identifier()",
        )

    @classmethod
    def payload_model(cls) -> type[T]:
        """Return the concrete Pydantic payload model for this repository."""
        payload_type = getattr(cls, "payload_type", None)
        if payload_type is None:
            raise RepositorySetupError(
                f"{cls.__name__} must set class attribute 'payload_type' or override payload_model()",
            )
        return cast(type[T], payload_type)  # CAST-RATIONALE-SECURE-REPOSITORY-PAYLOAD-MODEL

    # ------------------------------------------------------------------
    # Logical path markers (diagnostic surface only)
    # ------------------------------------------------------------------

    @property
    def store_dir(self) -> Path:
        """Return a logical backend marker for diagnostic CLI output."""
        return Path("db://secure_objects") / self.namespace

    def envelope_path_for(self, identifier: str) -> Path:
        """Return a logical path marker for ``identifier``."""
        safe_repository_id(identifier, context="identifier")
        return self.store_dir / identifier

    def lock_target_for(self, identifier: str) -> Path:
        """Return a logical lock-target marker for ``identifier``.

        SQL transactions govern actual write atomicity; this is only
        surfaced for diagnostic parity with file-backed repositories.
        """
        safe_repository_id(identifier, context="identifier")
        return self.store_dir / f"{identifier}.lock"

    @property
    def secure_object_repository(self) -> SecureObjectRepository:
        """Return the concrete :class:`SecureObjectRepository` backing this logical repository."""
        return self._objects

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def load(self, identifier: str) -> T | None:
        """Return the persisted payload or ``None`` if absent."""
        safe_repository_id(identifier, context="identifier")
        record = self._objects.load(
            self.namespace,
            identifier,
            expected_class=self.sensitivity,
            max_supported_version=self.schema_version,
        )
        if record is None:
            return None
        envelope = self._envelope_cls().model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not self.sensitivity:
            raise ClassificationError(
                f"{self.namespace}/{identifier} has classification "
                f"{envelope.classification}; consumer expected {self.sensitivity}",
            )
        if envelope.schema_version != self.schema_version:
            raise EnvelopeVersionError(
                f"{self.namespace}/{identifier} is at version "
                f"{envelope.schema_version}; consumer expects "
                f"{self.schema_version}",
            )
        # Safe: _envelope_cls() returns Envelope[self.payload_model()] which equals
        # Envelope[T] for this repository's concrete T. Pydantic's model_validate_json
        # has already validated payload against the T schema, so the runtime type
        # of envelope.payload IS T. The cast bridges the ClassVar[type[BaseModel]]
        # declaration (required for cross-subclass compatibility) to the generic T
        # visible to type checkers at the call site. Future improvement: replace the
        # ClassVar[type[BaseModel]] fallback with explicit payload_model() overrides
        # to eliminate this cast entirely (see: CAST-RATIONALE-SECURE-REPOSITORY-LOAD).
        return cast(T, envelope.payload)  # CAST-RATIONALE-SECURE-REPOSITORY-LOAD

    def save(self, payload: T) -> None:
        """Persist ``payload`` as an encrypted envelope row.

        The natural id is recovered from the payload via
        :meth:`extract_identifier`.
        """
        identifier = self.extract_identifier(payload)
        safe_repository_id(identifier, context="identifier")
        envelope = self._envelope_cls()(
            schema_version=self.schema_version,
            written_at=now(),
            classification=self.sensitivity,
            payload=payload,
        )
        self._objects.save(
            namespace=self.namespace,
            object_key=identifier,
            classification=self.sensitivity,
            schema_version=self.schema_version,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )
        _log.debug(
            "secure-bound: saved %s/%s",
            self.namespace,
            identifier,
        )

    def delete(self, identifier: str) -> bool:
        """Remove the row for ``identifier``; return whether a row was deleted."""
        safe_repository_id(identifier, context="identifier")
        deleted = self._objects.delete(self.namespace, identifier)
        if deleted:
            _log.debug("secure-bound: deleted %s/%s", self.namespace, identifier)
        return deleted

    # ------------------------------------------------------------------
    # Enumeration
    # ------------------------------------------------------------------

    def iter_ids(self) -> Iterator[str]:
        """Yield every persisted identifier in storage order.

        Order is the secure-object storage order (the ``object_key`` digest
        order), not the natural-id order: a caller that needs a specific
        order sorts the result itself. Streams one identifier at a time
        rather than buffering and sorting the whole namespace in memory.

        Fail-closed: :meth:`SecureObjectRepository.list_records` scans the
        whole namespace and raises ``SecureObjectUnreadableError`` if any row
        is unreadable, so a full consumption (``tuple(...)``) never yields a
        readable subset past a corrupt row.
        """
        envelope_cls = self._envelope_cls()
        for record in self._objects.list_records(
            self.namespace,
            expected_class=self.sensitivity,
            max_supported_version=self.schema_version,
        ):
            envelope = envelope_cls.model_validate_json(record.payload.decode("utf-8"))
            if envelope.classification is not self.sensitivity:
                raise ClassificationError(
                    f"{self.namespace} iterator row has classification "
                    f"{envelope.classification}; consumer expected {self.sensitivity}",
                )
            if envelope.schema_version != self.schema_version:
                raise EnvelopeVersionError(
                    f"{self.namespace} iterator row is at version "
                    f"{envelope.schema_version}; consumer expects {self.schema_version}",
                )
            # Safe: same rationale as the load() path — envelope was validated by
            # model_validate_json against Envelope[self.payload_type] == Envelope[T].
            # Future improvement: eliminate via generic ClassVar alias
            # (see: CAST-RATIONALE-SECURE-REPOSITORY-ITER).
            yield self.extract_identifier(cast(T, envelope.payload))  # CAST-RATIONALE-SECURE-REPOSITORY-ITER

    def iter_records(self) -> Iterator[T]:
        """Yield every persisted payload in storage order.

        Streams each payload straight from
        :meth:`~aeat.adapters.persistence.storage.sql.SecureObjectRepository.list_records`
        without buffering the whole namespace or sorting it in memory. Order
        is storage-defined (the ``object_key`` digest order), not the
        natural-id order; a caller that needs a specific order sorts the
        result itself.

        Parses each row's decrypted payload bytes directly from
        ``list_records`` rather than routing through :meth:`load`.  The SQL
        ``WHERE object_key = ?`` lookup inside :meth:`load` cannot
        match the stored ciphertext when ``object_key`` is an
        ``EncryptedString`` column (AES-256-GCM uses a random nonce, so
        the bind-parameter ciphertext differs from the stored ciphertext
        every time).  Iterating directly over the decrypted rows is the
        correct pattern for full-scan enumeration.

        Fail-closed: ``list_records`` scans the whole namespace and raises
        ``SecureObjectUnreadableError`` if any row is unreadable before this
        generator yields a readable subset on full consumption.
        """
        envelope_cls = self._envelope_cls()
        for record in self._objects.list_records(
            self.namespace,
            expected_class=self.sensitivity,
            max_supported_version=self.schema_version,
        ):
            envelope = envelope_cls.model_validate_json(record.payload.decode("utf-8"))
            if envelope.classification is not self.sensitivity:
                raise ClassificationError(
                    f"{self.namespace} iterator row has classification "
                    f"{envelope.classification}; consumer expected {self.sensitivity}",
                )
            if envelope.schema_version != self.schema_version:
                raise EnvelopeVersionError(
                    f"{self.namespace} iterator row is at version "
                    f"{envelope.schema_version}; consumer expects {self.schema_version}",
                )
            yield cast(T, envelope.payload)  # CAST-RATIONALE-SECURE-REPOSITORY-ITER

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _envelope_cls(self) -> type[Envelope[BaseModel]]:
        """Return the parameterised ``Envelope[payload_type]`` class.

        Delegates to :meth:`Envelope.for_payload_type` which encapsulates the
        typed generic parameterisation. The return type is widened to
        ``Envelope[BaseModel]`` because the method signature must be invariant
        across all concrete subclasses (which each supply a different ``T``).
        """
        # The widening to Envelope[BaseModel] is the only remaining escape hatch
        # here. Envelope.for_payload_type returns type[Envelope[self.payload_model()]];
        # the mismatch is between the invariant return annotation and the
        # covariant usage at call sites. Safe at runtime because Pydantic enforces
        # the concrete type during model_validate_json.
        # CAST-RATIONALE-SECURE-REPOSITORY-ENVCLS (future: eliminate via generic ClassVar alias)
        return Envelope.for_payload_type(self.payload_model())  # type: ignore[return-value]


__all__ = ["SecureBoundRepository"]
