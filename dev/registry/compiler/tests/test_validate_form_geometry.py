"""Authored shapes that differ from the declared form geometry stop publication."""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace
from typing import Any

import pytest

from cadrumo.domain.calculations.registry.form_codes import resolve_form_codes
from cadrumo.domain.calculations.registry.prorrata_register_catalogue import resolve_prorrata_register_catalogue

from ...compiler.validate_form_geometry import (
    modelo_geometry_failures,
    prorrata_catalogue_failures,
    validate_form_geometry,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]


def _codes() -> Any:
    return resolve_form_codes("form-row-codes")


def _modelo(*, prefix_fields: int, tipo_renta: tuple[str, ...] | None) -> Any:
    header = SimpleNamespace(prefix_fields=(None,) * prefix_fields)
    layout = SimpleNamespace(auxiliary_envelope_header=header)
    window = SimpleNamespace(tipo_renta_scope=tipo_renta)
    revision = SimpleNamespace(export_layouts=(layout,), deadline_windows=(window,))
    return SimpleNamespace(id="000", revisions={"rev": revision})


def test_the_bundled_catalogues_have_the_declared_shape() -> None:
    assert validate_form_geometry(()) == ()


def test_a_prorrata_catalogue_of_another_size_is_refused() -> None:
    catalogue = resolve_prorrata_register_catalogue()
    assert prorrata_catalogue_failures(catalogue, _codes()) == []
    short = dataclasses.replace(catalogue, sector_letters=catalogue.sector_letters[:-1])
    assert any("sector_letters" in failure for failure in prorrata_catalogue_failures(short, _codes()))


def test_an_auxiliary_header_of_another_size_is_refused() -> None:
    declared = int(_codes().code("aeat.aux.prefix_fields"))
    assert modelo_geometry_failures((_modelo(prefix_fields=declared, tipo_renta=None),), _codes()) == []
    failures = modelo_geometry_failures((_modelo(prefix_fields=declared - 1, tipo_renta=None),), _codes())
    assert any("auxiliary header" in failure for failure in failures)


def test_a_deadline_code_of_another_width_is_refused() -> None:
    declared = int(_codes().code("aeat.aux.prefix_fields"))
    width = next(iter(_codes().codes("m210.tipo_renta_digits")))
    wrong = "1" * (int(width) + 1)
    failures = modelo_geometry_failures((_modelo(prefix_fields=declared, tipo_renta=(wrong,)),), _codes())
    assert any("deadline code" in failure for failure in failures)
