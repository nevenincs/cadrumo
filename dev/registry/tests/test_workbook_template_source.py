"""Exact historical preview selection stays separate from filing admission."""

from collections.abc import MutableMapping
from typing import cast

import pytest
from pydantic import ValidationError

from cadrumo.application.storage.calc_sheets.template_source import WorkbookTemplateSource
from cadrumo.domain.calculations.registry.errors import NoRevisionForPeriodError, RegistryValidationError

from ..workbook_template_source import load_workbook_template_source
from .authored_edition_support import authored_revisions

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

#: Modelo 232 authors a closed historical edition and the open-ended one that follows it.
_BASE, _DELTA = authored_revisions("232")
_BASE_ID, _DELTA_ID = str(_BASE.id), str(_DELTA.id)
assert _BASE.valid_to is not None
_BASE_YEAR, _DELTA_YEAR = _BASE.valid_to.year, _DELTA.valid_from.year
_BASE_DESIGN = next(str(ref) for ref in _BASE.source_refs if str(ref).startswith("aeat-dr-232-"))
_DELTA_DESIGN = next(str(ref) for ref in _DELTA.source_refs if str(ref).startswith("aeat-dr-232-"))


def _source() -> WorkbookTemplateSource:
    return load_workbook_template_source(
        "232", revision_id=_BASE_ID, source_ref=_BASE_DESIGN, preview_year=_BASE_YEAR, preview_period="0A"
    )


def test_historical_source_is_exact_immutable_and_not_a_filing_snapshot() -> None:
    source = _source()
    assert source.revision.id == _BASE_ID
    assert source.preview_frame.filing_year == _BASE_YEAR
    assert source.source_ref == _BASE_DESIGN
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
        revision_id=_BASE_ID,
        source_ref="boe-2017-10042-modelo-232-form-pdf",
        preview_year=_BASE_YEAR,
        preview_period="0A",
    )
    assert source.sources[source.source_ref].id == source.source_ref
    assert source.template_digest != _source().template_digest


@pytest.mark.parametrize(
    ("revision_id", "source_ref", "year", "period", "error"),
    [
        (_DELTA_ID, _DELTA_DESIGN, _BASE_YEAR, "0A", NoRevisionForPeriodError),
        (_BASE_ID, _BASE_DESIGN, _DELTA_YEAR, "0A", NoRevisionForPeriodError),
        (_BASE_ID, _BASE_DESIGN, _BASE_YEAR, "4T", NoRevisionForPeriodError),
        (_BASE_ID, "unrelated-source", _BASE_YEAR, "0A", RegistryValidationError),
        (_BASE_ID, _DELTA_DESIGN, _BASE_YEAR, "0A", RegistryValidationError),
    ],
)
def test_preview_refuses_mismatched_design_frame_and_source(
    revision_id: str, source_ref: str, year: int, period: str, error: type[Exception]
) -> None:
    with pytest.raises(error):
        load_workbook_template_source(
            "232", revision_id=revision_id, source_ref=source_ref, preview_year=year, preview_period=period
        )
