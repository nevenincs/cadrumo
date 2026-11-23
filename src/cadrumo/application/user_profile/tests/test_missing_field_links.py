"""Every detail completeness names is a real profile field a view link can open.

The readiness notice links each missing detail to ``cadrumo://view/profile?field=<path>``
with the path the completeness owner served. These tests run the real
completeness resolver over the bundled profile schema, so a path it names that
the schema does not declare, or one the register's ``profile-field`` kind does
not admit, fails here rather than as a dead link in the window.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.user_profile.schema import ProfileSchemaDefinition
from cadrumo_client.contracts.navigation import ViewLink, load_navigation_register, parse_view_link, view_link

from ..completeness import conditional_profile_missing_required, missing_required_field_paths

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SHAPES: dict[str, dict[str, str]] = {
    "nothing stated": {},
    "iva block without the large-company answer": {
        "taxpayer_type.entity_type": "natural_person",
        "taxpayer_type.irpf_income_categories": "actividad_economica",
        "iva.regime": "GENERAL",
    },
    "a stated withholding payer": {
        "taxpayer_type.entity_type": "natural_person",
        "taxpayer_type.irpf_income_categories": "rendimientos_trabajo",
        "withholding.has_employees": "true",
    },
    "a legal entity": {"taxpayer_type.entity_type": "legal_entity"},
}


@pytest.fixture(scope="module")
def schema() -> ProfileSchemaDefinition:
    with bundled_indexed_authority().operation() as operation:
        return operation.profile_schema()


def _missing(schema: ProfileSchemaDefinition, values: dict[str, str]) -> tuple[str, ...]:
    return (*missing_required_field_paths(schema, values), *conditional_profile_missing_required(values))


@pytest.mark.parametrize("shape", list(_SHAPES))
def test_every_missing_detail_is_a_schema_field_its_link_opens(shape: str, schema: ProfileSchemaDefinition) -> None:
    missing = _missing(schema, _SHAPES[shape])
    assert missing
    declared = set(schema.field_paths)
    register = load_navigation_register()
    for path in missing:
        assert path in declared
        link = view_link("profile", {"field": path}, register=register)
        assert parse_view_link(link, register=register) == ViewLink("profile", (("field", path),))


def test_the_large_company_answer_is_named_with_its_own_link(schema: ProfileSchemaDefinition) -> None:
    missing = _missing(schema, _SHAPES["iva block without the large-company answer"])
    assert "censo.large_company" in missing
    assert view_link("profile", {"field": "censo.large_company"}) == "cadrumo://view/profile?field=censo.large_company"


def test_every_profile_field_fits_the_register_kind(schema: ProfileSchemaDefinition) -> None:
    """Whatever completeness names next, its path is one the link grammar carries."""
    register = load_navigation_register()
    profile = register.element("profile")
    assert profile is not None
    kind = register.value_kind(profile.params["field"])
    refused = sorted(path for path in schema.field_paths if not kind.admits(path))
    assert refused == []
