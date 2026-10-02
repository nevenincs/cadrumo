"""Every binding source kind is explained, and its override policy is the calculation's own.

The table must be total over the source kinds, must agree with the calculation's
caller-override precedence ladder in both directions, and must never claim a lock
or an override for a kind the ladder does not govern. Every source must also be
nameable in every supported language, because an editor shows it to a person.
"""

from __future__ import annotations

import pytest

from ....application.aggregation.source_mesh import CallerOverrideDisposition, precedence_ladder_sources
from ....core.aggregation import BindingSourceKind
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import lookup_translation
from ..source_policy import SourceFamily, SourceOverridePolicy, SourceSurface, source_policy

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_every_source_kind_has_exactly_one_policy() -> None:
    policies = tuple(source_policy(kind) for kind in BindingSourceKind)

    assert [policy.source_kind for policy in policies] == list(BindingSourceKind)


def test_locked_and_carried_policies_are_exactly_the_calculation_ladder() -> None:
    fixed_at_source = {
        policy.source_kind
        for policy in (source_policy(kind) for kind in BindingSourceKind)
        if policy.override_policy is SourceOverridePolicy.FIX_AT_SOURCE
    }
    overridable = {
        policy.source_kind
        for policy in (source_policy(kind) for kind in BindingSourceKind)
        if policy.override_policy is SourceOverridePolicy.OVERRIDE_WITH_REASON
    }

    assert fixed_at_source == precedence_ladder_sources(CallerOverrideDisposition.LOCK)
    assert overridable == precedence_ladder_sources(CallerOverrideDisposition.CARRY)


def test_a_kind_outside_the_ladder_is_never_claimed_locked_or_overridable() -> None:
    governed = precedence_ladder_sources(CallerOverrideDisposition.LOCK) | precedence_ladder_sources(
        CallerOverrideDisposition.CARRY
    )

    for kind in set(BindingSourceKind) - governed:
        assert source_policy(kind).override_policy in {
            SourceOverridePolicy.ENTER,
            SourceOverridePolicy.FIXED,
            SourceOverridePolicy.EDIT_AT_HOME,
            SourceOverridePolicy.UNDECIDED,
        }


def test_the_product_owned_policies_name_their_home() -> None:
    assert source_policy(BindingSourceKind.MANUAL_INPUT).override_policy is SourceOverridePolicy.ENTER
    assert source_policy(BindingSourceKind.DESIGN_CONSTANT).family is SourceFamily.FIXED_BY_DESIGN
    profile = source_policy(BindingSourceKind.PROFILE)
    assert profile.override_policy is SourceOverridePolicy.EDIT_AT_HOME
    assert profile.surface is SourceSurface.PROFILE


def test_undecided_policies_are_the_kinds_nobody_has_classified() -> None:
    undecided = {
        kind for kind in BindingSourceKind if source_policy(kind).override_policy is SourceOverridePolicy.UNDECIDED
    }

    assert BindingSourceKind.BORRADOR in undecided
    assert BindingSourceKind.RETENCIONES_AGGREGATION in undecided
    assert BindingSourceKind.LEDGER_IVA_AGGREGATION not in undecided


@pytest.mark.parametrize("language", tuple(OutputLanguage))
def test_every_source_is_nameable_in_every_language(language: OutputLanguage) -> None:
    for kind in BindingSourceKind:
        policy = source_policy(kind)
        assert lookup_translation(policy.label_key, locale=language.value), policy.label_key
        assert lookup_translation(policy.origin_sentence_key, locale=language.value), policy.origin_sentence_key
