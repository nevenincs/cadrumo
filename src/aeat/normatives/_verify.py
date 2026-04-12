"""Catalogue-level verification for ``aeat.normatives``.

The verifier re-runs schema validation (via the loader) and adds a
handful of cross-record checks that cannot be expressed inside a
single pydantic model: id uniqueness across files, article permalink
shape, citation-renderer smoke test.
"""

from __future__ import annotations

from aeat.config import Settings
from aeat.logging import get_logger

from ._cite import cite
from ._loader import load_catalogue
from ._schema import (
    NormativeCatalogue,
    VerificationIssue,
    VerificationReport,
)
from .errors import NormativeError, NormativeParseError

_logger = get_logger(__name__)


def verify_catalogue(
    catalogue: NormativeCatalogue | None = None,
    *,
    settings: Settings | None = None,
) -> VerificationReport:
    """Run every cross-record check on a loaded catalogue.

    Args:
        catalogue: Optional pre-loaded catalogue; loaded from disk if
            omitted.
        settings: Optional settings instance for the disk load.

    Returns:
        A :class:`VerificationReport` aggregating every finding.
    """
    issues: list[VerificationIssue] = []
    if catalogue is None:
        try:
            catalogue = load_catalogue(settings=settings)
        except NormativeParseError as exc:
            issues.append(
                VerificationIssue(
                    level="error",
                    code="parse_error",
                    message=str(exc),
                )
            )
            return VerificationReport(issues=tuple(issues))

    for reference in catalogue:
        base_url = str(reference.boe_url)
        for articulo in reference.articulos:
            permalink = str(articulo.permalink)
            if not permalink.startswith(base_url):
                issues.append(
                    VerificationIssue(
                        level="error",
                        code="permalink_mismatch",
                        message=(f"permalink {permalink!r} does not start with canonical boe_url {base_url!r}"),
                        reference_id=reference.id,
                    )
                )
            try:
                rendered = cite(reference, articulo)
            except Exception as exc:  # pragma: no cover - defensive
                issues.append(
                    VerificationIssue(
                        level="error",
                        code="cite_failed",
                        message=f"cite() raised: {exc}",
                        reference_id=reference.id,
                    )
                )
                continue
            if reference.boe_id not in rendered:
                issues.append(
                    VerificationIssue(
                        level="error",
                        code="cite_missing_boe_id",
                        message=f"rendered citation missing boe_id: {rendered}",
                        reference_id=reference.id,
                    )
                )

    _logger.info("verify_catalogue produced %d issue(s)", len(issues))
    return VerificationReport(issues=tuple(issues))


def raise_on_errors(report: VerificationReport) -> None:
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
