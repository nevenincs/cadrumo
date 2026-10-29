"""Stable identifiers for draft blocking findings."""

from ...core.errors.severity import BaseSeverity
from .protocols import RegistryModeloDraftProtocol


def draft_blocking_finding_codes(draft: RegistryModeloDraftProtocol) -> tuple[str, ...]:
    """Return stable finding identifiers without retaining rendered descriptions.

    ``severity`` and ``code`` are read as typed attributes, never through
    ``getattr(..., None)``: :attr:`RegistryModeloDraftProtocol.findings` is
    typed ``tuple[WorkflowFindingLike, ...]``, and that Protocol declares both
    fields required, so a rename fails loud here. Read defensively, a renamed
    field would silently drop every finding from this diagnostic detail --
    the same fail-open shape ``_stage_validating_draft`` and
    ``domain/submission/preflight.py`` carried, just feeding a reported
    detail on an already-decided abort rather than the abort decision itself.
    """
    codes: set[str] = set()
    for finding in draft.findings:
        code = finding.code
        if (
            finding.severity in {BaseSeverity.ERROR, BaseSeverity.WARNING}
            and code
            and not any(character.isspace() for character in code)
        ):
            codes.add(code)
    return tuple(sorted(codes))
