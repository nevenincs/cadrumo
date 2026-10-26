"""The caller context a calculation revision was computed from, owned in one place.

A revision records more than values the sources produced. The operator's own
inputs (its operator layer and explicit clears), the detail rows, the Modelo
303 filing-instance evidence, the Modelo 210 selections and the borrador
snapshot were all supplied by the caller of the calculation, and the next
calculation of the same declaration must receive them again or it silently
discards them. Edit execution and the workspace recalculation both read that
context from here, so the two can never replay different lists.

The merged ``input_values_by_casilla_id`` and ``binding_overrides`` maps are
deliberately NOT part of it: they fold every source tier together, and
replaying them would freeze ledger, profile and borrador values as operator
overrides that outrank every later source.

See Also:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
        The stored calculation head carrying values, provenance and lifecycle facts.
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`
        The registry declaration supplying casillas, formulas, bindings and layout metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ...core.casilla_id import CasillaId
from ...core.irnr import M210GrossIncomeSourceMode
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.calculation_revision_m303_handoff import FilingInstanceEvidence
from ...domain.modelos.calculation_revision_operator_layer import CalculationOperatorLayer
from ...domain.modelos.row_models import ModeloDetailRow
from .calculate_input import resolve_binding_overrides


@dataclass(frozen=True, slots=True)
class CalculationCallerContext:
    """Every caller-supplied, non-source input one revision was calculated from.

    ``operator_layer`` is ``None`` when the revision was stored before operator
    layers existed: the operator's values are then UNKNOWN, and a consumer must
    say so rather than treat them as absent. A work unit with no calculation
    yet has a known, empty layer -- nobody has typed anything.
    """

    operator_layer: CalculationOperatorLayer | None
    cleared_casilla_ids: tuple[CasillaId, ...]
    detail_rows: tuple[ModeloDetailRow, ...]
    filing_instance_evidence: FilingInstanceEvidence | None
    m210_official_tipo_renta_code: str | None
    m210_gross_income_source_mode: M210GrossIncomeSourceMode | None
    borrador_snapshot_id: str | None

    @property
    def operator_layer_known(self) -> bool:
        """Whether the operator's own values are recorded for this context."""
        return self.operator_layer is not None

    @property
    def known_operator_layer(self) -> CalculationOperatorLayer:
        """The recorded layer, or an empty one when it is unknown.

        Only for a consumer that has already surfaced the unknown state (see
        :attr:`operator_layer_known`); it must never be used to decide that an
        unknown layer held nothing.
        """
        return self.operator_layer if self.operator_layer is not None else CalculationOperatorLayer()


def caller_context_of(revision: CalculationRevision | None) -> CalculationCallerContext:
    """Return the caller context of ``revision``, or of a work unit not yet calculated.

    ``None`` stands for a work unit with no current calculation: its caller
    context is empty and its operator layer is known to be empty.

    See Also:
        :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
            The stored calculation head carrying values, provenance and lifecycle facts.
    """
    if revision is None:
        return CalculationCallerContext(
            operator_layer=CalculationOperatorLayer(),
            cleared_casilla_ids=(),
            detail_rows=(),
            filing_instance_evidence=None,
            m210_official_tipo_renta_code=None,
            m210_gross_income_source_mode=None,
            borrador_snapshot_id=None,
        )
    return CalculationCallerContext(
        operator_layer=revision.operator_layer,
        cleared_casilla_ids=revision.cleared_casilla_ids,
        detail_rows=revision.detail_rows,
        filing_instance_evidence=revision.filing_instance_evidence,
        m210_official_tipo_renta_code=revision.m210_official_tipo_renta_code,
        m210_gross_income_source_mode=revision.m210_gross_income_source_mode,
        borrador_snapshot_id=revision.borrador_snapshot_id,
    )


@dataclass(frozen=True, slots=True)
class CallerContextCalculationInputs:
    """A caller context projected onto the calculation boundary's own input channels.

    Every field maps one-to-one onto a keyword of
    :func:`~cadrumo.application.modelo.calculation_actions.calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`;
    a replaying caller passes each of them and sets ``record_operator_layer``,
    so the revision it produces records the same operator layer it replayed.
    """

    casilla_inputs: dict[CasillaId, Decimal]
    text_casilla_inputs: dict[CasillaId, str]
    cleared_casilla_ids: tuple[CasillaId, ...]
    binding_values: dict[BindingId, Decimal]
    enum_binding_values: dict[BindingId, str]
    detail_rows: tuple[ModeloDetailRow, ...]
    filing_instance_evidence: FilingInstanceEvidence | None
    m210_official_tipo_renta_code: str | None
    m210_gross_income_source_mode: M210GrossIncomeSourceMode | None
    borrador_snapshot_id: str | None


def caller_context_calculation_inputs(
    context: CalculationCallerContext,
    *,
    revision: ModeloRevision,
) -> CallerContextCalculationInputs:
    """Project ``context`` onto the calculation channels ``revision`` declares.

    Binding overrides are routed by the binding's declared channel through the
    same resolver the explicit ``--binding`` path uses, so a replayed override
    reaches the engine exactly as it did when the operator entered it. A
    binding the revision no longer declares refuses there rather than being
    dropped. An unknown operator layer replays no values: nothing is guessed.

    See Also:
        :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`
            The registry declaration supplying casillas, formulas, bindings and layout metadata.
    """
    layer = context.known_operator_layer
    binding_values, enum_binding_values = resolve_binding_overrides(layer.binding_overrides, revision)
    return CallerContextCalculationInputs(
        casilla_inputs={casilla_id: Decimal(raw) for casilla_id, raw in layer.decimal_casilla_inputs.items()},
        text_casilla_inputs=dict(layer.text_casilla_inputs),
        cleared_casilla_ids=context.cleared_casilla_ids,
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        detail_rows=context.detail_rows,
        filing_instance_evidence=context.filing_instance_evidence,
        m210_official_tipo_renta_code=context.m210_official_tipo_renta_code,
        m210_gross_income_source_mode=context.m210_gross_income_source_mode,
        borrador_snapshot_id=context.borrador_snapshot_id,
    )


__all__ = [
    "CalculationCallerContext",
    "CallerContextCalculationInputs",
    "caller_context_calculation_inputs",
    "caller_context_of",
]
