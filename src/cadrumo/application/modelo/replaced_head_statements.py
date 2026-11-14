"""The statements a replaced calculation head recorded that the new calculation did not carry.

A calculation that carries its own inputs stands in the new head in place of
whatever the person had entered in the earlier one. Values typed into boxes,
input overrides, statements about earlier filings, explicit clears and the
other caller-supplied inputs of that earlier head are then absent from the new
one. This module names each of them, with served words, so no frontend has to
infer from a bare carry token what was left behind.

Both sides are read through the one owner of a revision's caller context,
:func:`~cadrumo.application.modelo.caller_context.caller_context_of`, so this
list and the replay of the same head can never disagree about what the head
recorded.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from ...core.authority_grade import RegistryAuthorityGrade
from ...core.i18n.render import tr
from ...domain.calculations.registry.modelo_localization import resolve_modelo_localization
from .printed_boxes import snapshot_printed_boxes
from .work_calculation_contracts import ModeloHeadStatementKind, ModeloUnusedHeadStatement

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ...core.external_constants import OutputLanguage
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
    from ...domain.modelos.calculation_revision_operator_layer import CalculationOperatorLayer
    from ...domain.modelos.work_unit import WorkUnit
    from .caller_context import CalculationCallerContext
    from .printed_boxes import PrintedBoxes

_WORDS_LOCALE_KEYS: Final[Mapping[ModeloHeadStatementKind, str]] = MappingProxyType(
    {
        ModeloHeadStatementKind.CASILLA_VALUE: "application.modelo.replaced_head.statement.casilla_value",
        ModeloHeadStatementKind.BINDING_OVERRIDE: "application.modelo.replaced_head.statement.binding_override",
        ModeloHeadStatementKind.ABSENCE_ATTESTATION: "application.modelo.replaced_head.statement.absence_attestation",
        ModeloHeadStatementKind.VALUE_ATTESTATION: "application.modelo.replaced_head.statement.value_attestation",
        ModeloHeadStatementKind.ROW_ATTESTATION: "application.modelo.replaced_head.statement.row_attestation",
        ModeloHeadStatementKind.INCOME_FAMILY_ENTRY: "application.modelo.replaced_head.statement.income_family_entry",
        ModeloHeadStatementKind.CLEARED_CASILLA: "application.modelo.replaced_head.statement.cleared_casilla",
        ModeloHeadStatementKind.DETAIL_ROWS: "application.modelo.replaced_head.statement.detail_rows",
        ModeloHeadStatementKind.M303_FILING_EVIDENCE: "application.modelo.replaced_head.statement.m303_filing_evidence",
        ModeloHeadStatementKind.M210_SELECTION: "application.modelo.replaced_head.statement.m210_selection",
        ModeloHeadStatementKind.BORRADOR_SNAPSHOT: "application.modelo.replaced_head.statement.borrador_snapshot",
    }
)
"""The sentence that says what each kind of recorded statement was."""


def unused_head_statements(
    head: CalculationCallerContext,
    new: CalculationCallerContext,
    *,
    work_unit: WorkUnit,
    operation: PinnedAuthorityOperation,
    language: OutputLanguage,
) -> tuple[ModeloUnusedHeadStatement, ...]:
    """Name every statement ``head`` recorded that ``new`` does not hold unchanged.

    A statement counts as carried only when the new head holds the same
    statement with the same value: a box the request typed again with another
    value, or an input the request set as a plain value where the person had
    stated it for an earlier filing, is named as not carried. An unknown
    operator layer on ``head`` contributes nothing here; the caller reports
    that the list is incomplete.
    """
    namer = _statement_namer(work_unit=work_unit, operation=operation, language=language)
    statements: list[ModeloUnusedHeadStatement] = []
    if head.operator_layer is not None:
        statements.extend(_unused_value_statements(head.operator_layer, new.known_operator_layer, namer))
        statements.extend(_unused_attestation_statements(head.operator_layer, new.known_operator_layer, namer))
    statements.extend(_unused_whole_statements(head, new, namer))
    return tuple(statements)


def _statement_namer(
    *, work_unit: WorkUnit, operation: PinnedAuthorityOperation, language: OutputLanguage
) -> _StatementNamer:
    """Read the revision's boxes and labels once for naming every statement of one result."""
    snapshot = operation.snapshot(
        str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    casillas = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    bound_casillas: dict[str, CasillaDefinition] = {}
    for casilla in snapshot.revision.casillas:
        if casilla.binding is not None:
            bound_casillas.setdefault(casilla.binding, casilla)
    boxes = snapshot_printed_boxes(operation, snapshot)
    return _StatementNamer(casillas=casillas, bound_casillas=bound_casillas, boxes=boxes, language=language)


def _unused_whole_statements(
    head: CalculationCallerContext, new: CalculationCallerContext, namer: _StatementNamer
) -> list[ModeloUnusedHeadStatement]:
    """Name the head's clears and declaration-wide statements that ``new`` does not hold unchanged."""
    statements: list[ModeloUnusedHeadStatement] = []
    statements.extend(
        namer.casilla(ModeloHeadStatementKind.CLEARED_CASILLA, casilla_id)
        for casilla_id in head.cleared_casilla_ids
        if casilla_id not in new.cleared_casilla_ids
    )
    if head.detail_rows and head.detail_rows != new.detail_rows:
        statements.append(namer.whole(ModeloHeadStatementKind.DETAIL_ROWS, value=str(len(head.detail_rows))))
    if head.filing_instance_evidence is not None and head.filing_instance_evidence != new.filing_instance_evidence:
        statements.append(namer.whole(ModeloHeadStatementKind.M303_FILING_EVIDENCE))
    head_m210 = (head.m210_official_tipo_renta_code, head.m210_gross_income_source_mode)
    new_m210 = (new.m210_official_tipo_renta_code, new.m210_gross_income_source_mode)
    if head_m210 != (None, None) and head_m210 != new_m210:
        statements.append(namer.whole(ModeloHeadStatementKind.M210_SELECTION))
    if head.borrador_snapshot_id is not None and head.borrador_snapshot_id != new.borrador_snapshot_id:
        statements.append(
            namer.whole(
                ModeloHeadStatementKind.BORRADOR_SNAPSHOT,
                subject=head.borrador_snapshot_id,
                value=head.borrador_snapshot_id,
            )
        )
    return statements


def _unused_value_statements(
    head: CalculationOperatorLayer, new: CalculationOperatorLayer, namer: _StatementNamer
) -> list[ModeloUnusedHeadStatement]:
    """Name the typed box values and plain binding overrides of ``head`` that ``new`` does not hold unchanged."""
    statements: list[ModeloUnusedHeadStatement] = []
    new_casilla_values = {**new.decimal_casilla_inputs, **new.text_casilla_inputs}
    for casilla_id, value in sorted({**head.decimal_casilla_inputs, **head.text_casilla_inputs}.items()):
        if new_casilla_values.get(casilla_id) != value:
            statements.append(namer.casilla(ModeloHeadStatementKind.CASILLA_VALUE, casilla_id, value=value))
    stated_bindings = set(head.attested_binding_ids).union(head.value_attestations)
    for binding_id, value in sorted(head.binding_overrides.items()):
        if binding_id not in stated_bindings and new.binding_overrides.get(binding_id) != value:
            statements.append(namer.binding(ModeloHeadStatementKind.BINDING_OVERRIDE, binding_id, value=value))
    return statements


def _unused_attestation_statements(
    head: CalculationOperatorLayer, new: CalculationOperatorLayer, namer: _StatementNamer
) -> list[ModeloUnusedHeadStatement]:
    """Name the attestations and income-family entries of ``head`` that ``new`` does not hold unchanged."""
    statements: list[ModeloUnusedHeadStatement] = []
    statements.extend(
        namer.binding(ModeloHeadStatementKind.ABSENCE_ATTESTATION, binding_id)
        for binding_id in head.attested_binding_ids
        if binding_id not in new.attested_binding_ids
    )
    for binding_id, attestation in sorted(head.value_attestations.items()):
        value = head.binding_overrides.get(binding_id)
        if new.value_attestations.get(binding_id) != attestation or new.binding_overrides.get(binding_id) != value:
            statements.append(namer.binding(ModeloHeadStatementKind.VALUE_ATTESTATION, binding_id, value=value))
    statements.extend(
        namer.binding(
            ModeloHeadStatementKind.ROW_ATTESTATION,
            row.binding_id,
            row_identity=row.source_row_identity,
            value=None if row.absent else row.amount,
        )
        for row in head.row_attestations
        if row not in new.row_attestations
    )
    statements.extend(
        namer.whole(ModeloHeadStatementKind.INCOME_FAMILY_ENTRY, subject=family)
        for family in sorted(head.income_family_entry_digests)
        if family not in new.income_family_entry_digests
    )
    return statements


class _StatementNamer:
    """Attach the served words, and the box and label a statement reaches, to one statement."""

    def __init__(
        self,
        *,
        casillas: dict[str, CasillaDefinition],
        bound_casillas: dict[str, CasillaDefinition],
        boxes: PrintedBoxes,
        language: OutputLanguage,
    ) -> None:
        self._casillas = casillas
        self._bound_casillas = bound_casillas
        self._boxes = boxes
        self._language = language

    def _words(self, kind: ModeloHeadStatementKind) -> str:
        return tr(_WORDS_LOCALE_KEYS[kind], locale=self._language.value)

    def _placed(
        self,
        kind: ModeloHeadStatementKind,
        subject: str,
        casilla: CasillaDefinition | None,
        *,
        row_identity: str | None,
        value: str | None,
    ) -> ModeloUnusedHeadStatement:
        return ModeloUnusedHeadStatement(
            kind=kind,
            subject=subject,
            row_identity=row_identity,
            box=self._boxes.number(casilla.id) if casilla is not None else None,
            # Read as optional: the revision is already stored when this runs, so a box
            # without a catalogue label is served without one rather than failing the result.
            label=(
                resolve_modelo_localization(casilla.localization_keys, locale=self._language.value)
                if casilla is not None
                else None
            ),
            value=value or None,
            words=self._words(kind),
        )

    def casilla(
        self, kind: ModeloHeadStatementKind, casilla_id: str, *, value: str | None = None
    ) -> ModeloUnusedHeadStatement:
        """Name a statement about one box."""
        return self._placed(kind, casilla_id, self._casillas.get(casilla_id), row_identity=None, value=value)

    def binding(
        self,
        kind: ModeloHeadStatementKind,
        binding_id: str,
        *,
        row_identity: str | None = None,
        value: str | None = None,
    ) -> ModeloUnusedHeadStatement:
        """Name a statement about one input, placed on the box it fills when it fills one."""
        return self._placed(
            kind, binding_id, self._bound_casillas.get(binding_id), row_identity=row_identity, value=value
        )

    def whole(
        self, kind: ModeloHeadStatementKind, *, subject: str | None = None, value: str | None = None
    ) -> ModeloUnusedHeadStatement:
        """Name a statement that reaches no single box."""
        return ModeloUnusedHeadStatement(kind=kind, subject=subject, value=value, words=self._words(kind))


__all__ = ["unused_head_statements"]
