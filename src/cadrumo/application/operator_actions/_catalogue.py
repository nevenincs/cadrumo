"""Canonical declarations for operator-recovery actions.

An entry states only the stable action identifier, its canonical result-schema
command key, and where a later verdict may obtain each named argument.  Adding
an action means appending one :class:`ActionCatalogueEntry` literal to
:data:`OPERATOR_ACTION_CATALOGUE`; applicability remains with the application
guard and live command/input resolution remains with the operator-surface
projection.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ._models import ActionArgumentSource

_NAMESPACED_ID_PATTERN = r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$"
_FIELD_KEY_PATTERN = r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$"


class ActionArgumentBindingSpecification(BaseModel):
    """Declare how a verdict may materialise one named target argument.

    This is deliberately distinct from the value-bearing
    :class:`~cadrumo.application.operator_actions.ActionArgumentBinding` on a
    verdict.  It admits a source strategy but contains neither a runtime value
    nor a resolution status.
    """

    model_config = _STRICT_FROZEN

    argument_name: str = Field(pattern=_FIELD_KEY_PATTERN, min_length=1, max_length=120)
    source: ActionArgumentSource
    source_key: str = Field(pattern=_FIELD_KEY_PATTERN, min_length=1, max_length=160)
    source_evidence_id: str | None = Field(
        default=None,
        pattern=_NAMESPACED_ID_PATTERN,
        min_length=3,
        max_length=160,
    )

    @model_validator(mode="after")
    def _validate_evidence_requirement(self) -> ActionArgumentBindingSpecification:
        """Require an exact evidence identity only for evidence-derived arguments."""
        if self.source is ActionArgumentSource.CONDITION_EVIDENCE:
            if self.source_evidence_id is None:
                raise ValueError("condition-evidence argument specifications require source_evidence_id")
        elif self.source_evidence_id is not None:
            raise ValueError("only condition-evidence argument specifications can carry source_evidence_id")
        return self


class ActionCatalogueEntry(BaseModel):
    """One stable recovery action projected to a canonical command-schema key."""

    model_config = _STRICT_FROZEN

    action_id: str = Field(pattern=_NAMESPACED_ID_PATTERN, min_length=3, max_length=160)
    target_command_key: str = Field(pattern=_FIELD_KEY_PATTERN, min_length=1, max_length=160)
    argument_specifications: tuple[ActionArgumentBindingSpecification, ...] = ()

    @field_validator("argument_specifications")
    @classmethod
    def _unique_argument_names(
        cls,
        value: tuple[ActionArgumentBindingSpecification, ...],
    ) -> tuple[ActionArgumentBindingSpecification, ...]:
        """Refuse competing source strategies for the same target argument."""
        names = tuple(item.argument_name for item in value)
        if len(set(names)) != len(names):
            raise ValueError("action argument specification names must be unique")
        return tuple(sorted(value, key=lambda item: item.argument_name))


class ActionCatalogue(BaseModel):
    """Immutable deterministic action-id registry with fail-closed lookup."""

    model_config = _STRICT_FROZEN

    entries: tuple[ActionCatalogueEntry, ...] = Field(min_length=1)

    @field_validator("entries")
    @classmethod
    def _unique_action_ids(
        cls,
        value: tuple[ActionCatalogueEntry, ...],
    ) -> tuple[ActionCatalogueEntry, ...]:
        """Canonicalise entries and reject a second declaration for one action."""
        action_ids = tuple(entry.action_id for entry in value)
        if len(set(action_ids)) != len(action_ids):
            raise ValueError("operator action catalogue action IDs must be unique")
        return tuple(sorted(value, key=lambda entry: entry.action_id))

    def lookup(self, action_id: str) -> ActionCatalogueEntry:
        """Return the one declaration for ``action_id`` or fail closed."""
        for entry in self.entries:
            if entry.action_id == action_id:
                return entry
        raise KeyError(f"unknown operator action ID: {action_id!r}")


def build_action_catalogue(entries: Iterable[ActionCatalogueEntry]) -> ActionCatalogue:
    """Construct a deterministic catalogue from declarations supplied by one owner."""
    return ActionCatalogue(entries=tuple(entries))


OPERATOR_ACTION_CATALOGUE = build_action_catalogue(
    (
        ActionCatalogueEntry(
            action_id="operator.profile.create",
            target_command_key="config.profile.create",
            argument_specifications=(
                ActionArgumentBindingSpecification(
                    argument_name="profile_name",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="profile_name",
                ),
            ),
        ),
        ActionCatalogueEntry(
            action_id="operator.profile.login",
            target_command_key="config.login",
            argument_specifications=(
                ActionArgumentBindingSpecification(
                    argument_name="name",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="name",
                ),
            ),
        ),
        ActionCatalogueEntry(
            action_id="operator.profile.repair_clear_active",
            target_command_key="config.repair.profile",
            argument_specifications=(
                ActionArgumentBindingSpecification(
                    argument_name="clear_active",
                    source=ActionArgumentSource.REQUEST_CONTEXT,
                    source_key="clear_active",
                ),
                ActionArgumentBindingSpecification(
                    argument_name="profile",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="profile",
                ),
                ActionArgumentBindingSpecification(
                    argument_name="yes",
                    source=ActionArgumentSource.REQUEST_CONTEXT,
                    source_key="yes",
                ),
            ),
        ),
        ActionCatalogueEntry(
            action_id="operator.profile.edit",
            target_command_key="config.profile.edit",
            argument_specifications=(
                ActionArgumentBindingSpecification(
                    argument_name="profile_name",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="profile_name",
                ),
            ),
        ),
        ActionCatalogueEntry(
            action_id="operator.overview.status",
            target_command_key="overview.status",
        ),
        ActionCatalogueEntry(
            action_id="operator.modelo.work.calculate",
            target_command_key="modelo.work.calculate",
            argument_specifications=(
                ActionArgumentBindingSpecification(
                    argument_name="work_unit_id",
                    source=ActionArgumentSource.CONDITION_EVIDENCE,
                    source_key="work_unit_id",
                    source_evidence_id="workflow.work_unit.addressing",
                ),
            ),
        ),
        ActionCatalogueEntry(
            action_id="operator.modelo.verification_report.list",
            target_command_key="modelo.verification_report.list",
            argument_specifications=(
                ActionArgumentBindingSpecification(
                    argument_name="calculation_revision_id",
                    source=ActionArgumentSource.CONDITION_EVIDENCE,
                    source_key="calculation_revision_id",
                    source_evidence_id="workflow.calculation_revision.addressing",
                ),
            ),
        ),
    ),
)
"""Initial evidence-grounded actions for profile and workflow migrations.

The catalogue expands only as an owned producer-to-projection slice introduces
another canonical action.  It does not infer actions from command strings and
does not make external-environment remediation appear executable.
"""


def lookup_action(action_id: str) -> ActionCatalogueEntry:
    """Look up one declared operator action in the canonical catalogue."""
    return OPERATOR_ACTION_CATALOGUE.lookup(action_id)


__all__ = [
    "OPERATOR_ACTION_CATALOGUE",
    "ActionArgumentBindingSpecification",
    "ActionCatalogue",
    "ActionCatalogueEntry",
    "build_action_catalogue",
    "lookup_action",
]
