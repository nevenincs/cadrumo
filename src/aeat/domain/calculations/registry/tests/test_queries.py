"""Tests for the typed modelo registry query API."""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .._authority import ValidatedRegistryAuthority
from .._errors import RegistryValidationError
from .._queries import RegistryQueryService
from .._schema import InputKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")


def _service() -> RegistryQueryService:
    authority = ValidatedRegistryAuthority.load(_REGISTRY_ROOT, source_root=bundled_path())
    return RegistryQueryService(authority)


@pytest.mark.parametrize("period", ("2026Q1", "2026-Q4", "2026-03", "2026"))
def test_query_service_rejects_combined_period_shapes(period: str) -> None:
    service = _service()

    with pytest.raises(RegistryValidationError, match="bare registry token"):
        service.describe_modelo("303", period=period)


def test_query_service_lists_and_describes_committed_modelo() -> None:
    service = _service()

    listed = service.list_modelos(year=2026)
    described = service.describe_modelo_for_scope("303", filing_year=2026, period="1T")

    assert "303" in {row.code for row in listed.modelos}
    assert described.code == "303"
    assert described.filing_year == 2026
    assert described.period == "1T"
    assert described.tax_domain == "iva"
    assert described.casilla_count > 0
    assert described.binding_count > 0
    assert described.formula_count > 0


def test_describe_lists_every_declared_revision_id() -> None:
    """``describe_modelo`` surfaces all declared revision ids so an
    operator can discover the valid ``--revision`` value for
    ``modelo work create`` without first guessing wrong."""

    service = _service()
    authority = ValidatedRegistryAuthority.load(_REGISTRY_ROOT, source_root=bundled_path())

    described = service.describe_modelo_for_scope("303", filing_year=2026, period="1T")
    expected = {str(item.id) for item in authority.modelo("303").revisions.values()}

    assert set(described.revision_ids) == expected
    # The resolved revision is always one of the listed ids.
    assert described.revision in described.revision_ids
    # The list is non-empty and oldest valid_from first (deterministic).
    assert len(described.revision_ids) == len(expected)


def test_query_service_exposes_casillas_bindings_and_formulas_from_same_revision() -> None:
    service = _service()

    casillas = service.casillas_for_scope("303", filing_year=2026, period="1T", input_kind=InputKind.COMPUTED)
    bindings = service.bindings_for_scope("130", filing_year=2026, period="1T")
    formulas = service.formulas_for_scope("303", filing_year=2026, period="1T")

    assert casillas.code == "303"
    assert casillas.rows
    assert all(row.input_kind == InputKind.COMPUTED for row in casillas.rows)
    assert all(row.formula for row in casillas.rows)
    assert bindings.code == "130"
    assert any(row.binding_id == "irpf.previous_year_economic_activity_net_income" for row in bindings.rows)
    assert "previous_filing" in {row.source for row in bindings.rows}
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


def test_describe_accepts_censo_event_period_token() -> None:
    """``describe`` resolves a non-date censo period token to a revision.

    Modelo 036 declares ``alta`` / ``modificacion`` / ``baja`` as its
    period tokens. None match the registry time-code pattern, so the
    query must match them verbatim against the revision's declared
    periods rather than refuse them.
    """

    service = _service()

    described = service.describe_modelo("036", period="alta")

    assert described.code == "036"
    assert described.period == "alta"
    assert "alta" in described.periods


def test_describe_for_scope_preserves_declared_censo_period_casing() -> None:
    """Exact scope resolution returns the registry-declared non-date token."""

    service = _service()

    described = service.describe_modelo_for_scope("036", filing_year=2026, period="ALTA")

    assert described.code == "036"
    assert described.period == "alta"
    assert "alta" in described.periods


def test_casillas_accepts_censo_event_period_token() -> None:
    """``casillas`` resolves the same censo period tokens as ``describe``."""

    service = _service()

    report = service.casillas("036", period="modificacion")

    assert report.code == "036"
    assert report.period == "modificacion"
    assert report.rows


def test_bindings_for_year_resolves_the_year_covering_revision() -> None:
    """``bindings_for_year`` selects the revision covering the filing year.

    Modelo 100 carries one revision per renta year. Resolving by year
    must return the 2024 revision's binding ids, not the latest
    revision's.
    """

    service = _service()

    report = service.bindings_for_year("100", filing_year=2024)

    assert report.code == "100"
    assert report.filing_year == 2024
    assert report.rows
    assert all(row.binding_id.startswith("renta-2024-") for row in report.rows)


def test_binding_rows_report_decimal_input_channel_for_typed_enum_binding() -> None:
    """A ``typed_enum`` binding consumed as a Decimal operand reports
    ``input_channel = "decimal"``.

    The Modelo 100 estimación-directa modality binding carries a
    ``typed_enum`` annotation yet its formulas compare it against a
    numeric literal, so the operator-facing input channel is decimal.
    """

    service = _service()

    report = service.bindings_for_year("100", filing_year=2024)
    row = next(r for r in report.rows if "estimacion-directa-es-normal" in r.binding_id)

    assert row.typed_enum == "EstimacionDirectaModalidad"
    assert row.input_channel == "decimal"


def test_input_casilla_alias_map_resolves_registry_number_to_canonical_id() -> None:
    """``input_casilla_alias_map`` maps an unambiguous registry number
    and BOE form number to the canonical casilla id.

    Modelo 303 casilla ``iva.compensacion-pendiente-periodos-anteriores``
    carries the registry number ``110``. The alias map must resolve
    ``110`` to the canonical id while leaving the id mapped to itself.
    """

    from .._runtime_graph import input_casilla_alias_map

    service = _service()
    described = service.describe_modelo("303", period="1T")
    authority = service._authority
    definition = authority.validate_modelo("303")
    revision = definition.revisions[described.revision]

    alias_map = input_casilla_alias_map(revision)

    canonical = "iva.compensacion-pendiente-periodos-anteriores"
    assert alias_map[canonical] == canonical
    assert alias_map["110"] == canonical
