"""Whole-inventory accounting and real compiler evidence stay distinguishable."""

import pytest
from pydantic import TypeAdapter

from cadrumo.application.storage.calc_sheets.errors import CalcSheetsEngineError

from .. import workbook_probe
from ..compiler.authority import compiled_bundled_authority
from ..form_layout.coverage import coverage_rows
from ..workbook_probe import ProbeResult, declared_probe_frame, probe_authority, probe_revision

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


@pytest.fixture(scope="module")
def authority():
    return compiled_bundled_authority()


def _row(authority):
    return next(
        row
        for row in coverage_rows(authority.modelos)
        if row.modelo_id == "130" and row.revision_id == "2019-y-siguientes"
    )


def test_real_declared_frame_and_compiler_are_used(authority):
    result = probe_revision(authority, _row(authority))
    assert result.status == "compiled", result.as_json()
    assert result.frame is not None
    revision = authority.modelo("130").revisions[result.coverage.revision_id]
    assert revision.period_selector.includes_year(result.frame.filing_year)
    assert result.frame.period in revision.period_selector.periods_for_year(result.frame.filing_year)
    assert result.value_cells > 0 and result.formula_cells > 0


def test_inventory_accounts_for_every_revision_and_does_not_claim_live_evidence(authority, monkeypatch):
    inventory = coverage_rows(authority.modelos)
    seen = []

    def alternating_probe(current, row):
        assert current is authority
        seen.append((row.modelo_id, row.revision_id))
        return ProbeResult(row, "compiled" if len(seen) % 2 else "compiler_refused")

    monkeypatch.setattr(workbook_probe, "probe_revision", alternating_probe)
    report = probe_authority(authority)
    assert seen == [(row.modelo_id, row.revision_id) for row in inventory]
    results = TypeAdapter(list[dict[str, object]]).validate_python(report["results"], strict=True)
    outcomes = TypeAdapter(dict[str, int]).validate_python(report["outcomes"], strict=True)
    assert len(results) == len(inventory)
    assert sum(outcomes.values()) == len(inventory)
    assert report["full_inventory"] is True
    assert report["live_google_verification"] is False
    assert report["official_visual_verification"] is False
    assert report["populated_calculation_verification"] is False


@pytest.mark.parametrize(
    ("error", "status"),
    (
        (CalcSheetsEngineError("missing authored label", context={"reference": "registry-input"}), "compiler_refused"),
        (RuntimeError("injected compiler defect"), "unexpected_error"),
    ),
)
def test_compiler_refusals_and_unexpected_errors_remain_distinct(authority, monkeypatch, error, status):
    def fail(_snapshot):
        raise error

    monkeypatch.setattr(workbook_probe, "build_export_plan", fail)
    result = probe_revision(authority, _row(authority))
    assert result.status == status
    assert result.frame is not None
    assert result.stage == "engine"
    assert result.error_type == type(error).__name__
    assert result.message == str(error)
    if status == "compiler_refused":
        assert result.context == {"reference": "registry-input"}


def test_declared_but_outside_supported_span_has_no_probe_frame(authority):
    modelo = authority.modelo("130")
    revision = modelo.revisions["2019-y-siguientes"]
    support = authority.supported_filing_years()
    outside = support.model_copy(update={"floor": 2090, "horizon": 2090})
    closed = revision.model_copy(
        update={
            "period_selector": revision.period_selector.model_copy(
                update={"years": (2025,), "year_from": None, "year_to": None}
            )
        }
    )
    assert declared_probe_frame(modelo, closed, outside) is None


def test_subset_is_explicit_and_unknown_modelo_is_refused(authority, monkeypatch):
    monkeypatch.setattr(workbook_probe, "probe_revision", lambda _authority, row: ProbeResult(row, "unsupported_frame"))
    report = probe_authority(authority, modelos=frozenset({"130"}))
    assert report["full_inventory"] is False
    results = TypeAdapter(list[dict[str, object]]).validate_python(report["results"], strict=True)
    inventory_revisions = report["inventory_revisions"]
    assert isinstance(inventory_revisions, int)
    assert {row["modelo"] for row in results} == {"130"}
    assert inventory_revisions > len(results)
    with pytest.raises(ValueError, match="present in the registry"):
        probe_authority(authority, modelos=frozenset({"not-a-modelo"}))
