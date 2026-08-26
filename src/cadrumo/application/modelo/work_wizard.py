"""Frontend-neutral Modelo work-wizard discovery and flow construction.

The guided work wizard is an application-owned projection of the outstanding
registry input surface for one :class:`~cadrumo.domain.modelos.WorkUnit`.
It discovers only manual casillas and the remaining promptable binding or
relation inputs, attaches the registry grounding that explains each question,
and builds one runtime :class:`~cadrumo.application.flows.definition.FlowDefinition`.

The returned run owns its registry-derived copy table for its entire lifetime.
The CLI line frontend and the installed full-screen frontend both consume that
same definition; neither owns step discovery, copy resolution, or the run
lifecycle.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from ...application.flows.copy import register_copy_source
from ...application.flows.definition import CopyRef, FlowDefinition, FlowPage, FlowSection
from ...core import STRICT_FROZEN_CONFIG
from ...core.bucket_pointer import resolve_active_bucket_id
from ...core.flows import CheckpointAvailability, CopyRefKind, FlowMode, FlowWidgetKind
from ...core.i18n import tr
from ...domain.calculations.registry.errors import (
    RegistrySnapshotError,
    RegistryValidationError,
)
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.user_profile.errors import ProfileNotFoundError
from ._binding_readiness import profile_resolvable_binding_ids
from .registry_discovery import registry_bindings_for_scope, registry_casillas_for_registry_scope

if TYPE_CHECKING:
    from ...application.flows.engine import FlowState
    from ...domain.modelos import WorkUnit


ModeloWorkWizardPromptChannel = Literal["casilla", "binding", "relation"]
"""The calculation-input channel selected by one guided wizard question."""


class ModeloWorkWizardAnswers(BaseModel):
    """Typed shell for a run whose answers stay in the flow state."""

    model_config = STRICT_FROZEN_CONFIG


class ModeloWorkWizardStep(BaseModel):
    """One registry-grounded question outstanding for a Modelo work unit."""

    model_config = STRICT_FROZEN_CONFIG

    channel: ModeloWorkWizardPromptChannel
    key: str = Field(min_length=1)
    casilla_id: str = Field(min_length=1)
    number: str = Field(min_length=1)
    label: str = Field(min_length=1)
    help_text: str | None = None
    legal_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


_COPY_NAMESPACE = "modelo-work"
_ACTIVE_COPY_RUNS: dict[str, dict[str, str]] = {}
_PROMPTABLE_BINDING_SOURCES: frozenset[str] = frozenset({"manual_input", "profile"})
_MISSING_INPUT_TRANSLATED_MESSAGES: frozenset[str] = frozenset(
    {
        "errors.calc.binding_value_missing",
        "errors.calc.bound_casilla_binding_value_missing",
        "errors.calc.date_binding_value_missing",
        "errors.calc.enum_binding_value_missing",
        "errors.calc.relation_value_missing",
    },
)


def _resolve_modelo_work_wizard_copy(ref: str) -> str | None:
    """Resolve copy only from the addressed live wizard run."""
    prefix = f"{_COPY_NAMESPACE}:"
    if not ref.startswith(prefix):
        return None
    run_token, _, _ = ref[len(prefix) :].partition(":")
    table = _ACTIVE_COPY_RUNS.get(run_token)
    return table.get(ref) if table is not None else None


register_copy_source(CopyRefKind.SCHEMA_FIELD, _resolve_modelo_work_wizard_copy)


def _page_key(step: ModeloWorkWizardStep) -> str:
    return f"{step.channel}:{step.key}"


def _copy_ref_id(run_token: str, step: ModeloWorkWizardStep, facet: str) -> str:
    return f"{_COPY_NAMESPACE}:{run_token}:{_page_key(step)}:{facet}"


def _profile_resolved_binding_ids(unit: WorkUnit) -> frozenset[str]:
    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        return frozenset[str]()
    try:
        values = profile_resolvable_binding_ids(
            modelo=str(unit.modelo),
            bucket_id=bucket_id,
            filing_year=unit.filing_year,
            period=unit.period,
        )
    except (RegistrySnapshotError, RegistryValidationError, ProfileNotFoundError):
        return frozenset[str]()
    if not isinstance(values, (set, frozenset, tuple, list)) or not all(isinstance(value, str) for value in values):
        raise TypeError("binding-id projection must be a collection of text")
    return frozenset(values)


def discover_modelo_work_wizard_steps(unit: WorkUnit) -> tuple[ModeloWorkWizardStep, ...]:
    """Discover each remaining manual, binding, or relation question.

    Registry-computed and ledger-fed values are deliberately absent: their
    normal calculation inputs are already supplied by the canonical calculate
    path, so prompting would create an invalid competing override.
    """
    casillas_report = registry_casillas_for_registry_scope(
        str(unit.modelo),
        filing_year=unit.filing_year,
        period=unit.period.registry_token,
        input_kind=InputKind.MANUAL,
    )
    casilla_steps = tuple(
        ModeloWorkWizardStep(
            channel="casilla",
            key=row.casilla_id,
            casilla_id=row.casilla_id,
            number=row.number,
            label=row.label,
            help_text=row.help_text,
            legal_refs=tuple(row.legal_refs),
            source_refs=tuple(row.source_refs),
        )
        for row in casillas_report.rows
    )
    bindings_report = registry_bindings_for_scope(str(unit.modelo), period=unit.period)
    profile_resolved = _profile_resolved_binding_ids(unit)
    binding_steps: list[ModeloWorkWizardStep] = []
    for row in bindings_report.rows:
        if not getattr(row, "operator_input_required", True):
            continue
        if row.relation_inputs:
            binding_steps.extend(
                ModeloWorkWizardStep(
                    channel="relation",
                    key=str(relation_id),
                    casilla_id=str(row.binding_id),
                    number=str(row.binding_id),
                    label=str(row.binding_id),
                    help_text=tr(
                        "cli.app.modelo.work.wizard_relation_help",
                        binding_id=str(row.binding_id),
                        default=(
                            "Fed by registry relation {binding_id}; supply the cross-period or cross-modelo value "
                            "this relation carries."
                        ),
                    ),
                    legal_refs=tuple(row.legal_refs),
                    source_refs=tuple(row.source_refs),
                )
                for relation_id in row.relation_inputs
            )
            continue
        if row.source not in _PROMPTABLE_BINDING_SOURCES or row.binding_id in profile_resolved:
            continue
        binding_steps.append(
            ModeloWorkWizardStep(
                channel="binding",
                key=str(row.binding_id),
                casilla_id=str(row.binding_id),
                number=str(row.binding_id),
                label=str(row.binding_id),
                help_text=None,
                legal_refs=tuple(row.legal_refs),
                source_refs=tuple(row.source_refs),
            )
        )
    return (*casilla_steps, *binding_steps)


def _binding_grounding_lookup(unit: WorkUnit) -> dict[str, tuple[tuple[str, ...], tuple[str, ...]]]:
    """Return binding and relation IDs mapped to their registry grounding."""
    bindings_report = registry_bindings_for_scope(str(unit.modelo), period=unit.period)
    lookup: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {}
    for row in bindings_report.rows:
        grounding = (tuple(row.legal_refs), tuple(row.source_refs))
        lookup[str(row.binding_id)] = grounding
        for relation_id in row.relation_inputs:
            lookup[str(relation_id)] = grounding
    return lookup


def modelo_work_wizard_follow_up_step(
    error: RegistryValidationError,
    *,
    unit: WorkUnit,
) -> ModeloWorkWizardStep | None:
    """Convert a recognised missing calculation input into one extra question."""
    if error.translated_message not in _MISSING_INPUT_TRANSLATED_MESSAGES:
        return None
    context = error.context or {}
    grounding_lookup = _binding_grounding_lookup(unit)
    if error.translated_message == "errors.calc.relation_value_missing":
        relation_id = context.get("relation_id")
        if not isinstance(relation_id, str):
            return None
        legal_refs, source_refs = grounding_lookup.get(relation_id, ((), ()))
        return ModeloWorkWizardStep(
            channel="relation",
            key=relation_id,
            casilla_id=relation_id,
            number=relation_id,
            label=relation_id,
            help_text=tr(
                "cli.app.modelo.work.wizard_relation_help",
                binding_id=relation_id,
                default=(
                    "Fed by registry relation {binding_id}; supply the cross-period or cross-modelo value "
                    "this relation carries."
                ),
            ),
            legal_refs=legal_refs,
            source_refs=source_refs,
        )
    binding_id = context.get("binding_id")
    if not isinstance(binding_id, str):
        return None
    legal_refs, source_refs = grounding_lookup.get(binding_id, ((), ()))
    return ModeloWorkWizardStep(
        channel="binding",
        key=binding_id,
        casilla_id=binding_id,
        number=binding_id,
        label=binding_id,
        help_text=None,
        legal_refs=legal_refs,
        source_refs=source_refs,
    )


@dataclass(frozen=True, slots=True)
class ModeloWorkWizardRun:
    """One live wizard run with its registry-derived step and copy authority."""

    unit: WorkUnit
    steps: tuple[ModeloWorkWizardStep, ...]
    _run_token: str

    def definition_for(self, steps: tuple[ModeloWorkWizardStep, ...] | None = None) -> FlowDefinition:
        """Build the canonical flow definition for these run-owned steps."""
        current_steps = self.steps if steps is None else steps
        table = _ACTIVE_COPY_RUNS.get(self._run_token)
        if table is None:
            raise RuntimeError("Modelo work wizard run is closed")
        pages: list[FlowPage] = []
        for step in current_steps:
            prompt_ref = _copy_ref_id(self._run_token, step, "prompt")
            table[prompt_ref] = tr(
                "cli.app.modelo.work.wizard_prompt",
                number=step.number,
                label=step.label,
                default="Casilla {number} ({label})",
            )
            help_ref: str | None = None
            if step.help_text:
                help_ref = _copy_ref_id(self._run_token, step, "help")
                table[help_ref] = step.help_text
            pages.append(
                FlowPage(
                    id=_page_key(step),
                    widget=FlowWidgetKind.TEXT,
                    prompt=CopyRef(kind=CopyRefKind.SCHEMA_FIELD, ref=prompt_ref),
                    help=CopyRef(kind=CopyRefKind.SCHEMA_FIELD, ref=help_ref) if help_ref else None,
                    required=False,
                    answer_type=str,
                )
            )
        help_key = CopyRef(kind=CopyRefKind.LOCALE_KEY, ref="cli.app.modelo.work.wizard_help")
        return FlowDefinition(
            id="modelo-work-wizard",
            title=help_key,
            description=help_key,
            sections=(FlowSection(id="manual-inputs", title=help_key, items=tuple(pages)),),
            answers_model=ModeloWorkWizardAnswers,
            checkpoint={
                FlowMode.CREATE: CheckpointAvailability.UNAVAILABLE,
                FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
            },
        )

    def answer_pairs(
        self,
        state: FlowState,
        *,
        steps: tuple[ModeloWorkWizardStep, ...] | None = None,
    ) -> tuple[tuple[ModeloWorkWizardStep, str], ...]:
        """Read canonical stripped answers for the supplied pages from a flow state."""
        current_steps = self.steps if steps is None else steps
        return tuple((step, (state.answers.get(_page_key(step)) or "").strip()) for step in current_steps)


@contextmanager
def open_modelo_work_wizard(unit: WorkUnit) -> Iterator[ModeloWorkWizardRun]:
    """Open one copy-scoped wizard run and remove its entries on exit."""
    run_token = uuid4().hex
    _ACTIVE_COPY_RUNS[run_token] = {}
    try:
        yield ModeloWorkWizardRun(unit=unit, steps=discover_modelo_work_wizard_steps(unit), _run_token=run_token)
    finally:
        _ACTIVE_COPY_RUNS.pop(run_token, None)


__all__ = [
    "ModeloWorkWizardAnswers",
    "ModeloWorkWizardPromptChannel",
    "ModeloWorkWizardRun",
    "ModeloWorkWizardStep",
    "discover_modelo_work_wizard_steps",
    "modelo_work_wizard_follow_up_step",
    "open_modelo_work_wizard",
]
