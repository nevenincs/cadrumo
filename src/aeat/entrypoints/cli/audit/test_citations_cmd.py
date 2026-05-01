"""Tests for ``aeat audit rulesets citations`` (#339).

Three paths exercised via :class:`typer.testing.CliRunner` against
``audit_app`` directly — the command is not yet registered on the root
``aeat`` Typer (Phase 2 deferral). All tests use real
:class:`Ruleset` / :class:`CasillaDefinition` / :class:`LegalCitation`
instances; the gap-path fixture uses pydantic's documented
``model_construct`` escape hatch to assemble a "missing-citation"
casilla without bypassing every other validator on the model.
"""

from __future__ import annotations

import io

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from ....domain.casillas import CasillaDataType
from ....domain.formulas._casilla import CasillaDefinition
from ....domain.formulas._rulesets import MODELO_130_2025, MODELO_303_2025
from . import (
    aggregate_reports,
    audit_app,
    validate_citation_coverage,
)
from ._helpers import CitationCoverageReport

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


def _runner() -> CliRunner:
    """Return a :class:`CliRunner` configured for UTF-8 capture."""
    return CliRunner()


def test_citations_cmd_happy_path_exits_zero() -> None:
    """Every registered ruleset has 100% coverage; exit code is 0."""
    runner = _runner()
    result = runner.invoke(audit_app, ["rulesets", "citations"])
    assert result.exit_code == 0, result.output
    assert "modelo_130.2025" in result.output
    assert "modelo_303.2025" in result.output
    assert "aggregate" in result.output
    assert "GAP" not in result.output
    assert "OK " in result.output


def test_citations_cmd_renders_spanish_diacritics() -> None:
    """Spanish modelo / casilla rendering survives a non-ASCII path.

    The audit-CLI reports include ruleset_id strings that don't carry
    diacritics, but a regression elsewhere could allow a ruleset author
    to introduce a non-ASCII identifier. We probe the encoding-safety
    of the command's output stream by writing a control sample through
    a UTF-8-backed buffer and confirming the framing characters
    survive.

    Wave-69 regression #389 surfaced a Windows cp1252 crash on
    non-ASCII output. The :func:`_reconfigure_utf8` helper invoked at
    command entry guards against that path.
    """
    runner = _runner()
    result = runner.invoke(audit_app, ["rulesets", "citations"])
    assert result.exit_code == 0, result.output
    rendered = result.output.encode("utf-8").decode("utf-8")
    assert "OK " in rendered
    probe = io.StringIO()
    probe.write("artículo 110 — agrícolas, ganaderas, forestales y pesqueras\n")
    assert "artículo" in probe.getvalue()


def test_validate_citation_coverage_detects_simulated_gap() -> None:
    """The helper returns a non-100% report when a casilla is missing.

    This is the only documented way to construct a casilla with empty
    ``legal_basis`` and ``computed=True`` after #339: pydantic's
    ``model_construct`` skips the validator stack. We use it here to
    prove the audit reporter's gap path independently of the
    validator's protection. A real ruleset can never reach this state
    via normal construction.
    """
    bypassed = CasillaDefinition.model_construct(
        casilla_id="99",
        label={"es": "x", "en": "x", "hu": "x"},
        computed=True,
        data_type=CasillaDataType.CURRENCY_EUR,
        legal_basis=(),
        notes_es=None,
    )
    base = MODELO_130_2025
    augmented_casillas = (*base.casillas, bypassed)
    mutated = base.model_construct(
        ruleset_id=base.ruleset_id,
        modelo=base.modelo,
        variant=base.variant,
        effective_from=base.effective_from,
        effective_to=base.effective_to,
        casillas=augmented_casillas,
        formulas=base.formulas,
        parameters=base.parameters,
        legal_citations=base.legal_citations,
    )
    report = validate_citation_coverage(mutated)
    assert report.coverage_percent < 1.0
    assert "99" in report.missing_casillas
    assert report.is_complete is False


def test_validate_citation_coverage_handles_zero_computed() -> None:
    """A ruleset with no computed casillas reports 100% trivially.

    Edge case: division-by-zero protection in the helper. No real
    ruleset reaches this state today (every shipped ruleset has at
    least one computed casilla), but the helper must not raise.
    """
    base = MODELO_130_2025
    user_only_casillas = tuple(c for c in base.casillas if not c.computed)
    mutated = base.model_construct(
        ruleset_id=base.ruleset_id,
        modelo=base.modelo,
        variant=base.variant,
        effective_from=base.effective_from,
        effective_to=base.effective_to,
        casillas=user_only_casillas,
        formulas=(),
        parameters=base.parameters,
        legal_citations=base.legal_citations,
    )
    report = validate_citation_coverage(mutated)
    assert report.total_computed == 0
    assert report.with_citation == 0
    assert report.coverage_percent == 1.0
    assert report.missing_casillas == ()


def test_citation_coverage_report_is_strict_frozen() -> None:
    """Confirms the report model contract: strict + frozen + extra=forbid."""
    report = validate_citation_coverage(MODELO_130_2025)
    with pytest.raises(ValidationError):
        report.coverage_percent = 0.0  # type: ignore[misc]


def test_aggregate_report_includes_every_missing_casilla() -> None:
    """Aggregate prefixes missing-casilla ids with the contributing ruleset."""
    base = MODELO_130_2025
    bypassed = CasillaDefinition.model_construct(
        casilla_id="50",
        label={"es": "x", "en": "x", "hu": "x"},
        computed=True,
        data_type=CasillaDataType.CURRENCY_EUR,
        legal_basis=(),
        notes_es=None,
    )
    mutated = base.model_construct(
        ruleset_id=base.ruleset_id,
        modelo=base.modelo,
        variant=base.variant,
        effective_from=base.effective_from,
        effective_to=base.effective_to,
        casillas=(*base.casillas, bypassed),
        formulas=base.formulas,
        parameters=base.parameters,
        legal_citations=base.legal_citations,
    )
    reports = (validate_citation_coverage(mutated),)
    aggregate = aggregate_reports(reports)
    assert aggregate.is_complete is False
    assert any("50" in m for m in aggregate.missing_casillas)


def test_aggregate_single_modelo_preserves_modelo() -> None:
    """When every input shares a modelo, the aggregate carries it."""
    reports = (validate_citation_coverage(MODELO_130_2025),)
    aggregate = aggregate_reports(reports)
    assert aggregate.modelo == MODELO_130_2025.modelo


def test_aggregate_mixed_modelos_yields_none_modelo() -> None:
    """A mixed-modelo aggregate sets ``modelo`` to ``None``.

    Picking an arbitrary "representative" modelo from a mixed bag
    would mislead any downstream consumer that filters by modelo
    (Gemini #433 medium finding).
    """
    reports = (
        validate_citation_coverage(MODELO_130_2025),
        validate_citation_coverage(MODELO_303_2025),
    )
    aggregate = aggregate_reports(reports)
    assert aggregate.modelo is None
    assert aggregate.is_complete is True


def test_aggregate_with_none_modelo_renders_as_all() -> None:
    """The CLI line for a multi-modelo aggregate renders 'modelo all'."""
    from . import _render_line

    aggregate_like = CitationCoverageReport(
        ruleset_id="aggregate",
        modelo=None,
        effective_from=MODELO_130_2025.effective_from,
        effective_to=MODELO_130_2025.effective_to,
        total_computed=10,
        with_citation=10,
        coverage_percent=1.0,
        missing_casillas=(),
    )
    rendered = _render_line(aggregate_like)
    assert "modelo all" in rendered
