"""Application-owned capabilities for the Modelo 232 related-party statements.

The taxpayer's operations, its "no operations" statements and its turnover
statements for an ejercicio share one encrypted namespace. The application owns
the key forms, the read capability a later derivation uses and the one guarded
write path per payload. Nothing here logs a counterparty, an amount or a note.

Keys, all inside the namespace and none naming a counterparty:

* ``operation:{ejercicio}:{operation_id}`` for each stated operation;
* ``none:{ejercicio}:{statement_id}`` for each "none" statement;
* ``turnover:{ejercicio}:{statement_id}`` for each turnover statement;
* ``year:{ejercicio}`` for the ejercicio's guard row.

A restated statement is a new row beside the withdrawn one, so the history of
what the taxpayer said and took back stays. At most one statement of each kind
stands per ejercicio.

Every write reads the whole ejercicio, checks it, then commits the new row and
the advanced guard row in one batch that asserts the guard at the revision it was
read. Two writes of one ejercicio that both read before either committed
therefore cannot both commit: the second gets a revision conflict, which is what
keeps an operation and a "none" statement from standing together.

Every write is refused, before anything is stored, when:

* the ejercicio is outside the filing years the pinned authority supports;
* an operation's relationship, type or valuation code is not published by the
  record design pinned for its ejercicio;
* the payload is not an active one, or a statement of that kind already stands;
* an operation is stated while a "none" statement stands, or the "none"
  statement is made while the ejercicio holds an active operation;
* a withdrawal names a payload that is not active;
* the row, or the guard the caller asserted, is no longer at the revision read.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Final, Literal, Protocol

from ...core.errors.hierarchy import CadrumoError
from ...core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ...domain.calculations.registry.form_codes import resolve_form_codes
from ...domain.modelos.m232_related_party import (
    Modelo232NoneStatement,
    Modelo232Operation,
    Modelo232TurnoverStatement,
    Modelo232YearGuard,
)

if TYPE_CHECKING:
    from ...core.time.utc import UtcInstant
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

__all__ = [
    "M232_GUARD_KEY_PREFIX",
    "M232_NONE_KEY_PREFIX",
    "M232_OPERATION_KEY_PREFIX",
    "M232_RELATED_PARTY_MESSAGE_LOCALE_KEYS",
    "M232_TURNOVER_KEY_PREFIX",
    "Modelo232PinnedWriteAuthority",
    "Modelo232RefusalReason",
    "Modelo232RelatedPartyPersistenceError",
    "Modelo232RelatedPartyReader",
    "Modelo232RelatedPartyRefusedError",
    "Modelo232RelatedPartyRevisionConflictError",
    "Modelo232RelatedPartyStore",
    "Modelo232RelatedPartyWritePorts",
    "Modelo232Row",
    "Modelo232WriteAuthority",
    "Modelo232YearView",
    "m232_guard_key",
    "m232_none_key",
    "m232_operation_key",
    "m232_turnover_key",
    "state_m232_none",
    "state_m232_operation",
    "state_m232_turnover",
    "withdraw_m232_none",
    "withdraw_m232_operation",
    "withdraw_m232_turnover",
]

M232_OPERATION_KEY_PREFIX: Final = "operation:"
M232_NONE_KEY_PREFIX: Final = "none:"
M232_TURNOVER_KEY_PREFIX: Final = "turnover:"
M232_GUARD_KEY_PREFIX: Final = "year:"

_ABSENT: Final = ABSENT_SECURE_OBJECT_REVISION_ID
_FORM_ROW_CODES_FACT: Final = "form-row-codes"
_TIPO_VINCULACION_CODES: Final = "m232.tipo_vinculacion.codes"
_TIPO_OPERACION_CODES: Final = "m232.tipo_operacion.codes"
_METODO_VALORACION_CODES: Final = "m232.metodo_valoracion.codes"

type Modelo232Row = Modelo232Operation | Modelo232NoneStatement | Modelo232TurnoverStatement
"""Every payload kind a write may carry; the guard row is advanced by the store, never written by a caller."""


def m232_operation_key(identity: tuple[int, str]) -> str:
    """Return the object key ``operation:{ejercicio}:{operation_id}`` for one operation."""
    ejercicio, operation_id = identity
    return f"{M232_OPERATION_KEY_PREFIX}{ejercicio}:{operation_id}"


def m232_none_key(identity: tuple[int, str]) -> str:
    """Return the object key ``none:{ejercicio}:{statement_id}`` for one "none" statement."""
    ejercicio, statement_id = identity
    return f"{M232_NONE_KEY_PREFIX}{ejercicio}:{statement_id}"


def m232_turnover_key(identity: tuple[int, str]) -> str:
    """Return the object key ``turnover:{ejercicio}:{statement_id}`` for one turnover statement."""
    ejercicio, statement_id = identity
    return f"{M232_TURNOVER_KEY_PREFIX}{ejercicio}:{statement_id}"


def m232_guard_key(ejercicio: int) -> str:
    """Return the object key ``year:{ejercicio}`` for one ejercicio's guard row."""
    return f"{M232_GUARD_KEY_PREFIX}{ejercicio}"


type Modelo232RefusalReason = Literal[
    "ejercicio_unsupported",
    "code_unknown",
    "already_stated",
    "not_stated",
    "none_stated",
    "operations_present",
]
"""Why a statement or its withdrawal was refused before it reached storage."""

M232_RELATED_PARTY_MESSAGE_LOCALE_KEYS: Final[Mapping[str, str]] = {
    "ejercicio_unsupported": "aggregation.modelo_232_related_party.errors.ejercicio_unsupported",
    "code_unknown": "aggregation.modelo_232_related_party.errors.code_unknown",
    "already_stated": "aggregation.modelo_232_related_party.errors.already_stated",
    "not_stated": "aggregation.modelo_232_related_party.errors.not_stated",
    "none_stated": "aggregation.modelo_232_related_party.errors.none_stated",
    "operations_present": "aggregation.modelo_232_related_party.errors.operations_present",
    "stale_revision": "aggregation.modelo_232_related_party.errors.stale_revision",
}
"""The worded message of each refusal reason, the stale revision of a guarded write included."""


class Modelo232RelatedPartyRefusedError(CadrumoError):
    """A statement or withdrawal the write path refuses to store."""

    def __init__(self, reason: Modelo232RefusalReason, *, ejercicio: int) -> None:
        """Name the refusal and the ejercicio; never a counterparty, an amount or a note."""
        self.reason: Modelo232RefusalReason = reason
        super().__init__(
            f"modelo 232 related-party statement refused: {reason}",
            context={"reason": reason, "ejercicio": str(ejercicio)},
            translated_message=M232_RELATED_PARTY_MESSAGE_LOCALE_KEYS[reason],
        )


class Modelo232RelatedPartyRevisionConflictError(CadrumoError):
    """The stored rows moved since the revision the write was prepared against."""

    def __init__(self) -> None:
        """Say only that the revision is stale; the row is named by nothing identifying."""
        super().__init__(
            "the modelo 232 related-party rows changed since they were read",
            translated_message=M232_RELATED_PARTY_MESSAGE_LOCALE_KEYS["stale_revision"],
        )


class Modelo232RelatedPartyPersistenceError(CadrumoError):
    """Translated failure from the Modelo 232 related-party persistence port."""

    def __init__(self, operation: str) -> None:
        """Carry only the application operation, never storage details or row content."""
        self.operation = operation
        super().__init__(f"modelo 232 related-party persistence operation failed: {operation}")


class Modelo232RelatedPartyReader(Protocol):
    """The read capability a derivation over the stated facts uses; rows are active or withdrawn, ordered by key."""

    def load_operations(self, ejercicio: int) -> tuple[Modelo232Operation, ...]:
        """Return every stated operation of ``ejercicio``."""
        ...

    def load_none_statements(self, ejercicio: int) -> tuple[Modelo232NoneStatement, ...]:
        """Return every "none" statement of ``ejercicio``, the withdrawn ones included."""
        ...

    def load_turnover_statements(self, ejercicio: int) -> tuple[Modelo232TurnoverStatement, ...]:
        """Return every turnover statement of ``ejercicio``, the withdrawn ones included."""
        ...


@dataclass(frozen=True, slots=True)
class Modelo232YearView:
    """Everything stored for one ejercicio, each row beside the revision it was read at."""

    ejercicio: int
    guard: Modelo232YearGuard | None
    guard_revision_id: str
    operations: tuple[tuple[Modelo232Operation, str], ...]
    nones: tuple[tuple[Modelo232NoneStatement, str], ...]
    turnovers: tuple[tuple[Modelo232TurnoverStatement, str], ...]


class Modelo232RelatedPartyStore(Modelo232RelatedPartyReader, Protocol):
    """The read and guarded-write capability over the namespace."""

    def read_year(self, ejercicio: int) -> Modelo232YearView:
        """Return everything stored for ``ejercicio`` with the revisions it was read at."""
        ...

    def commit(self, view: Modelo232YearView, row: Modelo232Row, *, row_expected_revision_id: str) -> str:
        """Store ``row`` and the advanced guard of ``view`` in one batch; return the row's new revision.

        Raises:
            Modelo232RelatedPartyRevisionConflictError: The guard or the row moved since it was read.
            Modelo232RelatedPartyPersistenceError: Storage failed.
        """
        ...


class Modelo232WriteAuthority(Protocol):
    """What the pinned authority says about the ejercicio a statement is made for."""

    def admits_ejercicio(self, ejercicio: int) -> bool:
        """Return whether ``ejercicio`` is inside the supported filing years."""
        ...

    def declared_codes(self, ejercicio: int, key: str) -> frozenset[str]:
        """Return the record design's codes under ``key`` for the edition that governs ``ejercicio``."""
        ...


@dataclass(frozen=True, slots=True)
class Modelo232PinnedWriteAuthority:
    """Answer the write authority's questions from one pinned authority generation."""

    operation: PinnedAuthorityOperation

    def admits_ejercicio(self, ejercicio: int) -> bool:
        """Return whether the generation's support envelope admits ``ejercicio``."""
        return self.operation.supported_filing_years().admits_filing_year(ejercicio)

    def declared_codes(self, ejercicio: int, key: str) -> frozenset[str]:
        """Return the codes the pinned ``form-row-codes`` fact declares under ``key`` at the end of ``ejercicio``."""
        return resolve_form_codes(
            _FORM_ROW_CODES_FACT,
            effective_date=date(ejercicio, 12, 31),
            authority=self.operation,
        ).codes(key)


@dataclass(frozen=True, slots=True)
class Modelo232RelatedPartyWritePorts:
    """What one statement write reads and writes through."""

    store: Modelo232RelatedPartyStore
    authority: Modelo232WriteAuthority


def _read_admitted(ports: Modelo232RelatedPartyWritePorts, ejercicio: int) -> Modelo232YearView:
    if not ports.authority.admits_ejercicio(ejercicio):
        raise Modelo232RelatedPartyRefusedError("ejercicio_unsupported", ejercicio=ejercicio)
    return ports.store.read_year(ejercicio)


def _require_guard_current(view: Modelo232YearView, expected_guard_revision_id: str | None) -> None:
    if expected_guard_revision_id is not None and expected_guard_revision_id != view.guard_revision_id:
        raise Modelo232RelatedPartyRevisionConflictError


def _require_row_current(revision_id: str, expected_revision_id: str) -> None:
    if revision_id != expected_revision_id:
        raise Modelo232RelatedPartyRevisionConflictError


def _require_codes(operation: Modelo232Operation, authority: Modelo232WriteAuthority) -> None:
    for code, key in (
        (operation.tipo_vinculacion, _TIPO_VINCULACION_CODES),
        (operation.tipo_operacion, _TIPO_OPERACION_CODES),
        (operation.valuation_method, _METODO_VALORACION_CODES),
    ):
        if code is not None and code not in authority.declared_codes(operation.ejercicio, key):
            raise Modelo232RelatedPartyRefusedError("code_unknown", ejercicio=operation.ejercicio)


def state_m232_operation(
    operation: Modelo232Operation,
    *,
    ports: Modelo232RelatedPartyWritePorts,
    expected_guard_revision_id: str | None = None,
) -> str:
    """Store one new active operation and return the revision it was stored at.

    ``expected_guard_revision_id`` is the guard revision of a year view the
    caller read; pass it to refuse the write when the ejercicio changed since.

    Raises:
        Modelo232RelatedPartyRefusedError: The operation is refused (see the module).
        Modelo232RelatedPartyRevisionConflictError: The ejercicio changed since it was read.
        Modelo232RelatedPartyPersistenceError: Storage failed.
    """
    ejercicio = operation.ejercicio
    if not operation.active:
        raise Modelo232RelatedPartyRefusedError("not_stated", ejercicio=ejercicio)
    view = _read_admitted(ports, ejercicio)
    _require_guard_current(view, expected_guard_revision_id)
    _require_codes(operation, ports.authority)
    if any(stored.operation_id == operation.operation_id for stored, _revision in view.operations):
        raise Modelo232RelatedPartyRefusedError("already_stated", ejercicio=ejercicio)
    if any(statement.active for statement, _revision in view.nones):
        raise Modelo232RelatedPartyRefusedError("none_stated", ejercicio=ejercicio)
    return ports.store.commit(view, operation, row_expected_revision_id=_ABSENT)


def withdraw_m232_operation(
    identity: tuple[int, str],
    *,
    at: UtcInstant,
    ports: Modelo232RelatedPartyWritePorts,
    expected_revision_id: str,
) -> tuple[Modelo232Operation, str]:
    """Take back the active operation at ``identity``; return it withdrawn and its new revision.

    Raises:
        Modelo232RelatedPartyRefusedError: No active operation is stored there.
        Modelo232RelatedPartyRevisionConflictError: The row is not at ``expected_revision_id``.
        Modelo232RelatedPartyPersistenceError: Storage failed.
    """
    ejercicio, operation_id = identity
    view = ports.store.read_year(ejercicio)
    found = next(((op, rev) for op, rev in view.operations if op.operation_id == operation_id), None)
    stored, revision_id = found if found is not None else (None, _ABSENT)
    _require_row_current(revision_id, expected_revision_id)
    if stored is None or not stored.active:
        raise Modelo232RelatedPartyRefusedError("not_stated", ejercicio=ejercicio)
    withdrawn = stored.withdrawn(at)
    return withdrawn, ports.store.commit(view, withdrawn, row_expected_revision_id=revision_id)


def state_m232_none(
    statement: Modelo232NoneStatement,
    *,
    ports: Modelo232RelatedPartyWritePorts,
    expected_guard_revision_id: str | None = None,
) -> str:
    """Store one new active "none" statement beside any withdrawn ones; return the revision it was stored at.

    Raises:
        Modelo232RelatedPartyRefusedError: The statement is refused (see the module).
        Modelo232RelatedPartyRevisionConflictError: The ejercicio changed since it was read.
        Modelo232RelatedPartyPersistenceError: Storage failed.
    """
    ejercicio = statement.ejercicio
    if not statement.active:
        raise Modelo232RelatedPartyRefusedError("not_stated", ejercicio=ejercicio)
    view = _read_admitted(ports, ejercicio)
    _require_guard_current(view, expected_guard_revision_id)
    if any(stored.statement_id == statement.statement_id or stored.active for stored, _revision in view.nones):
        raise Modelo232RelatedPartyRefusedError("already_stated", ejercicio=ejercicio)
    if any(operation.active for operation, _revision in view.operations):
        raise Modelo232RelatedPartyRefusedError("operations_present", ejercicio=ejercicio)
    return ports.store.commit(view, statement, row_expected_revision_id=_ABSENT)


def withdraw_m232_none(
    ejercicio: int,
    *,
    at: UtcInstant,
    ports: Modelo232RelatedPartyWritePorts,
    expected_revision_id: str,
) -> tuple[Modelo232NoneStatement, str]:
    """Take back the active "none" statement of ``ejercicio``, which returns it to undecided.

    ``expected_revision_id`` is the revision of the active statement's row.

    Raises:
        Modelo232RelatedPartyRefusedError: No active statement is stored there.
        Modelo232RelatedPartyRevisionConflictError: The row is not at ``expected_revision_id``.
        Modelo232RelatedPartyPersistenceError: Storage failed.
    """
    view = ports.store.read_year(ejercicio)
    found = next(((item, rev) for item, rev in view.nones if item.active), None)
    stored, revision_id = found if found is not None else (None, _ABSENT)
    _require_row_current(revision_id, expected_revision_id)
    if stored is None:
        raise Modelo232RelatedPartyRefusedError("not_stated", ejercicio=ejercicio)
    withdrawn = stored.withdrawn(at)
    return withdrawn, ports.store.commit(view, withdrawn, row_expected_revision_id=revision_id)


def state_m232_turnover(
    statement: Modelo232TurnoverStatement,
    *,
    ports: Modelo232RelatedPartyWritePorts,
    expected_guard_revision_id: str | None = None,
) -> str:
    """Store one new active turnover statement beside any withdrawn ones; return the revision it was stored at.

    A stated turnover is replaced by withdrawing it and stating the new one, so
    the rows keep what was said and when it was taken back.

    Raises:
        Modelo232RelatedPartyRefusedError: The statement is refused (see the module).
        Modelo232RelatedPartyRevisionConflictError: The ejercicio changed since it was read.
        Modelo232RelatedPartyPersistenceError: Storage failed.
    """
    ejercicio = statement.ejercicio
    if not statement.active:
        raise Modelo232RelatedPartyRefusedError("not_stated", ejercicio=ejercicio)
    view = _read_admitted(ports, ejercicio)
    _require_guard_current(view, expected_guard_revision_id)
    if any(stored.statement_id == statement.statement_id or stored.active for stored, _revision in view.turnovers):
        raise Modelo232RelatedPartyRefusedError("already_stated", ejercicio=ejercicio)
    return ports.store.commit(view, statement, row_expected_revision_id=_ABSENT)


def withdraw_m232_turnover(
    ejercicio: int,
    *,
    at: UtcInstant,
    ports: Modelo232RelatedPartyWritePorts,
    expected_revision_id: str,
) -> tuple[Modelo232TurnoverStatement, str]:
    """Take back the active turnover statement of ``ejercicio``; its 2.3 ground is then undecided.

    ``expected_revision_id`` is the revision of the active statement's row.

    Raises:
        Modelo232RelatedPartyRefusedError: No active statement is stored there.
        Modelo232RelatedPartyRevisionConflictError: The row is not at ``expected_revision_id``.
        Modelo232RelatedPartyPersistenceError: Storage failed.
    """
    view = ports.store.read_year(ejercicio)
    found = next(((item, rev) for item, rev in view.turnovers if item.active), None)
    stored, revision_id = found if found is not None else (None, _ABSENT)
    _require_row_current(revision_id, expected_revision_id)
    if stored is None:
        raise Modelo232RelatedPartyRefusedError("not_stated", ejercicio=ejercicio)
    withdrawn = stored.withdrawn(at)
    return withdrawn, ports.store.commit(view, withdrawn, row_expected_revision_id=revision_id)
