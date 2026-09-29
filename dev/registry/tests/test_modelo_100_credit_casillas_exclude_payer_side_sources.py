"""No Modelo 100 credit casilla may be reachable from a withholding-agent return.

The annual IRPF declaration credits the withholding and the payments on account
the taxpayer BORE (LIRPF arts. 99 and 105; RIRPF arts. 76 and 108). A return the
taxpayer files as a withholding agent reports tax withheld from other people, so
crediting it would claim someone else's tax.

The credit set is read from the registry: it is the operand set of the formula
that totals the payments on account into casilla ``0609``. Reachability follows
every path a value can take into one of those casillas -- the primary binding of
a bound casilla, its reviewed alternates, and the bindings a computing formula
reads, transitively through the casillas that formula reads.

The gate runs over every authored Modelo 100 edition. Its teeth are proven
against in-memory defective revisions, one per reachability path; the authored
tree is never mutated and no production module is patched.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.domain.calculations.registry.binding_selector_utils import selector_as_dict
from cadrumo.domain.calculations.registry.ids import BindingId
from cadrumo.domain.calculations.registry.runtime_graph import expression_binding_refs, expression_casilla_refs
from cadrumo.domain.calculations.registry.schema import BindingDefinition, FormulaDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind

from ._modelo_100_registry_support import _loaded_registry

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_TOTAL_PAGOS_A_CUENTA_CASILLA: CasillaId = validated_casilla_id(
    "0609",
    surface="test_modelo_100_credit_casillas.total",
)

# The withholding-agent returns the product supports: three quarterly retención
# declarations and the three annual summaries that reconcile them. Each reports
# withholding the declarant practised, which is the perceptor's credit and never
# the declarant's.
_PAYER_SIDE_MODELOS = frozenset({"111", "115", "123", "180", "190", "193"})


def _credit_casilla_ids(revision: ModeloRevision) -> tuple[CasillaId, ...]:
    """Return the casillas the payments-on-account total is built from."""
    total = next(formula for formula in revision.formulas if formula.target_casilla_id == _TOTAL_PAGOS_A_CUENTA_CASILLA)
    return expression_casilla_refs(total.expression)


def _reachable_binding_ids(
    casilla_id: CasillaId,
    *,
    casillas_by_id: Mapping[CasillaId, CasillaDefinition],
    formulas_by_target: Mapping[CasillaId, FormulaDefinition],
    visited: set[CasillaId],
) -> set[BindingId]:
    """Return every binding id whose value can reach ``casilla_id``."""
    if casilla_id in visited:
        return set()
    visited.add(casilla_id)
    reachable: set[BindingId] = set()
    casilla = casillas_by_id.get(casilla_id)
    if casilla is not None and casilla.input_kind == InputKind.BOUND:
        if casilla.binding is not None:
            reachable.add(casilla.binding)
        reachable.update(casilla.alternate_bindings)
    formula = formulas_by_target.get(casilla_id)
    if formula is not None:
        expression = formula.expression
        reachable.update(expression_binding_refs(expression))
        for operand in expression_casilla_refs(expression):
            reachable.update(
                _reachable_binding_ids(
                    operand,
                    casillas_by_id=casillas_by_id,
                    formulas_by_target=formulas_by_target,
                    visited=visited,
                )
            )
    return reachable


def payer_side_sources_in_credit_set(revision: ModeloRevision) -> dict[CasillaId, tuple[tuple[BindingId, str], ...]]:
    """Return every credit casilla reachable from a withholding-agent return."""
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
    formulas_by_target = {formula.target_casilla_id: formula for formula in revision.formulas}
    bindings_by_id = {binding.id: binding for binding in revision.bindings}
    findings: dict[CasillaId, tuple[tuple[BindingId, str], ...]] = {}
    for casilla_id in _credit_casilla_ids(revision):
        offenders: list[tuple[BindingId, str]] = []
        for binding_id in sorted(
            _reachable_binding_ids(
                casilla_id,
                casillas_by_id=casillas_by_id,
                formulas_by_target=formulas_by_target,
                visited=set(),
            )
        ):
            binding = bindings_by_id.get(binding_id)
            if binding is None:
                continue
            source_modelo = selector_as_dict(binding).get("source_modelo")
            if isinstance(source_modelo, str) and source_modelo in _PAYER_SIDE_MODELOS:
                offenders.append((binding_id, source_modelo))
        if offenders:
            findings[casilla_id] = tuple(offenders)
    return findings


def _modelo_100_revisions() -> dict[str, ModeloRevision]:
    modelos_by_id, _catalogues = _loaded_registry()
    return dict(modelos_by_id["100"].revisions)


def test_no_authored_edition_reaches_a_credit_casilla_from_a_payer_side_return() -> None:
    """Every authored edition keeps the withholding-agent returns out of the credits."""
    offenders = {
        revision_id: payer_side_sources_in_credit_set(revision)
        for revision_id, revision in sorted(_modelo_100_revisions().items())
    }
    assert not {revision_id: found for revision_id, found in offenders.items() if found}, offenders


def test_the_credit_set_the_gate_reads_is_not_empty() -> None:
    """A gate that reads no casilla would pass on an empty registry."""
    for revision_id, revision in sorted(_modelo_100_revisions().items()):
        credit_ids = _credit_casilla_ids(revision)
        assert len(credit_ids) >= 10, f"edition {revision_id} declares only {len(credit_ids)} credit operands"
        assert _TOTAL_PAGOS_A_CUENTA_CASILLA not in credit_ids


def _payer_side_binding(revision: ModeloRevision) -> BindingDefinition:
    """Return a payer-side relation binding built from an authored relation binding.

    Copying an authored ``relation_prefill`` binding and repointing only its
    source modelo keeps the defect minimal: everything except the one fact the
    gate judges stays exactly as the registry authors it.
    """
    donor = next(binding for binding in revision.bindings if binding.id == "renta-modelo-130-pagos-fraccionados")
    return donor.model_copy(
        update={
            "id": "defect-payer-side-m111-retenciones",
            "provider": donor.provider.model_copy(update={"source_modelo": "111"}),
        }
    )


def _revision_with_bindings(revision: ModeloRevision, extra: BindingDefinition) -> ModeloRevision:
    return revision.model_copy(update={"bindings": (*revision.bindings, extra)})


def _newest_revision() -> ModeloRevision:
    revisions = _modelo_100_revisions()
    return revisions[max(revisions)]


def test_gate_detects_a_payer_side_binding_as_a_credit_casilla_primary() -> None:
    """Teeth: a payer-side binding named as a credit casilla's primary is found."""
    revision = _newest_revision()
    defect = _payer_side_binding(revision)
    target = validated_casilla_id("0597", surface="test_modelo_100_credit_casillas.primary")
    casillas = tuple(
        casilla.model_copy(update={"input_kind": InputKind.BOUND, "binding": defect.id})
        if casilla.id == target
        else casilla
        for casilla in revision.casillas
    )
    defective = _revision_with_bindings(revision, defect).model_copy(update={"casillas": casillas})

    assert payer_side_sources_in_credit_set(defective) == {target: ((defect.id, "111"),)}


def test_gate_detects_a_payer_side_binding_as_a_credit_casilla_alternate() -> None:
    """Teeth: a payer-side binding hidden in the alternates is found."""
    revision = _newest_revision()
    defect = _payer_side_binding(revision)
    target = validated_casilla_id("0596", surface="test_modelo_100_credit_casillas.alternate")
    casillas = tuple(
        casilla.model_copy(update={"alternate_bindings": (defect.id,)}) if casilla.id == target else casilla
        for casilla in revision.casillas
    )
    defective = _revision_with_bindings(revision, defect).model_copy(update={"casillas": casillas})

    assert payer_side_sources_in_credit_set(defective) == {target: ((defect.id, "111"),)}


def test_gate_detects_a_payer_side_binding_read_by_a_credit_formula() -> None:
    """Teeth: a payer-side binding reached through a computing formula is found."""
    revision = _newest_revision()
    defect = _payer_side_binding(revision)
    target = validated_casilla_id("0604", surface="test_modelo_100_credit_casillas.formula")
    formulas = tuple(
        formula.model_copy(
            update={
                "expression": formula.expression.model_copy(
                    update={
                        "args": (
                            *formula.expression.args,
                            FormulaExpression.model_validate({"binding": defect.id}),
                        )
                    }
                )
            }
        )
        if formula.target_casilla_id == target
        else formula
        for formula in revision.formulas
    )
    defective = _revision_with_bindings(revision, defect).model_copy(update={"formulas": formulas})

    assert payer_side_sources_in_credit_set(defective) == {target: ((defect.id, "111"),)}
