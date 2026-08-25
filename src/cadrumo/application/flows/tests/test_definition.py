"""Build-time validator coverage for the flow definition family.

The strict frozen pydantic records reject a structurally invalid flow at
construction time, so every model-validator refusal below surfaces as a
pydantic ``ValidationError``. The tests drive each validator with an
input crafted to trip exactly that rule and assert the refusal by
exception type (structural), never by matching the developer-facing
prose. The fingerprint stability contract that ``resume`` relies on is
pinned last.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from ....core.flows import (
    DEFER_TOKEN,
    CheckpointAvailability,
    CopyRefKind,
    FlowMode,
    FlowWidgetKind,
)
from ....core.hashing import content_hash_hex
from .. import (
    CopyRef,
    FlowChoice,
    FlowCondition,
    FlowDefinition,
    FlowLegalRef,
    FlowPage,
    FlowRepeatingGroup,
    FlowSection,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_flow_page_legal_zone_defaults_empty() -> None:
    page = _page("p_a")

    assert page.legal_zone == ()


def test_flow_legal_ref_carries_structured_ref_and_optional_label() -> None:
    label = _copy("wizard.setup.title")
    with_label = FlowLegalRef(ref="ley-35-2006:art-27", label=label)
    without_label = FlowLegalRef(ref="ley-35-2006:art-28")

    assert with_label.ref == "ley-35-2006:art-27"
    assert with_label.label is label
    assert without_label.label is None


def test_flow_legal_ref_rejects_a_blank_ref() -> None:
    with pytest.raises(ValidationError):
        FlowLegalRef(ref="")


def test_flow_page_carries_a_structured_legal_zone() -> None:
    page = FlowPage(
        id="p_legal",
        widget=FlowWidgetKind.TEXT,
        prompt=_copy(),
        legal_zone=(FlowLegalRef(ref="ley-35-2006:art-27"),),
        answer_type=str,
    )

    assert page.legal_zone[0].ref == "ley-35-2006:art-27"


class _Answers(BaseModel):
    """Trivial answers model; the definition only needs the type identity."""


_FULL_CHECKPOINT: dict[FlowMode, CheckpointAvailability] = {
    FlowMode.CREATE: CheckpointAvailability.AVAILABLE,
    FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
}


def _copy(ref: str = "flows.test.copy") -> CopyRef:
    return CopyRef(kind=CopyRefKind.LOCALE_KEY, ref=ref)


def _page(
    page_id: str,
    *,
    widget: FlowWidgetKind = FlowWidgetKind.TEXT,
    answer_type: type[str] | type[bool] | type[int] | type[Path] = str,
    choices: tuple[FlowChoice, ...] = (),
    visible_when: object | None = None,
    required: bool = True,
) -> FlowPage:
    return FlowPage(
        id=page_id,
        widget=widget,
        prompt=_copy(),
        choices=choices,
        visible_when=visible_when,  # type: ignore[arg-type]
        required=required,
        answer_type=answer_type,
    )


def _section(section_id: str, items: tuple[FlowPage | FlowRepeatingGroup, ...]) -> FlowSection:
    return FlowSection(id=section_id, title=_copy(), items=items)  # type: ignore[arg-type]


def _definition(sections: tuple[FlowSection, ...]) -> FlowDefinition:
    return FlowDefinition(
        id="flows.test.flow",
        title=_copy(),
        description=_copy(),
        sections=sections,
        answers_model=_Answers,
        checkpoint=dict(_FULL_CHECKPOINT),
    )


def _choice(value: str, *, provenance: CopyRef | None = None) -> FlowChoice:
    return FlowChoice(value=value, label=_copy(), provenance=provenance)


def test_duplicate_page_ids_raise() -> None:
    with pytest.raises(ValidationError):
        _definition((_section("s1", (_page("dup"), _page("dup"))),))


def test_visible_when_naming_a_later_page_raises() -> None:
    # 'gate' references 'target', which is declared *after* it in walk order.
    gated = _page("gate", visible_when=FlowCondition(page_id="target", equals="x"))
    with pytest.raises(ValidationError):
        _definition((_section("s1", (gated, _page("target"))),))


def test_visible_when_naming_an_unknown_page_raises() -> None:
    gated = _page("gate", visible_when=FlowCondition(page_id="nowhere", equals="x"))
    with pytest.raises(ValidationError):
        _definition((_section("s1", (_page("first"), gated)),))


def test_flow_condition_with_zero_clauses_raises() -> None:
    with pytest.raises(ValidationError):
        FlowCondition(page_id="p")


def test_flow_condition_with_two_clauses_raises() -> None:
    with pytest.raises(ValidationError):
        FlowCondition(page_id="p", equals="a", contains="b")


def test_choice_widget_without_choices_raises() -> None:
    with pytest.raises(ValidationError):
        _page("pick", widget=FlowWidgetKind.SELECT, choices=())


def test_choices_on_a_non_choice_widget_raise() -> None:
    with pytest.raises(ValidationError):
        _page("free", widget=FlowWidgetKind.TEXT, choices=(_choice("a"),))


def test_compare_select_candidate_without_provenance_raises() -> None:
    with pytest.raises(ValidationError):
        _page(
            "cmp",
            widget=FlowWidgetKind.COMPARE_SELECT,
            choices=(_choice("a", provenance=None),),
        )


def test_flow_choice_with_reserved_defer_token_raises() -> None:
    with pytest.raises(ValidationError):
        FlowChoice(value=DEFER_TOKEN, label=_copy())


def test_repeating_group_count_from_non_integer_page_raises() -> None:
    # 'count' is a TEXT page, not an earlier INTEGER page.
    group = FlowRepeatingGroup(
        id="grp",
        title=_copy(),
        count_from="count",
        pages=(_page("g_item"),),
    )
    with pytest.raises(ValidationError):
        _definition((_section("s1", (_page("count", widget=FlowWidgetKind.TEXT), group)),))


def test_repeating_group_count_from_missing_page_raises() -> None:
    group = FlowRepeatingGroup(
        id="grp",
        title=_copy(),
        count_from="does_not_exist",
        pages=(_page("g_item"),),
    )
    with pytest.raises(ValidationError):
        _definition((_section("s1", (_page("first"), group)),))


def test_repeating_group_with_earlier_integer_count_source_builds() -> None:
    group = FlowRepeatingGroup(
        id="grp",
        title=_copy(),
        count_from="count",
        pages=(_page("g_item"),),
    )
    definition = _definition(
        (_section("s1", (_page("count", widget=FlowWidgetKind.INTEGER, answer_type=int), group)),),
    )
    assert definition.sections[0].items[1] is group


def test_checkpoint_missing_a_mode_raises() -> None:
    with pytest.raises(ValidationError):
        FlowDefinition(
            id="flows.test.flow",
            title=_copy(),
            description=_copy(),
            sections=(_section("s1", (_page("only"),)),),
            answers_model=_Answers,
            checkpoint={FlowMode.CREATE: CheckpointAvailability.AVAILABLE},
        )


def test_fingerprint_is_stable_across_identical_builds() -> None:
    build = lambda: _definition(  # noqa: E731 - inline builder keeps the two builds byte-identical
        (
            _section(
                "s1",
                (
                    _page("name"),
                    _page("home", widget=FlowWidgetKind.PATH, answer_type=Path),
                ),
            ),
        ),
    )
    assert build().fingerprint == build().fingerprint


def test_fingerprint_changes_when_a_page_is_added() -> None:
    base = _definition((_section("s1", (_page("name"),)),))
    grown = _definition((_section("s1", (_page("name"), _page("extra"))),))
    assert base.fingerprint != grown.fingerprint


def test_fingerprint_has_core_content_hash_parity_after_type_normalisation() -> None:
    definition = FlowDefinition(
        id="flows.test.flow",
        title=_copy("flows.test.ñ.title"),
        description=_copy("flows.test.ñ.description"),
        sections=(_section("s1", (_page("nombre"),)),),
        answers_model=_Answers,
        checkpoint=dict(_FULL_CHECKPOINT),
    )
    payload = definition.model_dump(mode="python", exclude={"answers_model"})
    payload["answers_model"] = f"{definition.answers_model.__module__}.{definition.answers_model.__qualname__}"
    payload["sections"][0]["items"][0]["answer_type"] = "builtins.str"

    assert definition.fingerprint == content_hash_hex(payload)
