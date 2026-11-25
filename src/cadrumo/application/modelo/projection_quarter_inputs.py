"""What a calculated quarterly declaration still lacks, named from the form it serves.

A quarter can be calculated and still be unable to give a box the annual
estimate reads, because values behind some of its boxes were never given. The
quarter's own work form already states which boxes could not be worked out and
which values they read, so the estimate's refusal names those boxes from that
form, in the language of the refusal's words, and never repeats a figure.

A box counts as open when the form asks the filer for it, or when the
calculation could not produce it and it reads a value that no field of the form
holds: a value that is missing at its source, not a box that failed only
because another did.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from .work_form_field_vocabulary import (
    ModeloFormOrigin,
    address_key,
)
from .work_form_next_step import applicable_fields
from .work_form_service import load_modelo_work_form

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.modelos.work_unit import WorkUnit
    from .calculation_action_ports import CalculationActionPorts
    from .work_form_models import ModeloFormField

_INPUT_LOCALE_KEY = "application.modelo.projection_words.quarter_input"
_INPUT_SEPARATOR = ", "


def _reads_a_value_no_field_holds(field: ModeloFormField, held: frozenset[str]) -> bool:
    return any(operand not in held for operand in field.formula_operands)


def _open_fields(fields: tuple[ModeloFormField, ...]) -> tuple[ModeloFormField, ...]:
    """The fields that name what is missing: asked of the filer, or failed on a value nothing holds."""
    held = frozenset(address_key(field.address)[1] for field in fields)
    return tuple(
        field
        for field in fields
        if field.origin is ModeloFormOrigin.NEEDS_INPUT
        or (field.origin is ModeloFormOrigin.CALCULATION_FAILED and _reads_a_value_no_field_holds(field, held))
    )


def quarter_open_inputs(
    unit: WorkUnit,
    *,
    ports: CalculationActionPorts,
    operation: PinnedAuthorityOperation,
    language: OutputLanguage,
) -> str:
    """The boxes ``unit``'s own form says are still open, named in ``language`` and joined for one sentence.

    The text is empty when the form names none. Each box is named by its label
    and its printed number, never by a value.
    """
    loaded = load_modelo_work_form(
        unit.bucket_id,
        unit.modelo,
        unit.filing_year,
        unit.period,
        operation=operation,
        work_unit_repository=ports.work_unit_repository,
        calculation_repository=ports.calculation_repository,
        verification_repository=ports.verification_repository,
        admission=None,
        language=language,
        borrador_snapshots=ports.borrador_snapshot_repository,
        bucket_events=ports.bucket_event_repository,
        activity_assets=ports.activity_asset_history_repository,
        credit_resolutions=ports.credit_resolution_reader,
    )
    named: dict[tuple[str, str], str] = {}
    for field in _open_fields(applicable_fields(loaded.form)):
        label = field.label.text
        named.setdefault(
            address_key(field.address),
            label if field.box is None else tr(_INPUT_LOCALE_KEY, label=label, box=field.box, locale=language.value),
        )
    return _INPUT_SEPARATOR.join(named.values())


__all__ = ["quarter_open_inputs"]
