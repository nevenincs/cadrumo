"""A calculation report lists the source disagreements the operator had accepted, and only then.

The listing is part of the canonical payload when there is one, and absent from it
when there is none, so a report that applies no acceptance has the bytes and the
digest it had before the section existed. The independent oracle for those bytes
is the legacy payload shape written out here, not the model under test.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.calculation_revision_sources import CalculationSourceIssue
from ....domain.modelos.credit_resolution import CreditResolutionRecord
from ....domain.modelos.tests.source_disagreement_support import sample_source_disagreement
from ..calculation_report import CALCULATION_REPORT_CONTENT_VERSION, ModeloCalculationReport
from ..calculation_report_document import calculation_report_csv_preamble_lines, serialize_calculation_report_csv
from ..credit_resolution import credit_resolution_for_finding
from .calculation_report_fixture import build_fixture_report

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_AT = datetime(1980, 4, 2, 9, 0, tzinfo=UTC)
_REASON = "Synthetic reason, with a comma:\nthe payer's copy states\tthis amount."


def _record(casilla_id: str = "0596") -> CreditResolutionRecord:
    issue = CalculationSourceIssue(
        reason="credit_source_disagreement",
        binding_source=None,
        message="synthetic",
        casilla_id=casilla_id,
        disagreement=sample_source_disagreement(casilla_id=casilla_id),
    )
    return credit_resolution_for_finding(issue, reason=_REASON, at=_AT, by_session="session-one")


def _legacy_payload(report: ModeloCalculationReport) -> dict[str, object]:
    """The payload shape a report had before it could list acceptances, written out independently."""
    return {
        "content_version": CALCULATION_REPORT_CONTENT_VERSION,
        "header": report.header.model_dump(mode="json"),
        "rows": [row.model_dump(mode="json") for row in report.rows],
    }


def _legacy_bytes(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def test_a_report_that_applies_no_acceptance_keeps_the_bytes_and_digest_it_always_had(
    operation: PinnedAuthorityOperation,
) -> None:
    report, _ = build_fixture_report(operation)

    expected = _legacy_bytes(_legacy_payload(report))

    assert report.credit_resolutions == ()
    assert set(report.canonical_payload()) == {"content_version", "header", "rows"}
    assert report.canonical_bytes() == expected
    assert report.report_sha256 == hashlib.sha256(expected).hexdigest()
    assert not [line for line in calculation_report_csv_preamble_lines(report) if "credit_resolution" in line]


def test_a_report_with_an_acceptance_lists_it_in_its_payload_and_changes_its_digest(
    operation: PinnedAuthorityOperation,
) -> None:
    without, _ = build_fixture_report(operation)
    record = _record()

    report, _ = build_fixture_report(operation, credit_resolutions=(record,))

    (item,) = report.credit_resolutions
    assert item.finding_id == record.finding_key[:16]
    assert item.box == "0596"
    assert [(source.role, source.value) for source in item.sources] == [
        ("value_source", "500.00"),
        ("cross_check", "499.99"),
    ]
    assert (item.accepted_role, item.reason, item.resolved_at) == ("value_source", _REASON, _AT)
    payload = report.canonical_payload()
    assert set(payload) == {"content_version", "header", "rows", "credit_resolutions"}
    assert report.canonical_bytes() == _legacy_bytes(payload)
    assert report.report_sha256 != without.report_sha256
    # Nothing but the section differs: the rows are the same rows.
    assert report.rows == without.rows


def test_the_csv_lists_each_acceptance_on_one_comment_line_above_an_unchanged_table(
    operation: PinnedAuthorityOperation,
) -> None:
    without, _ = build_fixture_report(operation)
    report, _ = build_fixture_report(operation, credit_resolutions=(_record("0596"), _record("0597")))

    lines = [line for line in calculation_report_csv_preamble_lines(report) if "credit_resolution" in line]
    csv = serialize_calculation_report_csv(report).decode()

    assert len(lines) == 2
    assert lines[0].startswith("# credit_resolution_1: box=0596 finding=") and lines[1].startswith(
        "# credit_resolution_2: box=0597 finding="
    )
    for line in lines:
        assert "\n" not in line and "\t" not in line
        assert "reason=Synthetic reason, with a comma: the payer's copy states this amount." in line
        assert "sources=value_source=500.00; cross_check=499.99" in line

    def table(text: str) -> str:
        return text[text.index("casilla_id,") :]

    assert table(csv) == table(serialize_calculation_report_csv(without).decode())
