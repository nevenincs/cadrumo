"""Tests for the disabled ``aeat audit rulesets citations`` command."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from ....domain.modelos import ModeloCode
from . import audit_app
from ._helpers import CitationCoverageReport, aggregate_reports, validate_citation_coverage

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _runner() -> CliRunner:
    """Return a :class:`CliRunner` configured for UTF-8 capture."""
    return CliRunner()


def _report(
    ruleset_id: str,
    *,
    modelo: ModeloCode | None = ModeloCode.MODELO_130,
    missing: tuple[str, ...] = (),
) -> CitationCoverageReport:
    total = 2
    with_citation = total - len(missing)
    return CitationCoverageReport(
        ruleset_id=ruleset_id,
        modelo=modelo,
        effective_from=date(2025, 1, 1),
        effective_to=None,
        total_computed=total,
        with_citation=with_citation,
        coverage_percent=with_citation / total,
        missing_casillas=missing,
    )


def test_citations_cmd_requires_registry_snapshot() -> None:
    runner = _runner()
    result = runner.invoke(audit_app, ["rulesets", "citations"])

    assert result.exit_code == 1, result.output
    assert "legacy ruleset audits are disabled" in result.output
    assert "use the registry" in result.output


def test_validate_citation_coverage_rejects_legacy_rulesets() -> None:
    with pytest.raises(ValueError, match="legacy ruleset citation audits are disabled"):
        validate_citation_coverage(object())


def test_citation_coverage_report_is_strict_frozen() -> None:
    report = _report("modelo_130.2025")

    with pytest.raises(ValidationError):
        report.coverage_percent = 0.0  # type: ignore[misc]


def test_aggregate_report_includes_every_missing_casilla() -> None:
    aggregate = aggregate_reports((_report("modelo_130.2025", missing=("50",)),))

    assert aggregate.is_complete is False
    assert aggregate.missing_casillas == ("modelo_130.2025:50",)


def test_aggregate_single_modelo_preserves_modelo() -> None:
    aggregate = aggregate_reports((_report("modelo_130.2025"),))

    assert aggregate.modelo == ModeloCode.MODELO_130


def test_aggregate_mixed_modelos_yields_none_modelo() -> None:
    aggregate = aggregate_reports(
        (
            _report("modelo_130.2025", modelo=ModeloCode.MODELO_130),
            _report("modelo_303.2025", modelo=ModeloCode.MODELO_303),
        )
    )

    assert aggregate.modelo is None
    assert aggregate.is_complete is True
