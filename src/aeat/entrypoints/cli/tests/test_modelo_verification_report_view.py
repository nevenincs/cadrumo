"""CLI modelo verification report rendering tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....domain.calculations.registry import CasillaId, validated_casilla_id

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_VERIFICATION_FINDING_CASILLA: CasillaId = validated_casilla_id(
    "0100",
    surface="_VERIFICATION_FINDING_CASILLA",
)


def test_verification_report_lines_includes_next_action_when_refused() -> None:
    """A refused verification report surfaces a retrieval next_action pointer."""
    from datetime import UTC, datetime

    from ....domain.modelos._verification_report import (
        ModeloVerificationFinding,
        ModeloVerificationFindingKind,
        ModeloVerificationFindingSeverity,
        VerificationCompletenessStatus,
        VerificationReport,
        derive_verification_report_id,
    )
    from .._modelo_rendering import verification_report_lines as _verification_report_lines

    run_at = datetime(2026, 5, 27, 10, 0, 0, tzinfo=UTC)
    calc_id = "a" * 64
    report_id = derive_verification_report_id(
        calculation_revision_id=calc_id,
        run_at=run_at,
        verified_by="test-actor",
    )
    report = VerificationReport(
        verification_report_id=report_id,
        calculation_revision_id=calc_id,
        completeness_status=VerificationCompletenessStatus.BLOCKED,
        findings=(
            ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.BLOCKING_RULE,
                severity=ModeloVerificationFindingSeverity.BLOCKING,
                message="cross-casilla predicate failed",
            ),
        ),
        run_at=run_at,
        verified_by="test-actor",
        granted_verificado_completo=False,
    )

    lines = _verification_report_lines(report)

    next_action_lines = [line for line in lines if line.startswith("next_action\t")]
    assert len(next_action_lines) == 1
    assert calc_id in next_action_lines[0]
    assert "verification-report list" in next_action_lines[0]


def test_verification_report_lines_omits_next_action_when_granted() -> None:
    """A granted verification report does NOT emit a next_action pointer."""
    from datetime import UTC, datetime

    from ....domain.modelos._verification_report import (
        VerificationCompletenessStatus,
        VerificationReport,
        derive_verification_report_id,
    )
    from .._modelo_rendering import verification_report_lines as _verification_report_lines

    run_at = datetime(2026, 5, 27, 10, 0, 0, tzinfo=UTC)
    calc_id = "b" * 64
    report_id = derive_verification_report_id(
        calculation_revision_id=calc_id,
        run_at=run_at,
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

    assert not any(line.startswith("next_action\t") for line in lines)


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

    from ....domain.modelos._verification_report import (
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
    report_id = derive_verification_report_id(
        calculation_revision_id=calc_id,
        run_at=run_at,
        verified_by="test-actor",
    )
    legal = ("ley-37-1992:art-88", "rd-1624-1992:art-71")
    sources = ("orden-eha-3786-2008:art-1",)
    report = VerificationReport(
        verification_report_id=report_id,
        calculation_revision_id=calc_id,
        completeness_status=VerificationCompletenessStatus.BLOCKED,
        findings=(
            ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.BLOCKING_RULE,
                severity=ModeloVerificationFindingSeverity.BLOCKING,
                casilla_id=_VERIFICATION_FINDING_CASILLA,
                message="cuota repercutida is under-declared",
                legal_refs=legal,
                source_refs=sources,
            ),
        ),
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

    from ....domain.modelos._verification_report import (
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
        run_at=run_at,
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
