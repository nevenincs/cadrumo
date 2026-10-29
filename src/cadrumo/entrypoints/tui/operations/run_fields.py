"""Construct request field labels and input controls."""

from __future__ import annotations

from textual.widgets import Input, Select, Static, TextArea

from ....core.i18n.render import tr
from .request_form import RequestFieldKind, RequestFieldV1
from .run_wording import kind_hint


def field_label(field: RequestFieldV1) -> str:
    """Label a request field and its admitted status."""
    heading = field.name
    if field.required:
        heading = f"{heading} ({tr('tui.operations.form.required')})"
    if field.session_fixed:
        heading = f"{heading} ({tr('tui.operations.form.fixed')})"
    return heading if not field.description else f"{heading}\n{field.description}"


def field_widget(index: int, field: RequestFieldV1) -> Static | Select[str] | TextArea | Input:
    """Build the control suited to a request field."""
    widget_id = f"operation-field-{index}"
    if field.session_fixed:
        return Static(field.initial, id=widget_id, markup=False)
    if field.kind in {RequestFieldKind.BOOLEAN, RequestFieldKind.ENUM}:
        labels = ("true", "false") if field.kind is RequestFieldKind.BOOLEAN else field.choice_labels
        return Select[str](
            [(label, label) for label in labels],
            prompt=tr("tui.operations.form.choose"),
            value=field.initial if field.initial in labels else Select.NULL,
            id=widget_id,
        )
    if field.kind is RequestFieldKind.JSON:
        return TextArea(field.initial, id=widget_id, classes="operation-json")
    return Input(value=field.initial, placeholder=kind_hint(field.kind), id=widget_id)
