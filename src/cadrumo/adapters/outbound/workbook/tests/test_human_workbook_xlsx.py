"""Inspect the delivered XLSX bytes, including comments and custom properties."""

from io import BytesIO
from zipfile import ZipFile

import pytest

from cadrumo.application.storage.calc_sheets.engine import build_export_plan
from cadrumo.application.storage.calc_sheets.human_workbook import human_workbook
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ..calc_sheets_xlsx import materialize_export_plan

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_human_workbook_has_no_technical_custom_properties_or_notes():
    snapshot = published_snapshot("130", filing_year=2025, period="4T")
    source = build_export_plan(snapshot)
    plan = human_workbook(source, snapshot)
    with ZipFile(BytesIO(materialize_export_plan(plan))) as archive:
        payload = "\n".join(archive.read(name).decode("utf-8") for name in archive.namelist() if name.endswith(".xml"))
        assert "docProps/custom.xml" not in archive.namelist()
    assert source.metadata.registry_sha not in payload
    assert "cadrumo_engine_version" not in payload
    assert "Snapshot fingerprint" not in payload
    assert all(binding.id not in payload for binding in snapshot.revision.bindings)
    assert "<f>" in payload
