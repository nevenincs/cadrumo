"""Real-engine coverage for the descendant repeating group.

The descendant group is a substrate-only construct (the one-shot wizard
catalogue has no repeating-group primitive), so these tests drive the
pure flow engine over the production
:data:`~cadrumo.application.wizard._descendant_group.DESCENDANT_GROUP`
and count page: the count answer gates the instance pages, the instance
answers project through
:func:`~cadrumo.application.wizard.descendant_facts_from_answers`, and the
NIF page validates through the canonical identity authority. Expected
fact keys and values are the documented ``renta_family.descendiente.{n}.*``
shape, derived from the specification, never from running the projection
under test.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from ....core import STRICT_FROZEN_CONFIG
from ....core.flows import (
    CheckpointAvailability,
    CopyRefKind,
    FlowMode,
    FlowWidgetKind,
)
from ....domain.deadlines import EntityType
from ...flows import (
    CopyRef,
    FlowChoice,
    FlowDefinition,
    FlowPage,
    FlowSection,
    answer,
    start_flow,
    visible_sequence,
)
from .. import attach_descendant_group, descendant_facts_from_answers
from .._descendant_group import DESCENDANT_GROUP, DESCENDANTS_COUNT_PAGE

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


def _visible_keys(definition: FlowDefinition, state) -> set[str]:
    return {entry.key for entry in visible_sequence(definition, state)}


def test_count_two_projects_the_exact_documented_fact_shape() -> None:
    definition = _probe_definition()
    state = start_flow(definition, mode=FlowMode.CREATE)
    state = answer(definition, state, "entity-type", EntityType.NATURAL_PERSON.value)
    state = answer(definition, state, "descendientes-count", "2")

    # Instance 0: menor de tres years old in 2024, disabled, guardería spend.
    state = answer(definition, state, "descendientes#0.birth-date", "2023-05-10")
    state = answer(definition, state, "descendientes#0.discapacidad", "33")
    state = answer(definition, state, "descendientes#0.convivencia", "true")
    state = answer(definition, state, "descendientes#0.custodia-compartida", "false")
    state = answer(definition, state, "descendientes#0.meses-madre-trabajo", "6")
    state = answer(definition, state, "descendientes#0.gastos-guarderia", "900")

    # Instance 1: older adopted child under shared custody, carrying a NIF.
    state = answer(definition, state, "descendientes#1.birth-date", "2015-03-01")
    state = answer(definition, state, "descendientes#1.adoption-date", "2016-06-01")
    state = answer(definition, state, "descendientes#1.convivencia", "true")
    state = answer(definition, state, "descendientes#1.custodia-compartida", "true")
    state = answer(definition, state, "descendientes#1.nif", _VALID_NIF)

    for key in state.verdicts:
        assert not key.startswith("descendientes"), f"unexpected verdict on {key}: {state.verdicts[key]}"

    projected = dict(descendant_facts_from_answers(state.answers))

    expected = {
        "renta_family.descendiente.0.birth_date": "2023-05-10",
        "renta_family.descendiente.0.discapacidad": "33",
        "renta_family.descendiente.0.convivencia": "true",
        "renta_family.descendiente.0.meses_madre_trabajo": "6",
        "renta_family.descendiente.0.gastos_guarderia": "900",
        "renta_family.descendiente.1.birth_date": "2015-03-01",
        "renta_family.descendiente.1.adoption_date": "2016-06-01",
        "renta_family.descendiente.1.convivencia": "true",
        "renta_family.descendiente.1.custodia_compartida": "true",
        "renta_family.descendiente.1.nif": _VALID_NIF,
        "renta_family.descendientes_count": "2",
        "renta_family.gastos_guarderia_reales_2024": "900",
    }
    assert projected == expected


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
