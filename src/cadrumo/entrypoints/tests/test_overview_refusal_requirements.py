"""Owning contract probes extracted from native integration scenarios."""

from __future__ import annotations

import pytest

from cadrumo.application.user_profile.preflight import build_profile_preflight_requirement
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.calculations.registry.tests.published_authority import published_profile_schema
from cadrumo.entrypoints.overview_read_composition import _refusal_requirements

_ENTITY_TYPE_SELECTOR = "taxpayer.entity_type"
_IRPF_INCOME_CATEGORIES_SELECTOR = "taxpayer.irpf_income_categories"


pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_an_undeclared_entity_type_is_named_rather_than_summarised() -> None:
    """The refusal names the entity-type field, not only "model undeclared"."""
    with bundled_indexed_authority().operation() as operation:
        requirements = _refusal_requirements(
            operation=operation, taxpayer=_profile(), taxpayer_model_declared=False, warning_codes=()
        )
    assert any(_label_for(_ENTITY_TYPE_SELECTOR) in requirement for requirement in requirements)
    assert _ENTITY_TYPE_SELECTOR not in ", ".join(requirements)


def test_a_natural_person_without_income_categories_is_told_about_the_categories() -> None:
    """A field the operator already filled in must not be named.

    The entity type IS declared here, so naming it would send the operator
    back to a box they already answered.
    """
    from cadrumo.domain.contribuyente.entity_type import EntityType

    with bundled_indexed_authority().operation() as operation, validating_governed_facts(operation):
        requirements = _refusal_requirements(
            operation=operation,
            taxpayer=_profile(entity_type=EntityType.from_registry("natural_person")),
            taxpayer_model_declared=False,
            warning_codes=(),
        )
    assert any(_label_for(_IRPF_INCOME_CATEGORIES_SELECTOR) in requirement for requirement in requirements)
    assert _label_for(_ENTITY_TYPE_SELECTOR) not in ", ".join(requirements)


def _label_for(selector: str) -> str:
    schema = published_profile_schema()
    path = schema.path_for_model_selector(selector)
    assert path is not None, f"{selector} does not resolve to a schema field"
    return build_profile_preflight_requirement(path, schema=schema, selector=selector).label


def _profile(**kwargs):
    from cadrumo.domain.deadlines.models import IVARegime, TaxpayerProfile

    with bundled_indexed_authority().operation() as operation, validating_governed_facts(operation):
        return TaxpayerProfile(tax_id="00000000T", iva_regime=IVARegime("GENERAL"), **kwargs)


def test_the_taxpayer_model_fields_have_labels_that_differ_from_their_tokens() -> None:
    """Anchor: the two tests below are vacuous if label and token coincide."""
    assert _label_for(_ENTITY_TYPE_SELECTOR) != _ENTITY_TYPE_SELECTOR
    assert _label_for(_IRPF_INCOME_CATEGORIES_SELECTOR) != _IRPF_INCOME_CATEGORIES_SELECTOR
