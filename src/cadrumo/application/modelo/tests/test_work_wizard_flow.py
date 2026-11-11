"""Copy lifetime and flow structure for supplied Modelo wizard steps."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....core.flows import CheckpointAvailability, FlowMode, FlowWidgetKind
from ....core.period import Period
from ....domain.modelos.work_unit import WorkUnit, WorkUnitState, derive_work_unit_id
from ...flows.copy import resolve_copy
from ...flows.definition import FlowDefinition, FlowPage
from ...flows.engine import FlowState
from ...flows.errors import FlowCopyResolutionError
from .. import work_wizard
from ..work_wizard import ModeloWorkWizardStep, open_modelo_work_wizard_from_steps

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _unit() -> WorkUnit:
    period = Period.from_year_and_code(2026, "1T")
    instant = datetime(2026, 3, 10, 12, tzinfo=UTC)
    bucket_id = "5aa00000-0000-4000-8000-0000000000aa"
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id, modelo="303", filing_year=2026, period=period, revision_id="2026-y-siguientes"
        ),
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id="2026-y-siguientes",
        name="First-quarter return",
        created_at=instant,
        updated_at=instant,
        state=WorkUnitState.BORRADOR,
    )


def _step(label: str = "First input") -> ModeloWorkWizardStep:
    return ModeloWorkWizardStep(
        channel="binding",
        key="synthetic.binding",
        casilla_id="synthetic.binding",
        number="Synthetic binding",
        label=label,
        help_text="Binding help",
        legal_refs=("synthetic-legal-ref",),
        source_refs=("synthetic-source-ref",),
    )


def _only_page(definition: FlowDefinition) -> FlowPage:
    assert len(definition.sections) == 1
    assert len(definition.sections[0].items) == 1
    page = definition.sections[0].items[0]
    assert isinstance(page, FlowPage)
    return page


def test_supplied_steps_keep_existing_flow_structure_and_answers_without_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unit = _unit()
    step = _step()

    def refuse_discovery(*_args: object, **_kwargs: object) -> tuple[ModeloWorkWizardStep, ...]:
        raise AssertionError("supplied steps must not rediscover private profile inputs")

    monkeypatch.setattr(work_wizard, "discover_modelo_work_wizard_steps", refuse_discovery)
    with open_modelo_work_wizard_from_steps(unit, steps=(step,)) as wizard:
        definition = wizard.definition_for()
        assert wizard.unit is unit
        assert wizard.steps == (step,)
        assert definition.id == "modelo-work-wizard"
        assert definition.checkpoint[FlowMode.CREATE] is CheckpointAvailability.UNAVAILABLE
        assert definition.checkpoint[FlowMode.MODIFY] is CheckpointAvailability.UNAVAILABLE
        assert len(definition.sections) == 1
        section = definition.sections[0]
        assert section.id == "manual-inputs"
        page = _only_page(definition)
        assert page.id == "binding:synthetic.binding"
        assert page.widget is FlowWidgetKind.TEXT
        assert page.required is False
        assert resolve_copy(page.prompt)
        assert page.help is not None
        assert resolve_copy(page.help) == "Binding help"
        state = FlowState(
            flow_id=definition.id,
            mode=FlowMode.CREATE,
            answers={"binding:synthetic.binding": "  42  "},
        )
        assert wizard.answer_pairs(state) == ((step, "42"),)


def test_independent_copy_tables_close_on_normal_and_exception_exit() -> None:
    unit = _unit()
    with open_modelo_work_wizard_from_steps(unit, steps=(_step("Outer"),)) as outer:
        outer_page = _only_page(outer.definition_for())
        outer_prompt = outer_page.prompt
        outer_copy = resolve_copy(outer_prompt)
        with open_modelo_work_wizard_from_steps(unit, steps=(_step("Inner"),)) as inner:
            inner_prompt = _only_page(inner.definition_for()).prompt
            assert inner_prompt.ref != outer_prompt.ref
            assert resolve_copy(inner_prompt) != outer_copy
            assert resolve_copy(outer_prompt) == outer_copy
        with pytest.raises(FlowCopyResolutionError):
            resolve_copy(inner_prompt)
        assert resolve_copy(outer_prompt) == outer_copy
    with pytest.raises(FlowCopyResolutionError):
        resolve_copy(outer_prompt)

    exception_prompt = outer_prompt
    with (
        pytest.raises(RuntimeError, match="abort"),
        open_modelo_work_wizard_from_steps(unit, steps=(_step(),)) as aborted,
    ):
        exception_prompt = _only_page(aborted.definition_for()).prompt
        assert resolve_copy(exception_prompt)
        raise RuntimeError("abort")
    with pytest.raises(FlowCopyResolutionError):
        resolve_copy(exception_prompt)
