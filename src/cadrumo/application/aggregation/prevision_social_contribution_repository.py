"""Application-owned capabilities for the pension contribution certificate records.

The application owns the key grammar, the read capability the calculation uses
and the one write path with its refusals. The encrypted implementation, which
alone holds the profile key the issuer and plan references are digested under,
is bound by an outer composition root. Nothing here logs an amount, a tax
identifier or a name.

The write refuses, before anything is stored:

* an ejercicio the pinned authority does not support;
* a record the pinned Modelo 100 revision of its ejercicio places in no box: a
  clave no official text places, one that fits a box only by analogy, an
  ejercicio whose Modelo 345 design is not bundled, a same-plan split the record
  leaves unstated, or a spouse's or disabled person's system. The filer enters
  that box as an operator value instead;
* a record whose references are not this profile's keyed digests of its issuer
  and plan, or which names a replaced certificate that is not the one stored;
* an overwrite or removal under a revision that is no longer the stored row's;
* a record whose evidence fingerprint names bytes the profile's attachment
  custody does not hold, or holds in a state that no longer hashes to it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal, Protocol

from ...core.errors.hierarchy import CadrumoError
from ...core.period import StandardPeriodCode
from ...core.prevision_social import PrevisionSocialPlacementRefusal
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.renta.prevision_social_contribution import (
    PrevisionSocialContribution,
    PrevisionSocialContributionIdentity,
)
from ...domain.renta.prevision_social_contribution_placement import (
    ContributionPlacement,
    ContributionPlacementRefused,
    place_contribution,
)
from .observation_key_component import validate_observation_key_component

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.schema import ModeloRevision

__all__ = [
    "NO_KEY_SEGMENT",
    "PinnedPrevisionSocialContributionWriteAuthority",
    "PrevisionSocialContributionEvidenceCustody",
    "PrevisionSocialContributionPersistenceError",
    "PrevisionSocialContributionRecordReader",
    "PrevisionSocialContributionRecordRepository",
    "PrevisionSocialContributionRevisionConflictError",
    "PrevisionSocialContributionWriteAuthority",
    "PrevisionSocialContributionWriteRefusal",
    "PrevisionSocialContributionWriteRefusedError",
    "annual_renta_revision",
    "prevision_social_contribution_record_key",
    "record_prevision_social_contribution",
    "require_prevision_social_contribution_writable",
    "served_placement_words_key",
]

NO_KEY_SEGMENT: Final = "-"
"""The key segment of a plan without a tax identifier of its own, or of a clave without a subclave."""


def prevision_social_contribution_record_key(identity: PrevisionSocialContributionIdentity) -> str:
    """Return the object key ``{ejercicio}:{issuer_ref}:{plan_ref|-}:{clave}:{subclave|-}`` of one record.

    Both references are already keyed digests, so the key carries no tax
    identifier and no unkeyed hash of one.
    """
    ejercicio, issuer_ref, plan_ref, clave, subclave = identity
    validate_observation_key_component(issuer_ref, context="issuer_ref")
    if plan_ref is not None:
        validate_observation_key_component(plan_ref, context="plan_ref")
    plan = NO_KEY_SEGMENT if plan_ref is None else plan_ref
    sub = NO_KEY_SEGMENT if subclave is None else subclave.value
    return f"{ejercicio}:{issuer_ref}:{plan}:{clave.value}:{sub}"


_SERVED_PLACEMENT_WORDS_LOCALE_KEYS: Final[Mapping[PrevisionSocialPlacementRefusal, str]] = {
    PrevisionSocialPlacementRefusal.UNPLACED_CLAVE: "aggregation.prevision_social_contribution.served.unplaced_clave",
    PrevisionSocialPlacementRefusal.INDIRECT_MATCH: "aggregation.prevision_social_contribution.served.indirect_match",
    PrevisionSocialPlacementRefusal.DESIGN_NOT_BUNDLED: (
        "aggregation.prevision_social_contribution.served.design_not_bundled"
    ),
    PrevisionSocialPlacementRefusal.SAME_PLAN_SPLIT_UNSTATED: (
        "aggregation.prevision_social_contribution.served.same_plan_split_unstated"
    ),
    PrevisionSocialPlacementRefusal.BENEFICIARY_OUT_OF_SCOPE: (
        "aggregation.prevision_social_contribution.served.beneficiary_out_of_scope"
    ),
}


def served_placement_words_key(reason: PrevisionSocialPlacementRefusal) -> str:
    """Return the catalogue key of the served words saying why a record reaches no box, and the door out."""
    return _SERVED_PLACEMENT_WORDS_LOCALE_KEYS[reason]


class PrevisionSocialContributionPersistenceError(CadrumoError):
    """Translated failure from the contribution-record persistence port."""

    def __init__(self, operation: str) -> None:
        """Carry only the application operation, never storage details or record content."""
        self.operation = operation
        super().__init__(f"prevision social contribution persistence operation failed: {operation}")


class PrevisionSocialContributionRevisionConflictError(CadrumoError):
    """The stored row moved since the revision the write or removal was prepared against."""

    def __init__(self) -> None:
        """Say only that the revision is stale; the row is named by nothing identifying."""
        super().__init__(
            "the pension contribution record changed since it was read",
            translated_message="aggregation.prevision_social_contribution.errors.stale_revision",
        )


type PrevisionSocialContributionWriteRefusal = Literal[
    "ejercicio_unsupported",
    "identity_mismatch",
    "certificate_not_in_custody",
    "unplaced_clave",
    "indirect_match",
    "design_not_bundled",
    "same_plan_split_unstated",
    "beneficiary_out_of_scope",
]
"""Why a write was refused before it reached storage; the last five are the placement refusals."""

_PLACEMENT_REFUSALS: Final[Mapping[PrevisionSocialPlacementRefusal, PrevisionSocialContributionWriteRefusal]] = {
    PrevisionSocialPlacementRefusal.UNPLACED_CLAVE: "unplaced_clave",
    PrevisionSocialPlacementRefusal.INDIRECT_MATCH: "indirect_match",
    PrevisionSocialPlacementRefusal.DESIGN_NOT_BUNDLED: "design_not_bundled",
    PrevisionSocialPlacementRefusal.SAME_PLAN_SPLIT_UNSTATED: "same_plan_split_unstated",
    PrevisionSocialPlacementRefusal.BENEFICIARY_OUT_OF_SCOPE: "beneficiary_out_of_scope",
}


_WRITE_REFUSAL_ERROR_LOCALE_KEYS: Final[Mapping[PrevisionSocialContributionWriteRefusal, str]] = {
    "ejercicio_unsupported": "aggregation.prevision_social_contribution.errors.ejercicio_unsupported",
    "identity_mismatch": "aggregation.prevision_social_contribution.errors.identity_mismatch",
    "certificate_not_in_custody": "aggregation.prevision_social_contribution.errors.certificate_not_in_custody",
}
"""The worded message of each write refusal that is not a placement refusal."""


class PrevisionSocialContributionWriteRefusedError(CadrumoError):
    """A contribution record the write path refuses to store."""

    def __init__(self, reason: PrevisionSocialContributionWriteRefusal, *, ejercicio: int) -> None:
        """Name the refusal and the ejercicio; never the issuer, the plan or an amount."""
        self.reason: PrevisionSocialContributionWriteRefusal = reason
        placement = next((item for item, token in _PLACEMENT_REFUSALS.items() if token == reason), None)
        super().__init__(
            f"pension contribution record refused: {reason}",
            context={"reason": reason, "ejercicio": str(ejercicio)},
            translated_message=(
                _WRITE_REFUSAL_ERROR_LOCALE_KEYS[reason] if placement is None else served_placement_words_key(placement)
            ),
        )


class PrevisionSocialContributionRecordReader(Protocol):
    """The read capability a calculation uses."""

    def load_records(self, ejercicio: int) -> tuple[PrevisionSocialContribution, ...]:
        """Return every contribution record of ``ejercicio``."""
        ...


class PrevisionSocialContributionRecordRepository(PrevisionSocialContributionRecordReader, Protocol):
    """The read, guarded-write and guarded-removal capability over the encrypted store."""

    def issuer_reference(self, issuer_tax_id: str) -> str:
        """Return this profile's keyed digest of the issuer's ``issuer_tax_id``."""
        ...

    def plan_reference(self, plan_tax_id: str) -> str:
        """Return this profile's keyed digest of the plan's ``plan_tax_id``."""
        ...

    def load_revisioned(
        self, identity: PrevisionSocialContributionIdentity
    ) -> tuple[PrevisionSocialContribution | None, str]:
        """Return the stored record at ``identity`` and the exact revision it was read at.

        An absent row returns ``None`` beside the absent-row revision sentinel,
        which is the revision a first write must be prepared against.
        """
        ...

    def list_revisioned(self, ejercicio: int) -> tuple[tuple[PrevisionSocialContribution, str], ...]:
        """Return every record of ``ejercicio`` beside the revision it was read at, ordered by object key."""
        ...

    def save_revisioned(self, record: PrevisionSocialContribution, *, expected_revision_id: str) -> None:
        """Store ``record`` only if its row is still at ``expected_revision_id``.

        Raises:
            PrevisionSocialContributionRevisionConflictError: The row moved.
        """
        ...

    def delete_revisioned(self, identity: PrevisionSocialContributionIdentity, *, expected_revision_id: str) -> None:
        """Remove the row at ``identity`` only if it is still at ``expected_revision_id``.

        Raises:
            PrevisionSocialContributionRevisionConflictError: The row moved or is gone.
        """
        ...


class PrevisionSocialContributionEvidenceCustody(Protocol):
    """What the profile's attachment custody says about the bytes a record's fingerprint names."""

    def holds(self, fingerprint: str) -> bool:
        """Return whether custody holds the bytes addressed by ``fingerprint`` and they still hash to it."""
        ...


class PrevisionSocialContributionWriteAuthority(Protocol):
    """What the pinned authority says about the ejercicio and the clave a record is written for."""

    def admits_ejercicio(self, ejercicio: int) -> bool:
        """Return whether ``ejercicio`` is inside the supported filing years."""
        ...

    def placement(self, record: PrevisionSocialContribution) -> ContributionPlacement | ContributionPlacementRefused:
        """Return the box the Modelo 100 revision of the record's ejercicio places it in, or why none."""
        ...


def annual_renta_revision(operation: PinnedAuthorityOperation, ejercicio: int) -> ModeloRevision:
    """Return the annual Renta revision ``operation`` pins for ``ejercicio``."""
    return operation.revision_for_context(
        form_for_role("renta.annual", authority=operation),
        filing_year=ejercicio,
        period=StandardPeriodCode.ANNUAL.value,
    )


@dataclass(frozen=True, slots=True)
class PinnedPrevisionSocialContributionWriteAuthority:
    """Answer the write authority's questions from one pinned authority generation."""

    operation: PinnedAuthorityOperation

    def admits_ejercicio(self, ejercicio: int) -> bool:
        """Return whether the generation's support envelope admits ``ejercicio``."""
        return self.operation.supported_filing_years().admits_filing_year(ejercicio)

    def placement(self, record: PrevisionSocialContribution) -> ContributionPlacement | ContributionPlacementRefused:
        """Place ``record`` in the pinned annual Renta revision of its ejercicio."""
        return place_contribution(annual_renta_revision(self.operation, record.ejercicio), record)


def _require_admitted(
    record: PrevisionSocialContribution, *, authority: PrevisionSocialContributionWriteAuthority
) -> None:
    if not authority.admits_ejercicio(record.ejercicio):
        raise PrevisionSocialContributionWriteRefusedError("ejercicio_unsupported", ejercicio=record.ejercicio)
    placed = authority.placement(record)
    if isinstance(placed, ContributionPlacementRefused):
        raise PrevisionSocialContributionWriteRefusedError(
            _PLACEMENT_REFUSALS[placed.reason], ejercicio=record.ejercicio
        )


def _require_identity(record: PrevisionSocialContribution, stored: PrevisionSocialContribution | None) -> None:
    if stored is None:
        if record.replaces_evidence_fingerprint is not None:
            raise PrevisionSocialContributionWriteRefusedError("identity_mismatch", ejercicio=record.ejercicio)
        return
    if stored.identity != record.identity or record.replaces_evidence_fingerprint != stored.evidence_fingerprint:
        raise PrevisionSocialContributionWriteRefusedError("identity_mismatch", ejercicio=record.ejercicio)


def require_prevision_social_contribution_writable(
    record: PrevisionSocialContribution,
    *,
    repository: PrevisionSocialContributionRecordRepository,
    authority: PrevisionSocialContributionWriteAuthority,
    expected_revision_id: str,
) -> None:
    """Refuse, before anything is stored, every ground except the evidence's custody.

    A caller that must put the certificate bytes in custody first runs this to
    learn that the record would be accepted, so a refused record leaves no bytes
    behind. :func:`record_prevision_social_contribution` runs it again at the write.

    Raises:
        PrevisionSocialContributionWriteRefusedError: The record is refused (see the module).
        PrevisionSocialContributionRevisionConflictError: The row is no longer at
            ``expected_revision_id``.
        PrevisionSocialContributionPersistenceError: Storage failed.
    """
    _require_admitted(record, authority=authority)
    if record.issuer_ref != repository.issuer_reference(record.issuer_tax_id):
        raise PrevisionSocialContributionWriteRefusedError("identity_mismatch", ejercicio=record.ejercicio)
    if record.plan_tax_id is not None and record.plan_ref != repository.plan_reference(record.plan_tax_id):
        raise PrevisionSocialContributionWriteRefusedError("identity_mismatch", ejercicio=record.ejercicio)
    stored, current_revision_id = repository.load_revisioned(record.identity)
    if current_revision_id != expected_revision_id:
        raise PrevisionSocialContributionRevisionConflictError
    _require_identity(record, stored)


def record_prevision_social_contribution(
    record: PrevisionSocialContribution,
    *,
    repository: PrevisionSocialContributionRecordRepository,
    authority: PrevisionSocialContributionWriteAuthority,
    custody: PrevisionSocialContributionEvidenceCustody,
    expected_revision_id: str,
) -> None:
    """Store one contribution record, or its correction, after every refusal has been checked.

    ``expected_revision_id`` is the revision the caller read the row at: the
    absent-row sentinel for a first record, the stored row's revision for a
    correction. A correction names the certificate it replaces in
    ``replaces_evidence_fingerprint``, which must be the stored one; a correction
    made against the same certificate names that same fingerprint.

    Raises:
        PrevisionSocialContributionWriteRefusedError: The record is refused (see the module).
        PrevisionSocialContributionRevisionConflictError: The row is no longer at
            ``expected_revision_id``.
        PrevisionSocialContributionPersistenceError: Storage failed.
    """
    require_prevision_social_contribution_writable(
        record, repository=repository, authority=authority, expected_revision_id=expected_revision_id
    )
    if not custody.holds(record.evidence_fingerprint):
        raise PrevisionSocialContributionWriteRefusedError("certificate_not_in_custody", ejercicio=record.ejercicio)
    repository.save_revisioned(record, expected_revision_id=expected_revision_id)
