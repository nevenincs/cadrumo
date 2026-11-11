"""Communication workbooks retain their coordinate without becoming filings."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from .....core.period import Period, PeriodError
from ..records import SheetAdministrativeFrame, SheetExportMetadata

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("code", ["comunicacion", "variacion"])
def test_administrative_metadata_round_trip_preserves_nonfiling_coordinate(code: str) -> None:
    frame = SheetAdministrativeFrame(filing_year=2025, code=code)
    metadata = SheetExportMetadata(
        modelo_id="145",
        revision_id="2012-01-31-y-siguientes",
        filing_year=2025,
        period=frame,
        engine_version="test",
        registry_sha="0123456789abcdef",
        exported_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    restored = SheetExportMetadata.model_validate_json(metadata.model_dump_json())
    assert isinstance(restored.period, SheetAdministrativeFrame)
    assert restored.period.registry_token == code
    with pytest.raises(PeriodError):
        Period.from_year_and_code(2025, code)
    with pytest.raises(ValidationError, match="does not match period year"):
        SheetExportMetadata.model_validate({**dict(metadata), "filing_year": 2026})


@pytest.mark.parametrize("code", ["4T", "0A", "EVENT-3", "EVENT-N", "invented"])
def test_administrative_frame_does_not_relax_filing_or_selector_validation(code: str) -> None:
    with pytest.raises(ValidationError):
        SheetAdministrativeFrame(filing_year=2025, code=code)
