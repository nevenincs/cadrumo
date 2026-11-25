"""Builders for flow copy references, pages and choices."""

from __future__ import annotations

from pathlib import Path

from ....core.flows import CopyRefKind, FlowWidgetKind
from ..definition import CopyRef, FlowChoice, FlowCondition, FlowPage


def copy_ref(ref: str = "wizard.setup.title") -> CopyRef:
    # A real bundled locale key so the render-time copy assembler resolves.
    return CopyRef(kind=CopyRefKind.LOCALE_KEY, ref=ref)


def flow_page(
    page_id: str,
    *,
    widget: FlowWidgetKind = FlowWidgetKind.TEXT,
    answer_type: type[str] | type[bool] | type[int] | type[Path] = str,
    choices: tuple[FlowChoice, ...] = (),
    visible_when: FlowCondition | None = None,
    required: bool = True,
) -> FlowPage:
    return FlowPage(
        id=page_id,
        widget=widget,
        prompt=copy_ref(),
        choices=choices,
        visible_when=visible_when,
        required=required,
        answer_type=answer_type,
    )


def flow_choice(value: str, *, provenance: CopyRef | None = None) -> FlowChoice:
    return FlowChoice(value=value, label=copy_ref(), provenance=provenance)
