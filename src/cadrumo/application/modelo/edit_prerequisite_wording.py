"""What a refused Apply's retained prerequisite says: the source a value it keeps waits on, and where to fix it.

An Apply that keeps a value whose source cannot be worked out is refused, and
the worker retains which box it was for the frontend session that asked. Every
frontend says that prerequisite in the same words, chosen here: the earlier
declaration the value is carried from when the form names one, else what the
source is, whether the form can tell the filer's own entries apart, and which
boxes of the earlier filing the source reads.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from ...core.casilla_id import CasillaId
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from .work_form_models import ModeloFormCasillaAddressV1, ModeloFormField, ModeloWorkForm
from .work_form_service import load_modelo_work_form
from .work_form_source_groups import earlier_filing_text

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from .workbench_read import ModeloWorkbenchReadPorts


def prerequisite_words(
    field: ModeloFormField,
    *,
    operator_entries_known: bool,
    source_boxes: Sequence[CasillaId],
    language: OutputLanguage,
) -> str:
    """Say the prerequisite of the box ``field`` shows, one sentence per line, in ``language``.

    The value is carried from the earlier declarations its source names, when
    it names any; a form that cannot tell the filer's own entries from the
    calculation's says so, since the kept value may be either.
    """
    locale = language.value
    source = field.source
    filings = () if source is None else source.earlier_filings
    key = "workspace.modelo.apply_prerequisite.earlier" if filings else "workspace.modelo.apply_prerequisite.what"
    lines = [tr(key, locale=locale)]
    if not operator_entries_known:
        lines.append(tr("workspace.modelo.apply_prerequisite.legacy", locale=locale))
    if filings:
        lines.append(earlier_filing_text(filings, language))
    if source_boxes:
        boxes = ", ".join(f"[{box}]" for box in source_boxes)
        lines.append(tr("workspace.modelo.apply_prerequisite.source_boxes", boxes=boxes, locale=locale))
    return "\n".join(lines)


def form_prerequisite_words(
    form: ModeloWorkForm, casilla_id: CasillaId, source_boxes: Sequence[CasillaId], language: OutputLanguage
) -> str | None:
    """Say the prerequisite of the box ``casilla_id`` on ``form``; ``None`` when the form no longer shows it."""
    field = next(
        (
            item
            for item in form.fields()
            if isinstance(item.address, ModeloFormCasillaAddressV1) and item.address.casilla_id == casilla_id
        ),
        None,
    )
    if field is None:
        return None
    return prerequisite_words(
        field, operator_entries_known=form.operator_entries_known, source_boxes=source_boxes, language=language
    )


def read_prerequisite_words(
    work_unit_id: str,
    casilla_id: CasillaId,
    source_boxes: Sequence[CasillaId],
    *,
    bucket_id: str,
    ports: ModeloWorkbenchReadPorts,
    operation: PinnedAuthorityOperation,
    language: OutputLanguage,
) -> str | None:
    """Read the declaration's form as it now stands and say the prerequisite of one of its boxes.

    ``None`` when the declaration is not this profile's or no longer shows the
    box; no edit baseline is admitted by this read.
    """
    unit = ports.work_units.load().get(work_unit_id)
    if unit is None or unit.bucket_id != bucket_id:
        return None
    loaded = load_modelo_work_form(
        bucket_id,
        unit.modelo,
        unit.filing_year,
        unit.period,
        operation=operation,
        work_unit_repository=ports.work_units,
        calculation_repository=ports.calculations,
        verification_repository=ports.verifications,
        admission=None,
        language=language,
    )
    return form_prerequisite_words(loaded.form, casilla_id, source_boxes, language)


__all__ = ["form_prerequisite_words", "prerequisite_words", "read_prerequisite_words"]
