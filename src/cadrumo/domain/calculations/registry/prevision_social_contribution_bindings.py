"""The binding family that carries pension contribution certificate records to the Modelo 100 contribution boxes.

A binding of the family names no clave and no casilla. The revision's casilla
declarations say which box each binding fills, and the revision's placement rows
say which box each Modelo 345 clave and subclave reaches
(:mod:`.prevision_social_placement`). A record placed in a box is summed into the
one family binding that box is bound to.

Registry build checks the two declarations against each other: every box a
placement row names is bound to exactly one family binding, and a revision that
places any clave declares the family, so no placed record is left unread.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import AfterValidator, BaseModel

from ....core.aggregation import BindingAggregationOp, BindingSourceKind
from ....core.models import STRICT_FROZEN_CONFIG
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import provider_member
from .binding_targets import casillas_by_binding
from .binding_value_contract import BindingDataType, BindingValueChannel
from .errors import RegistryValidationError
from .form_codes import form_role_validator
from .ledger_binding_validation import ledger_binding_build_diagnostics, ledger_binding_selector

if TYPE_CHECKING:
    from ....core.casilla_id import CasillaId
    from .ids import BindingId
    from .schema import BindingDefinition, ModeloRevision

__all__ = [
    "PrevisionSocialContributionProvider",
    "prevision_social_contribution_binding_by_casilla",
    "prevision_social_contribution_bindings",
    "prevision_social_contribution_revision_failures",
    "revision_declares_prevision_social_contribution",
    "validate_prevision_social_contribution_binding",
]


class PrevisionSocialContributionProvider(BaseModel):
    """Validated form of a ``prevision_social_contribution`` binding selector."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.PREVISION_SOCIAL_CONTRIBUTION] = BindingSourceKind.PREVISION_SOCIAL_CONTRIBUTION
    modelo: Annotated[str, AfterValidator(form_role_validator("renta.annual"))]
    period: Literal["0A"] = "0A"


def _validate_definition(binding: BindingDefinition) -> None:
    ledger_binding_selector(
        binding, BindingSourceKind.PREVISION_SOCIAL_CONTRIBUTION, PrevisionSocialContributionProvider
    )
    if binding.value.data_type is not BindingDataType.MONEY or binding.value.channel is not BindingValueChannel.DECIMAL:
        raise RegistryValidationError(f"binding {binding.id!r} carries money on the decimal channel")
    if binding_aggregation_op(binding) is not BindingAggregationOp.SUM:
        raise RegistryValidationError(
            f"binding {binding.id!r} sums the records placed in its box, so its operation is sum"
        )


def validate_prevision_social_contribution_binding(binding: BindingDefinition) -> list[str]:
    """Validate a ``prevision_social_contribution`` binding at registry-build time.

    Returns:
        The failures found, empty when the binding is valid.
    """
    return ledger_binding_build_diagnostics(binding, PrevisionSocialContributionProvider, _validate_definition)


def prevision_social_contribution_bindings(
    revision: ModeloRevision,
) -> tuple[tuple[BindingDefinition, PrevisionSocialContributionProvider], ...]:
    """Return every family binding of a :class:`ModeloRevision` beside its typed provider, in declaration order."""
    return tuple(
        (binding, provider_member(binding, PrevisionSocialContributionProvider))
        for binding in revision.bindings
        if binding.source is BindingSourceKind.PREVISION_SOCIAL_CONTRIBUTION
    )


def revision_declares_prevision_social_contribution(revision: ModeloRevision) -> bool:
    """Return whether a :class:`ModeloRevision` declares any member of the family."""
    return any(binding.source is BindingSourceKind.PREVISION_SOCIAL_CONTRIBUTION for binding in revision.bindings)


def prevision_social_contribution_binding_by_casilla(revision: ModeloRevision) -> Mapping[CasillaId, BindingId]:
    """Return the family binding each box of a :class:`ModeloRevision` is bound to, for every box bound to one.

    A box bound to several family bindings is left out; registry build refuses it.
    """
    family = {binding.id for binding, _provider in prevision_social_contribution_bindings(revision)}
    owners: dict[CasillaId, list[BindingId]] = {}
    for binding_id, casilla_ids in casillas_by_binding(revision).items():
        if binding_id in family:
            for casilla_id in casilla_ids:
                owners.setdefault(casilla_id, []).append(binding_id)
    return {casilla_id: bindings[0] for casilla_id, bindings in owners.items() if len(bindings) == 1}


def _placed_declared_casillas(revision: ModeloRevision) -> list[str]:
    """Return the declared boxes the revision's placement rows name, in order."""
    declared = {str(casilla.id) for casilla in revision.casillas}
    return sorted(
        {
            str(row.casilla_id)
            for row in revision.prevision_social_placements
            if row.casilla_id is not None and str(row.casilla_id) in declared
        }
    )


def prevision_social_contribution_revision_failures(revision: ModeloRevision) -> tuple[str, ...]:
    """Return every way the revision's family bindings and placement rows fail to meet.

    A revision that places a clave must declare the family, every box a placement
    row names must be bound to exactly one family binding, and every family binding
    fills exactly one box. A placed box the edition does not declare is refused by
    the placement rows' own check, so it is not reported here a second time.
    """
    failures: list[str] = []
    placed = _placed_declared_casillas(revision)
    bindings = prevision_social_contribution_bindings(revision)
    if placed and not bindings:
        failures.append(f"revision {revision.id!r} places pension contributions but declares no family binding")
    targets = casillas_by_binding(revision)
    failures.extend(
        f"prevision social contribution binding {binding.id!r} must fill exactly one casilla"
        for binding, _provider in bindings
        if len(targets.get(binding.id, ())) != 1
    )
    if bindings:
        owned = {str(casilla_id) for casilla_id in prevision_social_contribution_binding_by_casilla(revision)}
        failures.extend(
            f"casilla {casilla_id!r} is placed by a pension contribution row but bound to no single family binding"
            for casilla_id in placed
            if casilla_id not in owned
        )
    return tuple(failures)
