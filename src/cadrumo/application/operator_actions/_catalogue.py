"""Canonical declarations for operator next actions.

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

from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.operator_action_enums import ActionArgumentSource
from ...core.identifier_grammar import FIELD_KEY_PATTERN, NamespacedId
from ...core.json_contract import ResolvedActionReference, ResolvedNoticeAction


class ActionArgumentBindingSpecification(BaseModel):
    """Declare how an application outcome may materialise one target argument.

    This is deliberately distinct from the value-bearing
    :class:`~cadrumo.application.operator_actions.ActionArgumentBinding` on a
    verdict.  It admits a source strategy but contains neither a runtime value
    nor a resolution status.
    """

    model_config = _STRICT_FROZEN

    argument_name: str = Field(pattern=FIELD_KEY_PATTERN, min_length=1, max_length=120)
    source: ActionArgumentSource
    source_key: str = Field(pattern=FIELD_KEY_PATTERN, min_length=1, max_length=160)
    source_evidence_id: NamespacedId | None = None

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
    """One stable next action projected to a canonical command-schema key."""

    model_config = _STRICT_FROZEN

    action_id: NamespacedId
    target_command_key: str = Field(pattern=FIELD_KEY_PATTERN, min_length=1, max_length=160)
    argument_specifications: tuple[ActionArgumentBindingSpecification, ...] = ()

    @field_validator("argument_specifications")
    @classmethod
    def _unique_source_specifications(
        cls,
        value: tuple[ActionArgumentBindingSpecification, ...],
    ) -> tuple[ActionArgumentBindingSpecification, ...]:
        """Refuse only a duplicated full source strategy for one target argument.

        A successful notice can honestly materialise one canonical argument from
        more than one declared provenance.  For example, a work-unit address
        may come from a verified condition evidence record or from the concrete
        verdict context of a successful operation.  The resolver matches the
        producer binding against this full tuple, so merely sharing an argument
        name is not ambiguous.
        """
        identities = tuple(
            (item.argument_name, item.source, item.source_key, item.source_evidence_id) for item in value
        )
        if len(set(identities)) != len(identities):
            raise ValueError("action argument source specifications must be unique")
        return tuple(
            sorted(
                value,
                key=lambda item: (
                    item.argument_name,
                    item.source.value,
                    item.source_key,
                    item.source_evidence_id or "",
                ),
            ),
        )


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
            action_id="operator.auth.configure",
            target_command_key="config.auth.configure",
            argument_specifications=(
                ActionArgumentBindingSpecification(
                    argument_name="provider",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="provider",
                ),
                ActionArgumentBindingSpecification(
                    argument_name="file",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="file",
                ),
            ),
        ),
        ActionCatalogueEntry(
            action_id="operator.auth.login",
            target_command_key="config.auth.login",
            argument_specifications=(
                ActionArgumentBindingSpecification(
                    argument_name="provider",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="provider",
                ),
            ),
        ),
        ActionCatalogueEntry(
            action_id="operator.diagnostics.secure_objects.quarantine",
            target_command_key="config.repair.quarantine",
            argument_specifications=(
                ActionArgumentBindingSpecification(
                    argument_name="yes",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="yes",
                ),
            ),
        ),
        ActionCatalogueEntry(
            action_id="operator.diagnostics.repair",
            target_command_key="config.repair",
        ),
        ActionCatalogueEntry(
            action_id="operator.diagnostics.workflow.reset_progress",
            target_command_key="config.repair.reset_progress",
            argument_specifications=(
                ActionArgumentBindingSpecification(
                    argument_name="yes",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="yes",
                ),
            ),
        ),
        ActionCatalogueEntry(
            action_id="operator.profile.descendiente",
            target_command_key="config.profile.descendiente.list",
        ),
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
            action_id="operator.profile.repair_active_pointer",
            target_command_key="config.repair.profile",
            argument_specifications=(
                ActionArgumentBindingSpecification(
                    argument_name="clear_active",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="clear_active",
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
            action_id="operator.profile.list",
            target_command_key="config.profile.list",
        ),
        ActionCatalogueEntry(
            action_id="operator.profile.status",
            target_command_key="config.profile.status",
        ),
        ActionCatalogueEntry(
            action_id="operator.ledger.link",
            target_command_key="ledger.link",
            argument_specifications=(
                ActionArgumentBindingSpecification(
                    argument_name="transaction_id",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="transaction_id",
                ),
                ActionArgumentBindingSpecification(
                    argument_name="invoice_id",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="invoice_id",
                ),
            ),
        ),
        ActionCatalogueEntry(
            action_id="operator.ledger.evidence.review.list",
            target_command_key="ledger.evidence.review.list",
        ),
        ActionCatalogueEntry(
            action_id="operator.ledger.classify",
            target_command_key="ledger.classify",
        ),
        ActionCatalogueEntry(
            action_id="operator.ledger.review",
            target_command_key="ledger.review",
        ),
        ActionCatalogueEntry(
            action_id="operator.ledger.preflight",
            target_command_key="ledger.preflight",
            argument_specifications=(
                ActionArgumentBindingSpecification(
                    argument_name="period",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="period",
                ),
                ActionArgumentBindingSpecification(
                    argument_name="year",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="year",
                ),
            ),
        ),
        ActionCatalogueEntry(
            action_id="operator.live.filed.pull",
            target_command_key="app.live.filed.pull",
            argument_specifications=(
                ActionArgumentBindingSpecification(
                    argument_name="modelos",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="modelos",
                ),
                ActionArgumentBindingSpecification(
                    argument_name="period",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="period",
                ),
                ActionArgumentBindingSpecification(
                    argument_name="year",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="year",
                ),
            ),
        ),
        ActionCatalogueEntry(
            action_id="operator.modelo.filing_record.list",
            target_command_key="modelo.filing_record.list",
            argument_specifications=(
                ActionArgumentBindingSpecification(
                    argument_name="modelo",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="modelo",
                ),
            ),
        ),
        ActionCatalogueEntry(
            action_id="operator.modelo.work.list",
            target_command_key="modelo.work.list",
        ),
        ActionCatalogueEntry(
            action_id="operator.modelo.work.create",
            target_command_key="modelo.work.create",
            argument_specifications=(
                ActionArgumentBindingSpecification(
                    argument_name="modelo",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="modelo",
                ),
                ActionArgumentBindingSpecification(
                    argument_name="period",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="period",
                ),
                ActionArgumentBindingSpecification(
                    argument_name="year",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="year",
                ),
            ),
        ),
        ActionCatalogueEntry(
            action_id="operator.modelo.work.file",
            target_command_key="modelo.work.file",
            argument_specifications=(
                ActionArgumentBindingSpecification(
                    argument_name="work_unit_id",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="work_unit_id",
                ),
            ),
        ),
        ActionCatalogueEntry(
            action_id="operator.modelo.work.revisions",
            target_command_key="modelo.work.revisions",
            argument_specifications=(
                ActionArgumentBindingSpecification(
                    argument_name="work_unit_id",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="work_unit_id",
                ),
            ),
        ),
        ActionCatalogueEntry(
            action_id="operator.live.filed.pull_all",
            target_command_key="app.live.filed.pull_all",
        ),
        ActionCatalogueEntry(
            action_id="operator.live.notifications.list",
            target_command_key="app.live.notifications.list",
        ),
        ActionCatalogueEntry(
            action_id="operator.storage.init",
            target_command_key="config.storage.init",
        ),
        ActionCatalogueEntry(
            action_id="operator.overview.status",
            target_command_key="overview.status",
        ),
        ActionCatalogueEntry(
            action_id="operator.overview.explain",
            target_command_key="overview.explain",
            argument_specifications=(
                ActionArgumentBindingSpecification(
                    argument_name="modelo",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="modelo",
                ),
                ActionArgumentBindingSpecification(
                    argument_name="year",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="year",
                ),
            ),
        ),
        ActionCatalogueEntry(
            action_id="operator.modelo.bindings.list",
            target_command_key="modelo.bindings.list",
            argument_specifications=(
                ActionArgumentBindingSpecification(
                    argument_name="modelo",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="modelo",
                ),
                ActionArgumentBindingSpecification(
                    argument_name="year",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="year",
                ),
                ActionArgumentBindingSpecification(
                    argument_name="period",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="period",
                ),
            ),
        ),
        ActionCatalogueEntry(
            action_id="operator.modelo.describe",
            target_command_key="modelo.describe",
            argument_specifications=(
                ActionArgumentBindingSpecification(
                    argument_name="modelo",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="modelo",
                ),
            ),
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
                ActionArgumentBindingSpecification(
                    argument_name="work_unit_id",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="work_unit_id",
                ),
            ),
        ),
        ActionCatalogueEntry(
            action_id="operator.modelo.work.verify",
            target_command_key="modelo.work.verify",
            argument_specifications=(
                ActionArgumentBindingSpecification(
                    argument_name="work_unit_id",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="work_unit_id",
                ),
            ),
        ),
        ActionCatalogueEntry(
            action_id="operator.modelo.work.status",
            target_command_key="modelo.work.status",
            argument_specifications=(
                ActionArgumentBindingSpecification(
                    argument_name="work_unit_id",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="work_unit_id",
                ),
            ),
        ),
        ActionCatalogueEntry(
            action_id="operator.registry.verify",
            target_command_key="registry.verify",
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
        ActionCatalogueEntry(
            action_id="operator.profile.archive.reconcile",
            target_command_key="config.profile.archive.reconcile",
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


def next_action(action_id: str) -> ResolvedNoticeAction:
    """Resolve a zero-argument action into a fully materialised notice action.

    Forward guidance on a SUCCESS path used to be a literal ``aeat ...`` string
    inside a locale message. That is untestable and rots silently: renaming a
    verb sweeps the registrations and leaves four translated catalogues naming a
    command that no longer exists, handing the operator - frequently an
    non-interactive caller - an instruction it cannot recover from.

    Resolution runs through :func:`lookup_action`, which fails closed on an
    unknown id, so the command key comes from the catalogue rather than from
    prose and a renamed action raises here instead of shipping.

    This lives beside the catalogue rather than in the CLI transport because the
    application layer also emits such notices; a CLI-owned helper would force an
    application module to import ``entrypoints``, against the layer direction.

    Args:
        action_id: A namespaced id declared in the operator action catalogue.

    Returns:
        The fully materialised action to attach as ``Notice(action=...)``.

    Raises:
        KeyError: ``action_id`` is not declared in the catalogue.
    """
    entry = lookup_action(action_id)
    if entry.argument_specifications:
        raise ValueError(
            f"notice action requires materialised argument bindings: {entry.action_id}",
        )
    return ResolvedNoticeAction(
        action=ResolvedActionReference(
            action_id=entry.action_id,
            target_command_key=entry.target_command_key,
        ),
    )


__all__ = [
    "OPERATOR_ACTION_CATALOGUE",
    "ActionArgumentBindingSpecification",
    "ActionCatalogue",
    "ActionCatalogueEntry",
    "build_action_catalogue",
    "lookup_action",
    "next_action",
]
