"""Stage 6 must block on ERROR findings, and must fail LOUD if it cannot read them.

``_stage_validating_draft`` re-scans a built draft for ERROR-severity findings
and aborts the workflow when any exist. It previously read the severity through
``_enum_value(getattr(f, "severity", None))``, which is fail-OPEN: a renamed
``severity`` field yields ``None`` for every finding, ``_enum_value(None)``
returns ``""``, no finding matches, and the stage records SUCCESS on a draft
that carries real errors.

That is not a hypothetical shape. The identical defect shipped in this file's
sibling gate, ``domain.submission._preflight``, where the captured log line
``preflight gate-2 ok: no error findings`` was emitted for a draft holding a
genuine ``BaseSeverity.ERROR``.

The two failure modes are indistinguishable by OUTCOME -- an empty error set
from a clean draft and one caused by drift both produce a success step. So the
drift proof below separates them by EXCEPTION TYPE: ``AttributeError`` when the
read breaks, ``WorkflowAbortSignalError`` when the gate correctly fires.

The stage does not touch ``self``, so it is exercised unbound rather than by
standing up a whole :class:`WorkflowEngine` with its full Protocol handle set.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from ....core.errors.severity import BaseSeverity
from ....domain.submission.models import ModeloFinding
from ..engine import WorkflowEngine
from ..errors import WorkflowAbortSignalError
from ..run_models import WorkflowAbortReason, WorkflowStage, WorkflowStep

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _Draft:
    """Minimal structural stand-in carrying only what stage 6 reads."""

    def __init__(self, *, findings: tuple[ModeloFinding, ...]) -> None:
        self.findings = findings


def _run(draft: _Draft) -> list[WorkflowStep]:
    steps: list[WorkflowStep] = []
    WorkflowEngine._stage_validating_draft(
        cast(Any, None),
        draft=cast(Any, draft),
        steps=steps,
    )
    return steps


def test_an_error_finding_aborts_the_workflow() -> None:
    """The gate fires, and it fires with its own abort reason."""
    draft = _Draft(
        findings=(ModeloFinding(severity=BaseSeverity.ERROR, message="casilla 03 is required"),),
    )

    with pytest.raises(WorkflowAbortSignalError) as excinfo:
        _run(draft)

    assert excinfo.value.reason is WorkflowAbortReason.DRAFT_HAS_ERRORS


def test_non_error_findings_do_not_block() -> None:
    """Anti-tautology companion: the gate is not simply raising on any finding.

    Without this, a guard that aborted unconditionally would pass the test
    above and look correct.
    """
    draft = _Draft(
        findings=(
            ModeloFinding(severity=BaseSeverity.WARNING, message="rounding differs by 0.01"),
            ModeloFinding(severity=BaseSeverity.INFO, message="draft built from cached snapshot"),
        ),
    )

    steps = _run(draft)

    assert [step.stage for step in steps] == [WorkflowStage.VALIDATING_DRAFT]
    assert steps[0].success is True


def test_a_renamed_severity_field_fails_loud_instead_of_reporting_success() -> None:
    """Drift proof: the read must raise, not silently find zero errors.

    ``severity`` is deleted from a REAL ``ModeloFinding`` instance's own
    ``__dict__`` rather than substituted with a look-alike class, because the
    Protocol makes the field required -- a stand-in without it is not the
    object that reaches this code path.

    The assertion is on ``AttributeError`` naming ``severity``, explicitly NOT
    on "an exception was raised": a legitimately-failing draft raises
    ``WorkflowAbortSignalError`` from the very same line, and the two exception
    types are the only thing separating "the read broke" from "the gate
    correctly fired".
    """
    finding = ModeloFinding(severity=BaseSeverity.ERROR, message="casilla 03 is required")
    object.__getattribute__(finding, "__dict__").pop("severity")

    with pytest.raises(AttributeError, match="severity"):
        _run(_Draft(findings=(finding,)))
