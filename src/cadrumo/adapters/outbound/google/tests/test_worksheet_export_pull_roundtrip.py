"""Historical workbook input records stay readable after remote calculation retirement."""

import pytest

from ..calc_sheets_pull_records import MetadataMatchState, PullMetadata, PullResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_historical_pull_record_roundtrip_retains_its_identity_without_execution() -> None:
    record = PullResult(
        spreadsheet_id="historical-sheet",
        operator_edits=(),
        binding_edits=(),
        relation_edits=(),
        metadata=PullMetadata(
            modelo_id="303",
            revision_id="2025",
            filing_year=2025,
            period="1T",
            engine_version="historical",
            registry_sha="recorded-registry",
        ),
        metadata_match=MetadataMatchState.MATCHES,
        cells_read=0,
    )
    assert PullResult.model_validate_json(record.model_dump_json()) == record
