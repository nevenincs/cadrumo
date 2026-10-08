"""Exact historical preview selection stays separate from filing admission."""

from collections.abc import MutableMapping
from typing import cast

import pytest
from pydantic import ValidationError

from cadrumo.application.storage.calc_sheets.template_source import WorkbookTemplateSource
from cadrumo.domain.calculations.registry.errors import NoRevisionForPeriodError, RegistryValidationError

from ..workbook_template_source import load_workbook_template_source

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def _source() -> WorkbookTemplateSource:
    return load_workbook_template_source(
        "232", revision_id="2016-2017", source_ref="aeat-dr-232-2016", preview_year=2017, preview_period="0A"
    )


def test_historical_source_is_exact_immutable_and_not_a_filing_snapshot() -> None:
    source = _source()
    assert source.revision.id == "2016-2017"
    assert source.preview_frame.filing_year == 2017
    assert source.source_ref == "aeat-dr-232-2016"
    assert source.template_digest == _source().template_digest
    assert not hasattr(source, "snapshot_ref")
    assert not hasattr(source, "filing_period")
    with pytest.raises(TypeError):
        cast("MutableMapping[str, object]", source.sources)["invented"] = source.sources[source.source_ref]
    with pytest.raises(ValidationError):
        WorkbookTemplateSource.model_validate({**dict(source), "source_ref": "invented"})


def test_form_design_pin_is_included_in_preview_evidence_and_identity() -> None:
    source = load_workbook_template_source(
        "232",
        revision_id="2016-2017",
        source_ref="boe-2017-10042-modelo-232-form-pdf",
        preview_year=2017,
        preview_period="0A",
    )
    assert source.sources[source.source_ref].id == source.source_ref
    assert source.template_digest != _source().template_digest


@pytest.mark.parametrize(
    ("revision_id", "source_ref", "year", "period", "error"),
    [
        ("2018-y-siguientes", "aeat-dr-232-2018", 2017, "0A", NoRevisionForPeriodError),
        ("2016-2017", "aeat-dr-232-2016", 2025, "0A", NoRevisionForPeriodError),
        ("2016-2017", "aeat-dr-232-2016", 2017, "4T", NoRevisionForPeriodError),
        ("2016-2017", "unrelated-source", 2017, "0A", RegistryValidationError),
        ("2016-2017", "aeat-dr-232-2018", 2017, "0A", RegistryValidationError),
    ],
)
def test_preview_refuses_mismatched_design_frame_and_source(
    revision_id: str, source_ref: str, year: int, period: str, error: type[Exception]
) -> None:
    with pytest.raises(error):
        load_workbook_template_source(
            "232", revision_id=revision_id, source_ref=source_ref, preview_year=year, preview_period=period
        )
