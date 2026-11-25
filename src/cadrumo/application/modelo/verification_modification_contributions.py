"""Keep the two contributions to the Modelo 303 modification boxes apart at verification.

Casillas 14, 15 and 26 each print ONE figure that the record keeps as two
contributions: the modification the period's facturas rectificativas make, which
a binding reads, and the modification the person states for what the catalogue
holds no document for, which its own named casilla holds. The box adds them.

Three things can go wrong once a box states both, and each is refused here
rather than filed:

- A typed contribution standing beside an invoice-sourced one in the same
  period. The governing decision admits the typed figure only for a
  modification the catalogue holds no document for, and the record carries no
  attestation of that scope, so the two may be describing the same document and
  the box would state it twice.
- An operator value stored against a box that is now computed. Such a value was
  entered before the box carried an invoice-sourced contribution. It is neither
  dropped nor read as the contribution: the finding names the box, the figure
  and the casilla to re-enter it in, with the scope the decision asks for.
- A recargo modification whose base the return does not state. Casilla 26 reads
  the recargo the rectificativas moved; casilla 25, its base, stays the
  operator's, exactly as the ordinary recargo bases [16], [19] and [22] do,
  because a base sum cannot select only the rows that bore recargo. A 26
  without a 25 files the recargo without the base it was charged on.

Every one of them is a verification refusal rather than a calculation refusal:
the figures are computed and visible, and what is missing is the person's
answer. That is the grade the governing decision sets for this family.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Final

from ...core.decimal.constants import ZERO
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...domain.calculations.registry.runtime_graph import expression_casilla_refs
from ...domain.calculations.registry.schema_form_layouts import FormGridBlock
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from .action_errors import WORKFLOW_GATE_LEGAL_REFS

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ...core.casilla_id import CasillaId
    from ...domain.calculations.registry.schema import ModeloRevision
    from ...domain.calculations.registry.schema_form_layouts import FormLayoutDefinition

__all__ = ["modification_contribution_findings"]

#: The carriers the facturas rectificativas feed, one per modification box. The
#: box each one prints in and the casilla the person's own contribution goes in
#: are read from the edition's projection formula, the one formula that adds the
#: carrier to that contribution, so a box absent from the selected edition
#: simply yields no finding.
_MODIFICATION_CARRIERS: Final[tuple[str, ...]] = (
    "iva.modificacion-bases-cuotas.base",
    "iva.modificacion-bases-cuotas",
    "iva.modificacion-recargo",
)

_RECARGO_CARRIER: Final = "iva.modificacion-recargo"
_MODIFICATION_BASE_CARRIER: Final = "iva.modificacion-bases-cuotas.base"


def modification_contribution_findings(
    *,
    revision: ModeloRevision,
    form_layout: FormLayoutDefinition | None,
    casilla_values: Mapping[CasillaId, Decimal],
    input_values_by_casilla_id: Mapping[CasillaId, str],
) -> list[ModeloVerificationFinding]:
    """Refuse a modification box whose two contributions the record cannot keep apart.

    ``form_layout`` is the edition's published form, whose official row pairs
    the recargo modification's cuota box with its base box.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    boxes = _modification_boxes(revision)
    findings: list[ModeloVerificationFinding] = []
    for carrier in _MODIFICATION_CARRIERS:
        if carrier not in boxes:
            continue
        box, contribution = boxes[carrier]
        invoice_sourced = _amount(casilla_values, carrier)
        findings.extend(_stored_on_computed_box(box, contribution, input_values_by_casilla_id))
        if invoice_sourced == ZERO:
            continue
        typed = _typed(input_values_by_casilla_id, contribution)
        if typed != ZERO:
            findings.append(_both_contributions_finding(box, contribution, invoice_sourced, typed))
    recargo = boxes.get(_RECARGO_CARRIER)
    if recargo is not None and form_layout is not None:
        findings.extend(
            _recargo_base_findings(_row_base_box(form_layout, recargo[0]), casilla_values, input_values_by_casilla_id)
        )
    return findings


def _modification_boxes(revision: ModeloRevision) -> dict[str, tuple[str, str]]:
    """Map each declared carrier to its box and the person's contribution casilla.

    The box is the target of the edition's one formula that reads the carrier,
    and the contribution is that formula's other operand. A carrier read by no
    such formula, or by more than one, names no box here.
    """
    found: dict[str, list[tuple[str, str]]] = {}
    for formula in revision.formulas:
        operands = tuple(dict.fromkeys(str(ref) for ref in expression_casilla_refs(formula.expression)))
        if len(operands) != 2:
            continue
        for carrier in _MODIFICATION_CARRIERS:
            if carrier in operands:
                (contribution,) = (operand for operand in operands if operand != carrier)
                found.setdefault(carrier, []).append((str(formula.target_casilla_id), contribution))
    return {carrier: pairs[0] for carrier, pairs in found.items() if len(pairs) == 1}


def _row_base_box(form_layout: FormLayoutDefinition, cuota_box: str) -> str | None:
    """The other box the official printed row of ``cuota_box`` holds, or ``None`` when it holds none or several."""
    for page in form_layout.pages:
        for section in page.sections:
            for block in section.blocks:
                if not isinstance(block, FormGridBlock):
                    continue
                for row in block.rows:
                    boxes = tuple(str(cell.casilla_id) for cell in row.cells if cell.casilla_id is not None)
                    if cuota_box not in boxes:
                        continue
                    others = tuple(box for box in boxes if box != cuota_box)
                    return others[0] if len(others) == 1 else None
    return None


def _amount(values: Mapping[CasillaId, Decimal], casilla_id: str) -> Decimal:
    """The computed figure for ``casilla_id``, or zero where the revision holds none."""
    for stated, amount in values.items():
        if str(stated) == casilla_id:
            return amount
    return ZERO


def _typed(values: Mapping[CasillaId, str], casilla_id: str) -> Decimal:
    """The figure the person typed into ``casilla_id``, or zero where they typed none.

    The stored value is the operator's own text, so it is read through the one
    canonical decimal grammar. Text that does not conform reads as nothing here:
    the calculation's own boundary is what refuses a malformed figure, and this
    gate is about which box a well-formed one belongs in.
    """
    for stated, raw in values.items():
        if str(stated) != casilla_id:
            continue
        parsed = try_parse_canonical_decimal(raw)
        return ZERO if parsed is None else parsed
    return ZERO


def _stored_on_computed_box(
    box: str,
    contribution: str,
    input_values_by_casilla_id: Mapping[CasillaId, str],
) -> list[ModeloVerificationFinding]:
    """Refuse an operator value stored against a box the edition now computes."""
    stored = _typed(input_values_by_casilla_id, box)
    if stored == ZERO:
        return []
    return [
        ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.modification_value_stored_on_computed_box",
            message_facts={"casilla_id": box, "stored_value": stored, "contribution_casilla_id": contribution},
            legal_refs=WORKFLOW_GATE_LEGAL_REFS,
        )
    ]


def _both_contributions_finding(
    box: str,
    contribution: str,
    invoice_sourced: Decimal,
    typed: Decimal,
) -> ModeloVerificationFinding:
    """Refuse a typed contribution standing beside an invoice-sourced one with no stated scope."""
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key="application.modelo.findings.modification_typed_beside_invoice_sourced",
        message_facts={
            "casilla_id": box,
            "contribution_casilla_id": contribution,
            "invoice_sourced_value": invoice_sourced,
            "typed_value": typed,
        },
        legal_refs=WORKFLOW_GATE_LEGAL_REFS,
    )


def _recargo_base_findings(
    base_box: str | None,
    casilla_values: Mapping[CasillaId, Decimal],
    input_values_by_casilla_id: Mapping[CasillaId, str],
) -> list[ModeloVerificationFinding]:
    """Refuse a recargo modification whose base box the return leaves blank."""
    if base_box is None:
        return []
    recargo = _amount(casilla_values, _RECARGO_CARRIER)
    if recargo == ZERO or _typed(input_values_by_casilla_id, base_box) != ZERO:
        return []
    return [
        ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.modification_recargo_base_missing",
            message_facts={
                "casilla_id": base_box,
                "recargo_value": recargo,
                # The period's whole modification base, which is the base of the
                # recargo-bearing rows when they are the period's only
                # modification. It is named as what it is so the person reads it
                # as a starting figure rather than as the answer.
                "modification_base_value": _amount(casilla_values, _MODIFICATION_BASE_CARRIER),
            },
            legal_refs=WORKFLOW_GATE_LEGAL_REFS,
        )
    ]
