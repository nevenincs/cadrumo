"""Encrypted SQL repository for verification reports.

:class:`~adapters.persistence.profile.modelos_verification_reports.VerificationReportCatalogueRepository` persists
and loads :class:`VerificationReport` entries in a
:class:`VerificationReportCatalogue` via
:class:`~cadrumo.adapters.persistence.storage.SecureObjectRepository` at
``FINANCIAL`` :class:`~cadrumo.adapters.persistence.storage.SensitivityClass`.
The catalogue is stored as a single encrypted BLOB per profile bucket and
wrapped in :class:`~cadrumo.adapters.persistence.storage.Envelope` before
serialisation.
The storage contract is declared by
:data:`cadrumo.adapters.persistence.storage.MODELO_VERIFICATION_REPORT_CATALOGUE_NAMESPACE`;
its default object key is the singleton ``catalogue`` row.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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
    """Return a new catalogue with ``report`` inserted or replaced.

    Returns:
        A :class:`VerificationReportCatalogue` with the given report added or updated.
    """
    mapping = dict(catalogue.reports)
    mapping[report.verification_report_id] = report
    return VerificationReportCatalogue(reports=mapping)


__all__ = [
    "VerificationReportPersistenceError",
    "upsert_verification_report",
]
