"""The one key contract shared by the borrador import and the borrador tier.

A borrador snapshot stores values under the binding ids of the pinned Modelo 100
revision, never under free casilla keys. The import projects each printed
casilla through the revision's bound-casilla map to the binding that owns it;
the tier and every read admit exactly the same set. A binding is admitted when
the registry marks it ``aeat_prefilled``. A printed casilla no admitted binding
owns is reported to the operator rather than stored or dropped, and a casilla
two admitted bindings could own is refused because the value has no single
owner.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal

from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.binding_targets import bound_casilla_binding_ids
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from .errors import LiveApplicationInputError

__all__ = [
    "BorradorCasillaProjection",
    "borrador_admitted_bindings",
    "project_printed_casillas",
    "require_borrador_keys_admitted",
]


@dataclass(frozen=True, slots=True)
class BorradorCasillaProjection:
    """Printed values keyed by their owning binding, plus the casillas nothing owns."""

    binding_values: Mapping[BindingId, Decimal | str]
    unowned_casillas: tuple[CasillaId, ...]


def borrador_admitted_bindings(revision: ModeloRevision) -> dict[BindingId, BindingDefinition]:
    """Return the bindings a borrador snapshot of ``revision`` may hold, by id."""
    return {binding.id: binding for binding in revision.bindings if binding.aeat_prefilled is True}


def project_printed_casillas(
    revision: ModeloRevision,
    printed: Mapping[CasillaId, Decimal | str],
) -> BorradorCasillaProjection:
    """Key each printed casilla by the one admitted binding the revision binds it to.

    Raises:
        LiveApplicationInputError: When a printed casilla has more than one
            admitted owner, or one admitted binding owns several printed casillas.
    """
    admitted = borrador_admitted_bindings(revision)
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    owned_by: dict[BindingId, list[CasillaId]] = {}
    unowned: list[CasillaId] = []
    ambiguous: list[CasillaId] = []
    for casilla_id in sorted(printed):
        casilla = casillas.get(casilla_id)
        bound = () if casilla is None else bound_casilla_binding_ids(casilla)
        owners = [binding_id for binding_id in bound if binding_id in admitted]
        if not owners:
            unowned.append(casilla_id)
        elif len(owners) > 1:
            ambiguous.append(casilla_id)
        else:
            owned_by.setdefault(owners[0], []).append(casilla_id)
    ambiguous.extend(casilla_id for owned in owned_by.values() if len(owned) > 1 for casilla_id in owned)
    if ambiguous:
        raise LiveApplicationInputError(
            translated_message="cli.app.live.borrador.import_casilla_owner_ambiguous",
            context={"casillas": ", ".join(sorted(ambiguous))},
        )
    return BorradorCasillaProjection(
        binding_values={binding_id: printed[owned[0]] for binding_id, owned in sorted(owned_by.items())},
        unowned_casillas=tuple(unowned),
    )


def require_borrador_keys_admitted(keys: Iterable[BindingId], revision: ModeloRevision) -> None:
    """Refuse stored keys the pinned revision does not admit to a borrador snapshot.

    This refuses a free casilla key and a binding id the revision no longer
    declares alike. No stored key is rewritten: such a snapshot is unusable and
    the document has to be imported again.
    """
    admitted = borrador_admitted_bindings(revision)
    refused = sorted(key for key in keys if key not in admitted)
    if refused:
        raise LiveApplicationInputError(
            translated_message="application.live.borrador.errors.binding_keys_not_admitted",
            context={"bindings": ", ".join(refused)},
        )
