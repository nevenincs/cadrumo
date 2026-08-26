"""Modelo 309's exact historical record-design epochs."""

from __future__ import annotations

from datetime import date
from functools import cache

import pytest

from .....core import RegistryAuthorityGrade
from .....core.hashing import hash_file
from .....core.resources import bundled_path
from .._validate_export_layout_coverage import validate_export_layout_record_coverage
from ..errors import AmbiguousRevisionSelectionError, NoRevisionForPeriodError, RegistryValidationError
from ..loader import _load_shared_catalogue_files, load_modelo_directory
from ..record_design import extract_record_design
from ..schema import ModeloDefinition, RegistryCatalogues
from ..snapshot import build_snapshot
from ..temporal import select_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@cache
def _modelo_309() -> tuple[ModeloDefinition, RegistryCatalogues]:
    """Load this modelo and shared catalogues without in-flight peer modelos."""
    return (
        load_modelo_directory(bundled_path("registry", "aeat", "modelos", "309")),
        _load_shared_catalogue_files(bundled_path("registry", "aeat", "legal")),
    )


_SOURCES = {
    "2004-2015": ("aeat-dr-309-2004", 44858, "7a855ce41e9b2363a5275b7e88a9587616cfb13db2c2e541c2665ece1815e7b6"),
    "2016-2017": ("aeat-dr-309-2016", 177152, "a54467bf47a3a8b16be42e770c174347fea14ca4315cc1b35c10d81f85c159c5"),
    "2018-2022": ("aeat-dr-309-2018", 185856, "7f46a0301f27345c19530a6a12acfa976ab5b60a67e563afa68277c12f2b07a8"),
    "2023-y-siguientes": ("aeat-dr-309-2023", 192000, "a84c6347a87ac4c4db8610010e100cb8632518a9d20e54e79ffbc713d770beb5"),
}


def test_modelo_309_exact_source_bytes_and_complete_extractions_are_pinned() -> None:
    """Each served geometry has one official record-design source and full parse."""
    _modelo, catalogues = _modelo_309()
    expected_sheets = {
        "aeat-dr-309-2004": (("PDF record design", 64, 1300),),
        "aeat-dr-309-2016": (("M30900", 13, None), ("M30901", 61, 1500)),
        "aeat-dr-309-2018": (("M30900", 13, None), ("M30901", 65, 1500)),
        "aeat-dr-309-2023": (("M30900", 13, None), ("M30901", 68, 1500)),
    }

    for source_ref, expected_bytes, expected_sha256 in _SOURCES.values():
        source = catalogues.sources[source_ref]
        path = bundled_path() / source.corpus_path
        assert source.evidence_tier == "layout_authority"
        assert source.authority == "aeat"
        assert source.kind == "record_design"
        assert hash_file(path) == (expected_sha256, expected_bytes)
        assert tuple((sheet.name, len(sheet.fields), sheet.total_positions) for sheet in extract_record_design(path).require_complete()) == expected_sheets[source_ref]


def test_modelo_309_selects_four_non_overlapping_epochs_and_refuses_pre_design_years() -> None:
    """A proved record layout cannot be backdated or allowed to overlap another."""
    modelo, _catalogues = _modelo_309()

    with pytest.raises(NoRevisionForPeriodError):
        select_revision(modelo, filing_year=2003, period="AD-HOC", on=date(2003, 12, 31))

    for filing_year, expected_revision in ((2004, "2004-2015"), (2015, "2004-2015"), (2016, "2016-2017"), (2017, "2016-2017"), (2018, "2018-2022"), (2022, "2018-2022"), (2023, "2023-y-siguientes"), (2026, "2023-y-siguientes")):
        selected = select_revision(modelo, filing_year=filing_year, period="AD-HOC", on=date(filing_year, 12, 31))
        assert selected.id == expected_revision


def test_modelo_309_historical_epochs_are_applicability_only_and_refuse_filing_snapshot() -> None:
    """Historical geometry is never silently promoted into a filing writer."""
    modelo, catalogues = _modelo_309()
    for revision_id in ("2004-2015", "2016-2017", "2018-2022"):
        assert modelo.revisions[revision_id].authority_grade is RegistryAuthorityGrade.APPLICABILITY

    with pytest.raises(RegistryValidationError, match="cannot satisfy the requested 'filing' snapshot authority"):
        build_snapshot(
            modelo,
            catalogues,
            source_root=bundled_path(),
            filing_year=2018,
            period="AD-HOC",
        )


def test_modelo_309_layouts_cover_every_proven_source_coordinate() -> None:
    """The generic source-layout gate sees no invented or missing byte range."""
    modelo, catalogues = _modelo_309()
    for revision_id, (source_ref, _bytes, _sha256) in _SOURCES.items():
        revision = modelo.revisions[revision_id]
        assert {ref for layout in revision.export_layouts for ref in layout.source_refs} == {source_ref}
        assert validate_export_layout_record_coverage(
            prefix=f"modelo 309 revision {revision_id}",
            revision=revision,
            source_refs=catalogues.sources,
        ) == []


def test_modelo_309_2004_single_record_does_not_reuse_the_modern_two_record_shape() -> None:
    """The early PDF has one exact 1,300-position record, not M30900/M30901."""
    modelo, _catalogues = _modelo_309()
    revision = modelo.revisions["2004-2015"]
    (layout,) = revision.export_layouts
    (record,) = layout.records

    assert layout.id == "modelo-309-fichero-2004-2015"
    assert len(layout.records) == 1
    assert record.record_type == "historical_fixed_width"
    assert record.fields[0].offset == 1
    assert record.fields[-1].offset + record.fields[-1].length - 1 == 1300


def test_modelo_309_selector_boundary_mutation_is_refused() -> None:
    """Moving the 2018 upper boundary into 2023 creates a detectable overlap."""
    modelo, _catalogues = _modelo_309()
    historical = modelo.revisions["2018-2022"]
    widened = historical.model_copy(update={"period_selector": historical.period_selector.model_copy(update={"year_to": 2023})})
    mutated = modelo.model_copy(update={"revisions": {**modelo.revisions, historical.id: widened}})

    with pytest.raises(AmbiguousRevisionSelectionError):
        select_revision(mutated, filing_year=2023, period="AD-HOC")


def test_modelo_309_2004_offset_mutation_reopens_the_official_source_slot() -> None:
    """A one-byte drift in the historical record is caught by generic coverage."""
    modelo, catalogues = _modelo_309()
    revision = modelo.revisions["2004-2015"]
    (layout,) = revision.export_layouts
    (record,) = layout.records
    index = next(index for index, field in enumerate(record.fields) if field.id.endswith("historical-periodo"))
    fields = list(record.fields)
    fields[index] = fields[index].model_copy(update={"offset": 24})
    wounded_record = record.model_copy(update={"fields": tuple(fields)})
    wounded_revision = revision.model_copy(update={"export_layouts": (layout.model_copy(update={"records": (wounded_record,)}),)})

    failures = validate_export_layout_record_coverage(
        prefix="modelo 309 revision 2004-2015",
        revision=wounded_revision,
        source_refs=catalogues.sources,
    )

    assert len(failures) == 1
    assert "@23+2" in failures[0]


def test_modelo_309_historical_epochs_have_labels_in_every_shipped_locale() -> None:
    """The revision split never leaves a historical casilla on a retired key."""
    modelo, _catalogues = _modelo_309()
    for revision_id in _SOURCES:
        revision = modelo.revisions[revision_id]
        assert revision.casillas
        for locale in ("es", "en", "ca", "hu"):
            assert all(casilla.get_label(locale).strip() for casilla in revision.casillas)
