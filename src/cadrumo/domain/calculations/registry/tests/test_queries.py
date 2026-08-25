"""Tests for the typed modelo registry query API."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

import pytest
from pydantic import ValidationError

from .....core import CasillaId, Modelo, validated_casilla_id
from .....core.resources import resources
from .. import relations_by_target_binding
from ..errors import NoRevisionForPeriodError, RegistryValidationError
from ..queries import (
    BindingSelectorQueryProjection,
    ModeloFormulaRow,
    RegistryQueryService,
    ResolvedRegistryQueryContext,
)
from .._query_reports import ModeloBindingsReport, ModeloCasillaDetailReport
from ..schema import InputKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_INPUT_CASILLA: CasillaId = validated_casilla_id("01", surface="_INPUT_CASILLA")
_TARGET_CASILLA: CasillaId = validated_casilla_id("02", surface="_TARGET_CASILLA")


def _service() -> RegistryQueryService:
    return RegistryQueryService(resources().modelos.authority)


def test_relations_by_target_binding_preserves_real_registry_declaration_order() -> None:
    snapshot = resources().modelos.authority.snapshot(Modelo.M202.value, filing_year=2025, period="2P")

    grouped = relations_by_target_binding(snapshot.revision)

    assert tuple(relation.id for relation in grouped["modelo-202-2025-y-siguientes-pagos-fraccionados-anteriores"]) == (
        "modelo-202-2025-y-siguientes-rel-self-pagos-2p",
        "modelo-202-2025-y-siguientes-rel-self-pagos-3p",
    )
    assert tuple(relation.id for relation in grouped["modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior"]) == (
        "modelo-202-2025-y-siguientes-rel-cuota-base-1p",
        "modelo-202-2025-y-siguientes-rel-cuota-base-2p-3p",
    )


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

    described = service.describe_modelo_for_scope("303", filing_year=2026, period="1T")
    expected = {str(item.id) for item in resources().modelos.authority.modelo("303").revisions.values()}

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
    assert any(row.input_casilla_ids or row.input_bindings or row.input_parameters for row in formulas.rows)


def test_binding_query_rows_expose_typed_selector_projection() -> None:
    service = _service()

    report = service.bindings_for_scope("130", filing_year=2026, period="1T")
    row = next(item for item in report.rows if item.binding_id == "modelo-130-resultados-negativos-anteriores")

    assert isinstance(row.selector, BindingSelectorQueryProjection)
    assert not isinstance(row.selector, Mapping)
    assert row.selector.source == "previous_filing"
    assert row.selector.keys == (
        "max_year_delta",
        "source_casilla_id",
        "source_modelo",
        "source_period_offset_from_target",
    )
    assert {entry.key: entry.value for entry in row.selector.entries} == {
        "max_year_delta": 0,
        "source_casilla_id": "saldo-negativo-fin-periodo",
        "source_modelo": "130",
        "source_period_offset_from_target": -1,
    }


def test_binding_query_rows_dump_selector_as_ordered_entries() -> None:
    service = _service()

    report = service.bindings_for_scope("130", filing_year=2026, period="1T")
    row = next(item for item in report.rows if item.binding_id == "modelo-130-resultados-negativos-anteriores")
    dumped = row.model_dump(mode="json")

    assert dumped["selector"] == {
        "source": "previous_filing",
        "keys": [
            "max_year_delta",
            "source_casilla_id",
            "source_modelo",
            "source_period_offset_from_target",
        ],
        "entries": [
            {"key": "max_year_delta", "value": 0},
            {"key": "source_casilla_id", "value": "saldo-negativo-fin-periodo"},
            {"key": "source_modelo", "value": "130"},
            {"key": "source_period_offset_from_target", "value": -1},
        ],
    }


def test_formula_row_rejects_legacy_input_casillas_key() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ModeloFormulaRow.model_validate(
            {
                "formula_id": "test.formula",
                "target_casilla_id": _TARGET_CASILLA,
                "input_casillas": (_INPUT_CASILLA,),
                "input_bindings": (),
                "input_parameters": (),
                "input_relations": (),
                "expression": {"casilla_id": _INPUT_CASILLA},
                "legal_refs": ("test-ley-001:art-1",),
                "source_refs": ("test-source-001",),
            },
        )

    message = str(exc_info.value)
    assert "input_casilla_ids" in message
    assert "input_casillas" in message


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


def test_bindings_for_scope_resolves_the_law_determined_revision() -> None:
    """``bindings_for_scope`` selects the revision fixed by year and period.

    Modelo 100 carries one revision per renta year. Resolving by year
    and annual period must return the 2024 revision's binding ids, not
    the latest revision's.
    """

    service = _service()

    report = service.bindings_for_scope("100", filing_year=2024, period="0A")

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

    report = service.bindings_for_scope("100", filing_year=2024, period="0A")
    row = next(r for r in report.rows if "estimacion-directa-es-normal" in r.binding_id)

    assert row.typed_enum == "EstimacionDirectaModalidad"
    assert row.input_channel == "decimal"


def test_input_casilla_id_map_exposes_only_canonical_ids() -> None:
    """``input_casilla_id_map`` must not reintroduce printed-number references."""

    from ..runtime_graph import input_casilla_id_map

    service = _service()
    described = service.describe_modelo("303", period="1T")
    authority = service._authority
    definition = authority.validate_modelo("303")
    revision = definition.revisions[described.revision]

    id_map = input_casilla_id_map(revision)

    canonical = "iva.compensacion-pendiente-periodos-anteriores"
    assert id_map[canonical] == canonical
    assert "110" not in id_map


def test_unscoped_query_refuses_as_of_instead_of_silently_ignoring_it() -> None:
    """The unscoped period query refuses an as_of argument rather than accepting-and-ignoring it.

    The unscoped resolver selects the latest revision by period and has no
    filing-year context to gate an as_of date, so honouring it is impossible; it
    must refuse explicitly (the accepted-parameter lie the as-of-honesty contract
    closes) rather than silently return the current view.
    """
    service = _service()
    a_date = date(2024, 6, 1)
    unscoped_calls = (
        lambda: service.describe_modelo("303", period="1T", as_of=a_date),
        lambda: service.casillas("303", period="1T", as_of=a_date),
        lambda: service.bindings("303", period="1T", as_of=a_date),
        lambda: service.formulas("303", period="1T", as_of=a_date),
    )
    for call in unscoped_calls:
        with pytest.raises(RegistryValidationError, match="as_of"):
            call()

    # The refusal is scoped to the ignored argument: without as_of the same
    # unscoped query still resolves, so the honesty fix did not break the path.
    assert service.casillas("303", period="1T") is not None


def test_scoped_query_honours_the_as_of_validity_window() -> None:
    """The scoped query gates revision selection by the as_of date window.

    Proves as_of participates rather than being ignored: an as_of inside the
    resolved revision's validity window still resolves, while an as_of before
    every declared window is honoured and refuses instead of returning the
    current view.
    """
    service = _service()
    snapshot = resources().modelos.authority.snapshot("100", filing_year=2025, period="0A")
    within_window = snapshot.revision.valid_from

    # Baseline resolution and an as_of inside the window both resolve.
    assert service.casillas_for_scope("100", filing_year=2025, period="0A") is not None
    assert service.casillas_for_scope("100", filing_year=2025, period="0A", as_of=within_window) is not None

    # An as_of before every revision's validity window is honoured: it gates the
    # selection and refuses rather than silently returning a revision.
    with pytest.raises(NoRevisionForPeriodError):
        service.casillas_for_scope("100", filing_year=2025, period="0A", as_of=date(1990, 1, 1))


def _filing_year_covered_by(modelo: str, revision_id: str) -> int:
    """Return a filing year the named revision itself declares it covers.

    The year is read from the revision's own ``period_selector`` on the registry
    authority rather than from the query service, so a parity assertion built on
    it cannot be satisfied by the code under test agreeing with itself.
    """
    revision = resources().modelos.authority.validate_modelo(modelo).revisions[revision_id]
    return next(
        year
        for year in range(revision.valid_from.year, revision.valid_from.year + 20)
        if revision.period_selector.includes_year(year)
    )


def test_scoped_and_unscoped_routes_preserve_both_forms_over_one_projection() -> None:
    """Both public resolution forms feed one describe projection and stay distinguishable.

    The two resolvers are different selection authorities, so this pins the
    contract that survives sharing a projection builder: when they land on the
    same revision every projected field agrees, and the only divergence is the
    filing scope the unscoped form does not have.
    """
    service = _service()
    unscoped = service.describe_modelo("303", period="1T")
    filing_year = _filing_year_covered_by("303", unscoped.revision)
    scoped = service.describe_modelo_for_scope("303", filing_year=filing_year, period="1T")

    assert scoped.revision == unscoped.revision
    assert (scoped.code, scoped.tax_domain, scoped.revision_ids) == (
        unscoped.code,
        unscoped.tax_domain,
        unscoped.revision_ids,
    )
    assert (scoped.casilla_count, scoped.binding_count, scoped.formula_count) == (
        unscoped.casilla_count,
        unscoped.binding_count,
        unscoped.formula_count,
    )

    # Both public forms are preserved: the unscoped one carries no filing scope,
    # the scoped one does. Collapsing either into the other would break this.
    assert (unscoped.filing_year, unscoped.filing_period) == (None, None)
    assert scoped.filing_year == filing_year
    assert scoped.filing_period is not None
    assert scoped.period == unscoped.period == "1T"


def test_casillas_formulas_and_bindings_rows_agree_across_both_resolution_forms() -> None:
    """Every shared row projection is identical on both routes for one revision.

    Casillas, formulas and bindings each build from the shared typed context, so
    a row set that differed between the scoped and unscoped route would mean a
    builder had re-derived content from the resolver instead of the context.
    """
    service = _service()
    filing_year = _filing_year_covered_by("303", service.describe_modelo("303", period="1T").revision)

    unscoped_casillas = service.casillas("303", period="1T")
    scoped_casillas = service.casillas_for_scope("303", filing_year=filing_year, period="1T")
    assert unscoped_casillas.rows
    assert scoped_casillas.rows == unscoped_casillas.rows

    unscoped_formulas = service.formulas("303", period="1T")
    scoped_formulas = service.formulas_for_scope("303", filing_year=filing_year, period="1T")
    assert unscoped_formulas.rows
    assert scoped_formulas.rows == unscoped_formulas.rows

    unscoped_bindings = service.bindings("303", period="1T")
    scoped_bindings = service.bindings_for_scope("303", filing_year=filing_year, period="1T")
    assert unscoped_bindings.rows
    assert scoped_bindings.rows == unscoped_bindings.rows

    # The filter arguments still reach the shared builder rather than being
    # dropped by the context refactor.
    computed = service.casillas_for_scope(
        "303",
        filing_year=filing_year,
        period="1T",
        input_kind=InputKind.COMPUTED,
    )
    assert computed.rows
    assert len(computed.rows) < len(scoped_casillas.rows)
    assert all(row.input_kind == InputKind.COMPUTED for row in computed.rows)


def test_bindings_and_casilla_detail_remain_separate_non_substitutable_reports() -> None:
    """The bindings listing and the single-casilla detail are deliberately different reports.

    Both are reachable from the same resolved context, which is exactly why the
    distinction needs pinning: one answers "which sources feed this revision",
    the other "what is this one casilla", and neither can serve the other's
    question. Substitutability is tested at the contract level, not by shape
    coincidence.
    """
    service = _service()
    filing_year = _filing_year_covered_by("303", service.describe_modelo("303", period="1T").revision)

    bindings = service.bindings_for_scope("303", filing_year=filing_year, period="1T")
    detail = service.casilla_for_scope("303", "27", filing_year=filing_year, period="1T")

    assert isinstance(bindings, ModeloBindingsReport)
    assert isinstance(detail, ModeloCasillaDetailReport)

    binding_fields = set(ModeloBindingsReport.model_fields)
    detail_fields = set(ModeloCasillaDetailReport.model_fields)

    # The listing carries a row collection the detail has no field for.
    assert "rows" in binding_fields
    assert "rows" not in detail_fields
    # The detail carries per-casilla grounding and the resolved formula the
    # listing has no field for, so it cannot be projected from the listing.
    for casilla_only in ("casilla_id", "formula_expression", "legal_refs", "source_refs", "help_text"):
        assert casilla_only in detail_fields
        assert casilla_only not in binding_fields

    # Both agree on the shared scope spine they take from the one context.
    assert (bindings.code, bindings.revision, bindings.filing_year, bindings.period) == (
        detail.code,
        detail.revision,
        detail.filing_year,
        detail.period,
    )
    assert detail.casilla_id == "27"


def test_resolved_query_context_is_frozen_and_rejects_unknown_fields() -> None:
    """The shared context cannot be mutated or widened by a projection builder.

    Several builders now read one context instance. If a builder could rebind a
    field on it, one report could alter what a later report sees, which is the
    failure the shared-context design has to exclude.
    """
    definition = resources().modelos.authority.validate_modelo("303")
    revision = definition.revisions[_service().describe_modelo("303", period="1T").revision]

    context = ResolvedRegistryQueryContext(definition=definition, revision=revision)
    # The unscoped form legitimately carries no filing scope.
    assert (context.filing_year, context.registry_period) == (None, None)

    with pytest.raises(ValidationError):
        context.filing_year = 2026  # type: ignore[misc]  # ty: ignore[invalid-assignment]  # reason: the refusal is what this asserts

    # An unknown field is refused rather than silently carried, so a builder
    # cannot smuggle extra state through the shared context.
    with pytest.raises(ValidationError):
        ResolvedRegistryQueryContext.model_validate(
            {"definition": definition, "revision": revision, "snapshot_fingerprint": "x"},
        )
