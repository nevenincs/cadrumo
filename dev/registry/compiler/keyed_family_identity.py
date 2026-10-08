"""Guard the identities of keyed members and the concepts their references name."""

from __future__ import annotations

from collections.abc import Mapping

from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.keyed_families import (
    KeyedFamilySpec as _KeyedFamily,
)
from cadrumo.domain.calculations.registry.keyed_families import (
    family_identity_value as _family_identity_value,
)
from cadrumo.domain.calculations.registry.runtime_graph import expression_casilla_refs
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression
from dev.registry.compiler._toml_helpers import as_toml_table as _as_toml_table

from .casilla_identity import _same_casilla_identity


def _refuse_undeclared_repurpose(
    context: str,
    family: _KeyedFamily,
    identity: str,
    inherited: object,
    stated: object,
    *,
    inherited_casillas_by_id: Mapping[str, tuple[object, ...]],
    successor_casillas_by_id: Mapping[str, tuple[object, ...]],
) -> None:
    """Refuse a supersession that changes what the member IS rather than what it declares.

    Superseding in place is the ordinary way an edition restates a member: the
    declaration changes and the identity carries. It is an undeclared repurpose
    when a field carrying the member's identity changes under the same id - a
    binding that changes its provider kind or value channel is no longer the
    same binding, whatever its id says. Reusing an id for a different thing
    makes every earlier edition's reference to it silently wrong, so it must be
    declared as a ``replaced`` evolution naming a new id instead.

    The identity-carrying fields are data on the family, not a branch per
    family, so enrolling a family states its identity fields in one place.
    """
    for path in family.identity_fields:
        before = _field_at(inherited, path)
        after = _field_at(stated, path)
        unchanged = (
            _same_casilla_identity(before, after, inherited_casillas_by_id, successor_casillas_by_id)
            if path in family.casilla_identity_fields
            else before == after
        )
        if not unchanged:
            raise RegistryLoadError(
                f"{context}: states {family.section} {identity!r} with {path} {after!r}, but the inherited member "
                f"carries {before!r}; a change to a field carrying the member's identity is a repurpose, not a "
                f"supersession, so declare it as a replaced evolution naming a new {family.identity}",
            )
    if family.section == "formulas":
        _refuse_reinterpreted_formula_operands(
            context, identity, inherited, stated, inherited_casillas_by_id, successor_casillas_by_id
        )


def _refuse_reinterpreted_formula_operands(
    context: str,
    identity: str,
    inherited: object,
    stated: object,
    inherited_casillas_by_id: Mapping[str, tuple[object, ...]],
    successor_casillas_by_id: Mapping[str, tuple[object, ...]],
) -> None:
    """An unchanged expression cannot silently read different fiscal concepts.

    Expressions are declarations, not immutable formula identity axes: an
    explicitly changed successor expression remains allowed. For an unchanged
    expression, walk the canonical typed tree so nested references receive the
    same protection as direct operands, without rewriting any reference.
    """
    before = FormulaExpression.model_validate(_field_at(inherited, "expression"))
    after = FormulaExpression.model_validate(_field_at(stated, "expression"))
    if before != after:
        return
    for reference in expression_casilla_refs(before):
        if not _same_casilla_identity(reference, reference, inherited_casillas_by_id, successor_casillas_by_id):
            raise RegistryLoadError(
                f"{context}: formulas {identity!r} inherits an unchanged expression whose casilla operand "
                f"{reference!r} no longer identifies the predecessor's concept; state the successor's "
                "expression explicitly with its intended references instead of silently carrying values",
            )


def _field_at(member: object, path: str) -> object:
    """Return the value at a dotted ``path`` within ``member``, or ``None`` where it does not resolve."""
    return _family_identity_value(member, path)


def _member_identity(member: object, family: _KeyedFamily) -> str | None:
    """Return ``member``'s identity value for ``family``, or ``None`` when it states none."""
    table = _as_toml_table(member)
    if table is None:
        return None
    identity = table.get(family.identity)
    return identity if isinstance(identity, str) else None
