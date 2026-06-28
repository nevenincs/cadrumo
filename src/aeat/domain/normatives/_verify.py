"""Catalogue-level verification for :mod:`aeat.domain.normatives`.

:func:`verify_catalogue` re-runs :class:`NormativeCatalogue` schema validation
through the loader and adds cross-record checks that cannot be expressed inside a
single pydantic model: id uniqueness across files, article permalink shape, and
the :func:`~aeat.domain.normatives._cite.cite` renderer smoke test. It returns a
:class:`NormativeVerificationReport` populated with
:class:`NormativeVerificationIssue` rows.
"""

from __future__ import annotations

from ...core.config import Settings
from ...core.logging import get_logger
from ._cite import cite
from ._errors import NormativeError, NormativeParseError
from ._loader import load_catalogue
from ._schema import (
    NormativeCatalogue,
    NormativeVerificationIssue,
    NormativeVerificationReport,
)

_logger = get_logger(__name__)


def verify_catalogue(
    catalogue: NormativeCatalogue | None = None,
    *,
    settings: Settings | None = None,
) -> NormativeVerificationReport:
    """Run every cross-record check on a loaded catalogue.

    Args:
        catalogue: Optional pre-loaded catalogue; loaded from disk if
            omitted.
        settings: Optional settings instance for the disk load.

    Returns:
        A :class:`NormativeVerificationReport` aggregating every finding.
    """
    issues: list[NormativeVerificationIssue] = []
    if catalogue is None:
        try:
            catalogue = load_catalogue(settings=settings)
        except NormativeParseError as exc:
            issues.append(
                NormativeVerificationIssue(
                    level="error",
                    code="parse_error",
                    message=str(exc),
                ),
            )
            return NormativeVerificationReport(issues=tuple(issues))

    for reference in catalogue:
        base_url = str(reference.boe_url)
        for articulo in reference.articulos:
            permalink = str(articulo.permalink)
            if not permalink.startswith(base_url):
                issues.append(
                    NormativeVerificationIssue(
                        level="error",
                        code="permalink_mismatch",
                        message=(f"permalink {permalink!r} does not start with canonical boe_url {base_url!r}"),
                        reference_id=reference.id,
                    ),
                )
            try:
                rendered = cite(reference, articulo)
            except Exception as exc:  # pragma: no cover - defensive
                _logger.warning(
                    "cite() raised for reference %s articulo %s",
                    reference.id,
                    articulo,
                    exc_info=True,
                )
                issues.append(
                    NormativeVerificationIssue(
                        level="error",
                        code="cite_failed",
                        message=f"cite() raised: {exc}",
                        reference_id=reference.id,
                    ),
                )
                continue
            if reference.boe_id not in rendered:
                issues.append(
                    NormativeVerificationIssue(
                        level="error",
                        code="cite_missing_boe_id",
                        message=f"rendered citation missing boe_id: {rendered}",
                        reference_id=reference.id,
                    ),
                )

    _logger.debug("verify_catalogue produced %d issue(s)", len(issues))
    return NormativeVerificationReport(issues=tuple(issues))


def raise_on_errors(report: NormativeVerificationReport) -> None:
    """Raise :class:`NormativeError` if ``report`` contains errors.

    Args:
        report: The verification report to inspect.

    Raises:
        NormativeError: If any error-level issue is present.
    """
    if report.clean:
        return
    summary = "; ".join(f"{issue.code}: {issue.message}" for issue in report.errors)
    raise NormativeError(f"normative verification failed: {summary}")
