"""Generic SQL-backed envelope repository for secure objects.

Concrete domain and application repositories that wrap
:class:`adapters.persistence.storage.SecureObjectRepository`
all share the same boilerplate:
:class:`adapters.persistence.storage.Envelope` wrapping, namespace,
sensitivity, schema-version, Pydantic payload type, and a function that
extracts the natural id from the payload.

This module provides
:class:`adapters.persistence.storage.SecureBoundRepository`, a
generic base class that captures that shared shape exactly once. Concrete
subclasses override the four class-level descriptors (``namespace``,
``payload_type``, ``sensitivity``, ``schema_version``) and implement
``extract_identifier``; they inherit ``envelope_path_for``,
``lock_target_for``, ``load``, ``save``, ``to_secure_object_write``,
``delete``, ``iter_ids``, and ``iter_records`` for free.

The base class does NOT replace
:class:`adapters.persistence.storage.SecureObjectRepository`; it
composes one.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import ClassVar, cast

from pydantic import BaseModel

from .....core.classification.policies import SensitivityClass
from .....core.config import Settings
from .....core.logging import get_logger
from .....core.secure_object_write import SecureObjectWrite
from .....core.time.clock import now
from .._path_safety import safe_repository_id
from .._schema_lineage import inner_envelope_classification_is_expected
from ..crypto.encrypted_columns import secure_object_key_digest
from ..errors import (
    ClassificationError,
    EnvelopeVersionError,
    RepositorySetupError,
    SecureObjectRowIdentityError,
)
from ..runtime_repository import (
    secure_object_repository_for_active_bucket_or_default_route,
    secure_object_repository_for_bucket,
)
from ..sql import SecureObjectDeletion, SecureObjectRecord, SecureObjectRepository
from ._envelope import Envelope, _parameterized_envelope_type

_log = get_logger(__name__)


def _active_bucket_objects_or_default(settings: Settings | None = None) -> SecureObjectRepository:
    """Return active-bucket storage when selected, otherwise the process default.

    When an active profile bucket is available the repository is backed by
    the bucket's own encrypted database, resolved through
    :func:`adapters.persistence.storage.secure_object_repository_for_active_bucket_or_default_route`
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

    - :attr:`namespace`: the
      :class:`adapters.persistence.storage.SecureObjectRepository`
      namespace string for this payload family
      (e.g. ``"cadrumo.domain.filing.drafts"``).
    - :attr:`payload_type`: the typed Pydantic model class wrapped by the
      envelope.
    - :attr:`sensitivity`: the
      :class:`adapters.persistence.storage.SensitivityClass` that every
      row in this namespace MUST carry; mismatches raise
      :class:`adapters.persistence.storage.ClassificationError`.
    - :attr:`schema_version`: the current envelope schema version this
      consumer expects; rows whose version differs from it raise
      :class:`adapters.persistence.storage.EnvelopeVersionError`.

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
        """Return the concrete secure-object backend.

        Returns:
            The
            :class:`adapters.persistence.storage.SecureObjectRepository`
            backing this logical repository.
        """
        return self._objects

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def _validate_envelope(self, payload: bytes, *, subject: str) -> Envelope[T]:
        """Parse one stored payload and enforce the repository's envelope gates.

        The single classification/version gate behind both read paths. ``load``
        and :meth:`_iter_validated_envelopes` applied the same two checks
        independently and differed only in how they named the row, so a change
        to either gate had to be made twice. ``subject`` carries that naming --
        ``"namespace/identifier"`` for a single load, ``"namespace iterator
        row"`` for a scan -- so the diagnostics stay as specific as before.

        Raises:
            ClassificationError: The stored envelope's classification is not the
                one this repository expects.
            EnvelopeVersionError: The stored envelope is not at this
                repository's exact schema version.
        """
        envelope = self._envelope_cls().model_validate_json(payload.decode("utf-8"))
        if not inner_envelope_classification_is_expected(envelope.classification, self.sensitivity):
            raise ClassificationError(
                f"{subject} has classification {envelope.classification}; consumer expected {self.sensitivity}",
            )
        if envelope.schema_version != self.schema_version:
            raise EnvelopeVersionError(
                f"{subject} is at version {envelope.schema_version}; consumer expects {self.schema_version}",
            )
        return envelope

    def load(self, identifier: str) -> T | None:
        """Return the persisted payload or ``None`` if absent.

        The payload's own natural identity is compared with the key it was
        looked up under. ``save`` derives the row key from the payload via
        :meth:`extract_identifier`, so the two are meant to be one fact in two
        encodings -- but nothing on the read path checked that, and a row
        written under a different key returned its payload unremarked. A caller
        asking for one record was handed another and had no way to tell: the
        returned object describes itself truthfully, it simply is not the one
        that was requested.

        Raises:
            ClassificationError: Refused by the shared envelope gate.
            EnvelopeVersionError: Refused by the shared envelope gate.
            SecureObjectRowIdentityError: The payload's natural identity
                differs from ``identifier``. Raised rather than returning
                ``None``, because the row exists -- reporting it absent would
                hide a real inconsistency behind an ordinary miss.
        """
        safe_repository_id(identifier, context="identifier")
        record = self._objects.load(
            self.namespace,
            identifier,
            expected_class=self.sensitivity,
            max_supported_version=self.schema_version,
        )
        if record is None:
            return None
        envelope = self._validate_envelope(record.payload, subject=f"{self.namespace}/{identifier}")
        payload = envelope.payload
        payload_identifier = self.extract_identifier(payload)
        if payload_identifier != identifier:
            identity_error = SecureObjectRowIdentityError(
                self.namespace,
                expected_identifier=identifier,
                payload_identifier=payload_identifier,
            )
            translated = self._translate_row_identity_error(identity_error)
            if translated is identity_error:
                raise translated
            raise translated from identity_error
        return payload

    def _translate_row_identity_error(self, error: SecureObjectRowIdentityError) -> Exception:
        """Return the exception `load` should raise for a row-identity mismatch.

        Identity: returns `error` unchanged. A subclass overrides this hook
        (not `load`) to surface its own domain-specific error type while the
        shared gate keeps sole ownership of detecting the mismatch.
        """
        return error

    def save(self, payload: T) -> None:
        """Persist ``payload`` as an encrypted envelope row.

        The natural id is recovered from the payload via
        :meth:`extract_identifier`.
        """
        identifier, envelope = self._identified_envelope(payload)
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

    def to_secure_object_write(
        self,
        payload: T,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        """Return the prepared upsert for ``payload`` without committing it.

        The caller hands the returned
        :class:`adapters.persistence.storage.SecureObjectWrite` to
        :meth:`adapters.persistence.storage.SecureObjectRepository.save_many`
        (or ``apply_batch``) alongside a sibling repository's write, so both
        land in ONE SQL unit of work and a crash between them is impossible.
        That is the same co-emit shape the filing path already uses to keep the
        participation index from drifting from the filing catalogue; the
        catalogue repositories expose ``to_secure_object_write`` for exactly
        this, and this method extends it to every envelope-bound repository.

        The write carries the identical
        :class:`adapters.persistence.storage.Envelope`, classification and
        schema version :meth:`save` would persist directly — both build it
        through :meth:`_identified_envelope`, so the committed and the prepared
        forms cannot drift apart.
        """
        identifier, envelope = self._identified_envelope(payload)
        return SecureObjectWrite(
            namespace=self.namespace,
            object_key=identifier,
            classification=self.sensitivity,
            schema_version=self.schema_version,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
            expected_revision_id=expected_revision_id,
        )

    def to_secure_object_deletion(self, identifier: str) -> SecureObjectDeletion:
        """Return the prepared removal for ``identifier`` without committing it.

        The deletion counterpart of :meth:`to_secure_object_write`, so a caller
        that must remove some rows and write others can hand both to
        :meth:`adapters.persistence.storage.SecureObjectRepository.apply_batch`
        and land the whole change in ONE SQL unit of work.
        :class:`adapters.persistence.storage.SecureObjectDeletion` addresses a
        row by its stored HMAC digest, so the natural id is bound here with the
        same digest the storage column uses.
        """
        safe_repository_id(identifier, context="identifier")
        return SecureObjectDeletion(
            namespace=self.namespace,
            hashed_object_key=secure_object_key_digest(identifier),
        )

    def replace_records(self, replacements: Sequence[T], stale_identifiers: Iterable[str]) -> None:
        """Commit ``replacements`` and remove ``stale_identifiers`` in one transaction.

        The atomic set-replace primitive: a caller that must clear a window of
        rows and write its successor set gets all-or-nothing semantics instead
        of a delete loop followed by a save loop, where a failure part-way
        through leaves the store holding neither the old set nor the new one.

        An identifier that is BOTH stale and replaced is written, not deleted:
        :meth:`adapters.persistence.storage.SecureObjectRepository.apply_batch`
        applies writes before deletions, so a row carried across the replacement
        would otherwise be upserted and then removed in the same transaction.

        Args:
            replacements: The payloads that constitute the new set.
            stale_identifiers: Natural ids of rows to remove. Ids also carried
                by ``replacements`` are ignored.
        """
        writes = tuple(self.to_secure_object_write(payload) for payload in replacements)
        retained = {write.object_key for write in writes}
        deletions = tuple(
            self.to_secure_object_deletion(identifier)
            for identifier in dict.fromkeys(stale_identifiers)
            if identifier not in retained
        )
        self._objects.apply_batch(writes, deletions)
        _log.debug(
            "secure-bound: replaced %d row(s) in %s, removed %d stale",
            len(writes),
            self.namespace,
            len(deletions),
        )

    def _identified_envelope(self, payload: T) -> tuple[str, Envelope[T]]:
        """Return the validated natural id and the stamped envelope for ``payload``."""
        identifier = self.extract_identifier(payload)
        safe_repository_id(identifier, context="identifier")
        envelope = self._envelope_cls()(
            schema_version=self.schema_version,
            written_at=now(),
            classification=self.sensitivity,
            payload=payload,
        )
        return identifier, envelope

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

    def _iter_validated_rows(self) -> Iterator[tuple[SecureObjectRecord, Envelope[T]]]:
        """Yield each stored row beside its classification/version-validated envelope."""
        for record in self._objects.list_records(
            self.namespace,
            expected_class=self.sensitivity,
            max_supported_version=self.schema_version,
        ):
            yield record, self._validate_envelope(record.payload, subject=f"{self.namespace} iterator row")

    def _iter_identified_payloads(self) -> Iterator[tuple[str, T]]:
        """Yield each row's natural id beside its payload, refusing a misfiled row.

        The one scan behind :meth:`iter_ids` and :meth:`iter_records`:
        ``list_records`` → ``model_validate_json`` → classification check →
        version check → row-identity check.

        Each repository derives its object key from the payload's own natural
        identity, so the stored key and the decrypted payload are two encodings
        of one fact. Recomputing the key from the payload and comparing it with
        the key the row is actually filed under is what makes enumeration as
        strict as :meth:`load`; without it enumeration is the weaker door, and a
        record written under another row's key enters the window it was filed
        into rather than the one it describes. The comparison decrypts nothing
        extra: the stored key is already an HMAC digest of the natural id.

        Fail-closed twice over.
        :meth:`adapters.persistence.storage.SecureObjectRepository.list_records`
        scans the whole namespace and raises ``SecureObjectUnreadableError`` if
        any row is unreadable, so a full consumption never yields a readable
        subset past a corrupt row; and a misfiled row raises rather than being
        skipped, so a caller counting rows for a declaration is never handed a
        quietly shortened set.

        Raises:
            SecureObjectRowIdentityError: A row's payload rebuilds a different
                natural id than the key it is filed under.
        """
        for record, envelope in self._iter_validated_rows():
            # Safe: same rationale as the load() path — the envelope was validated
            # against Envelope[self.payload_type] == Envelope[T].
            payload = envelope.payload
            identifier = self.extract_identifier(payload)
            if secure_object_key_digest(identifier) != record.object_key:
                raise SecureObjectRowIdentityError(self.namespace, expected_identifier=identifier)
            yield identifier, payload

    def iter_ids(self) -> Iterator[str]:
        """Yield every persisted identifier in storage order.

        Order is the secure-object storage order (the ``object_key`` digest
        order), not the natural-id order: a caller that needs a specific
        order sorts the result itself. Streams one identifier at a time
        rather than buffering and sorting the whole namespace in memory.

        Every id is the one its own row is filed under: the scan refuses a row
        whose payload rebuilds a different key rather than reporting an id the
        store does not actually hold that record at.

        Raises:
            SecureObjectRowIdentityError: A row's payload rebuilds a different
                natural id than the key it is filed under.
        """
        for identifier, _payload in self._iter_identified_payloads():
            yield identifier

    def iter_records(self) -> Iterator[T]:
        """Yield every persisted payload whose identity matches the key it is filed under.

        Streams each payload straight from
        :meth:`adapters.persistence.storage.SecureObjectRepository.list_records`
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

        Verification is the DEFAULT, not an opt-in a caller must remember: a
        scan that filters on payload fields trusts each record to describe the
        key it is stored under, and the callers most exposed to that -- window
        counts, carry-forward reads, reconciliation history -- are the ones
        least able to notice a foreign row. An opt-in variant only protects the
        callers that already suspected the problem.

        Raises:
            SecureObjectRowIdentityError: A row's payload rebuilds a different
                natural id than the key it is filed under.
        """
        for _identifier, payload in self._iter_identified_payloads():
            yield payload

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _envelope_cls(self) -> type[Envelope[T]]:
        """Return the parameterised ``Envelope[payload_type]`` class.

        Delegates to :meth:`Envelope.for_payload_type` which encapsulates the
        typed generic parameterisation for this repository's concrete ``T``.
        """
        return _parameterized_envelope_type(self.payload_model())


__all__ = ["SecureBoundRepository"]
