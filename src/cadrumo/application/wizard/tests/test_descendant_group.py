"""Real-engine coverage for the descendant repeating group.

The descendant group is a substrate-only construct (the one-shot wizard
catalogue has no repeating-group primitive), so these tests drive the
pure flow engine over the production
:data:`~cadrumo.application.wizard.descendant_group.DESCENDANT_GROUP`
and count page: the count answer gates the instance pages, the instance
answers project through
:func:`~cadrumo.application.wizard.persistence.descendant_facts_from_answers`, and the
NIF page validates through the canonical identity authority. Expected
fact keys and values are the documented ``renta_family.descendiente.{n}.*``
shape, derived from the specification, never from running the projection
under test.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from ....core import DescendantRelacion
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.flows import (
    CheckpointAvailability,
    CopyRefKind,
    FlowMode,
    FlowWidgetKind,
)
from ....domain.deadlines.models import EntityType
from ...flows.definition import CopyRef, FlowChoice, FlowDefinition, FlowPage, FlowSection
from ...flows.engine import FlowState, answer, start_flow, visible_sequence
from ...flows.validators import resolve_cross_field_validator
from ..descendant_group import (
    _ALTA_POSTERIOR_INVALID_RANGE_LOCALE_KEY,
    _ENTRY_BEFORE_BIRTH_LOCALE_KEY,
    _ENTRY_IN_FUTURE_LOCALE_KEY,
    _GASTOS_BOTH_DECLARED_LOCALE_KEY,
    _GASTOS_INVALID_NEGATIVE_LOCALE_KEY,
    _GASTOS_MENSUALES_INVALID_LOCALE_KEY,
    _MESES_INVALID_RANGE_LOCALE_KEY,
    _RENTAS_INVALID_NEGATIVE_LOCALE_KEY,
    _RENTAS_NOT_A_VALID_AMOUNT_LOCALE_KEY,
    DESCENDANT_ENTRY_EVENT_VALIDATOR_ID,
    DESCENDANT_GROUP,
    DESCENDANT_GUARDERIA_SPEND_VALIDATOR_ID,
    DESCENDANTS_COUNT_PAGE,
    attach_descendant_group,
)
from ..persistence import descendant_facts_from_answers

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NIF_INVALID_KEY = "wizard.errors.invalid_tax_id"
_VALID_NIF = "00000000T"  # 00000000 mod 23 == 0 -> control letter T
_INVALID_NIF = "12345678A"  # correct control letter is Z, so A is malformed


class _ProbeAnswers(BaseModel):
    model_config = STRICT_FROZEN_CONFIG


def _ref(key: str) -> CopyRef:
    return CopyRef(kind=CopyRefKind.LOCALE_KEY, ref=key)


def _entity_type_page() -> FlowPage:
    return FlowPage(
        id="entity-type",
        widget=FlowWidgetKind.SELECT,
        prompt=_ref("wizard.setup.taxpayer-type.entity-type.prompt"),
        choices=(
            FlowChoice(value=EntityType.NATURAL_PERSON.value, label=_ref("probe.natural.label")),
            FlowChoice(value=EntityType.LEGAL_ENTITY.value, label=_ref("probe.legal.label")),
        ),
        required=False,
        answer_type=str,
    )


def _probe_definition() -> FlowDefinition:
    """A familia-only definition carrying the production count page and group.

    Constructed through the :class:`FlowDefinition` constructor so every
    model validator runs — proving the count-source wiring and the count
    page's ``entity-type`` gate resolve to earlier pages.
    """
    return FlowDefinition(
        id="descendant-probe",
        title=_ref("probe.title"),
        description=_ref("probe.description"),
        sections=(
            FlowSection(
                id="familia",
                title=_ref("probe.familia.title"),
                items=(_entity_type_page(), DESCENDANTS_COUNT_PAGE, DESCENDANT_GROUP),
            ),
        ),
        answers_model=_ProbeAnswers,
        checkpoint={
            FlowMode.CREATE: CheckpointAvailability.AVAILABLE,
            FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
        },
    )


def _visible_keys(definition: FlowDefinition, state: FlowState) -> set[str]:
    return {entry.key for entry in visible_sequence(definition, state)}


def test_count_two_projects_the_exact_documented_fact_shape() -> None:
    definition = _probe_definition()
    state = start_flow(definition, mode=FlowMode.CREATE)
    state = answer(definition, state, "entity-type", EntityType.NATURAL_PERSON.value)
    state = answer(definition, state, "descendientes-count", "3")

    # Instance 0: menor de tres years old in 2024, disabled, guardería spend.
    state = answer(definition, state, "descendientes#0.birth-date", "2023-05-10")
    state = answer(definition, state, "descendientes#0.discapacidad", "33")
    state = answer(definition, state, "descendientes#0.convivencia", "true")
    state = answer(definition, state, "descendientes#0.custodia-compartida", "false")
    state = answer(definition, state, "descendientes#0.meses-madre-trabajo", "1-6")
    state = answer(definition, state, "descendientes#0.alta-posterior-nacimiento-mes", "1")
    state = answer(definition, state, "descendientes#0.gastos-guarderia", "900")

    # Instance 1: older adopted child under shared custody, carrying a NIF.
    #
    # NOTE: the walk grows to a third instance below rather than moving the
    # monthly map onto one of these two. Instance 0 already declares an annual
    # figure and the two spend shapes are mutually exclusive, so reusing it
    # would have swapped one page's coverage for another's.
    state = answer(definition, state, "descendientes#1.birth-date", "2015-03-01")
    # The inscription page is GATED on this instance's relación, so the answer
    # has to precede it -- answering it first is not test convenience, it is the
    # gate being real: without it the engine refuses the target as not visible.
    state = answer(definition, state, "descendientes#1.relacion", DescendantRelacion.ADOPTADO.value)
    state = answer(definition, state, "descendientes#1.inscripcion-registro-civil", "2016-06-01")
    state = answer(definition, state, "descendientes#1.fallecimiento", "2024-06-15")
    state = answer(definition, state, "descendientes#1.convivencia", "true")
    state = answer(definition, state, "descendientes#1.custodia-compartida", "true")
    state = answer(definition, state, "descendientes#1.nif", _VALID_NIF)

    # Instance 2: the child who turns three in the period. The monthly map is
    # ANSWERED here, not merely reachable: three pages added earlier in this
    # campaign shipped visible and never given a value, so the walk proved only
    # that they rendered. What has to hold is that the answer lands as a fact.
    # The range form is used because it is the shape a taxpayer reads off a
    # certificate, and it is the half a parser could drop while still honouring
    # bare months.
    state = answer(definition, state, "descendientes#2.birth-date", "2021-04-15")
    state = answer(definition, state, "descendientes#2.convivencia", "true")
    state = answer(definition, state, "descendientes#2.custodia-compartida", "false")
    state = answer(definition, state, "descendientes#2.gastos-guarderia-mensuales", "5-8:210;1:180")

    for key in state.verdicts:
        assert not key.startswith("descendientes"), f"unexpected verdict on {key}: {state.verdicts[key]}"

    projected = dict(descendant_facts_from_answers(state.answers))

    expected = {
        "renta_family.descendiente.0.birth_date": "2023-05-10",
        "renta_family.descendiente.0.discapacidad": "33",
        "renta_family.descendiente.0.convivencia": "true",
        "renta_family.descendiente.0.meses_madre_trabajo": "01;02;03;04;05;06",
        "renta_family.descendiente.0.alta_posterior_nacimiento_mes": "1",
        "renta_family.descendiente.0.gastos_guarderia": "900",
        "renta_family.descendiente.1.birth_date": "2015-03-01",
        "renta_family.descendiente.1.relacion": "adoptado",
        "renta_family.descendiente.1.inscripcion_registro_civil": "2016-06-01",
        "renta_family.descendiente.1.fallecimiento": "2024-06-15",
        "renta_family.descendiente.1.convivencia": "true",
        "renta_family.descendiente.1.custodia_compartida": "true",
        "renta_family.descendiente.1.nif": _VALID_NIF,
        "renta_family.descendiente.2.birth_date": "2021-04-15",
        "renta_family.descendiente.2.convivencia": "true",
        # Stored in the canonical expanded form regardless of the range typed
        # above, so the same map entered two ways is one set of stored bytes.
        "renta_family.descendiente.2.gastos_guarderia_mensuales": "01:180;05:210;06:210;07:210;08:210",
        "renta_family.descendientes_count": "3",
    }
    # The Art. 81 bis sum is deliberately absent. It is derived at calculate
    # time from the per-child figure above, and the write door refuses it, so
    # projecting it here would refuse this whole batch.
    assert projected == expected


def test_the_monthly_guarderia_page_commits_a_range_and_refuses_a_bad_map() -> None:
    """The flattened month map is a real answer channel, not a rendered page.

    One page carries the WHOLE map because a per-month sub-question inside the
    per-descendant group is a nested repetition the substrate has no primitive
    for. The grammar validator is what carries the structure the widget cannot,
    so it is the thing that has to hold.
    """
    definition = _probe_definition()
    state = _one_descendant_state(definition)

    committed = answer(definition, state, "descendientes#0.gastos-guarderia-mensuales", "9-12:210;1:180")
    assert committed.answers["descendientes#0.gastos-guarderia-mensuales"] == "9-12:210;1:180"
    assert "descendientes#0.gastos-guarderia-mensuales" not in committed.verdicts

    rejected = answer(definition, state, "descendientes#0.gastos-guarderia-mensuales", "13:210")
    assert [v.message_key for v in rejected.verdicts["descendientes#0.gastos-guarderia-mensuales"]] == [
        _GASTOS_MENSUALES_INVALID_LOCALE_KEY
    ]
    assert "descendientes#0.gastos-guarderia-mensuales" not in rejected.answers


def test_the_wizard_grammar_is_the_domain_grammar() -> None:
    """A shape one door accepts is a shape every door accepts.

    The page-local alternative would be a second reader, and this exact surface
    has already shipped the failure that produces: a value one door honoured and
    another silently treated differently. Driving the wizard's own verdict from
    shapes the domain parser decides keeps them one rule rather than two that
    agree today.
    """
    from ....core.errors.hierarchy import ProfileAnswerTypeError
    from ....domain.contribuyente.guarderia_mensual import parse_guarderia_mensual

    definition = _probe_definition()
    state = _one_descendant_state(definition)
    key = "descendientes#0.gastos-guarderia-mensuales"

    for candidate in ("1:100", "9-12:210;1:180", "12:0", "13:100", "12-9:100", "1:100;1:200", "nonsense"):
        try:
            parse_guarderia_mensual(candidate, field="probe")
        except ProfileAnswerTypeError:
            domain_accepts = False
        else:
            domain_accepts = True
        wizard_accepts = key in answer(definition, state, key, candidate).answers
        assert wizard_accepts is domain_accepts, f"{candidate!r}: wizard and domain disagree"


def test_declaring_both_spend_shapes_blocks_submit_and_names_the_annual_page() -> None:
    """The record's one-authority-per-child rule, held before the persist path.

    A per-answer validator cannot see this: the annual figure is only wrong in
    the presence of a map on a sibling page. Left to the record it would raise
    from inside persist, which reads as a crash rather than a correction.

    The verdict points at the ANNUAL page because the monthly map is the
    authority where it exists — it is the only shape that can express the period
    the child turns three, so the annual figure is the one to drop.
    """
    definition = _probe_definition()
    state = _one_descendant_state(definition)
    state = answer(definition, state, "descendientes#0.gastos-guarderia", "900")
    state = answer(definition, state, "descendientes#0.gastos-guarderia-mensuales", "1:100")

    validator = resolve_cross_field_validator(DESCENDANT_GUARDERIA_SPEND_VALIDATOR_ID)
    verdicts = validator(state.answers)

    assert [v.message_key for v in verdicts] == [_GASTOS_BOTH_DECLARED_LOCALE_KEY]
    assert all(v.context.get("page") == "gastos-guarderia" for v in verdicts)


def test_a_zero_annual_answer_does_not_collide_with_a_monthly_map() -> None:
    """Zero states no annual spend, so it contradicts nothing.

    Refusing it would block an operator who typed ``0`` on the annual page
    before reaching the monthly one — a walk order the flow permits.
    """
    definition = _probe_definition()
    state = _one_descendant_state(definition)
    state = answer(definition, state, "descendientes#0.gastos-guarderia", "0")
    state = answer(definition, state, "descendientes#0.gastos-guarderia-mensuales", "1:100")

    validator = resolve_cross_field_validator(DESCENDANT_GUARDERIA_SPEND_VALIDATOR_ID)

    assert all(v.passed for v in validator(state.answers))


def test_the_guarderia_spend_validator_is_named_on_the_attached_definition() -> None:
    """A registered validator nothing names is a guard that never runs."""
    base = FlowDefinition(
        id="descendant-guarderia-splice",
        title=_ref("probe.title"),
        description=_ref("probe.description"),
        sections=(FlowSection(id="familia", title=_ref("probe.familia.title"), items=(_entity_type_page(),)),),
        answers_model=_ProbeAnswers,
        checkpoint={
            FlowMode.CREATE: CheckpointAvailability.AVAILABLE,
            FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
        },
    )

    attached = attach_descendant_group(base)

    assert DESCENDANT_GUARDERIA_SPEND_VALIDATOR_ID in attached.flow_validator_ids
    # Idempotent, like its sibling: re-applying must not duplicate either id.
    assert attach_descendant_group(attached).flow_validator_ids == attached.flow_validator_ids


def test_invalid_descendant_nif_refuses_and_valid_commits() -> None:
    definition = _probe_definition()
    state = start_flow(definition, mode=FlowMode.CREATE)
    state = answer(definition, state, "entity-type", EntityType.NATURAL_PERSON.value)
    state = answer(definition, state, "descendientes-count", "1")
    state = answer(definition, state, "descendientes#0.birth-date", "2020-01-01")

    rejected = answer(definition, state, "descendientes#0.nif", _INVALID_NIF)
    assert "descendientes#0.nif" in rejected.verdicts
    assert [v.message_key for v in rejected.verdicts["descendientes#0.nif"]] == [_NIF_INVALID_KEY]
    assert "descendientes#0.nif" not in rejected.answers

    committed = answer(definition, state, "descendientes#0.nif", _VALID_NIF)
    assert "descendientes#0.nif" not in committed.verdicts
    assert committed.answers["descendientes#0.nif"] == _VALID_NIF


def test_count_zero_hides_the_group_entirely() -> None:
    definition = _probe_definition()
    state = start_flow(definition, mode=FlowMode.CREATE)
    state = answer(definition, state, "entity-type", EntityType.NATURAL_PERSON.value)
    state = answer(definition, state, "descendientes-count", "0")

    visible = _visible_keys(definition, state)
    assert not any(key.startswith("descendientes#") for key in visible)
    # Zero descendants still emits the count aggregate, and nothing else.
    assert dict(descendant_facts_from_answers(state.answers)) == {"renta_family.descendientes_count": "0"}


def test_count_page_hidden_for_a_legal_entity() -> None:
    definition = _probe_definition()
    state = start_flow(definition, mode=FlowMode.CREATE)
    state = answer(definition, state, "entity-type", EntityType.LEGAL_ENTITY.value)

    visible = _visible_keys(definition, state)
    assert "descendientes-count" not in visible
    assert not any(key.startswith("descendientes#") for key in visible)


def test_descendant_free_answer_map_writes_no_descendant_fact() -> None:
    # The group was never reached: no count answer present, so the
    # projection contributes nothing (not even a zero count).
    assert descendant_facts_from_answers({"tax-id": _VALID_NIF}) == []


def test_attach_descendant_group_splices_count_then_group_into_familia() -> None:
    base = FlowDefinition(
        id="descendant-splice",
        title=_ref("probe.title"),
        description=_ref("probe.description"),
        sections=(FlowSection(id="familia", title=_ref("probe.familia.title"), items=(_entity_type_page(),)),),
        answers_model=_ProbeAnswers,
        checkpoint={
            FlowMode.CREATE: CheckpointAvailability.AVAILABLE,
            FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
        },
    )
    attached = attach_descendant_group(base)
    familia = next(section for section in attached.sections if section.id == "familia")
    assert familia.items[-2] is DESCENDANTS_COUNT_PAGE
    assert familia.items[-1] is DESCENDANT_GROUP


def _one_descendant_state(definition: FlowDefinition):
    state = start_flow(definition, mode=FlowMode.CREATE)
    state = answer(definition, state, "entity-type", EntityType.NATURAL_PERSON.value)
    state = answer(definition, state, "descendientes-count", "1")
    return answer(definition, state, "descendientes#0.birth-date", "2022-01-01")


def test_meses_out_of_range_refuses_as_a_verdict_and_valid_commits() -> None:
    definition = _probe_definition()
    state = _one_descendant_state(definition)

    rejected = answer(definition, state, "descendientes#0.meses-madre-trabajo", "15")
    assert [v.message_key for v in rejected.verdicts["descendientes#0.meses-madre-trabajo"]] == [
        _MESES_INVALID_RANGE_LOCALE_KEY
    ]
    assert "descendientes#0.meses-madre-trabajo" not in rejected.answers

    committed = answer(definition, state, "descendientes#0.meses-madre-trabajo", "1-6")
    assert committed.answers["descendientes#0.meses-madre-trabajo"] == "1-6"


def test_alta_posterior_month_refuses_out_of_range_and_commits_valid_month() -> None:
    definition = _probe_definition()
    state = _one_descendant_state(definition)

    rejected = answer(definition, state, "descendientes#0.alta-posterior-nacimiento-mes", "13")
    assert [v.message_key for v in rejected.verdicts["descendientes#0.alta-posterior-nacimiento-mes"]] == [
        _ALTA_POSTERIOR_INVALID_RANGE_LOCALE_KEY
    ]
    assert "descendientes#0.alta-posterior-nacimiento-mes" not in rejected.answers

    committed = answer(definition, state, "descendientes#0.alta-posterior-nacimiento-mes", "1")
    assert committed.answers["descendientes#0.alta-posterior-nacimiento-mes"] == "1"


def test_negative_gastos_refuses_as_a_verdict() -> None:
    definition = _probe_definition()
    state = _one_descendant_state(definition)

    rejected = answer(definition, state, "descendientes#0.gastos-guarderia", "-5")
    assert [v.message_key for v in rejected.verdicts["descendientes#0.gastos-guarderia"]] == [
        _GASTOS_INVALID_NEGATIVE_LOCALE_KEY
    ]
    assert "descendientes#0.gastos-guarderia" not in rejected.answers


def test_rentas_cents_figure_commits() -> None:
    """The rentas page accepts a two-decimal figure -- unlike gastos-guarderia.

    ``rentas_anuales_euros`` is genuinely ``Decimal`` on the domain model and
    Art. 58.1's ceiling comparison is strict (``>``), so a taxpayer must be
    able to enter a figure like ``8000.01`` precisely rather than round to a
    whole euro, which could silently flip mínimo eligibility either way.
    """
    definition = _probe_definition()
    state = _one_descendant_state(definition)

    committed = answer(definition, state, "descendientes#0.rentas-anuales", "8000.01")
    assert committed.answers["descendientes#0.rentas-anuales"] == "8000.01"


def test_rentas_over_precise_figure_refuses_as_a_verdict() -> None:
    """A third fraction digit refuses: it is genuinely ambiguous, not merely precise.

    A Spanish thousands grouping is always exactly three digits, so a figure
    at that precision cannot be told apart from a grouped whole-euro amount;
    the money-specific cap this validator applies (beyond the DECIMAL
    widget's own, uncapped grammar check) refuses it rather than guessing.
    """
    definition = _probe_definition()
    state = _one_descendant_state(definition)

    rejected = answer(definition, state, "descendientes#0.rentas-anuales", "8000.123")
    assert [v.message_key for v in rejected.verdicts["descendientes#0.rentas-anuales"]] == [
        _RENTAS_NOT_A_VALID_AMOUNT_LOCALE_KEY
    ]
    assert "descendientes#0.rentas-anuales" not in rejected.answers


def test_negative_rentas_refuses_as_a_verdict() -> None:
    definition = _probe_definition()
    state = _one_descendant_state(definition)

    rejected = answer(definition, state, "descendientes#0.rentas-anuales", "-1.50")
    assert [v.message_key for v in rejected.verdicts["descendientes#0.rentas-anuales"]] == [
        _RENTAS_INVALID_NEGATIVE_LOCALE_KEY
    ]
    assert "descendientes#0.rentas-anuales" not in rejected.answers


def test_adoption_before_birth_refuses_at_flow_scope() -> None:
    validator = resolve_cross_field_validator(DESCENDANT_ENTRY_EVENT_VALIDATOR_ID)
    verdicts = validator(
        {
            "descendientes#0.birth-date": "2020-05-10",
            "descendientes#0.inscripcion-registro-civil": "2010-01-01",
        },
    )
    assert [v.message_key for v in verdicts if not v.ok] == [_ENTRY_BEFORE_BIRTH_LOCALE_KEY]


def test_adoption_in_future_refuses_at_flow_scope() -> None:
    validator = resolve_cross_field_validator(DESCENDANT_ENTRY_EVENT_VALIDATOR_ID)
    verdicts = validator(
        {
            "descendientes#0.birth-date": "2020-05-10",
            "descendientes#0.inscripcion-registro-civil": "2999-01-01",
        },
    )
    assert [v.message_key for v in verdicts if not v.ok] == [_ENTRY_IN_FUTURE_LOCALE_KEY]


def test_valid_adoption_pair_passes_flow_scope() -> None:
    validator = resolve_cross_field_validator(DESCENDANT_ENTRY_EVENT_VALIDATOR_ID)
    verdicts = validator(
        {
            "descendientes#0.birth-date": "2015-03-01",
            "descendientes#0.inscripcion-registro-civil": "2016-06-01",
        },
    )
    assert all(v.ok for v in verdicts)


def test_attach_descendant_group_names_the_adoption_flow_validator() -> None:
    base = FlowDefinition(
        id="descendant-flowval",
        title=_ref("probe.title"),
        description=_ref("probe.description"),
        sections=(FlowSection(id="familia", title=_ref("probe.familia.title"), items=(_entity_type_page(),)),),
        answers_model=_ProbeAnswers,
        checkpoint={
            FlowMode.CREATE: CheckpointAvailability.AVAILABLE,
            FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
        },
    )
    attached = attach_descendant_group(base)
    assert attached.flow_validator_ids.count(DESCENDANT_ENTRY_EVENT_VALIDATOR_ID) == 1

    # Idempotent on the flow validator id: a definition already naming it is
    # not given a duplicate.
    pre_named = base.model_copy(update={"flow_validator_ids": (DESCENDANT_ENTRY_EVENT_VALIDATOR_ID,)})
    assert attach_descendant_group(pre_named).flow_validator_ids.count(DESCENDANT_ENTRY_EVENT_VALIDATOR_ID) == 1


def test_attach_descendant_group_refuses_without_a_familia_section() -> None:
    base = FlowDefinition(
        id="descendant-nofamilia",
        title=_ref("probe.title"),
        description=_ref("probe.description"),
        sections=(FlowSection(id="identidad", title=_ref("probe.id.title"), items=(_entity_type_page(),)),),
        answers_model=_ProbeAnswers,
        checkpoint={
            FlowMode.CREATE: CheckpointAvailability.AVAILABLE,
            FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
        },
    )
    with pytest.raises(ValueError, match="familia"):
        attach_descendant_group(base)
