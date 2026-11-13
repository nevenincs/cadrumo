"""Encrypted persistence adapters for the Modelo 232 related-party statements.

One namespace holds four payload kinds, each stored under a key that names the
ejercicio and, for an operation or statement, a random id; no key or error
carries a counterparty. Every row's payload says which kind it is. Each kind's
repository reads that marker from the decrypted envelope and decodes only the
rows of its own kind as its payload type, so a row of another kind is never
validated as this one.

:class:`Modelo232RelatedPartyStoreAdapter` composes the four repositories. Its
:meth:`~Modelo232RelatedPartyStoreAdapter.commit` writes the row and the advanced
guard of its ejercicio in one batch whose guard write asserts the revision the
ejercicio was read at, so two writers of one ejercicio cannot both commit.

Reads and guarded writes translate storage failures into the application-owned
errors, which name only the operation that failed.

Core types:
:class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`,
:class:`~cadrumo.domain.modelos.m232_related_party.Modelo232Operation`,
:class:`~cadrumo.domain.modelos.m232_related_party.Modelo232NoneStatement`,
:class:`~cadrumo.domain.modelos.m232_related_party.Modelo232TurnoverStatement`,
:class:`~cadrumo.domain.modelos.m232_related_party.Modelo232YearGuard`;
:class:`SensitivityClass`, the sensitivity classification of stored objects.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import ClassVar, Final, override

from pydantic import BaseModel

from ....application.aggregation.m232_related_party_repository import (
    Modelo232RelatedPartyPersistenceError,
    Modelo232RelatedPartyRevisionConflictError,
    Modelo232RelatedPartyStore,
    Modelo232Row,
    Modelo232YearView,
    m232_guard_key,
    m232_none_key,
    m232_operation_key,
    m232_turnover_key,
)
from ....core.classification.policies import SensitivityClass
from ....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID, SecureObjectWrite
from ....domain.modelos.m232_related_party import (
    M232_GUARD_KIND,
    M232_NONE_KIND,
    M232_OPERATION_KIND,
    M232_TURNOVER_KIND,
    Modelo232NoneStatement,
    Modelo232Operation,
    Modelo232TurnoverStatement,
    Modelo232YearGuard,
)
from ..storage.crypto.encrypted_columns import secure_object_key_digest
from ..storage.envelope.secure_bound_repository import SecureBoundRepository
from ..storage.errors import STORED_RECORD_FAILURES, SecureObjectRevisionConflictError, SecureObjectRowIdentityError
from ..storage.secure_object_namespaces import MODELO_232_RELATED_PARTY_NAMESPACE
from ..storage.sql.secure_objects import SecureObjectRepository

__all__ = [
    "Modelo232GuardRepositoryAdapter",
    "Modelo232NoneRepositoryAdapter",
    "Modelo232OperationRepositoryAdapter",
    "Modelo232RelatedPartyStoreAdapter",
    "Modelo232TurnoverRepositoryAdapter",
    "m232_related_party_row_kind",
]

_NAMESPACE: Final = MODELO_232_RELATED_PARTY_NAMESPACE


def m232_related_party_row_kind(stored_payload: bytes) -> str | None:
    """Return the ``kind`` marker of one decrypted envelope of the namespace, or ``None`` when it has none.

    A row that cannot be read as an envelope object has no kind, so no
    repository holds it and the namespace's integrity checks stay the ones that
    notice it.
    """
    try:
        document = json.loads(stored_payload)
    except ValueError:
        return None
    payload = document.get("payload") if isinstance(document, dict) else None
    kind = payload.get("kind") if isinstance(payload, dict) else None
    return kind if isinstance(kind, str) else None


def _translate_storage_failure[ResultT](operation: str, action: Callable[[], ResultT]) -> ResultT:
    """Translate storage failures into the application-owned error, keeping the conflict distinct."""
    try:
        return action()
    except (Modelo232RelatedPartyPersistenceError, Modelo232RelatedPartyRevisionConflictError):
        raise
    except SecureObjectRevisionConflictError as exc:
        raise Modelo232RelatedPartyRevisionConflictError from exc
    except (*STORED_RECORD_FAILURES, TypeError, KeyError) as exc:
        raise Modelo232RelatedPartyPersistenceError(operation) from exc


class _M232RowRepository[PayloadT: BaseModel](SecureBoundRepository[PayloadT]):
    """The scan, revision read and prepared write every kind of the namespace shares."""

    namespace: ClassVar[str] = _NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = _NAMESPACE.sensitivity
    schema_version: ClassVar[int] = _NAMESPACE.schema_version
    row_kind: ClassVar[str]

    def __init__(self, *, objects: SecureObjectRepository) -> None:
        """Bind an already-composed secure-object store."""
        super().__init__(objects=objects)

    @override
    def _holds_row(self, stored_payload: bytes) -> bool:
        """Hold the rows of this repository's kind only; the namespace's other kinds belong to their own."""
        return m232_related_party_row_kind(stored_payload) == self.row_kind

    def _ejercicio_of(self, payload: PayloadT) -> int:
        ejercicio = getattr(payload, "ejercicio", None)
        if not isinstance(ejercicio, int):
            raise Modelo232RelatedPartyPersistenceError("modelo_232_row_ejercicio")
        return ejercicio

    def list_revisioned(self, ejercicio: int) -> tuple[tuple[PayloadT, str], ...]:
        """Return every row of this kind for ``ejercicio`` beside the revision it was read at, ordered by key."""

        def scan() -> tuple[tuple[PayloadT, str], ...]:
            rows: list[tuple[str, PayloadT, str]] = []
            for stored, envelope in self._iter_validated_rows():
                payload = envelope.payload
                identifier = self.extract_identifier(payload)
                if secure_object_key_digest(identifier) != stored.object_key:
                    raise SecureObjectRowIdentityError(self.namespace, expected_identifier=identifier)
                if self._ejercicio_of(payload) == ejercicio:
                    rows.append((identifier, payload, stored.revision_id))
            return tuple((payload, revision) for _key, payload, revision in sorted(rows, key=lambda row: row[0]))

        return _translate_storage_failure(f"modelo_232_list_{self.row_kind}", scan)

    def decode_row(self, stored_payload: bytes) -> PayloadT:
        """Return the payload of one decrypted envelope of this kind, through the shared envelope gates."""
        return self._validate_envelope(stored_payload, subject=f"{self.namespace} carried row").payload

    def revision_of(self, payload: PayloadT) -> str:
        """Return the revision the stored row of ``payload`` is at."""

        def read() -> str:
            stored = self.secure_object_repository.load(
                self.namespace,
                self.extract_identifier(payload),
                expected_class=self.sensitivity,
                max_supported_version=self.schema_version,
            )
            if stored is None:
                raise Modelo232RelatedPartyPersistenceError(f"modelo_232_read_{self.row_kind}")
            return stored.revision_id

        return _translate_storage_failure(f"modelo_232_read_{self.row_kind}", read)


class Modelo232OperationRepositoryAdapter(_M232RowRepository[Modelo232Operation]):
    """Bind the operation rows of the Modelo 232 related-party namespace."""

    row_kind: ClassVar[str] = M232_OPERATION_KIND
    payload_type: Final[type[Modelo232Operation]] = Modelo232Operation

    @override
    def extract_identifier(self, payload: Modelo232Operation) -> str:
        return m232_operation_key(payload.identity)


class Modelo232NoneRepositoryAdapter(_M232RowRepository[Modelo232NoneStatement]):
    """Bind the "none" statement rows of the Modelo 232 related-party namespace."""

    row_kind: ClassVar[str] = M232_NONE_KIND
    payload_type: Final[type[Modelo232NoneStatement]] = Modelo232NoneStatement

    @override
    def extract_identifier(self, payload: Modelo232NoneStatement) -> str:
        return m232_none_key(payload.identity)


class Modelo232TurnoverRepositoryAdapter(_M232RowRepository[Modelo232TurnoverStatement]):
    """Bind the turnover statement rows of the Modelo 232 related-party namespace."""

    row_kind: ClassVar[str] = M232_TURNOVER_KIND
    payload_type: Final[type[Modelo232TurnoverStatement]] = Modelo232TurnoverStatement

    @override
    def extract_identifier(self, payload: Modelo232TurnoverStatement) -> str:
        return m232_turnover_key(payload.identity)


class Modelo232GuardRepositoryAdapter(_M232RowRepository[Modelo232YearGuard]):
    """Bind the per-ejercicio guard rows of the Modelo 232 related-party namespace."""

    row_kind: ClassVar[str] = M232_GUARD_KIND
    payload_type: Final[type[Modelo232YearGuard]] = Modelo232YearGuard

    @override
    def extract_identifier(self, payload: Modelo232YearGuard) -> str:
        return m232_guard_key(payload.identity)


class Modelo232RelatedPartyStoreAdapter(Modelo232RelatedPartyStore):
    """Read an ejercicio whole and commit one row with its advanced guard in a single batch."""

    def __init__(self, *, objects: SecureObjectRepository) -> None:
        """Bind an already-composed secure-object store."""
        self._objects = objects
        self._operations = Modelo232OperationRepositoryAdapter(objects=objects)
        self._nones = Modelo232NoneRepositoryAdapter(objects=objects)
        self._turnovers = Modelo232TurnoverRepositoryAdapter(objects=objects)
        self._guards = Modelo232GuardRepositoryAdapter(objects=objects)

    @override
    def load_operations(self, ejercicio: int) -> tuple[Modelo232Operation, ...]:
        """Return every stated operation of ``ejercicio``, active or withdrawn, ordered by key."""
        return tuple(item for item, _revision in self._operations.list_revisioned(ejercicio))

    @override
    def load_none_statements(self, ejercicio: int) -> tuple[Modelo232NoneStatement, ...]:
        """Return every "none" statement of ``ejercicio``, the withdrawn ones included."""
        return tuple(item for item, _revision in self._nones.list_revisioned(ejercicio))

    @override
    def load_turnover_statements(self, ejercicio: int) -> tuple[Modelo232TurnoverStatement, ...]:
        """Return every turnover statement of ``ejercicio``, the withdrawn ones included."""
        return tuple(item for item, _revision in self._turnovers.list_revisioned(ejercicio))

    @override
    def revision_marker(self, ejercicios: Sequence[int]) -> str:
        """Return the guard revision of every ejercicio, so any write of any of them changes the marker."""
        parts = []
        for ejercicio in ejercicios:
            guards = self._guards.list_revisioned(ejercicio)
            parts.append(f"{ejercicio}:{guards[0][1] if guards else ABSENT_SECURE_OBJECT_REVISION_ID}")
        return ",".join(parts)

    @override
    def read_year(self, ejercicio: int) -> Modelo232YearView:
        """Return everything stored for ``ejercicio`` with the revisions it was read at.

        The guard is read first, so a row a concurrent writer adds after it is
        read can only make the later commit conflict, never pass unnoticed.
        """
        guards = self._guards.list_revisioned(ejercicio)
        guard, guard_revision = guards[0] if guards else (None, ABSENT_SECURE_OBJECT_REVISION_ID)
        return Modelo232YearView(
            ejercicio=ejercicio,
            guard=guard,
            guard_revision_id=guard_revision,
            operations=self._operations.list_revisioned(ejercicio),
            nones=self._nones.list_revisioned(ejercicio),
            turnovers=self._turnovers.list_revisioned(ejercicio),
        )

    @override
    def commit(self, view: Modelo232YearView, row: Modelo232Row, *, row_expected_revision_id: str) -> str:
        """Store ``row`` and the advanced guard of ``view`` in one batch; return the row's new revision."""
        guard = view.guard.advanced() if view.guard else Modelo232YearGuard(ejercicio=view.ejercicio, counter=1)
        guard_write = self._guards.to_secure_object_write(guard, expected_revision_id=view.guard_revision_id)
        if isinstance(row, Modelo232Operation):
            return self._commit_with_guard(self._operations, row, row_expected_revision_id, guard_write)
        if isinstance(row, Modelo232NoneStatement):
            return self._commit_with_guard(self._nones, row, row_expected_revision_id, guard_write)
        return self._commit_with_guard(self._turnovers, row, row_expected_revision_id, guard_write)

    def _commit_with_guard[PayloadT: BaseModel](
        self,
        repository: _M232RowRepository[PayloadT],
        row: PayloadT,
        row_expected_revision_id: str,
        guard_write: SecureObjectWrite,
    ) -> str:
        write = repository.to_secure_object_write(row, expected_revision_id=row_expected_revision_id)

        def save() -> str:
            self._objects.save_many((guard_write, write))
            return repository.revision_of(row)

        return _translate_storage_failure("modelo_232_commit", save)
