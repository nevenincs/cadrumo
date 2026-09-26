"""The provenance matrix fixtures parse through the real product readers.

Each synthetic source is read by the same provider or invoice-book reader the
installed product uses, and the stored locator of the target record must be
the one the fixture computed from its own layout.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.adapters.inbound.financial.providers.base import FinancialProvider
from cadrumo.adapters.inbound.financial.providers.csv import CsvProvider
from cadrumo.adapters.inbound.financial.providers.detection import detect_provider
from cadrumo.adapters.inbound.financial.providers.ofx import OfxProvider
from cadrumo.adapters.inbound.financial.providers.pdf_n26 import PdfN26Provider
from cadrumo.adapters.inbound.financial.providers.xlsx import XlsxProvider
from cadrumo.application.invoices.bulk_import import read_bulk_invoice_import_source

from ..provenance_fixtures import ProvenanceCase, provenance_cases

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CASES = provenance_cases()
_EXPLICIT_PROVIDERS: dict[str, type[FinancialProvider]] = {
    "csv": CsvProvider,
    "xlsx": XlsxProvider,
    "ofx": OfxProvider,
    "pdf-n26": PdfN26Provider,
}


def _provider(case: ProvenanceCase, path: Path) -> FinancialProvider:
    if case.provider == "auto":
        detected = detect_provider(path)
        assert detected is not None
        return detected
    assert case.provider is not None
    return _EXPLICIT_PROVIDERS[case.provider]()


@pytest.mark.parametrize(
    "case", [case for case in _CASES if case.record == "transaction"], ids=lambda case: case.case_id
)
def test_statement_fixture_stores_the_expected_locator(case: ProvenanceCase, tmp_path: Path) -> None:
    path = case.write(tmp_path)
    provider = _provider(case, path)

    assert provider.validate_source(path).is_valid
    rows = list(provider.ingest(path))
    targets = [row for row in rows if row.raw.description == case.target_key]

    assert len(rows) == case.row_count
    assert len(targets) == 1
    provenance = targets[0].raw.provenance
    assert (provenance.source_path.name, provenance.source_row_index) == (case.filename, case.locator)


@pytest.mark.parametrize("case", [case for case in _CASES if case.record == "invoice"], ids=lambda case: case.case_id)
def test_invoice_fixture_reads_the_target_at_its_physical_row(case: ProvenanceCase, tmp_path: Path) -> None:
    source = read_bulk_invoice_import_source(case.write(tmp_path), mapper=None)

    targets = [row for row in source.rows if row.values.get("invoice_number") == case.target_key]

    assert len(source.rows) == case.row_count
    assert [row.row_number for row in targets] == [case.locator]
    provenance = targets[0].provenance
    assert provenance is not None
    assert (provenance.source_path.name, provenance.source_row_index) == (case.filename, case.locator)


def test_the_matrix_does_not_put_every_target_on_the_same_row() -> None:
    assert len({case.locator for case in _CASES}) > 1
    assert {case.import_frontend for case in _CASES} == {"cli", "tui"}


def test_case_sources_refuse_to_overwrite_an_existing_file(tmp_path: Path) -> None:
    case = _CASES[0]
    (tmp_path / case.filename).write_text("synthetic", encoding="utf-8")

    with pytest.raises(FileExistsError):
        case.write(tmp_path)

    assert (tmp_path / case.filename).read_text(encoding="utf-8") == "synthetic"


def test_no_target_key_is_contained_in_another_case_s_key() -> None:
    """The installed TUI finds a record by its visible text, so no key may appear inside another.

    ``ledger-prov-cli-xls`` inside ``ledger-prov-cli-xlsx`` once made the TUI
    see two matching rows for one case.
    """
    keys = {case.case_id: case.target_key for case in _CASES}
    clashes = [
        (case_id, other_id)
        for case_id, key in keys.items()
        for other_id, other in keys.items()
        if case_id != other_id and key in other
    ]
    assert clashes == []
