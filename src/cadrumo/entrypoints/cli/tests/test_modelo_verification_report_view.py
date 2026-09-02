"""CLI modelo verification report rendering tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from ....core.casilla_id import CasillaId, validated_casilla_id

if TYPE_CHECKING:
    from ....domain.modelos.verification_report import VerificationReport

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_VERIFICATION_FINDING_CASILLA: CasillaId = validated_casilla_id(
    "0100",
    surface="_VERIFICATION_FINDING_CASILLA",
)
_TEST_FINDING_LEGAL_REFS = ("ley-58-2003:art-119",)


def test_verification_finding_message_resolves_from_each_supported_locale_catalogue() -> None:
    """The CLI boundary renders typed facts through the selected locale catalogue."""
    from ....core.config import override_settings
    from ....domain.modelos.verification_report import (
        ModeloVerificationFinding,
        ModeloVerificationFindingKind,
        ModeloVerificationFindingSeverity,
    )
    from .._modelo_rendering import _render_verification_finding_message

    locale_key = "application.modelo.findings.cross_casilla_invariant_violated"
    predicate_id = "test-predicate"
    finding = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key=locale_key,
        message_facts={"predicate_id": predicate_id},
        legal_refs=_TEST_FINDING_LEGAL_REFS,
    )
    rendered: dict[str, str] = {}
    for locale in ("en", "es", "ca", "hu"):
        with override_settings(cadrumo_output_language=locale):
            rendered[locale] = _render_verification_finding_message(finding)

    assert len(set(rendered.values())) == len(rendered)
    for message in rendered.values():
        assert locale_key not in message
        assert "%{" not in message
        assert predicate_id in message


def test_verification_report_lines_preserve_persisted_findings_without_recovery_reconstruction() -> None:
    """Report history renders factual findings and never invents a recovery command."""
    from datetime import UTC, datetime

    from ....domain.modelos.verification_report import (
        ModeloVerificationFinding,
        ModeloVerificationFindingKind,
        ModeloVerificationFindingSeverity,
        VerificationCompletenessStatus,
        VerificationReport,
        derive_verification_report_id,
    )
    from .._modelo_payloads import VerificationReportListResult, VerificationReportShowResult
    from .._modelo_rendering import verification_report_lines as _verification_report_lines
    from .._modelo_rendering import verification_report_payload as _verification_report_payload

    run_at = datetime(2026, 5, 27, 10, 0, 0, tzinfo=UTC)
    calc_id = "a" * 64
    findings = (
        ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.cross_casilla_invariant_violated",
            message_facts={"predicate_id": "test-predicate"},
            legal_refs=_TEST_FINDING_LEGAL_REFS,
        ),
    )
    report_id = derive_verification_report_id(
        calculation_revision_id=calc_id,
        completeness_status=VerificationCompletenessStatus.BLOCKED,
        findings=findings,
        verified_by="test-actor",
    )
    report = VerificationReport(
        verification_report_id=report_id,
        calculation_revision_id=calc_id,
        completeness_status=VerificationCompletenessStatus.BLOCKED,
        findings=findings,
        run_at=run_at,
        verified_by="test-actor",
        granted_verificado_completo=False,
    )

    lines = _verification_report_lines(report)

    finding_line = next(line for line in lines if line.startswith("finding\t"))
    assert finding_line.endswith("\tnull")
    assert not any("next_action" in line for line in lines)
    assert not any("aeat app " in line for line in lines)

    # Persisted reports go through the same production finding projection as
    # report ``view`` and ``list``. Historical facts cannot reconstruct a live
    # recovery action, so the typed payload and its JSON wire shape must retain
    # an explicit null.
    payload = _verification_report_payload(report)
    assert payload.findings[0].action is None
    view = VerificationReportShowResult.model_validate(payload.model_dump(mode="python")).model_dump(mode="json")
    listing = VerificationReportListResult(report_count=1, reports=[payload]).model_dump(mode="json")
    assert view["findings"][0]["action"] is None
    assert listing["reports"][0]["findings"][0]["action"] is None


def test_verification_report_payload_resolves_the_exact_registry_recovery_verdict() -> None:
    """A live verification exposes only the typed action paired by the application."""
    from datetime import UTC, datetime

    from ....application.modelo.verification_preconditions import (
        VerificationFindingPreconditionProjection,
        build_verification_precondition_failure,
    )
    from ....core.operator_action_enums import ActionEvidenceProvenance
    from ....domain.modelos.verification_report import (
        ModeloVerificationFinding,
        ModeloVerificationFindingKind,
        ModeloVerificationFindingSeverity,
        VerificationCompletenessStatus,
        VerificationReport,
        derive_verification_report_id,
    )
    from .._action_rendering import resolved_precondition_action_json_cell
    from .._modelo_rendering import (
        verification_report_lines as _verification_report_lines,
    )
    from .._modelo_rendering import (
        verification_report_payload as _verification_report_payload,
    )

    calculation_revision_id = "e" * 64
    findings = (
        ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.cross_casilla_invariant_violated",
            message_facts={"predicate_id": "test-predicate"},
            legal_refs=_TEST_FINDING_LEGAL_REFS,
        ),
    )
    report = VerificationReport(
        verification_report_id=derive_verification_report_id(
            calculation_revision_id=calculation_revision_id,
            completeness_status=VerificationCompletenessStatus.BLOCKED,
            findings=findings,
            verified_by="test-actor",
        ),
        calculation_revision_id=calculation_revision_id,
        completeness_status=VerificationCompletenessStatus.BLOCKED,
        findings=findings,
        run_at=datetime(2026, 5, 27, 10, 0, 0, tzinfo=UTC),
        verified_by="test-actor",
        granted_verificado_completo=False,
    )

    precondition_failure = build_verification_precondition_failure(
        calculation_revision_id=calculation_revision_id,
        work_unit_id="w" * 64,
        condition_id="modelo.work.verify.registry_snapshot.available",
        scenario_id="modelo.work.verify.registry_snapshot.unavailable",
        evidence_id="modelo.work.verify.registry_snapshot",
        evidence_values={"modelo": "999"},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        action_id="operator.registry.verify",
    )
    projection = VerificationFindingPreconditionProjection(
        finding=findings[0],
        precondition_failure=precondition_failure,
    )
    payload = _verification_report_payload(report, finding_preconditions=(projection,))
    action = payload.findings[0].action

    assert action is not None
    assert action.action is not None
    assert action.action.model_dump(mode="json") == {
        "action_id": "operator.registry.verify",
        "target_command_key": "registry.verify",
        "cli_path": ["app", "registry", "verify"],
    }
    assert action.conditionality.value == "immediate"
    assert action.missing_argument_names == ()
    assert action.no_recovery_outcome is None

    lines = _verification_report_lines(report, finding_actions=(action,))
    finding_line = next(line for line in lines if line.startswith("finding\t"))
    assert finding_line.rsplit("\t", 1)[-1] == resolved_precondition_action_json_cell(action)
    assert '"action_id":"operator.registry.verify"' in finding_line
    assert '"conditionality":"immediate"' in finding_line
    assert "aeat app " not in finding_line


def test_verification_report_lines_omits_recovery_when_granted() -> None:
    """A granted verification report has neither findings nor a recovery field."""
    from datetime import UTC, datetime

    from ....domain.modelos.verification_report import (
        VerificationCompletenessStatus,
        VerificationReport,
        derive_verification_report_id,
    )
    from .._modelo_rendering import verification_report_lines as _verification_report_lines

    run_at = datetime(2026, 5, 27, 10, 0, 0, tzinfo=UTC)
    calc_id = "b" * 64
    report_id = derive_verification_report_id(
        calculation_revision_id=calc_id,
        completeness_status=VerificationCompletenessStatus.COMPLETE,
        findings=(),
        verified_by="test-actor",
    )
    report = VerificationReport(
        verification_report_id=report_id,
        calculation_revision_id=calc_id,
        completeness_status=VerificationCompletenessStatus.COMPLETE,
        run_at=run_at,
        verified_by="test-actor",
        granted_verificado_completo=True,
    )

    lines = _verification_report_lines(report)

    assert not any("next_action" in line for line in lines)


def test_verification_report_view_exposes_finding_legal_and_source_refs() -> None:
    """`verification-report view` surfaces each finding's legal_refs and source_refs.

    The verification-reports how-to promises every finding carries "the legal
    references behind the rule". This locks both transports the ``view`` command
    renders: the text ``finding_legal_refs`` / ``finding_source_refs`` lines and
    the typed JSON ``VerificationReportShowResult.findings[*].legal_refs`` /
    ``source_refs``. The grounding is pulled from the persisted finding, never
    invented.
    """
    from datetime import UTC, datetime

    from ....domain.modelos.verification_report import (
        ModeloVerificationFinding,
        ModeloVerificationFindingKind,
        ModeloVerificationFindingSeverity,
        VerificationCompletenessStatus,
        VerificationReport,
        derive_verification_report_id,
    )
    from .._modelo_payloads import VerificationReportShowResult
    from .._modelo_rendering import (
        verification_report_lines as _verification_report_lines,
    )
    from .._modelo_rendering import (
        verification_report_payload as _verification_report_payload,
    )

    run_at = datetime(2026, 5, 27, 10, 0, 0, tzinfo=UTC)
    calc_id = "c" * 64
    legal = ("ley-37-1992:art-88", "rd-1624-1992:art-71")
    sources = ("aeat-modelo-303-instructions",)
    findings = (
        ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            casilla_id=_VERIFICATION_FINDING_CASILLA,
            message_locale_key="application.modelo.findings.missing_required_casilla",
            message_facts={"casilla_id": str(_VERIFICATION_FINDING_CASILLA)},
            legal_refs=legal,
            source_refs=sources,
        ),
    )
    report_id = derive_verification_report_id(
        calculation_revision_id=calc_id,
        completeness_status=VerificationCompletenessStatus.BLOCKED,
        findings=findings,
        verified_by="test-actor",
    )
    report = VerificationReport(
        verification_report_id=report_id,
        calculation_revision_id=calc_id,
        completeness_status=VerificationCompletenessStatus.BLOCKED,
        findings=findings,
        run_at=run_at,
        verified_by="test-actor",
        granted_verificado_completo=False,
    )

    # Text transport: the line iterator the view command emits in text mode.
    lines = _verification_report_lines(report)
    legal_lines = [line for line in lines if line.startswith("finding_legal_refs\t")]
    source_lines = [line for line in lines if line.startswith("finding_source_refs\t")]
    assert len(legal_lines) == 1
    assert all(ref in legal_lines[0] for ref in legal)
    assert len(source_lines) == 1
    assert sources[0] in source_lines[0]

    # JSON transport: the exact typed payload the view command validates and
    # surfaces on the envelope's ``result``.
    payload = _verification_report_payload(report)
    result = VerificationReportShowResult.model_validate(payload.model_dump(mode="python"))
    dumped = result.model_dump(mode="json")
    finding = dumped["findings"][0]
    assert finding["legal_refs"] == list(legal)
    assert finding["source_refs"] == list(sources)


def test_verification_report_view_lists_missing_required_casillas() -> None:
    """`verification-report view` lists each missing required casilla id, not just a count.

    The verification-reports how-to ("The report says incomplete") promises the
    report lists which required casillas are still missing. This locks the text
    transport's per-id ``missing_casilla_id`` lines and the typed JSON
    ``missing_required_casilla_ids`` list against the bare ``count`` so the page's
    "lists which ones" claim cannot silently regress to a count-only view.
    """
    from datetime import UTC, datetime

    from ....domain.modelos.verification_report import (
        VerificationCompletenessStatus,
        VerificationReport,
        derive_verification_report_id,
    )
    from .._modelo_payloads import VerificationReportShowResult
    from .._modelo_rendering import (
        verification_report_lines as _verification_report_lines,
    )
    from .._modelo_rendering import (
        verification_report_payload as _verification_report_payload,
    )

    run_at = datetime(2026, 5, 27, 10, 0, 0, tzinfo=UTC)
    calc_id = "d" * 64
    report_id = derive_verification_report_id(
        calculation_revision_id=calc_id,
        completeness_status=VerificationCompletenessStatus.INCOMPLETE,
        findings=(),
        verified_by="test-actor",
    )
    missing = ("00501", "00552")
    report = VerificationReport(
        verification_report_id=report_id,
        calculation_revision_id=calc_id,
        completeness_status=VerificationCompletenessStatus.INCOMPLETE,
        missing_required_casilla_ids=missing,
        run_at=run_at,
        verified_by="test-actor",
        granted_verificado_completo=False,
    )

    # Text transport: one ``missing_casilla_id`` line per id, alongside the count.
    lines = _verification_report_lines(report)
    missing_lines = [line for line in lines if line.startswith("missing_casilla_id\t")]
    assert {line.split("\t", 1)[1] for line in missing_lines} == set(missing)
    assert f"missing_required_casilla_id_count\t{len(missing)}" in lines

    # JSON transport: the typed payload carries the full list, not just the count.
    payload = _verification_report_payload(report)
    result = VerificationReportShowResult.model_validate(payload.model_dump(mode="python"))
    dumped = result.model_dump(mode="json")
    assert dumped["missing_required_casilla_ids"] == list(missing)

    with pytest.raises(ValidationError) as raised:
        VerificationReportShowResult.model_validate(
            {
                **dumped,
                "resolved_casillas": [],
                "missing_required_casillas": list(missing),
            },
        )
    message = str(raised.value)
    assert "resolved_casillas" in message
    assert "missing_required_casillas" in message


def _blocked_report() -> VerificationReport:
    """Build one real, fully-validated canonical report to project."""
    from datetime import UTC, datetime

    from ....domain.modelos.verification_report import (
        ModeloVerificationFinding,
        ModeloVerificationFindingKind,
        ModeloVerificationFindingSeverity,
        VerificationCompletenessStatus,
        VerificationReport,
        derive_verification_report_id,
    )

    calculation_revision_id = "a" * 64
    findings = (
        ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.cross_casilla_invariant_violated",
            message_facts={"predicate_id": "test-predicate"},
            legal_refs=_TEST_FINDING_LEGAL_REFS,
        ),
    )
    return VerificationReport(
        verification_report_id=derive_verification_report_id(
            calculation_revision_id=calculation_revision_id,
            completeness_status=VerificationCompletenessStatus.BLOCKED,
            findings=findings,
            verified_by="test-actor",
        ),
        calculation_revision_id=calculation_revision_id,
        completeness_status=VerificationCompletenessStatus.BLOCKED,
        findings=findings,
        run_at=datetime(2026, 5, 27, 10, 0, 0, tzinfo=UTC),
        verified_by="test-actor",
        granted_verificado_completo=False,
    )


def test_the_projected_completeness_status_is_the_canonical_enum_not_a_free_string() -> None:
    """The projection carries the closed value the report holds, not a lookalike.

    A bare string admits ``"complete"`` misspelled, translated, or invented,
    and the one field an operator reads to decide whether a revision earned
    verificado-completo is the last place a lookalike should pass.
    """
    from ....domain.modelos.verification_report import VerificationCompletenessStatus
    from .._modelo_rendering import verification_report_payload

    payload = verification_report_payload(_blocked_report())

    assert payload.completeness_status is VerificationCompletenessStatus.BLOCKED


def test_a_completeness_status_outside_the_closed_set_is_refused() -> None:
    """Anti-vacuity: the narrowing rejects a value the bare string accepted."""
    from .._modelo_payloads import (
        VerificationReportPayload,
        VerificationReportShowResult,
        WorkVerifyResult,
    )
    from .._modelo_rendering import verification_report_payload

    fields = verification_report_payload(_blocked_report()).model_dump(mode="python")

    for schema in (VerificationReportPayload, VerificationReportShowResult, WorkVerifyResult):
        with pytest.raises(ValidationError):
            schema.model_validate({**fields, "completeness_status": "verificado_completo"})


def test_narrowing_the_status_left_the_json_wire_form_untouched() -> None:
    """The published value is still the enum's own token, byte for byte.

    A projection may tighten what it accepts; it may not quietly restate what
    it emits, because a machine consumer is reading the emitted token.
    """
    from .._modelo_rendering import verification_report_payload

    wire = verification_report_payload(_blocked_report()).model_dump(mode="json")

    assert wire["completeness_status"] == "blocked"
    assert wire["run_at"] == "2026-05-27T10:00:00+00:00"
