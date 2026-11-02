"""Application-owned capabilities for the operator's suffered-withholding absence attestations.

An attestation shares the per-payer records' namespace under the key
``absence:{ejercicio}:{income_class}``. The application owns that key, the
read capability the calculation uses and the one guarded write path for
attesting and withdrawing. Nothing here logs the operator's note.

The write refuses, before anything is stored:

* an ejercicio the pinned authority does not support, or whose pinned Modelo
  100 revision declares no member of the family, as the payer records are;
* an attestation for a class that already holds payer records, because the two
  would contradict each other;
* a second active attestation, or a withdrawal of one that is not active;
* any write under a revision that is no longer the stored row's.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, Literal, Protocol

from ...core.errors.hierarchy import CadrumoError
from ...core.retencion_soportada import RetencionSoportadaClase
from ...domain.renta.retencion_soportada_absence import (
    RetencionSoportadaAbsence,
    RetencionSoportadaAbsenceIdentity,
)
from .retencion_soportada_repository import (
    RetencionSoportadaRecordReader,
    RetencionSoportadaRevisionConflictError,
    RetencionSoportadaWriteAuthority,
)

if TYPE_CHECKING:
    from ...core.time.utc import UtcInstant

__all__ = [
    "RETENCION_SOPORTADA_ABSENCE_KEY_PREFIX",
    "RETENCION_SOPORTADA_ABSENCE_MESSAGE_KEYS",
    "RetencionSoportadaAbsenceReader",
    "RetencionSoportadaAbsenceRefusalReason",
    "RetencionSoportadaAbsenceRefusedError",
    "RetencionSoportadaAbsenceRepository",
    "RetencionSoportadaAbsenceWritePorts",
    "attest_retencion_soportada_absence",
    "retencion_soportada_absence_key",
    "withdraw_retencion_soportada_absence",
]

RETENCION_SOPORTADA_ABSENCE_KEY_PREFIX = "absence:"
"""The key prefix that keeps attestation rows apart from payer records in the shared namespace."""


def retencion_soportada_absence_key(identity: RetencionSoportadaAbsenceIdentity) -> str:
    """Return the object key ``absence:{ejercicio}:{income_class}`` for one attestation."""
    ejercicio, income_class = identity
    return f"{RETENCION_SOPORTADA_ABSENCE_KEY_PREFIX}{ejercicio}:{RetencionSoportadaClase(income_class).value}"


type RetencionSoportadaAbsenceRefusalReason = Literal[
    "ejercicio_unsupported",
    "family_not_declared",
    "records_present",
    "already_attested",
    "not_attested",
]
"""Why an attestation or its withdrawal was refused before it reached storage."""

RETENCION_SOPORTADA_ABSENCE_MESSAGE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "ejercicio_unsupported": "aggregation.retencion_soportada_absence.errors.ejercicio_unsupported",
        "family_not_declared": "aggregation.retencion_soportada_absence.errors.family_not_declared",
        "records_present": "aggregation.retencion_soportada_absence.errors.records_present",
        "already_attested": "aggregation.retencion_soportada_absence.errors.already_attested",
        "not_attested": "aggregation.retencion_soportada_absence.errors.not_attested",
        "stale_revision": "aggregation.retencion_soportada_absence.errors.stale_revision",
    },
)
"""The worded message of each refusal reason, the stale revision of a guarded write included."""


class RetencionSoportadaAbsenceRefusedError(CadrumoError):
    """An attestation or withdrawal the write path refuses to store."""

    def __init__(self, reason: RetencionSoportadaAbsenceRefusalReason, *, ejercicio: int) -> None:
        """Name the refusal and the ejercicio; never the operator's note."""
        self.reason: RetencionSoportadaAbsenceRefusalReason = reason
        super().__init__(
            f"suffered-withholding absence attestation refused: {reason}",
            context={"reason": reason, "ejercicio": str(ejercicio)},
            translated_message=RETENCION_SOPORTADA_ABSENCE_MESSAGE_KEYS[reason],
        )


class RetencionSoportadaAbsenceReader(Protocol):
    """The read capability a calculation uses."""

    def load_attestations(self, ejercicio: int) -> tuple[RetencionSoportadaAbsence, ...]:
        """Return every stored attestation of ``ejercicio``, active or withdrawn."""
        ...


class RetencionSoportadaAbsenceRepository(RetencionSoportadaAbsenceReader, Protocol):
    """The read and guarded-write capability over the attestation rows."""

    def load_revisioned(
        self, identity: RetencionSoportadaAbsenceIdentity
    ) -> tuple[RetencionSoportadaAbsence | None, str]:
        """Return the stored attestation at ``identity`` and the exact revision it was read at.

        An absent row returns ``None`` beside the absent-row revision sentinel.
        """
        ...

    def save_revisioned(self, attestation: RetencionSoportadaAbsence, *, expected_revision_id: str) -> str:
        """Store ``attestation`` only if its row is still at ``expected_revision_id``; return the new revision.

        Raises:
            RetencionSoportadaRevisionConflictError: The row moved.
        """
        ...


@dataclass(frozen=True, slots=True)
class RetencionSoportadaAbsenceWritePorts:
    """What one attestation write reads and writes through."""

    attestations: RetencionSoportadaAbsenceRepository
    records: RetencionSoportadaRecordReader
    authority: RetencionSoportadaWriteAuthority


def _require_current(
    ports: RetencionSoportadaAbsenceWritePorts,
    identity: RetencionSoportadaAbsenceIdentity,
    expected_revision_id: str,
) -> RetencionSoportadaAbsence | None:
    stored, current_revision_id = ports.attestations.load_revisioned(identity)
    if current_revision_id != expected_revision_id:
        raise RetencionSoportadaRevisionConflictError
    return stored


def attest_retencion_soportada_absence(
    attestation: RetencionSoportadaAbsence,
    *,
    ports: RetencionSoportadaAbsenceWritePorts,
    expected_revision_id: str,
) -> str:
    """Store one active attestation and return the revision it was stored at.

    ``expected_revision_id`` is the absent-row sentinel for a first attestation,
    or the revision of a withdrawn one it replaces.

    Raises:
        RetencionSoportadaAbsenceRefusedError: The attestation is refused (see the module).
        RetencionSoportadaRevisionConflictError: The row is no longer at ``expected_revision_id``.
        RetencionSoportadaPersistenceError: Storage failed.
    """
    ejercicio = attestation.ejercicio
    if not attestation.active:
        raise RetencionSoportadaAbsenceRefusedError("not_attested", ejercicio=ejercicio)
    if not ports.authority.admits_ejercicio(ejercicio):
        raise RetencionSoportadaAbsenceRefusedError("ejercicio_unsupported", ejercicio=ejercicio)
    if not ports.authority.declares_family(ejercicio):
        raise RetencionSoportadaAbsenceRefusedError("family_not_declared", ejercicio=ejercicio)
    stored = _require_current(ports, attestation.identity, expected_revision_id)
    if stored is not None and stored.active:
        raise RetencionSoportadaAbsenceRefusedError("already_attested", ejercicio=ejercicio)
    if any(record.income_class is attestation.income_class for record in ports.records.load_records(ejercicio)):
        raise RetencionSoportadaAbsenceRefusedError("records_present", ejercicio=ejercicio)
    return ports.attestations.save_revisioned(attestation, expected_revision_id=expected_revision_id)


def withdraw_retencion_soportada_absence(
    identity: RetencionSoportadaAbsenceIdentity,
    *,
    at: UtcInstant,
    ports: RetencionSoportadaAbsenceWritePorts,
    expected_revision_id: str,
) -> tuple[RetencionSoportadaAbsence, str]:
    """Take back the active attestation at ``identity``; return it withdrawn and its new revision.

    Raises:
        RetencionSoportadaAbsenceRefusedError: No active attestation is stored there.
        RetencionSoportadaRevisionConflictError: The row is no longer at ``expected_revision_id``.
        RetencionSoportadaPersistenceError: Storage failed.
    """
    stored = _require_current(ports, identity, expected_revision_id)
    if stored is None or not stored.active:
        raise RetencionSoportadaAbsenceRefusedError("not_attested", ejercicio=identity[0])
    withdrawn = stored.withdrawn(at)
    return withdrawn, ports.attestations.save_revisioned(withdrawn, expected_revision_id=expected_revision_id)
