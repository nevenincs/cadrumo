"""Tests for the typed modelo registry query API."""

from __future__ import annotations

import pytest

from aeat.core.resources import bundled_path

from ._authority import ValidatedRegistryAuthority
from ._errors import RegistryValidationError
from ._queries import RegistryQueryService, parse_modelo_period

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_REGISTRY_ROOT = bundled_path("registry", "aeat")


def _service() -> RegistryQueryService:
    authority = ValidatedRegistryAuthority.load(_REGISTRY_ROOT, source_root=bundled_path())
    return RegistryQueryService(authority)


def test_parse_modelo_period_accepts_user_period_shapes() -> None:
    assert parse_modelo_period("2026Q1") == (2026, "1T")
    assert parse_modelo_period("2026-Q4") == (2026, "4T")
    assert parse_modelo_period("2026-03") == (2026, "03")
    assert parse_modelo_period("2026") == (2026, "0A")


def test_query_service_lists_and_describes_committed_modelo() -> None:
    service = _service()

    listed = service.list_modelos(year=2026)
    described = service.describe_modelo("303", period="2026Q1")

    assert "303" in {row.code for row in listed.modelos}
    assert described.code == "303"
    assert described.filing_year == 2026
    assert described.period == "1T"
    assert described.tax_domain == "iva"
    assert described.casilla_count > 0
    assert described.binding_count > 0
    assert described.formula_count > 0


def test_query_service_exposes_casillas_bindings_and_formulas_from_same_revision() -> None:
    service = _service()

    casillas = service.casillas("303", period="2026Q1", input_kind="computed")
    bindings = service.bindings("130", period="2026Q1")
    formulas = service.formulas("303", period="2026Q1")

    assert casillas.code == "303"
    assert casillas.rows
    assert all(row.input_kind == "computed" for row in casillas.rows)
    assert all(row.formula for row in casillas.rows)
    assert bindings.code == "130"
    assert any(row.binding_id == "irpf.previous_year_economic_activity_net_income" for row in bindings.rows)
    assert {row.source for row in bindings.rows} == {"previous_filing"}
    assert formulas.code == "303"
    assert formulas.rows
    assert any(row.input_casillas or row.input_bindings or row.input_parameters for row in formulas.rows)


def test_describe_accepts_bare_registry_period_token() -> None:
    """``describe`` resolves a bare registry period token to a declaring revision.

    Modelo 100 declares ``0A`` (annual) as its only period. The
    operator passing ``--period 0A`` must select a 100 revision rather
    than be rejected because the token carries no filing year.
    """

    service = _service()

    described = service.describe_modelo("100", period="0A")

    assert described.code == "100"
    assert described.period == "0A"
    assert "0A" in described.periods
    assert described.filing_year is None


def test_describe_rejects_bare_period_not_declared_by_modelo() -> None:
    """A bare token no revision declares is refused naming the declared set."""

    service = _service()

    with pytest.raises(RegistryValidationError, match="not declared by any revision"):
        service.describe_modelo("303", period="0A")
