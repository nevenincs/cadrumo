"""``_draft_blocking_finding_codes`` must read severity/code typed, and fail loud on drift.

Sibling defect to the one fixed in
``test_validating_draft_stage_reads_severity_typed.py``: this helper backs
``WorkflowDraftNotReadyDetails.blocking_finding_codes``, the diagnostic detail
an operator reads to learn WHICH findings blocked a draft from reaching a
ready status. It does not itself decide the abort -- ``_abort_if_draft_not_ready``
aborts on ``draft.status`` alone -- so a drifted read here does not let an
error findings-bearing draft THROUGH; it silently empties the very detail an
operator would use to find out why. That is a real defect (a debugging dead
end dressed as "no blocking findings"), just a narrower one than a gate that
fails open.

The previous implementation read
``_enum_value(getattr(finding, "severity", None))`` and
``_enum_value(getattr(finding, "code", None))``: a renamed field on EITHER
yields ``""`` from ``_enum_value``, which never matches ``{"error",
"warning"}`` (severity) or is falsy (code), so a real blocking finding is
silently dropped from the reported set with no error at all.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from ....core.errors import BaseSeverity
from ....core.i18n import Translatable as tr
from ....domain.filing.schema import ModeloValidationFinding
from ..engine import _draft_blocking_finding_codes

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _Draft:
    """Minimal structural stand-in carrying only what this helper reads."""

    def __init__(self, *, findings: tuple[ModeloValidationFinding, ...]) -> None:
        self.findings = findings


def _finding(*, severity: BaseSeverity, code: str) -> ModeloValidationFinding:
    return ModeloValidationFinding(
        casilla_id=None,
        severity=severity,
        code=code,
        message=tr(f"workflow.test_draft_blocking_finding_codes.finding_{code}"),
    )


def test_error_and_warning_codes_are_collected_sorted_and_deduplicated() -> None:
    findings = (
        _finding(severity=BaseSeverity.ERROR, code="casilla-required-missing"),
        _finding(severity=BaseSeverity.WARNING, code="rounding-tolerance-exceeded"),
        _finding(severity=BaseSeverity.ERROR, code="casilla-required-missing"),
    )

    codes = _draft_blocking_finding_codes(cast(Any, _Draft(findings=findings)))

    assert codes == ("casilla-required-missing", "rounding-tolerance-exceeded")


def test_info_findings_and_blank_codes_do_not_block() -> None:
    """Anti-tautology companion: not every finding contributes a code.

    Without this, a helper that collected every finding's code unconditionally
    would pass the test above and look correct.
    """
    findings = (
        _finding(severity=BaseSeverity.INFO, code="draft-built-from-cached-snapshot"),
        _finding(severity=BaseSeverity.ERROR, code="  "),
    )

    assert _draft_blocking_finding_codes(cast(Any, _Draft(findings=findings))) == ()


def test_a_renamed_severity_field_fails_loud_instead_of_reporting_no_blockers() -> None:
    """Drift proof: the severity read must raise, not silently exclude the finding.

    ``severity`` is deleted from a REAL ``ModeloValidationFinding`` instance's
    own ``__dict__`` rather than substituted with a look-alike class, so the
    fixed function's OWN typed read (not the constructor's validation) is what
    is under test.
    """
    finding = _finding(severity=BaseSeverity.ERROR, code="casilla-required-missing")
    object.__getattribute__(finding, "__dict__").pop("severity")

    with pytest.raises(AttributeError, match="severity"):
        _draft_blocking_finding_codes(cast(Any, _Draft(findings=(finding,))))


def test_a_renamed_code_field_fails_loud_instead_of_reporting_no_blockers() -> None:
    """Drift proof, second field: the code read must raise too, not silently vanish."""
    finding = _finding(severity=BaseSeverity.ERROR, code="casilla-required-missing")
    object.__getattribute__(finding, "__dict__").pop("code")

    with pytest.raises(AttributeError, match="code"):
        _draft_blocking_finding_codes(cast(Any, _Draft(findings=(finding,))))
