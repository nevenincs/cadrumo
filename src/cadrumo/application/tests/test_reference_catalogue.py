"""The reference-catalogue service answers from the published authority and bundled data alone.

Every query runs against the real published authority generation, with no
profile and no session, and the answers are checked against the registry
reports they project and against independent properties of the data.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date

import pytest
from pydantic import BaseModel

from ...core.modelo import Modelo
from ...core.tax_domain import TaxDomain
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.portals.categories import PortalCategory
from ...domain.portals.errors import PortalRegistryError
from ...domain.portals.registry import PORTAL_REGISTRY
from .. import reference_catalogue as catalogue
from ..modelo.registry_discovery import (
    registry_casilla,
    registry_casilla_for_registry_scope,
    registry_casillas,
    registry_casillas_for_registry_scope,
    registry_describe_modelo,
    registry_describe_modelo_for_registry_scope,
    registry_formulas,
    registry_formulas_for_registry_scope,
    registry_list_modelos,
    registry_support_matrix,
)
from ..reference_catalogue_contracts import ModeloSupportMatrixResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CEDED = ("600", "620", "650", "660")


@pytest.fixture(scope="module")
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


def test_modelo_listing_is_the_registry_listing_with_local_work_posture(operation: PinnedAuthorityOperation) -> None:
    result = catalogue.list_modelos(operation=operation)
    registry = registry_list_modelos(operation=operation)

    assert [row.code for row in result.modelos] == [row.code for row in registry.modelos]
    assert result.modelo_count == len(registry.modelos)
    assert result.year_filter is None and result.domain_filter is None
    assert all(row.local_work_supported == (row.local_work_guidance is None) for row in result.modelos)


def test_modelo_listing_narrows_by_tax_domain_and_by_year(operation: PinnedAuthorityOperation) -> None:
    everything = catalogue.list_modelos(operation=operation)
    vat = catalogue.list_modelos(domain=TaxDomain("iva"), operation=operation)
    in_year = catalogue.list_modelos(year=2025, domain=TaxDomain("irpf"), operation=operation)

    assert vat.domain_filter == "iva"
    assert {row.tax_domain for row in vat.modelos} == {"iva"}
    assert "303" in {row.code for row in vat.modelos}
    assert {row.code for row in vat.modelos} < {row.code for row in everything.modelos}
    assert in_year.year_filter == 2025 and in_year.domain_filter == "irpf"
    assert {row.tax_domain for row in in_year.modelos} == {"irpf"}


def test_describe_composes_a_filing_year_and_period_into_one_revision(operation: PinnedAuthorityOperation) -> None:
    exact = catalogue.describe_modelo("130", year=2025, period=" 1T ", operation=operation)
    latest = catalogue.describe_modelo("130", period="1T", operation=operation)

    assert exact.code == "130"
    assert exact.filing_year == 2025 and exact.period == "1T"
    assert latest.filing_year is None and latest.period == "1T"
    assert exact.revision == latest.revision


@pytest.mark.parametrize("period", [None, "", "   "])
def test_a_filing_year_without_a_period_is_incomplete(operation: PinnedAuthorityOperation, period: str | None) -> None:
    with pytest.raises(catalogue.DiscoveryScopeIncompleteError):
        catalogue.describe_modelo("130", year=2025, period=period, operation=operation)


def test_an_invalid_period_token_names_the_tokens_the_modelo_declares(operation: PinnedAuthorityOperation) -> None:
    with pytest.raises(catalogue.DiscoveryPeriodTokenError) as refused:
        catalogue.list_casillas("130", year=2025, period="ZZ", operation=operation)

    assert refused.value.declared_tokens == ("1T", "2T", "3T", "4T")
    assert (refused.value.period_code, refused.value.filing_year) == ("ZZ", 2025)
    assert all(token in str(refused.value) for token in refused.value.declared_tokens)


def test_an_invalid_period_token_for_an_unknown_modelo_carries_the_period_refusal(
    operation: PinnedAuthorityOperation,
) -> None:
    with pytest.raises(catalogue.DiscoveryPeriodTokenError) as refused:
        catalogue.list_formulas("999", year=2025, period="ZZ", operation=operation)

    assert refused.value.declared_tokens == ()
    assert str(refused.value) == refused.value.detail


def test_a_year_that_is_a_period_token_is_not_a_period(operation: PinnedAuthorityOperation) -> None:
    with pytest.raises(catalogue.DiscoveryPeriodTokenError):
        catalogue.describe_casilla("130", "03", year=2025, period="2025", operation=operation)


@pytest.mark.parametrize("token", ["alta", "modificacion", "baja"])
def test_a_census_event_the_modelo_declares_scopes_a_read_together_with_its_filing_year(
    operation: PinnedAuthorityOperation, token: str
) -> None:
    as_of = date(2024, 12, 31)
    scoped = catalogue.describe_modelo("036", year=2024, period=token, as_of=as_of, operation=operation)
    registry = registry_describe_modelo_for_registry_scope(
        "036", filing_year=2024, period=token, as_of=as_of, operation=operation
    )

    assert (scoped.filing_year, scoped.period) == (2024, token)
    assert (scoped.revision, scoped.authority_grade) == (registry.revision, registry.authority_grade)


def test_a_census_event_is_refused_for_a_modelo_that_does_not_declare_it(operation: PinnedAuthorityOperation) -> None:
    with pytest.raises(catalogue.DiscoveryPeriodTokenError) as refused:
        catalogue.describe_modelo("130", year=2025, period="alta", operation=operation)

    assert "alta" not in refused.value.declared_tokens


def test_a_filing_period_the_modelo_declares_is_still_refused_with_an_unsupported_year(
    operation: PinnedAuthorityOperation,
) -> None:
    with pytest.raises(catalogue.DiscoveryPeriodTokenError):
        catalogue.describe_modelo("130", year=1, period="1T", operation=operation)


@pytest.mark.parametrize("modelo", _CEDED)
def test_a_ceded_autonomic_tax_is_redirected_before_any_registry_lookup(
    operation: PinnedAuthorityOperation, modelo: str
) -> None:
    for call in (
        lambda: catalogue.describe_modelo(modelo, operation=operation),
        lambda: catalogue.list_casillas(modelo, operation=operation),
        lambda: catalogue.describe_casilla(modelo, "01", operation=operation),
        lambda: catalogue.list_formulas(modelo, operation=operation),
    ):
        with pytest.raises(catalogue.CededAutonomicModeloError) as refused:
            call()
        assert refused.value.modelo == modelo
        assert refused.value.locale_key


def test_the_redirect_ignores_surrounding_whitespace_and_leaves_other_codes_alone() -> None:
    with pytest.raises(catalogue.CededAutonomicModeloError) as refused:
        catalogue.refuse_ceded_autonomic_modelo(" 650 ")
    assert refused.value.modelo == "650"
    catalogue.refuse_ceded_autonomic_modelo("303")
    catalogue.refuse_ceded_autonomic_modelo("999")


def test_casillas_narrow_by_kind_requiredness_form_box_and_number(operation: PinnedAuthorityOperation) -> None:
    everything = catalogue.list_casillas("130", year=2025, period="1T", operation=operation)
    computed = catalogue.list_casillas(
        "130", year=2025, period="1T", input_kind=InputKind.COMPUTED, operation=operation
    )
    required = catalogue.list_casillas("130", year=2025, period="1T", required=True, operation=operation)
    by_number = catalogue.list_casillas("130", year=2025, period="1T", casilla_number="03", operation=operation)
    blank_number = catalogue.list_casillas("130", year=2025, period="1T", casilla_number="  ", operation=operation)
    boxed = catalogue.list_casillas("303", year=2025, period="1T", form_number="46", operation=operation)

    assert everything.casilla_count == len(everything.rows) > len(computed.rows) > 0
    assert {row.input_kind for row in computed.rows} == {"computed"}
    assert required.rows and all(row.required for row in required.rows)
    assert [row.number for row in by_number.rows] == ["03"]
    assert blank_number.rows == everything.rows
    registry_boxed = registry_casillas_for_registry_scope(
        "303", filing_year=2025, period="1T", form_number="46", operation=operation
    )
    assert [row.casilla_id for row in boxed.rows] == [row.casilla_id for row in registry_boxed.rows]
    unboxed = catalogue.list_casillas("303", year=2025, period="1T", operation=operation)
    assert 0 < boxed.casilla_count < unboxed.casilla_count


def test_a_single_casilla_carries_its_formula_only_when_it_is_computed(operation: PinnedAuthorityOperation) -> None:
    computed = catalogue.describe_casilla("130", "03", year=2025, period="1T", operation=operation)
    bound = catalogue.describe_casilla("130", "01", year=2025, period="1T", operation=operation)
    unscoped = catalogue.describe_casilla("130", "03", operation=operation)

    assert computed.input_kind == "computed" and computed.formula_id and "op" in (computed.formula_expression or {})
    assert bound.input_kind == "bound" and bound.formula_id is None and bound.formula_expression is None
    assert (computed.filing_year, unscoped.filing_year) == (2025, None)
    assert unscoped.formula_id == computed.formula_id


def test_formulas_count_their_rows_and_ground_every_one(operation: PinnedAuthorityOperation) -> None:
    result = catalogue.list_formulas("130", period="1T", operation=operation)

    assert result.formula_count == len(result.rows) > 0
    assert all(row.legal_refs and row.source_refs and row.expression for row in result.rows)


def test_the_support_matrix_has_one_entry_per_modelo(operation: PinnedAuthorityOperation) -> None:
    result = catalogue.read_support_matrix(operation=operation)

    assert result.modelo_count == len(result.entries) > 0
    assert len({entry.modelo_id for entry in result.entries}) == len(result.entries)
    assert all(entry.supported_revision_ids for entry in result.entries)


def test_the_ledger_categories_are_the_catalogued_vocabularies() -> None:
    result = catalogue.read_ledger_categories()

    assert result.income_requires_category is False
    assert result.families and all(family.category_ids for family in result.families)
    assert set().union(*(family.category_ids for family in result.families)) <= set(result.category_ids)
    assert result.irpf_category_ids == [category.id for category in result.irpf_categories]
    assert set(result.net_paid_withholding_irpf_category_ids) == {
        category.id for category in result.irpf_categories if category.net_paid_invoice
    }


def test_the_portal_catalogue_lists_filters_and_views() -> None:
    everything = catalogue.list_portals()
    filing = catalogue.list_portals(category=PortalCategory.FILING)
    for_303 = catalogue.list_portals(modelo=Modelo("303"))
    one = catalogue.view_portal(everything.rows[0].portal)

    assert everything.count == len(everything.rows) == len(PORTAL_REGISTRY)
    assert filing.rows and {row.category for row in filing.rows} == {"filing"}
    assert for_303.count == len(for_303.rows) >= 1
    assert one.model_dump() == everything.rows[0].model_dump()
    assert not any(row.label.startswith("entries.") for row in everything.rows)


def test_portal_filters_exclude_each_other_and_an_unknown_portal_is_refused() -> None:
    with pytest.raises(catalogue.PortalFilterConflictError):
        catalogue.list_portals(category=PortalCategory.FILING, modelo=Modelo("303"))
    with pytest.raises(PortalRegistryError):
        catalogue.view_portal("NOT_A_PORTAL_ID")


def test_the_authentication_providers_are_listed_with_rendered_labels() -> None:
    result = catalogue.list_auth_providers()

    assert {"certificate", "clave_movil"} <= {str(provider.id) for provider in result.providers}
    assert all(provider.label and "." not in provider.label for provider in result.providers)


def test_the_representative_scopes_come_from_the_published_catalogue(operation: PinnedAuthorityOperation) -> None:
    result = catalogue.list_apoderado_scopes(operation=operation)

    assert result.catalogue_version
    assert {"IVA", "RENT", "CENSO"} <= {scope.code for scope in result.scopes}


def _dump(value: BaseModel) -> object:
    return value.model_dump(mode="json")


def _missing(old: object, new: object, path: str = "") -> list[str]:
    """Name every field of ``old`` that ``new`` lacks or carries with another value."""
    if isinstance(old, dict) and isinstance(new, dict):
        return [
            problem
            for key, value in old.items()
            for problem in (_missing(value, new[key], f"{path}/{key}") if key in new else [f"{path}/{key} is absent"])
        ]
    if isinstance(old, list) and isinstance(new, list):
        if len(old) != len(new):
            return [f"{path} has {len(new)} items, not {len(old)}"]
        return [
            problem
            for old_item, new_item in zip(old, new, strict=True)
            for problem in _missing(old_item, new_item, f"{path}[]")
        ]
    return [] if old == new else [f"{path} is {new!r}, not {old!r}"]


# Each answer is checked against the registry report it projects: that report is
# what the harness tool returned before the projection, so nothing it carried
# may be dropped from the answer.
_RETAINED: tuple[tuple[str, Callable[[PinnedAuthorityOperation], tuple[BaseModel, BaseModel]]], ...] = (
    (
        "modelos",
        lambda op: (registry_list_modelos(operation=op), catalogue.list_modelos(operation=op)),
    ),
    (
        "support",
        lambda op: (registry_support_matrix(operation=op), catalogue.read_support_matrix(operation=op)),
    ),
    (
        "describe-scoped",
        lambda op: (
            registry_describe_modelo_for_registry_scope("130", filing_year=2025, period="1T", operation=op),
            catalogue.describe_modelo("130", year=2025, period="1T", operation=op),
        ),
    ),
    (
        "describe-unscoped",
        lambda op: (
            registry_describe_modelo("130", period="1T", operation=op),
            catalogue.describe_modelo("130", period="1T", operation=op),
        ),
    ),
    (
        "casillas-scoped",
        lambda op: (
            registry_casillas_for_registry_scope("303", filing_year=2025, period="1T", operation=op),
            catalogue.list_casillas("303", year=2025, period="1T", operation=op),
        ),
    ),
    (
        "casillas-filtered",
        lambda op: (
            registry_casillas_for_registry_scope(
                "303", filing_year=2025, period="1T", input_kind=InputKind.MANUAL, required=True, operation=op
            ),
            catalogue.list_casillas(
                "303", year=2025, period="1T", input_kind=InputKind.MANUAL, required=True, operation=op
            ),
        ),
    ),
    (
        "casillas-unscoped",
        lambda op: (
            registry_casillas("130", period="1T", operation=op),
            catalogue.list_casillas("130", period="1T", operation=op),
        ),
    ),
    (
        "casilla-scoped",
        lambda op: (
            registry_casilla_for_registry_scope("130", "03", filing_year=2025, period="1T", operation=op),
            catalogue.describe_casilla("130", "03", year=2025, period="1T", operation=op),
        ),
    ),
    (
        "casilla-unscoped",
        lambda op: (
            registry_casilla("130", "01", period="1T", operation=op),
            catalogue.describe_casilla("130", "01", period="1T", operation=op),
        ),
    ),
    (
        "formulas-scoped",
        lambda op: (
            registry_formulas_for_registry_scope("130", filing_year=2025, period="1T", operation=op),
            catalogue.list_formulas("130", year=2025, period="1T", operation=op),
        ),
    ),
    (
        "formulas-unscoped",
        lambda op: (
            registry_formulas("130", period="1T", operation=op),
            catalogue.list_formulas("130", period="1T", operation=op),
        ),
    ),
)


@pytest.mark.parametrize(("label", "pair"), _RETAINED, ids=[row[0] for row in _RETAINED])
def test_an_answer_carries_every_field_of_the_registry_report_it_projects(
    operation: PinnedAuthorityOperation,
    label: str,
    pair: Callable[[PinnedAuthorityOperation], tuple[BaseModel, BaseModel]],
) -> None:
    report, answer = pair(operation)

    assert _missing(_dump(report), _dump(answer)) == [], label


def test_the_restored_fields_are_named_per_query(operation: PinnedAuthorityOperation) -> None:
    casillas = catalogue.list_casillas("303", year=2025, period="1T", operation=operation)
    casilla = catalogue.describe_casilla("130", "03", year=2025, period="1T", operation=operation)
    formulas = catalogue.list_formulas("130", year=2025, period="1T", operation=operation)

    assert {"code", "filing_year", "filing_period", "period"} <= set(casillas.model_dump())
    assert {"section", "data_type", "binding", "formula", "form_number"} <= set(casillas.rows[0].model_dump())
    assert {"code", "filing_period"} <= set(casilla.model_dump())
    assert "filing_period" in formulas.model_dump()


def test_a_pinned_reference_read_reports_the_generation_its_reader_was_given(
    operation: PinnedAuthorityOperation,
) -> None:
    seen: list[PinnedAuthorityOperation] = []

    def read(pinned: PinnedAuthorityOperation) -> ModeloSupportMatrixResult:
        seen.append(pinned)
        return catalogue.read_support_matrix(operation=pinned)

    answer = catalogue.read_pinned_reference(read)

    assert len(seen) == 1
    assert answer.generation == seen[0].generation
    # The fixture holds an independent pin of the same publication, so both name one generation.
    assert answer.generation.logical_generation == operation.generation.logical_generation
    assert answer.report == catalogue.read_support_matrix(operation=operation)


def test_a_pinned_reference_read_lets_the_readers_refusal_through_unchanged() -> None:
    with pytest.raises(catalogue.CededAutonomicModeloError):
        catalogue.read_pinned_reference(
            lambda pinned: catalogue.describe_modelo(_CEDED[0], year=None, period=None, as_of=None, operation=pinned)
        )
