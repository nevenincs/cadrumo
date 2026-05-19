"""Generic SQL-backed envelope repository built on :class:`SecureObjectRepository`.

The 8 domain repositories that wrap :class:`SecureObjectRepository`
(filing drafts, submissions, filing history, complementaria,
justificantes, observations, assets, inventory) all share the same
boilerplate: namespace + sensitivity + schema-version + Pydantic payload
type + a function that extracts the natural id from the payload.

This module introduces :class:`SecureBoundRepository`, a generic base
class that captures that shared shape exactly once. Concrete subclasses
override the four class-level descriptors (`namespace`, `payload_type`,
`sensitivity`, `schema_version`) and implement `extract_identifier`;
they inherit `envelope_path_for`, `lock_target_for`, `load`, `save`,
`delete`, `iter_ids`, and `iter_records` for free.

The base class does NOT replace :class:`SecureObjectRepository`; it
composes one. The 8 concrete repositories are migrated to this base
under separate steps.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar, Generic, TypeVar

from pydantic import BaseModel

from .....core.classification import SensitivityClass
from .....core.logging import get_logger
from .._path_safety import safe_repository_id
from ..errors import ClassificationError, EnvelopeVersionError
from ..sql import SecureObjectRepository
from ._envelope import Envelope

_log = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class SecureBoundRepository(Generic[T]):
    """Generic repository over encrypted SQL-backed envelopes for one payload type.

    Subclasses MUST set class attributes:

    - :attr:`namespace`: the :class:`SecureObjectRepository` namespace
      string for this payload family (e.g. ``"aeat.domain.filing.drafts"``).
    - :attr:`payload_type`: the typed Pydantic model class wrapped by the
      envelope.
    - :attr:`sensitivity`: the :class:`SensitivityClass` that every row
      in this namespace MUST carry; mismatches raise
      :class:`ClassificationError`.
    - :attr:`schema_version`: the highest envelope schema version this
      consumer supports; rows whose version exceeds it raise
      :class:`EnvelopeVersionError`.

    Subclasses MUST implement :meth:`extract_identifier` so that
    :meth:`save` and :meth:`iter_ids` can recover the natural id from
    the decrypted payload.
    """

    namespace: ClassVar[str]
    sensitivity: ClassVar[SensitivityClass]
    schema_version: ClassVar[int]
    # ``payload_type`` is also a ClassVar in practice; declared as a
    # plain attribute so subclasses can write
    # ``payload_type: ClassVar[type[ModeloDraft]] = ModeloDraft`` or just
    # assign the concrete class. Marked ClassVar here for clarity.
    payload_type: ClassVar[type[BaseModel]]

    def __init__(self, *, objects: SecureObjectRepository | None = None) -> None:
        self._objects = objects or SecureObjectRepository()
        cls = type(self)
        for attr in ("namespace", "payload_type", "sensitivity", "schema_version"):
            if not hasattr(cls, attr) or getattr(cls, attr, None) is None:
                raise TypeError(
                    f"{cls.__name__} must set class attribute {attr!r} "
                    f"before instantiating SecureBoundRepository",
                )

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
        if envelope.schema_version > self.schema_version:
            raise EnvelopeVersionError(
                f"{self.namespace}/{identifier} is at version "
                f"{envelope.schema_version}; consumer supports up to "
                f"{self.schema_version}",
            )
        return envelope.payload  # type: ignore[return-value]

    def save(self, payload: T) -> None:
        """Persist ``payload`` as an encrypted envelope row.

        The natural id is recovered from the payload via
        :meth:`extract_identifier`.
        """
        identifier = self.extract_identifier(payload)
        safe_repository_id(identifier, context="identifier")
        envelope = self._envelope_cls()(
            schema_version=self.schema_version,
            written_at=datetime.now(UTC),
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
        """Yield every persisted identifier in lexicographic order."""
        identifiers: list[str] = []
        for record in self._objects.list_records(
            self.namespace,
            expected_class=self.sensitivity,
            max_supported_version=self.schema_version,
        ):
            envelope = self._envelope_cls().model_validate_json(record.payload.decode("utf-8"))
            identifiers.append(self.extract_identifier(envelope.payload))  # type: ignore[arg-type]
        yield from sorted(identifiers)

    def iter_records(self) -> Iterator[T]:
        """Yield every persisted payload in lexicographic id order."""
        for identifier in self.iter_ids():
            payload = self.load(identifier)
            if payload is not None:
                yield payload

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _envelope_cls(self) -> type[Envelope[BaseModel]]:
        """Return the parameterised ``Envelope[payload_type]`` class.

        ``Envelope[T]`` is parameterised via :pep:`695` generic syntax;
        subscripting it with the subclass's concrete payload type
        produces the validator Pydantic needs at the JSON boundary.
        """
        return Envelope[self.payload_type]  # type: ignore[name-defined,valid-type]


__all__ = ["SecureBoundRepository"]
