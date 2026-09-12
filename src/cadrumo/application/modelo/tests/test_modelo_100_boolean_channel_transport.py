"""The boolean value channel travels end to end, and the declared contract picks it.

Companion to ``test_modelo_100_boolean_channel_profile_bindings``, which pins
the DECLARATIONS. This module pins the TRANSPORT: that a boolean-contract
binding leaves the profile resolver on ``boolean_binding_values`` rather than
folded onto Decimal, survives the source-resolution merge, reaches the formula
evaluator, and is refused rather than coerced when a value arrives for the wrong
contract.

It also pins the routing AUTHORITY. Channel selection reads the binding's own
authored ``value.channel``, not the shape of whatever formula happens to consume
it: a declared date binding with no ``age_at_year_end`` consumer still resolves
on the date channel, which is the case consumer-shape inference got wrong by
construction.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.binding_value_contract import BindingValueChannel
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.formula_runtime import (
    calculate_registry_snapshot,
    evaluate_expression,
)
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.user_profile.registry_contract import profile_binding_selectors
from ...aggregation.source_mesh import CalculationSourceResolution
from ...aggregation.source_resolution_operations import (
    merge_source_resolutions,
    merge_source_resolutions_by_precedence,
)
from ..profile_binding import (
    ProfileBindingResolutionError,
    profile_resolved_binding_ids,
    resolve_profile_binding_channels,
    resolve_profile_sourced_bindings,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_ANUALIDADES_BINDING = "renta-profile-anualidades-sin-minimo-descendientes"
_ECONOMIC_ACTIVITY_BINDING = "renta-profile-has-economic-activity"
_BIRTH_DATE_BINDING = "renta-profile-taxpayer-birth-date"


def _snapshot(year: int = 2025) -> RegistrySnapshot:
    return bundled_authority().snapshot("100", filing_year=year, period="0A")


def _binding(snapshot: RegistrySnapshot, binding_id: str) -> Any:
    return next((b for b in snapshot.revision.bindings if b.id == binding_id), None)


# ---------------------------------------------------------------------------
# Transport: the resolver populates the boolean channel, not the Decimal one
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("year", [2020, 2021, 2022, 2023, 2024, 2025])
def test_boolean_contract_bindings_never_appear_on_the_decimal_channel(year: int) -> None:
    """Whatever the profile holds, a boolean contract does not land on Decimal.

    The defect this closes is silent, so the assertion is stated as an
    invariant over the whole resolution rather than over one binding: NO
    binding whose registry contract declares the boolean channel may appear in
    ``binding_values``. A regression that re-collapses the channel shows up
    here regardless of which binding it happens to affect.
    """
    snapshot = _snapshot(year)
    boolean_ids = {
        binding.id for binding in snapshot.revision.bindings if binding.value.channel is BindingValueChannel.BOOLEAN
    }
    resolution = resolve_profile_sourced_bindings(snapshot, bucket_id="nonexistent-bucket-for-channel-shape")

    assert not (boolean_ids & set(resolution.binding_values))


def test_resolution_envelope_carries_the_boolean_channel_as_real_bools() -> None:
    """The carrier stores ``bool``, and ``profile_resolved_binding_ids`` counts it.

    ``Decimal("1") == True``, so a value assertion cannot tell the encodings
    apart. ``is`` can, and the channel exists precisely so the distinction
    survives transport.
    """
    resolution = CalculationSourceResolution(
        resolver_id="profile",
        boolean_binding_values={_ANUALIDADES_BINDING: True, _ECONOMIC_ACTIVITY_BINDING: False},
    )

    assert resolution.boolean_binding_values[_ANUALIDADES_BINDING] is True
    assert resolution.boolean_binding_values[_ECONOMIC_ACTIVITY_BINDING] is False
    assert not resolution.binding_values
    assert profile_resolved_binding_ids(resolution) == frozenset(
        {_ANUALIDADES_BINDING, _ECONOMIC_ACTIVITY_BINDING},
    )


def test_exclusive_merge_carries_the_boolean_channel_and_clears_its_unresolved_mark() -> None:
    """A boolean-channel value resolves its binding as surely as a Decimal one.

    The second assertion is the load-bearing one: a binding satisfied ONLY on
    the boolean channel must not remain in ``unresolved_binding_ids``, or the
    engine omits every formula target that depends on it and the casilla goes
    quietly absent.
    """
    decimal_tier = CalculationSourceResolution(
        resolver_id="ledger",
        binding_values={"some-decimal-binding": Decimal("10")},
        unresolved_binding_ids=(_ANUALIDADES_BINDING,),
    )
    boolean_tier = CalculationSourceResolution(
        resolver_id="profile",
        boolean_binding_values={_ANUALIDADES_BINDING: True},
    )

    merged = merge_source_resolutions((decimal_tier, boolean_tier))

    assert merged.boolean_binding_values[_ANUALIDADES_BINDING] is True
    assert _ANUALIDADES_BINDING not in merged.unresolved_binding_ids


def test_precedence_merge_lets_a_later_tier_overlay_a_truth_value() -> None:
    """Later tiers win on the boolean channel exactly as on the Decimal one."""
    lower = CalculationSourceResolution(
        resolver_id="profile",
        boolean_binding_values={_ANUALIDADES_BINDING: True},
    )
    higher = CalculationSourceResolution(
        resolver_id="calculate_caller_bindings",
        boolean_binding_values={_ANUALIDADES_BINDING: False},
    )

    merged = merge_source_resolutions_by_precedence((lower, higher))

    assert merged.boolean_binding_values[_ANUALIDADES_BINDING] is False


# ---------------------------------------------------------------------------
# The formula evaluator reads the boolean channel
# ---------------------------------------------------------------------------


def _calculate(snapshot: RegistrySnapshot, **kwargs: Any) -> Any:
    return calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context={"filing_period": date(snapshot.filing_year, 12, 31)},
        **kwargs,
    )


def test_engine_refuses_a_binding_claimed_by_both_the_boolean_and_decimal_channels() -> None:
    """Two channels, two disagreeing authorities, no defensible winner.

    Preferring either silently resolves a contradiction the caller can still
    see and fix, so the engine refuses instead. The refusal names the binding,
    which is what makes it actionable.
    """
    snapshot = _snapshot()

    with pytest.raises(RegistryValidationError, match="both the boolean and the"):
        _calculate(
            snapshot,
            binding_values={_ANUALIDADES_BINDING: Decimal("1")},
            boolean_binding_values={_ANUALIDADES_BINDING: True},
        )


def test_engine_refuses_a_truth_value_for_a_binding_that_declares_a_quantity() -> None:
    """The boolean channel is not a general-purpose side door into the engine.

    A resolver routing a truth value at a binding the registry says holds an
    amount is the same defect as the original collapse, running the other way;
    it is refused at the same boundary.
    """
    snapshot = _snapshot()
    decimal_binding = next(
        binding.id for binding in snapshot.revision.bindings if binding.value.channel is BindingValueChannel.DECIMAL
    )

    with pytest.raises(RegistryValidationError, match="do not declare the boolean value contract"):
        _calculate(snapshot, boolean_binding_values={decimal_binding: True})


def test_engine_refuses_a_truth_value_for_a_binding_the_revision_never_declared() -> None:
    """An undeclared binding id on the boolean channel is refused, not waved through.

    The boolean channel screens its ids against the revision's declared set
    exactly as the Decimal, relation and enum channels do. Without the screen a
    typo'd or stale id arrives carrying a truth value, matches no declaration,
    and is silently discarded: the formula that wanted the fact then reports the
    binding as unsupplied and the operator is sent after the wrong defect.
    """
    snapshot = _snapshot()
    undeclared = "renta-profile-binding-this-revision-never-declared"
    assert undeclared not in {binding.id for binding in snapshot.revision.bindings}

    with pytest.raises(RegistryValidationError, match="boolean_binding"):
        _calculate(snapshot, boolean_binding_values={undeclared: True})


def _casilla_values_reaching_the_regimen_predicate(snapshot: RegistrySnapshot) -> dict[str, Decimal]:
    """Casilla values that steer the real expression AS FAR AS the régimen predicate.

    The predicate is nested behind two guards the authority puts there (LIRPF
    art. 64 applies only when anualidades are declared and do not exhaust the
    base liquidable general), so a uniform fill never reaches it and the test
    would pass while proving nothing. 0527 < 0505 with both positive is the
    statutory shape under which the régimen question is actually asked.
    """
    values = dict.fromkeys((casilla.id for casilla in snapshot.revision.casillas), Decimal("1000"))
    values["0527"] = Decimal("1000")
    values["0505"] = Decimal("50000")
    return values


def _expression_uses_binding(node: object, binding_id: str) -> bool:
    """Walk a compiled expression tree for a reference to ``binding_id``."""
    if isinstance(node, dict):
        if node.get("binding") == binding_id:
            return True
        return any(_expression_uses_binding(value, binding_id) for value in node.values())
    if isinstance(node, (list, tuple)):
        return any(_expression_uses_binding(item, binding_id) for item in node)
    return False


def test_boolean_operand_drives_a_real_registry_predicate_to_two_different_answers() -> None:
    """The two truth values steer the real compiled régimen predicate differently.

    The end-to-end proof that the channel is wired rather than merely declared.
    It evaluates a REAL compiled formula expression -- the anualidades
    separate-escala predicate off the published registry -- through the REAL
    evaluator, supplying the binding ONLY on the boolean channel. Three things
    are therefore proven at once: the operand was found (a dropped channel would
    raise ``binding ... has no supplied value``), it was read as a predicate,
    and it actually decides the branch (a channel read but ignored would return
    the same value twice).

    Deliberately NOT a whole-filing ``calculate_registry_snapshot`` run: Modelo
    100 needs a complete bound-casilla input set before it will evaluate at all,
    so a full run would test input assembly and report a régimen regression as
    an unrelated missing-casilla error.
    """
    snapshot = _snapshot()
    formula = next(
        (
            candidate
            for candidate in snapshot.revision.formulas
            if _expression_uses_binding(candidate.expression.model_dump(), _ANUALIDADES_BINDING)
        ),
        None,
    )
    assert formula is not None, "no published formula consumes the anualidades régimen binding"

    def _run(*, eligible: bool) -> tuple[Decimal, list[str]]:
        operand_refs: list[str] = []
        value = evaluate_expression(
            formula.expression,
            values=_casilla_values_reaching_the_regimen_predicate(snapshot),
            binding_values=dict.fromkeys(
                (binding.id for binding in snapshot.revision.bindings),
                Decimal("1000"),
            ),
            parameters={parameter.id: parameter for parameter in snapshot.revision.parameters},
            date_context={"filing_period": date(snapshot.filing_year, 12, 31)},
            relation_values={},
            unresolved_relation_ids=frozenset(),
            unresolved_casilla_ids=set(),
            operand_refs=operand_refs,
            operand_casilla_refs=[],
            operand_values=[],
            boolean_binding_values={_ANUALIDADES_BINDING: eligible},
            filing_year=snapshot.filing_year,
        )
        return value, operand_refs

    eligible_value, eligible_refs = _run(eligible=True)
    withheld_value, _ = _run(eligible=False)

    # The operand was supplied on the boolean channel and genuinely read.
    assert _ANUALIDADES_BINDING in eligible_refs
    # And it selects the branch: the régimen on and off are different answers.
    assert eligible_value != withheld_value


def test_the_boolean_operand_is_absent_from_the_decimal_channel_in_that_same_run() -> None:
    """The predicate above resolves with the binding ABSENT from ``binding_values``.

    Stated separately because it is the half that proves the boolean channel did
    the work. In the run above the Decimal channel was populated for every
    binding, so a boolean channel that silently fell back to Decimal would still
    have found a value and the test would pass for the wrong reason.
    """
    snapshot = _snapshot()
    formula = next(
        candidate
        for candidate in snapshot.revision.formulas
        if _expression_uses_binding(candidate.expression.model_dump(), _ANUALIDADES_BINDING)
    )
    operand_refs: list[str] = []
    value = evaluate_expression(
        formula.expression,
        values=_casilla_values_reaching_the_regimen_predicate(snapshot),
        binding_values={
            binding.id: Decimal("1000") for binding in snapshot.revision.bindings if binding.id != _ANUALIDADES_BINDING
        },
        parameters={parameter.id: parameter for parameter in snapshot.revision.parameters},
        date_context={"filing_period": date(snapshot.filing_year, 12, 31)},
        relation_values={},
        unresolved_relation_ids=frozenset(),
        unresolved_casilla_ids=set(),
        operand_refs=operand_refs,
        operand_casilla_refs=[],
        operand_values=[],
        boolean_binding_values={_ANUALIDADES_BINDING: True},
        filing_year=snapshot.filing_year,
    )

    assert isinstance(value, Decimal)
    assert _ANUALIDADES_BINDING in operand_refs


# ---------------------------------------------------------------------------
# The declared contract, not the consumer shape, picks the channel
# ---------------------------------------------------------------------------


def test_declared_date_binding_resolves_on_the_date_channel_without_a_date_consumer() -> None:
    """A date contract is a date contract even where no ``age_at_year_end`` reads it.

    The regression this pins is the one consumer-shape inference cannot avoid:
    with the date channel selected by "some formula consumes this under a
    date-aware op", a declared date binding whose consumer has not been written
    yet -- or was removed -- silently falls through to the Decimal channel,
    where ``_decimal_value`` reports the taxpayer's birth date as a type error
    and blames the profile for a registry gap.

    Exercised by resolving the real compiled birth-date binding with an EMPTY
    date-consumer set, which is exactly the "no consumer" world, against the
    real routing function.
    """
    snapshot = _snapshot()
    binding = _binding(snapshot, _BIRTH_DATE_BINDING)
    assert binding is not None
    assert binding.value.channel is BindingValueChannel.DATE

    channels = resolve_profile_binding_channels(
        (binding,),
        {"renta_taxpayer.birth_date": date(1980, 3, 4)},
        caller_binding_ids=frozenset(),
        formula_date_consumed=frozenset(),
        enum_bindings=frozenset(),
    )

    assert channels.date_values == {_BIRTH_DATE_BINDING: date(1980, 3, 4)}
    assert not channels.decimal_values
    assert not channels.boolean_values


def test_declared_boolean_binding_resolves_on_the_boolean_channel_without_a_consumer() -> None:
    """Same invariant on the boolean side: the declaration is the authority."""
    snapshot = _snapshot()
    binding = _binding(snapshot, _ANUALIDADES_BINDING)
    assert binding is not None

    channels = resolve_profile_binding_channels(
        (binding,),
        {"renta_family.anualidades_sin_minimo_descendientes_2025": True},
        caller_binding_ids=frozenset(),
        formula_date_consumed=frozenset(),
        enum_bindings=frozenset(),
    )

    assert channels.boolean_values == {_ANUALIDADES_BINDING: True}
    assert not channels.decimal_values


def test_resolver_refuses_a_decimal_standing_in_for_a_boolean_contract() -> None:
    """``Decimal("1")`` is not a truth value, and is not quietly read as one.

    Accepting it would restore the very ambiguity the channel removes, because
    ``Decimal("1") == True`` compares equal.
    """
    snapshot = _snapshot()
    binding = _binding(snapshot, _ANUALIDADES_BINDING)
    assert binding is not None

    with pytest.raises(ProfileBindingResolutionError, match="is not a boolean"):
        resolve_profile_binding_channels(
            (binding,),
            {"renta_family.anualidades_sin_minimo_descendientes_2025": Decimal("1")},
            caller_binding_ids=frozenset(),
            formula_date_consumed=frozenset(),
            enum_bindings=frozenset(),
        )


def test_resolver_refuses_a_truth_value_for_a_money_contract() -> None:
    """The symmetric refusal: a bool must not become an amount.

    This is the direction that produces a filing-grade figure out of a fact
    carrying no magnitude, so it fails closed rather than writing a zero.
    """
    snapshot = _snapshot()
    money_binding, selector = next(
        (binding, selectors[0])
        for binding in snapshot.revision.bindings
        if binding.value.channel is BindingValueChannel.DECIMAL
        if (selectors := profile_binding_selectors(binding.provider))
    )

    with pytest.raises(ProfileBindingResolutionError, match="is a boolean but the binding declares"):
        resolve_profile_binding_channels(
            (money_binding,),
            {selector: True},
            caller_binding_ids=frozenset(),
            formula_date_consumed=frozenset(),
            enum_bindings=frozenset(),
        )


def test_resolver_refuses_a_declaration_that_contradicts_its_consuming_formula() -> None:
    """A contract and its consumer disagreeing is a defect, not a routing choice.

    With the declaration made authoritative, this cross-check is what keeps a
    wrong declaration loud: without it, a binding declared ``money`` but
    consumed by ``age_at_year_end`` would resolve quietly as a quantity and the
    failure would surface later as a missing date binding, pointing at the
    wrong thing.
    """
    snapshot = _snapshot()
    binding = _binding(snapshot, _ANUALIDADES_BINDING)
    assert binding is not None

    with pytest.raises(ProfileBindingResolutionError, match="consumed as a date operand"):
        resolve_profile_binding_channels(
            (binding,),
            {"renta_family.anualidades_sin_minimo_descendientes_2025": True},
            caller_binding_ids=frozenset(),
            formula_date_consumed=frozenset({_ANUALIDADES_BINDING}),
            enum_bindings=frozenset(),
        )


def test_every_declared_channel_agrees_with_its_consuming_formulas_registry_wide() -> None:
    """No binding on any served revision declares one channel and is consumed as another.

    The detector for the class of defect this change corrected. Two real
    declarations disagreed with their own use when the routing authority moved
    to the declaration -- a birth date declared ``text`` and an ISO country code
    declared ``money`` -- and both were corrected at the declaration. This
    refuses a third.
    """
    from ....domain.calculations.registry.runtime_graph import (
        enum_consumed_binding_ids,
        expression_date_binding_refs,
    )

    authority = bundled_authority()
    conflicts: list[str] = []
    for modelo in authority.modelos:
        for revision_id, revision in modelo.revisions.items():
            date_consumed: set[str] = set()
            for formula in revision.formulas:
                date_consumed |= set(expression_date_binding_refs(formula.expression))
            enum_consumed = set(enum_consumed_binding_ids(revision))
            for binding in revision.bindings:
                channel = binding.value.channel
                where = f"{modelo.id}/{revision_id} {binding.id}"
                if binding.id in date_consumed and channel is not BindingValueChannel.DATE:
                    conflicts.append(f"{where}: declares {channel.value}, consumed as date")
                if binding.id in enum_consumed and channel not in {
                    BindingValueChannel.ENUM,
                    BindingValueChannel.TEXT,
                }:
                    conflicts.append(f"{where}: declares {channel.value}, consumed as enum")

    assert not conflicts, "declared value channel contradicts consuming formula: " + "; ".join(sorted(set(conflicts)))
