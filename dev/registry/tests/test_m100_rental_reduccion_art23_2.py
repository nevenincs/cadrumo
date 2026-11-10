"""Modelo 100 Art. 23.2 housing-rental reduction calculation tests, on the edition that declares the tier."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cadrumo.application.aggregation.source_mesh import CalculationSourceContext
from cadrumo.application.aggregation.source_profile import ProfileSourceResolver
from cadrumo.core.aggregation import BindingTypedEnumKind
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.binding_value_contract import BindingDataType, BindingValueChannel
from cadrumo.domain.calculations.registry.rental_reduction import resolve_rental_reduction_art232_tier_catalogue
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression
from cadrumo.domain.calculations.registry.tests import m100_rental_reduccion_art23_2_scenarios as scenarios
from cadrumo.domain.renta.rental_reduction import RentalReductionArt232Tier
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test,
)
from cadrumo.domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    create_user_profile_record,
)
from dev.registry.tests.profile_schema_support import load_user_profile_schema

from ..compiler.authority import compiled_bundled_authority

_TIER_DECLARED_ID = scenarios.TIER_BINDING
_REVISION_ID = scenarios.TIER_EDITION_ID
_EXERCISE = scenarios.TIER_EDITION_EXERCISE

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]


@pytest.fixture(scope="module")
def m100_tier_edition_snapshot(registry_snapshot: Callable[..., RegistrySnapshot]) -> RegistrySnapshot:
    """A formula-runtime calculation claim, never a filing one."""
    return registry_snapshot(
        "100",
        _EXERCISE,
        "0A",
        revision_id=_REVISION_ID,
        grade=RegistryAuthorityGrade.CALCULATION,
    )


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as operation:
        yield operation


def test_tier_binding_is_layout_and_law_grounded(m100_tier_edition_snapshot: RegistrySnapshot) -> None:
    scenarios.check_tier_binding_is_layout_and_law_grounded(m100_tier_edition_snapshot)


@pytest.mark.parametrize(
    ("tier", "expected"),
    (
        ("tier-50", Decimal("5000.00")),
        ("tier-60", Decimal("6000.00")),
        ("tier-70", Decimal("7000.00")),
        ("tier-90", Decimal("9000.00")),
    ),
)
def test_0150_uses_operator_selected_art23_2_tier(
    m100_tier_edition_snapshot: RegistrySnapshot, tier: str, expected: Decimal
) -> None:
    scenarios.check_0150_uses_operator_selected_art23_2_tier(m100_tier_edition_snapshot, tier, expected)


def test_0150_unchecked_eligibility_does_not_require_or_apply_tier(
    m100_tier_edition_snapshot: RegistrySnapshot,
) -> None:
    scenarios.check_0150_unchecked_eligibility_does_not_require_or_apply_tier(m100_tier_edition_snapshot)


@pytest.mark.parametrize(
    "inputs",
    (
        {"0100": Decimal("1"), "0102": Decimal("100.00"), "0104": Decimal("100.00")},
        {"0100": Decimal("1"), "0102": Decimal("100.00"), "0104": Decimal("250.00")},
    ),
)
def test_0150_non_positive_0149_does_not_create_positive_reduction(
    m100_tier_edition_snapshot: RegistrySnapshot, inputs: dict[str, Decimal]
) -> None:
    scenarios.check_0150_non_positive_0149_does_not_create_positive_reduction(m100_tier_edition_snapshot, inputs)


def test_0150_positive_checked_rental_fails_closed_without_tier(m100_tier_edition_snapshot: RegistrySnapshot) -> None:
    scenarios.check_0150_positive_checked_rental_fails_closed_without_tier(m100_tier_edition_snapshot)


def test_0150_rejects_unknown_tier_key(m100_tier_edition_snapshot: RegistrySnapshot) -> None:
    scenarios.check_0150_rejects_unknown_tier_key(m100_tier_edition_snapshot)


_TIER_PROFILE_KEY = "renta_rental.reduccion_art_23_2_tier_2024"
_PROFILE_ID = "10010010-0100-4100-8100-100100100100"


@pytest.fixture(scope="module")
def m100_tier_edition_compiled_snapshot() -> RegistrySnapshot:
    """A snapshot over the authored declarations, not a published artifact."""
    return compiled_bundled_authority().snapshot(
        "100",
        filing_year=_EXERCISE,
        period="0A",
        revision_id=_REVISION_ID,
        grade=RegistryAuthorityGrade.CALCULATION,
    )


def _tier_profile_record(tier: RentalReductionArt232Tier) -> UserProfileRecord:
    moment = datetime(_EXERCISE + 1, 5, 21, 10, 0, 0, tzinfo=UTC)
    return create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Ñ"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path=_TIER_PROFILE_KEY, value=tier.value),
        ),
        created_at=moment,
        updated_at=moment,
        context=profile_creation_context_for_test(),
    )


def _dispatch_keys(node: FormulaExpression) -> set[str]:
    """Collect every dispatch-table key an expression tree declares."""
    keys: set[str] = set(node.dispatch_table or ())
    for arg in node.args:
        keys |= _dispatch_keys(arg)
    return keys


def test_tier_binding_declares_the_closed_substrate_enum(
    m100_tier_edition_compiled_snapshot: RegistrySnapshot,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The tier is a closed-membership axis, and its value contract says so.

    A percentage tier is a dispatch key the formula looks a rate up by, never
    an amount, and the keys it may take are exactly the members of the owning
    substrate enum.
    """
    binding = next(
        item for item in m100_tier_edition_compiled_snapshot.revision.bindings if item.id == _TIER_DECLARED_ID
    )

    assert binding.value.data_type is BindingDataType.ENUM
    assert binding.value.channel is BindingValueChannel.ENUM
    assert binding.value.typed_enum is BindingTypedEnumKind.RENTAL_REDUCTION_ART_23_2_TIER

    formula = next(
        item
        for item in m100_tier_edition_compiled_snapshot.revision.formulas
        if item.id == "renta-capital-inmobiliario-reduccion-arrendamiento-vivienda-art-23-2"
    )
    catalogue = resolve_rental_reduction_art232_tier_catalogue(
        effective_date=scenarios.FILING_DATE,
        authority=authority_operation,
    )
    assert _dispatch_keys(formula.expression) == {member.value for member in catalogue.all_tiers}


def test_declared_tier_resolves_onto_the_enum_channel_through_the_profile_resolver(
    m100_tier_edition_compiled_snapshot: RegistrySnapshot,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Every tier member travels the live profile resolver onto the enum channel."""
    catalogue = resolve_rental_reduction_art232_tier_catalogue(
        effective_date=scenarios.FILING_DATE,
        authority=authority_operation,
    )
    for tier in catalogue.all_tiers:
        resolution = ProfileSourceResolver(
            registry_snapshot=m100_tier_edition_compiled_snapshot,
            profile_record=_tier_profile_record(tier),
            operation=authority_operation,
        ).resolve(
            CalculationSourceContext(
                bucket_id=_PROFILE_ID,
                modelo="100",
                filing_year=_EXERCISE,
                period=Period.from_year_and_code(_EXERCISE, "0A"),
                revision=m100_tier_edition_compiled_snapshot.revision,
            ),
        )

        assert resolution.enum_binding_values[_TIER_DECLARED_ID] == tier.value
        assert _TIER_DECLARED_ID not in resolution.binding_values


def test_profile_schema_and_substrate_enum_declare_the_same_tiers(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The taxpayer-facing vocabulary and the substrate enum cannot drift apart."""
    schema = load_user_profile_schema()
    catalogue = resolve_rental_reduction_art232_tier_catalogue(
        effective_date=scenarios.FILING_DATE,
        authority=authority_operation,
    )

    assert set(schema.field(_TIER_PROFILE_KEY).enum_values) == {member.value for member in catalogue.all_tiers}
