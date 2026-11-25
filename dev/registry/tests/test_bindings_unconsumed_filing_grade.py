"""Only a typed consumer proves a binding is used; filing-grade orphans block.

A form input, a construct membership or an unbound casilla names a binding
without carrying its value into a calculation or an export. Counting those
mentions as use let filing-grade bindings that feed nothing read as consumed,
so the strict signal passed while they went unwired.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..binding_signal.report import summary as build_summary
from ..binding_signal.semantics import structural_binding_mentions, unconsumed_binding_report

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REVISION = str(filing_year_envelope().horizon)


def _binding(*, applicability: Mapping[str, object] | None = None) -> dict[str, object]:
    return {
        "modelo": "303",
        "revision": _REVISION,
        "binding_id": "modelo-303-synthetic-binding",
        "provider_kind": "ledger_iva_aggregation",
        "applicability": applicability,
        "location": {"path": "synthetic.toml", "family": "bindings", "ordinal": 1},
    }


def _report(
    *,
    disposition: str = "filing_grade",
    typed: Sequence[Mapping[str, object]] = (),
    mentions: Sequence[str] = (),
    applicability: Mapping[str, object] | None = None,
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    return unconsumed_binding_report(
        _binding(applicability=applicability),
        typed_consumers=typed,
        structural_mentions=[{"family": family} for family in mentions],
        provider_disposition=disposition,
        python_literal_references=3,
    )


def test_a_filing_grade_binding_named_only_by_a_form_input_and_a_construct_blocks() -> None:
    row, finding = _report(mentions=("form_layouts", "constructs"))

    assert row is not None
    assert row["classification"] == "filing_grade_unconsumed"
    assert row["structural_mentions"] == ["construct_membership", "form_input"]
    assert finding is not None
    assert finding["code"] == "UNCONSUMED_FILING_GRADE_BINDING"
    assert (finding["severity"], finding["actionability"]) == ("error", "actionable")
    assert "construct_membership, form_input" in str(finding["message"])


def test_a_typed_consumer_clears_the_same_binding() -> None:
    row, finding = _report(
        typed=({"kind": "export_field", "owner": "record.field"},),
        mentions=("form_layouts", "constructs"),
    )

    assert (row, finding) == (None, None)


def test_an_unbound_casilla_mention_does_not_clear_a_filing_grade_binding() -> None:
    row, finding = _report(mentions=("casillas",))

    assert row is not None
    assert row["structural_mentions"] == ["unbound_casilla"]
    assert finding is not None


def test_non_calculation_applicability_is_reported_without_blocking() -> None:
    row, finding = _report(applicability={"kind": "non_calculation"})

    assert row is not None
    assert row["classification"] == "excluded_non_calculation"
    assert finding is None


@pytest.mark.parametrize(
    ("disposition", "classification"),
    (
        ("deferred", "deferred_provider"),
        ("non_runtime", "non_runtime_provider"),
        ("unregistered", "unregistered_provider"),
    ),
)
def test_unconsumed_bindings_below_filing_grade_are_counted_not_blocking(disposition: str, classification: str) -> None:
    row, finding = _report(disposition=disposition)

    assert row is not None
    assert row["classification"] == classification
    assert finding is None


def test_authoring_delta_families_are_not_read_as_mentions() -> None:
    families = {
        "bindings": [{"id": "b"}],
        "casilla_overrides": [{"id": "c", "fields": {"binding": "b"}}],
        "family_overrides": [{"id": "f", "sequence_additions": {"bindings": ["b"]}}],
        "constructs": [{"id": "k", "bindings": ["b"]}],
    }

    mentions = [(family, binding_id) for family, _row, _path, binding_id in structural_binding_mentions(families)]

    assert mentions == [("constructs", "b")]


def _payload(
    findings: list[dict[str, object]],
    *,
    classification: str = "measured",
    limitations: Sequence[Mapping[str, object]] = (),
) -> dict[str, object]:
    return {
        "summary": {"classification": classification, "findings": len(findings)},
        "lanes": {"declaration_shape": {}, "route_status": {}},
        "hotspots": {},
        "findings": findings,
        "limitations": list(limitations),
    }


def test_summary_names_each_blocking_finding(tmp_path: Path) -> None:
    _row, finding = _report()
    assert finding is not None

    summary = build_summary(_payload([finding]), tmp_path / "binding-signal.json")

    assert summary["blocking_findings_total"] == 1
    assert summary["blocking_findings"] == [
        {
            "code": "UNCONSUMED_FILING_GRADE_BINDING",
            "modelo": "303",
            "revision": _REVISION,
            "binding": "modelo-303-synthetic-binding",
        }
    ]
    assert str(summary["headline"]).startswith("1 blocking binding finding")


def test_summary_of_an_incomplete_census_says_the_counts_are_partial(tmp_path: Path) -> None:
    payload = _payload(
        [],
        classification="processing_error",
        limitations=({"code": "SUPPORT_ENVELOPE_UNAVAILABLE"}, {"code": "CONSUMER_CENSUS_UNAVAILABLE"}),
    )

    summary = build_summary(payload, tmp_path / "binding-signal.json")

    assert summary["headline"] == (
        "binding census incomplete (CONSUMER_CENSUS_UNAVAILABLE, SUPPORT_ENVELOPE_UNAVAILABLE); "
        "counts below are partial"
    )


def test_summary_without_blocking_findings_says_so(tmp_path: Path) -> None:
    summary = build_summary(_payload([]), tmp_path / "binding-signal.json")

    assert summary["blocking_findings_total"] == 0
    assert summary["blocking_findings"] == []
    assert summary["headline"] == "no blocking binding findings"
