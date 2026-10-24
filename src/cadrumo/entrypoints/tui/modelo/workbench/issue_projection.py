"""Place the application's check-view lines on the workbench's issue scale."""

from __future__ import annotations

from .....application.modelo.work_form_issue_lines import ModeloFormIssueLine, form_issue_lines
from .....application.modelo.work_form_models import ModeloWorkForm, address_key
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import output_language
from .issue_scale import IssueLine, attention_level
from .sources import surface_target

_NO_BOX: str = "·"


def _issue_line(line: ModeloFormIssueLine) -> IssueLine:
    surface = line.surface
    return IssueLine(
        level=attention_level(line.level),
        box=line.box or _NO_BOX,
        where=line.where,
        message=line.message,
        action=line.action,
        detail=line.detail or "",
        technical=line.technical,
        key=None if line.address is None else address_key(line.address),
        in_records=line.in_records,
        area=surface if surface is not None and surface_target(surface) is not None else None,
        from_calculation=line.from_calculation,
        recalculates=line.recalculates,
    )


def issue_lines(form: ModeloWorkForm) -> tuple[IssueLine, ...]:
    """The form's findings and calculation notes, most urgent first, in the filer's language."""
    return tuple(_issue_line(line) for line in form_issue_lines(form, OutputLanguage(output_language())))


__all__ = ("issue_lines",)
