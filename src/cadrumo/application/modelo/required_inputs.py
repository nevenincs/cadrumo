"""Which casillas a filer must supply before verification can find a declaration complete.

Verification reports a missing required casilla for a box the filer types
(``input_kind`` manual) that the registry declares ``required`` and that no
repeated detail row answers: a casilla an export record fills once per detail
row belongs to its rows, so its completeness is the row source's, not a scalar
the filer types once. Every surface that tells a filer a box "needs your value"
reads the same set from here, so a form cannot demand a box verification does
not, nor stay silent about one it does.

The calculation completeness manifest is deliberately not this set. It lists
the calculation closure (every casilla a formula, binding, relation or
verification expectation touches), which includes hundreds of optional boxes a
filer may leave empty; it measures how much of the calculation materialised,
not what the filer owes.

See Also:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`
        The registry declaration supplying casillas, formulas, bindings and layout metadata.
"""

from __future__ import annotations

from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.casilla_membership import row_field_template_records_by_casilla
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_input_kind import InputKind


def filer_required_casilla_ids(revision: ModeloRevision) -> frozenset[CasillaId]:
    """Return the casillas of ``revision`` the filer must type for verification to pass.

    A detail-row template casilla is excluded: a repeated record carries one
    value per row, and the rows answer for it.

    See Also:
        :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`
            The registry declaration supplying casillas, formulas, bindings and layout metadata.
    """
    row_templates = row_field_template_records_by_casilla(revision)
    return frozenset(
        casilla.id
        for casilla in revision.casillas
        if casilla.input_kind == InputKind.MANUAL and casilla.required and casilla.id not in row_templates
    )


__all__ = ["filer_required_casilla_ids"]
