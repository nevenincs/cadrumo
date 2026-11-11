"""Encrypted SQL repository for verification reports.

:class:`~adapters.persistence.profile.modelos_verification_reports.VerificationReportCatalogueRepository` persists
and loads :class:`VerificationReport` entries in a
:class:`VerificationReportCatalogue` via
:class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository` at
``FINANCIAL`` :class:`~cadrumo.core.classification.policies.SensitivityClass`.
The catalogue is stored as a single encrypted BLOB per profile bucket and
wrapped in :class:`~cadrumo.adapters.persistence.storage.envelope.contract.Envelope` before
serialisation.
The storage contract is declared by
:data:`cadrumo.adapters.persistence.storage.secure_object_namespaces.MODELO_VERIFICATION_REPORT_CATALOGUE_NAMESPACE`;
its default object key is the singleton ``catalogue`` row.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .calculation_revision import CalculationRevision
from .errors import ModeloError
from .verification_report import VerificationReport, VerificationReportCatalogue

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    pass


class VerificationReportPersistenceError(ModeloError):
    """Raised when the verification-report catalogue cannot be persisted or loaded.

    This wraps storage-boundary failures from
    :class:`~adapters.persistence.profile.modelos_verification_reports.VerificationReportCatalogueRepository` while
    preserving translated recovery context for callers.
    """


def upsert_verification_report(
    catalogue: VerificationReportCatalogue,
    report: VerificationReport,
) -> VerificationReportCatalogue:
    """Return a new catalogue holding ``report`` as the current outcome for its revision.

    An identical outcome replaces its earlier copy, since the report id is
    clock-free. Verification runs only against a revision that is not yet
    locked, so any other granting report for that revision is a grant whose
    lock never landed. The new outcome supersedes it: whoever runs
    verification again, the revision keeps at most one granting report, the
    one its lock will name. The superseded attempt's lifecycle event stays in
    the profile's event history.

    Returns:
        A :class:`VerificationReportCatalogue` with ``report`` and without the grants it supersedes.
    """
    mapping = {
        report_id: existing
        for report_id, existing in catalogue.reports.items()
        if existing.calculation_revision_id != report.calculation_revision_id
        or not existing.granted_verificado_completo
    }
    mapping[report.verification_report_id] = report
    return VerificationReportCatalogue(reports=mapping)


def revision_granting_reports(
    catalogue: VerificationReportCatalogue,
    revision: CalculationRevision,
) -> tuple[VerificationReport, ...]:
    """Return the granting reports that stand for ``revision``, ordered by run time.

    A locked revision names its witness: the grant made by the actor and at
    the instant its lock records. A grant that does not match the lock was
    left by an attempt whose lock never landed and stands for nothing. An
    unlocked revision has no witness yet, so every grant recorded for it is
    returned.
    """
    grants = tuple(
        candidate
        for candidate in catalogue.for_calculation_revision(revision.calculation_revision_id)
        if candidate.granted_verificado_completo
    )
    if revision.verified_at is None:
        return grants
    return tuple(
        candidate
        for candidate in grants
        if candidate.run_at == revision.verified_at and candidate.verified_by == revision.verified_by
    )


__all__ = [
    "VerificationReportPersistenceError",
    "revision_granting_reports",
    "upsert_verification_report",
]
