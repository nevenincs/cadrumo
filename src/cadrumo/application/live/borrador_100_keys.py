"""The one key contract shared by the borrador import and the borrador tier.

A borrador snapshot stores values under the binding ids of the pinned Modelo 100
revision, never under free casilla keys. The import projects each printed
casilla through the revision's bound-casilla map to the binding that owns it;
the tier and every read admit exactly the same set. A binding is admitted when
the registry marks it ``aeat_prefilled``; whether an admitted value may then
supply the binding is the binding's separate ``borrador_participation``, which
the tier reads. A casilla two admitted bindings could own is refused because
the value has no single owner.

A printed casilla no admitted binding owns is kept as a comparison-only
observation when the revision declares the box, under the registry's
continuity identity for it, and is never stored as a binding value. Only a
printed casilla the revision does not declare at all is reported to the
operator as kept nowhere.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import InternalInvariantError
from ...core.identity.continuidad import ContinuidadId
from ...domain.calculations.registry.binding_targets import bound_casilla_binding_ids
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from .errors import LiveApplicationInputError

__all__ = [
    "BorradorCasillaProjection",
    "BorradorPrintedBox",
    "BorradorPrintedBoxValue",
    "borrador_admitted_bindings",
    "borrador_keys_not_admitted",
    "printed_box_casilla",
    "project_printed_casillas",
    "require_borrador_keys_admitted",
    "require_printed_observations_resolve",
    "unresolved_printed_observations",
]


class BorradorPrintedBox(Protocol):
    """The identity a kept printed observation carries for its box."""

    @property
    def casilla_id(self) -> CasillaId:
        """The box as the capture's revision numbers it."""
        ...

    @property
    def continuidad_id(self) -> ContinuidadId | None:
        """The registry's identity for the box across revisions, when it declares one."""
        ...


@dataclass(frozen=True, slots=True)
class BorradorPrintedBoxValue:
    """One printed box no admitted binding owns, with its registry identity; ``None`` is a blank box."""

    casilla_id: CasillaId
    continuidad_id: ContinuidadId | None
    value: Decimal | str | None


@dataclass(frozen=True, slots=True)
class BorradorCasillaProjection:
    """Printed values keyed by their owning binding, the comparison-only boxes, and the boxes kept nowhere.

    ``observed`` holds each printed box the revision declares but no admitted
    binding owns. ``unowned_casillas`` lists printed boxes the revision does not
    declare at all; their values are kept nowhere.
    """

    binding_values: Mapping[BindingId, Decimal | str]
    observed: tuple[BorradorPrintedBoxValue, ...]
    unowned_casillas: tuple[CasillaId, ...]


def borrador_admitted_bindings(revision: ModeloRevision) -> dict[BindingId, BindingDefinition]:
    """Return the bindings a borrador snapshot of ``revision`` may hold, by id."""
    return {binding.id: binding for binding in revision.bindings if binding.aeat_prefilled is True}


def _sort_printed_by_owner(
    revision: ModeloRevision,
    admitted: Mapping[BindingId, BindingDefinition],
    printed: Mapping[CasillaId, Decimal | str],
) -> tuple[dict[BindingId, list[CasillaId]], list[CasillaId], list[CasillaId]]:
    """Sort each printed casilla, in order, to its one owner, to unowned, or to ambiguous."""
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
    return owned_by, unowned, ambiguous


def _observed_boxes(
    revision: ModeloRevision,
    admitted: Mapping[BindingId, BindingDefinition],
    printed: Mapping[CasillaId, Decimal | str | None],
) -> tuple[tuple[BorradorPrintedBoxValue, ...], tuple[CasillaId, ...]]:
    """Split printed boxes no admitted binding owns into declared observations and undeclared boxes."""
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    observed: list[BorradorPrintedBoxValue] = []
    undeclared: list[CasillaId] = []
    for casilla_id in sorted(printed):
        casilla = casillas.get(casilla_id)
        if casilla is None:
            undeclared.append(casilla_id)
        elif not any(owner in admitted for owner in bound_casilla_binding_ids(casilla)):
            observed.append(
                BorradorPrintedBoxValue(
                    casilla_id=casilla_id, continuidad_id=casilla.continuidad_id, value=printed[casilla_id]
                )
            )
    return tuple(observed), tuple(undeclared)


def project_printed_casillas(
    revision: ModeloRevision,
    printed: Mapping[CasillaId, Decimal | str],
    *,
    blank: Iterable[CasillaId] = (),
) -> BorradorCasillaProjection:
    """Key each printed casilla by the one admitted binding the revision binds it to.

    A printed or blank box no admitted binding owns becomes a comparison-only
    observation when the revision declares it. A blank box an admitted binding
    owns contributes nothing, as before.

    Raises:
        LiveApplicationInputError: When a printed casilla has more than one
            admitted owner, or one admitted binding owns several printed casillas.
    """
    admitted = borrador_admitted_bindings(revision)
    owned_by, unowned, ambiguous = _sort_printed_by_owner(revision, admitted, printed)
    ambiguous.extend(casilla_id for owned in owned_by.values() if len(owned) > 1 for casilla_id in owned)
    if ambiguous:
        raise LiveApplicationInputError(
            translated_message="cli.app.live.borrador.import_casilla_owner_ambiguous",
            context={"casillas": ", ".join(sorted(ambiguous))},
        )
    blank_boxes = frozenset(casilla_id for casilla_id in blank if casilla_id not in printed)
    candidates: dict[CasillaId, Decimal | str | None] = {casilla_id: printed[casilla_id] for casilla_id in unowned}
    candidates.update(dict.fromkeys(blank_boxes))
    observed, undeclared = _observed_boxes(revision, admitted, candidates)
    return BorradorCasillaProjection(
        binding_values={binding_id: printed[owned[0]] for binding_id, owned in sorted(owned_by.items())},
        observed=observed,
        unowned_casillas=tuple(casilla_id for casilla_id in undeclared if casilla_id not in blank_boxes),
    )


def printed_box_casilla(
    revision: ModeloRevision, box: BorradorPrintedBox, *, captured_revision_id: str
) -> CasillaDefinition | None:
    """Return the box of ``revision`` a kept printed observation names, through registry continuity.

    A box with a continuity identity resolves to the one casilla of
    ``revision`` carrying it. A box without one resolves by number only in the
    revision it was captured under, because a number alone is no identity
    across revisions. ``None`` means the revision does not identify the box.
    """
    if box.continuidad_id is not None:
        matches = [casilla for casilla in revision.casillas if casilla.continuidad_id == box.continuidad_id]
        return matches[0] if len(matches) == 1 else None
    if revision.id != captured_revision_id:
        return None
    return next((casilla for casilla in revision.casillas if casilla.id == box.casilla_id), None)


def unresolved_printed_observations(
    revision: ModeloRevision, boxes: Iterable[BorradorPrintedBox], *, captured_revision_id: str
) -> tuple[CasillaId, ...]:
    """Return, sorted, the kept printed boxes ``revision`` does not identify."""
    return tuple(
        sorted(
            box.casilla_id
            for box in boxes
            if printed_box_casilla(revision, box, captured_revision_id=captured_revision_id) is None
        )
    )


def require_printed_observations_resolve(
    revision: ModeloRevision,
    boxes: Iterable[BorradorPrintedBox],
    *,
    captured_revision_id: str,
    refuse_owned_casillas: bool = False,
) -> None:
    """Refuse kept printed boxes the revision does not identify, and, at capture, boxes a binding owns.

    Raises:
        LiveApplicationInputError: When a kept printed box no longer resolves.
        InternalInvariantError: When ``refuse_owned_casillas`` is set and a
            printed observation names a box an admitted binding owns, which
            would give one printed value two roles.
    """
    boxes = tuple(boxes)
    unresolved = unresolved_printed_observations(revision, boxes, captured_revision_id=captured_revision_id)
    if unresolved:
        raise LiveApplicationInputError(
            translated_message="application.live.borrador.errors.printed_observations_unresolved",
            context={"casillas": ", ".join(unresolved)},
        )
    if not refuse_owned_casillas:
        return
    admitted = borrador_admitted_bindings(revision)
    for box in boxes:
        casilla = printed_box_casilla(revision, box, captured_revision_id=captured_revision_id)
        if casilla is not None and any(owner in admitted for owner in bound_casilla_binding_ids(casilla)):
            raise InternalInvariantError("a printed observation names a box an admitted binding owns")


def borrador_keys_not_admitted(keys: Iterable[BindingId], revision: ModeloRevision) -> tuple[BindingId, ...]:
    """Return, sorted, the keys the pinned revision does not admit to a borrador snapshot."""
    admitted = borrador_admitted_bindings(revision)
    return tuple(sorted(key for key in keys if key not in admitted))


def require_borrador_keys_admitted(keys: Iterable[BindingId], revision: ModeloRevision) -> None:
    """Refuse keys the pinned revision does not admit to a borrador snapshot.

    This refuses a free casilla key and a binding id the revision no longer
    declares alike. No stored key is rewritten: such a snapshot is unusable and
    the document has to be imported again.
    """
    refused = borrador_keys_not_admitted(keys, revision)
    if refused:
        raise LiveApplicationInputError(
            translated_message="application.live.borrador.errors.binding_keys_not_admitted",
            context={"bindings": ", ".join(refused)},
        )
