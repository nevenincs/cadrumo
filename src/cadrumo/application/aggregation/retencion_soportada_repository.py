"""Application-owned capabilities for the suffered-withholding per-payer records.

The application owns the key grammar, the read capability the calculation uses
and the one write path with its refusals. The encrypted implementation, which
alone holds the profile key ``payer_ref`` is digested under, is bound by an
outer composition root. Nothing here logs an amount, a tax identifier or a
payer's name.

The write refuses, before anything is stored:

* a payer whose tax identifier is the taxpayer's own -- withholding a taxpayer
  practises on themselves is a withholding-agent fact, never a credit;
* an ejercicio the pinned authority does not support, or whose pinned Modelo 100
  revision declares no member of the family, so no record is kept that no
  calculation would ever read or report;
* a record whose ``payer_ref`` is not this profile's keyed digest of its payer,
  or which names a replaced certificate that is not the one stored;
* an overwrite under a revision that is no longer the stored row's;
* a record whose evidence fingerprint names bytes the profile's attachment custody
  does not hold, or holds in a state that no longer hashes to that fingerprint.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

from ...core.errors.hierarchy import CadrumoError
from ...core.identity.tax_id import same_tax_identifier
from ...core.period import StandardPeriodCode
from ...core.retencion_soportada import RetencionSoportadaClase
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.retencion_soportada_bindings import revision_declares_retencion_soportada
from ...domain.renta.retencion_soportada import RetencionSoportadaIdentity, RetencionSoportadaRecord
from .observation_key_component import validate_observation_key_component

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from .retencion_soportada_absence_repository import RetencionSoportadaAbsenceReader

__all__ = [
    "PinnedRetencionSoportadaWriteAuthority",
    "RetencionSoportadaEvidenceCustody",
    "RetencionSoportadaPersistenceError",
    "RetencionSoportadaPorts",
    "RetencionSoportadaRecordReader",
    "RetencionSoportadaRecordRepository",
    "RetencionSoportadaRefusalReason",
    "RetencionSoportadaRevisionConflictError",
    "RetencionSoportadaWriteAuthority",
    "RetencionSoportadaWriteRefusedError",
    "record_retencion_soportada",
    "require_retencion_soportada_writable",
    "retencion_soportada_record_key",
]


def retencion_soportada_record_key(identity: RetencionSoportadaIdentity) -> str:
    """Return the object key ``{ejercicio}:{income_class}:{payer_ref}`` for one payer record.

    ``payer_ref`` is already a keyed digest, so the key carries no tax identifier
    and no unkeyed hash of one.
    """
    ejercicio, income_class, payer_ref = identity
    validate_observation_key_component(payer_ref, context="payer_ref")
    return f"{ejercicio}:{RetencionSoportadaClase(income_class).value}:{payer_ref}"


class RetencionSoportadaPersistenceError(CadrumoError):
    """Translated failure from the suffered-withholding persistence port."""

    def __init__(self, operation: str) -> None:
        """Carry only the application operation, never storage details or record content."""
        self.operation = operation
        super().__init__(f"retencion soportada persistence operation failed: {operation}")


class RetencionSoportadaRevisionConflictError(CadrumoError):
    """The stored row moved since the revision the write was prepared against."""

    def __init__(self) -> None:
        """Say only that the revision is stale; the row is named by nothing identifying."""
        super().__init__(
            "the suffered-withholding record changed since it was read",
            translated_message="aggregation.retencion_soportada.errors.stale_revision",
        )


type RetencionSoportadaRefusalReason = Literal[
    "own_tax_id",
    "ejercicio_unsupported",
    "family_not_declared",
    "identity_mismatch",
    "certificate_not_in_custody",
    "trabajo_certificate_figure_missing",
]
"""Why a write was refused before it reached storage."""


class RetencionSoportadaWriteRefusedError(CadrumoError):
    """A suffered-withholding record the write path refuses to store."""

    def __init__(self, reason: RetencionSoportadaRefusalReason, *, ejercicio: int) -> None:
        """Name the refusal and the ejercicio; never the payer or an amount."""
        self.reason: RetencionSoportadaRefusalReason = reason
        super().__init__(
            f"suffered-withholding record refused: {reason}",
            context={"reason": reason, "ejercicio": str(ejercicio)},
            translated_message=f"aggregation.retencion_soportada.errors.{reason}",
        )


class RetencionSoportadaRecordReader(Protocol):
    """The read capability a calculation uses."""

    def load_records(self, ejercicio: int) -> tuple[RetencionSoportadaRecord, ...]:
        """Return every payer record of ``ejercicio``, of every income class."""
        ...


class RetencionSoportadaRecordRepository(RetencionSoportadaRecordReader, Protocol):
    """The read and guarded-write capability over the encrypted per-payer store."""

    def payer_reference(self, payer_tax_id: str) -> str:
        """Return this profile's keyed digest of ``payer_tax_id``."""
        ...

    def load_revisioned(self, identity: RetencionSoportadaIdentity) -> tuple[RetencionSoportadaRecord | None, str]:
        """Return the stored record at ``identity`` and the exact revision it was read at.

        An absent row returns ``None`` beside the absent-row revision sentinel,
        which is the revision a first write must be prepared against.
        """
        ...

    def save_revisioned(self, record: RetencionSoportadaRecord, *, expected_revision_id: str) -> None:
        """Store ``record`` only if its row is still at ``expected_revision_id``.

        Raises:
            RetencionSoportadaRevisionConflictError: The row moved.
        """
        ...


@dataclass(frozen=True, slots=True)
class RetencionSoportadaPorts:
    """The suffered-withholding capability one calculation context reads through.

    ``absences`` reads the operator's absence attestations. Without it no
    attestation is honoured, so a class with no payer record stays unresolved
    unless the profile declares its income absent: the omission fails closed.
    """

    repository: RetencionSoportadaRecordReader
    absences: RetencionSoportadaAbsenceReader | None = None


class RetencionSoportadaEvidenceCustody(Protocol):
    """What the profile's attachment custody says about the bytes a record's fingerprint names."""

    def holds(self, fingerprint: str) -> bool:
        """Return whether custody holds the bytes addressed by ``fingerprint`` and they still hash to it.

        A missing blob and a blob that no longer hashes to its address both answer
        ``False``: the fingerprint then names no evidence. A storage failure raises
        :class:`RetencionSoportadaPersistenceError` and is never read as absence.
        """
        ...


class RetencionSoportadaWriteAuthority(Protocol):
    """What the pinned authority says about the ejercicio a record is written for."""

    def admits_ejercicio(self, ejercicio: int) -> bool:
        """Return whether ``ejercicio`` is inside the supported filing years."""
        ...

    def declares_family(self, ejercicio: int) -> bool:
        """Return whether the Modelo 100 revision for ``ejercicio`` declares any family member."""
        ...


@dataclass(frozen=True, slots=True)
class PinnedRetencionSoportadaWriteAuthority:
    """Answer the write authority's questions from one pinned authority generation."""

    operation: PinnedAuthorityOperation

    def admits_ejercicio(self, ejercicio: int) -> bool:
        """Return whether the generation's support envelope admits ``ejercicio``."""
        return self.operation.supported_filing_years().admits_filing_year(ejercicio)

    def declares_family(self, ejercicio: int) -> bool:
        """Return whether the pinned annual Renta revision for ``ejercicio`` declares the family."""
        revision = self.operation.revision_for_context(
            form_for_role("renta.annual", authority=self.operation),
            filing_year=ejercicio,
            period=StandardPeriodCode.ANNUAL.value,
        )
        return revision_declares_retencion_soportada(revision)


def _require_admitted(
    record: RetencionSoportadaRecord,
    *,
    authority: RetencionSoportadaWriteAuthority,
    taxpayer_tax_id: str,
) -> None:
    if same_tax_identifier(record.payer_tax_id, taxpayer_tax_id):
        raise RetencionSoportadaWriteRefusedError("own_tax_id", ejercicio=record.ejercicio)
    if not authority.admits_ejercicio(record.ejercicio):
        raise RetencionSoportadaWriteRefusedError("ejercicio_unsupported", ejercicio=record.ejercicio)
    if not authority.declares_family(record.ejercicio):
        raise RetencionSoportadaWriteRefusedError("family_not_declared", ejercicio=record.ejercicio)
    if record.lacks_work_certificate_figures:
        raise RetencionSoportadaWriteRefusedError("trabajo_certificate_figure_missing", ejercicio=record.ejercicio)


def _require_identity(record: RetencionSoportadaRecord, stored: RetencionSoportadaRecord | None) -> None:
    if stored is None:
        if record.replaces_evidence_fingerprint is not None:
            raise RetencionSoportadaWriteRefusedError("identity_mismatch", ejercicio=record.ejercicio)
        return
    if stored.identity != record.identity or not same_tax_identifier(stored.payer_tax_id, record.payer_tax_id):
        raise RetencionSoportadaWriteRefusedError("identity_mismatch", ejercicio=record.ejercicio)
    if record.replaces_evidence_fingerprint != stored.evidence_fingerprint:
        raise RetencionSoportadaWriteRefusedError("identity_mismatch", ejercicio=record.ejercicio)


def require_retencion_soportada_writable(
    record: RetencionSoportadaRecord,
    *,
    repository: RetencionSoportadaRecordRepository,
    authority: RetencionSoportadaWriteAuthority,
    taxpayer_tax_id: str,
    expected_revision_id: str,
) -> None:
    """Refuse, before anything is stored, every ground except the evidence's custody.

    A caller that must put the certificate bytes in custody first runs this to
    learn that the record would be accepted, so a refused record leaves no bytes
    behind. :func:`record_retencion_soportada` runs it again at the write.

    Raises:
        RetencionSoportadaWriteRefusedError: The record is refused (see the module).
        RetencionSoportadaRevisionConflictError: The row is no longer at
            ``expected_revision_id``.
        RetencionSoportadaPersistenceError: Storage failed.
    """
    _require_admitted(record, authority=authority, taxpayer_tax_id=taxpayer_tax_id)
    if record.payer_ref != repository.payer_reference(record.payer_tax_id):
        raise RetencionSoportadaWriteRefusedError("identity_mismatch", ejercicio=record.ejercicio)
    stored, current_revision_id = repository.load_revisioned(record.identity)
    # A row that moved is judged by nothing it held when the caller read it, so
    # the caller re-reads before its correction is compared with the stored one.
    if current_revision_id != expected_revision_id:
        raise RetencionSoportadaRevisionConflictError
    _require_identity(record, stored)


def record_retencion_soportada(
    record: RetencionSoportadaRecord,
    *,
    repository: RetencionSoportadaRecordRepository,
    authority: RetencionSoportadaWriteAuthority,
    custody: RetencionSoportadaEvidenceCustody,
    taxpayer_tax_id: str,
    expected_revision_id: str,
) -> None:
    """Store one payer record, or its correction, after every refusal has been checked.

    ``expected_revision_id`` is the revision the caller read the row at: the
    absent-row sentinel for a first record, the stored row's revision for a
    corrected or replacement certificate. A correction names the certificate it
    replaces in ``replaces_evidence_fingerprint``, which must be the stored one;
    a correction made against the same certificate names that same fingerprint.

    Raises:
        RetencionSoportadaWriteRefusedError: The record is refused (see the module).
        RetencionSoportadaRevisionConflictError: The row is no longer at
            ``expected_revision_id``.
        RetencionSoportadaPersistenceError: Storage failed.
    """
    require_retencion_soportada_writable(
        record,
        repository=repository,
        authority=authority,
        taxpayer_tax_id=taxpayer_tax_id,
        expected_revision_id=expected_revision_id,
    )
    if record.evidence_fingerprint is not None and not custody.holds(record.evidence_fingerprint):
        raise RetencionSoportadaWriteRefusedError("certificate_not_in_custody", ejercicio=record.ejercicio)
    repository.save_revisioned(record, expected_revision_id=expected_revision_id)
