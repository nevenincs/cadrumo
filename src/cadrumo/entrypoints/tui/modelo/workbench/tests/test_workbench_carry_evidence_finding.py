"""The check's finding about the annual compensation of Modelo 390 reads in the served words, in every language.

A required annual partition whose filed Modelo 303 source set is incomplete or stale blocks the declaration.
The finding has the shape the verification's own producer stores and is listed through the workbench's issue projection;
the sentence and the way out are the catalogue's, written in the filer's language, with the count of open
issues put in place and no token left bare.
"""

from __future__ import annotations

import pytest

from ......application.modelo.action_errors import WORKFLOW_GATE_LEGAL_REFS
from ......application.modelo.work_form_findings import ModeloFormIssue
from ......core.config import override_settings
from ......core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ......core.i18n.render import tr
from ......domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ..issue_projection import issue_lines
from ..issue_scale import IssueLevel
from .workbench_fixture import synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_KEY = "application.modelo.findings.iva_compensation_annual_source_evidence_failure"
_ACTION = "application.modelo.work_form.finding_action.resolve_303_returns"


@pytest.mark.parametrize("language", SUPPORTED_OUTPUT_LANGUAGES)
def test_the_annual_compensation_finding_blocks_and_reads_in_the_served_words(language: str) -> None:
    finding = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key=_KEY,
        message_facts={"source_issue_count": 2},
        legal_refs=WORKFLOW_GATE_LEGAL_REFS,
    )
    form = synthetic_form(needs_input=False).model_copy(update={"issues": (ModeloFormIssue(finding=finding),)})
    with override_settings(cadrumo_output_language=language):
        (line,) = issue_lines(form)
        expected_message = tr(_KEY, source_issue_count=2)
        expected_action = tr(_ACTION)

    assert line.level is IssueLevel.BLOCKS
    assert line.message == expected_message
    assert "2" in line.message and "%{" not in line.message
    assert expected_action in line.action
