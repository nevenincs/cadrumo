"""Calculate-path advisory for revisions that do not compute settlement casillas.

A settlement-bearing modelo's terminal liquidación casilla (Modelo 100 cuota
resultante de la autoliquidación / resultado de la declaración) is
``computed`` via formula on a fully-modelled revision. A partially-modelled
revision leaves those casillas as
``input_kind = "manual"``: formulas for upstream inputs and intermediates exist,
yet the final liquidación cells remain operator-entered. A ledger-driven
calculate on such a revision populates the inputs but never computes the
settlement, so an operator could file a blank or zero liquidación on positive
activity (``no-silent-under-declaration``). M100 2020-2023 are the live advisory
case.

This module surfaces that STRUCTURAL gap on the calculate path as a non-blocking
:class:`~application.aggregation.CalculationSourceDiagnostic`, grounded in
the loaded :class:`ModeloRevision` casilla ``input_kind`` and its
:class:`~domain.calculations.registry.InputKind` value (format-agnostic:
inline and fragmented registry content have already
been merged) -- never the formula output, so it is non-tautological. It is the
structural complement to the value-level settlement-completeness ADVISORY predicate
(``implies_nonzero``) the verify gate runs on revisions whose settlement IS
computed (#24-B / #38): together they cover the no-formula (structural) and
formula-resolves-to-zero (value) shapes of the same under-declaration.

Scope: the guard fires only for the grounded terminal-liquidación
``semantic_role`` set below (Modelo 100 today, the confirmed live candidate from the
#39 settlement-completeness audit); extend the set as further modelos' settlement
chains are modelled. A revision with no formula chain at all yields no advisory
(an informativa or an unmodelled revision is not a partial-settlement calc surface).

See Also:
    :func:`~application.modelo._calculation_diagnostics.collect_bucket_aggregation_advisory_diagnostics`:
        Wires this structural advisory into the bucket-aggregation calculate path.
    :mod:`~application.modelo._verification_actions`:
        Evaluates the value-level settlement-completeness predicates that complement
        this structural guard.
    :class:`~domain.calculations.registry.InputKind`:
        The registry enum used to distinguish manual settlement cells from computed
        ones.
"""

from __future__ import annotations

from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_input_kind import InputKind
from ..aggregation import CalculationSourceDiagnostic

__all__ = ["SETTLEMENT_SEMANTIC_ROLES", "collect_settlement_not_computed_diagnostics"]

# Terminal-liquidación casilla ``semantic_role`` values per settlement-bearing
# modelo. Grounded in the #39 settlement-completeness audit: Modelo 100 cuota
# resultante de la autoliquidación (0595, the liability before pagos a cuenta) and
# resultado de la declaración (0670). The guard fires only for these roles, so it
# never touches a modelo whose settlement role is absent here (safe false-negative);
# extend as further settlement chains are modelled.
SETTLEMENT_SEMANTIC_ROLES = frozenset(
    {
        "irpf_cuota_resultante_autoliquidacion",
        "irpf_resultado_declaracion",
    },
)


def collect_settlement_not_computed_diagnostics(
    revision: ModeloRevision,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return advisories for settlement casillas that are manual (not computed).

    For a revision that carries a substantial formula chain (a partially-modelled
    calc surface) whose terminal liquidación casilla is ``input_kind = "manual"``,
    the calculate path populates the inputs but does not compute the final
    liquidación -- the operator must enter / verify it. Read from the loaded
    snapshot's casilla ``input_kind`` (structural), not the formula output, so the
    advisory cannot drift with the numbers. A revision that computes the settlement
    (``input_kind = "computed"``) yields no advisory; a revision with no formula
    chain yields no advisory (not a partial-settlement calc surface).

    Args:
        revision: The :class:`ModeloRevision` whose settlement casillas are
            inspected (from the loaded, format-agnostic snapshot).

    Returns:
        Tuple of
        :class:`~application.aggregation.CalculationSourceDiagnostic`
        advisories for settlement casillas that require operator verification.

    See Also:
        :data:`SETTLEMENT_SEMANTIC_ROLES`:
            The narrow terminal-liquidación role allowlist this collector inspects.
        :func:`~application.modelo._calculation_diagnostics.collect_bucket_aggregation_advisory_diagnostics`:
            Calls this collector after calculation revision creation.
    """
    if not revision.formulas:
        return ()
    diagnostics: list[CalculationSourceDiagnostic] = []
    for casilla in revision.casillas:
        if casilla.semantic_role not in SETTLEMENT_SEMANTIC_ROLES:
            continue
        if casilla.input_kind == InputKind.COMPUTED:
            continue
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="settlement_not_computed",
                source_kind="settlement_casilla",
                message=(
                    f"settlement casilla {casilla.id!r} ({casilla.semantic_role}) is a manual input on "
                    f"revision {revision.id!r}; the calculate path populates the inputs but does not "
                    f"compute the final liquidación on this revision -- enter/verify it before filing"
                ),
                casilla_id=casilla.id,
            ),
        )
    return tuple(diagnostics)
