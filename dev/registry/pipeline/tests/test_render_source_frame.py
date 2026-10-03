"""Render input selection respects historical source frames and stable IDs."""

from __future__ import annotations

from dataclasses import replace

import pytest

from cadrumo.core.resources.bundled_data import bundled_path

from ...compiler.loader import load_modelo_directory, load_shared_catalogues
from ..render_check import GeneratedExportBootstrapTransport, _render_transport, _select_record_design_source

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("modelo", ("126", "128"))
def test_historical_design_source_selection_requires_the_actual_year(modelo: str) -> None:
    catalogues = load_shared_catalogues(bundled_path("registry", "aeat"))
    definition = load_modelo_directory(bundled_path("registry", "aeat", "modelos", modelo))
    selected = definition.revisions["2019-y-siguientes"]
    old, _epoch = _select_record_design_source(
        selected,
        catalogues.sources,
        modelo=modelo,
        revision="2019-y-siguientes",
        source_ref=None,
        filing_year=2019,
        period="0A",
    )
    new, _epoch = _select_record_design_source(
        selected,
        catalogues.sources,
        modelo=modelo,
        revision="2019-y-siguientes",
        source_ref=None,
        filing_year=2020,
        period="0A",
    )
    assert old != new
    with pytest.raises(ValueError, match="exactly one record-design source"):
        _select_record_design_source(
            selected,
            catalogues.sources,
            modelo=modelo,
            revision="2019-y-siguientes",
            source_ref=str(old),
            filing_year=2020,
            period="0A",
        )


def test_late_m131_source_is_only_eligible_for_its_quarters() -> None:
    catalogues = load_shared_catalogues(bundled_path("registry", "aeat"))
    definition = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "131"))
    selected = definition.revisions["2026-late"]
    source, epoch = _select_record_design_source(
        selected,
        catalogues.sources,
        modelo="131",
        revision="2026-late",
        source_ref=None,
        filing_year=2026,
        period="3T",
    )
    assert (source, epoch) == ("aeat-dr-131-2026-late", "2026-late")
    for period in (None, "1T"):
        with pytest.raises(ValueError, match="exactly one record-design source"):
            _select_record_design_source(
                selected,
                catalogues.sources,
                modelo="131",
                revision="2026-late",
                source_ref=None,
                filing_year=2026,
                period=period,
            )


@pytest.mark.parametrize(
    ("filing_year", "period"), ((2012, "comunicacion"), (2022, "comunicacion"), (2022, "variacion"))
)
def test_m145_administrative_frame_selects_its_exact_source(filing_year: int, period: str) -> None:
    catalogues = load_shared_catalogues(bundled_path("registry", "aeat"))
    definition = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "145"))
    revision = "2012-01-31-y-siguientes"
    selected = definition.revisions[revision]
    source, epoch = _select_record_design_source(
        selected,
        catalogues.sources,
        modelo="145",
        revision=revision,
        source_ref="aeat-dr-145-v20",
        filing_year=filing_year,
        period=period,
    )
    assert (source, epoch) == ("aeat-dr-145-v20", "2012")
    assert catalogues.sources[source].sha256 == "fe29e8df4db859b41c66aaaf96c1bd27bc2af9063d98a61e62f21832c091765c"


def test_m145_administrative_source_refuses_wrong_period_year_and_pin() -> None:
    catalogues = load_shared_catalogues(bundled_path("registry", "aeat"))
    definition = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "145"))
    revision = "2012-01-31-y-siguientes"
    selected = definition.revisions[revision]
    source_ref = "aeat-dr-145-v20"
    for filing_year, period, expected in (
        (2022, "alta", "administrative period"),
        (2011, "comunicacion", "administrative period"),
    ):
        with pytest.raises(ValueError, match=expected):
            _select_record_design_source(
                selected,
                catalogues.sources,
                modelo="145",
                revision=revision,
                source_ref=source_ref,
                filing_year=filing_year,
                period=period,
            )
    with pytest.raises(ValueError, match="does not declare record-design source"):
        _select_record_design_source(
            selected,
            catalogues.sources,
            modelo="145",
            revision=revision,
            source_ref="aeat-dr-126-2020",
            filing_year=2022,
            period="comunicacion",
        )

    bootstrap = GeneratedExportBootstrapTransport(
        layout_id="modelo-145-dr-v20-fixed-width",
        line_ending="none",
        source_ref=source_ref,
        source_sha256="fe29e8df4db859b41c66aaaf96c1bd27bc2af9063d98a61e62f21832c091765c",
        supersedes_layout_id="modelo-145-dr-v20-fixed-width",
    )
    assert (
        _render_transport(
            selected,
            catalogues.sources,
            modelo="145",
            revision=revision,
            selected_source_ref=source_ref,
            bootstrap_transport=bootstrap,
        )[0]
        == bootstrap.layout_id
    )
    with pytest.raises(ValueError, match="bootstrap source digest"):
        _render_transport(
            selected,
            catalogues.sources,
            modelo="145",
            revision=revision,
            selected_source_ref=source_ref,
            bootstrap_transport=replace(bootstrap, source_sha256="0" * 64),
        )


def test_stable_layout_bootstrap_requires_exact_declared_supersession_and_source() -> None:
    catalogues = load_shared_catalogues(bundled_path("registry", "aeat"))
    definition = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "123"))
    revision = "2024-y-siguientes"
    selected = definition.revisions[revision]
    source, _epoch = _select_record_design_source(
        selected,
        catalogues.sources,
        modelo="123",
        revision=revision,
        source_ref=None,
        filing_year=2024,
        period="0A",
    )
    stable = "modelo-123-fichero-boe"
    bootstrap = GeneratedExportBootstrapTransport(
        layout_id=stable,
        line_ending="crlf",
        source_ref=str(source),
        source_sha256=catalogues.sources[source].sha256,
        supersedes_layout_id=stable,
    )
    assert (
        _render_transport(
            selected,
            catalogues.sources,
            modelo="123",
            revision=revision,
            selected_source_ref=source,
            bootstrap_transport=bootstrap,
        )[0]
        == stable
    )
    for bad in (
        replace(bootstrap, layout_id="arbitrary-stable-name"),
        replace(bootstrap, supersedes_layout_id="arbitrary-stable-name"),
        replace(bootstrap, source_ref="aeat-dr-123-2019-2023-v13"),
        replace(bootstrap, source_sha256="0" * 64),
    ):
        with pytest.raises(ValueError, match="bootstrap"):
            _render_transport(
                selected,
                catalogues.sources,
                modelo="123",
                revision=revision,
                selected_source_ref=source,
                bootstrap_transport=bad,
            )
