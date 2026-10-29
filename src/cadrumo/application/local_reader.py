"""The local document reader: the model the person picked to read with, per role.

Cadrumo defines no model, and nothing here asks the local AI server anything.
Each role reads with the one model the person picked in the agent's model
picker, as the agent service answers it; the running operation asks it through its model-run port
(:func:`read_role_lanes`). A lane whose catalogue entry says it reads off this
computer needs nothing local. A lane that stays on this computer carries
whether the server holds the picked model, as the agent's live catalogue
states it.

An on-host role is judged in a fixed order: a model the server does not hold
refuses as not installed; then a model whose presence nobody stated refuses as
unknown, never as missing. No judgement is made here about this computer's
hardware or memory: whether a model loads is the agent's answer when it loads it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, model_validator

from cadrumo_client.contracts.model_runs import ModelRunLane, ModelRunRefusal, ModelRunRefusalCode

from ..core.errors.hierarchy import pydantic_validation_boundary
from ..core.model_roles import ModelRole
from ..core.models import STRICT_FROZEN_CONFIG
from .operations.model_runs import current_model_run_port
from .operator_actions.models import PreconditionVerdict
from .probe_outcomes import ProbeFactValue, ProbePreconditionCondition, probe_no_recovery_verdict

__all__ = [
    "EXTRACTION_READER_ROLES",
    "LocalReaderDocumentReadiness",
    "LocalReaderRoleStatus",
    "LocalReaderStatus",
    "RoleLane",
    "read_local_reader_status",
    "read_role_lanes",
]

#: The roles invoice evidence extraction reads with, text layer first.
EXTRACTION_READER_ROLES: tuple[ModelRole, ...] = (ModelRole.TEXT_EXTRACTION, ModelRole.VISION_TRANSCRIPTION)

type RoleLane = ModelRunLane | ModelRunRefusal
"""The lane the agent service resolved for one role, or why it resolves none."""


class LocalReaderDocumentReadiness(StrEnum):
    """Which invoice documents this machine can turn into drafts.

    Text-layer documents are read by label rules that need no model, so they
    are always readable; the model only fills fields the labels do not print.
    Every document is readable only when :attr:`LocalReaderStatus.extraction_ready`.
    """

    ALL_DOCUMENTS = "all_documents"
    TEXT_LAYER_ONLY = "text_layer_only"


async def read_role_lanes(roles: Iterable[ModelRole]) -> dict[ModelRole, RoleLane]:
    """Return the lane the agent service resolves for each of ``roles``, as the running operation sees it.

    Outside an operation there is no model-run port, so every role reads as
    the service being unavailable rather than as having no selection.
    """
    port = current_model_run_port()
    if port is None:
        return {role: ModelRunRefusal(code=ModelRunRefusalCode.SERVICE_UNAVAILABLE) for role in roles}
    return {role: await port.lookup(role) for role in roles}


class LocalReaderRoleStatus(BaseModel):
    """One role's reader: the model its on-host lane loads, and whether the program's server holds it.

    ``model`` is the selected model of a lane that stays on this computer, and
    ``None`` for a lane that reads off it or a role with no usable lane.
    ``installed`` is ``None`` when nobody stated it or it does not apply -- an
    off-host lane loads nothing here -- and ``None`` must not render as "not
    installed".
    """

    model_config = STRICT_FROZEN_CONFIG

    role: ModelRole
    model: str | None = None
    installed: bool | None = None
    ready: bool
    failed_condition_id: str | None = None


class LocalReaderStatus(BaseModel):
    """The whole local reader at one moment, for a status area.

    ``extraction_ready`` is true only when both invoice-extraction roles can
    read: each has a lane, and an on-host lane's model is held by the server. It is the single claim a surface may use to say every document
    can be read. ``document_readiness`` says which documents can be read
    either way, and ``text_layer_model_fill_available`` whether text-layer
    fields the labels do not print can be filled by the text role.
    """

    model_config = STRICT_FROZEN_CONFIG

    roles: tuple[LocalReaderRoleStatus, ...]
    extraction_ready: bool
    document_readiness: LocalReaderDocumentReadiness
    text_layer_model_fill_available: bool

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _readiness_agrees(self) -> LocalReaderStatus:
        expected = (
            LocalReaderDocumentReadiness.ALL_DOCUMENTS
            if self.extraction_ready
            else LocalReaderDocumentReadiness.TEXT_LAYER_ONLY
        )
        if self.document_readiness is not expected:
            raise ValueError("document readiness must follow extraction readiness")
        if self.extraction_ready and not self.text_layer_model_fill_available:
            raise ValueError("an extraction-ready reader can fill text-layer fields")
        return self


@dataclass(frozen=True, slots=True)
class _Judgement:
    ready: bool
    verdict: PreconditionVerdict | None = None


def selected_model_condition(code: ModelRunRefusalCode) -> ProbePreconditionCondition:
    """Return the failed condition a refused role reports: a model that cannot read images, or no usable model."""
    if code is ModelRunRefusalCode.MODEL_CANNOT_READ_IMAGES:
        return ProbePreconditionCondition.SELECTED_MODEL_READS_IMAGES
    return ProbePreconditionCondition.SELECTED_MODEL_AVAILABLE


def _refusal_judgement(role: ModelRole, refusal: ModelRunRefusal) -> _Judgement:
    facts: dict[str, ProbeFactValue] = {
        "role": role.value,
        "model_run_refusal": refusal.code.value,
        "role_selection_required": refusal.code is ModelRunRefusalCode.NO_SELECTION,
    }
    return _Judgement(
        ready=False,
        verdict=probe_no_recovery_verdict(selected_model_condition(refusal.code), facts=facts),
    )


def _on_host_judgement(role: ModelRole, lane: ModelRunLane) -> _Judgement:
    """Judge an on-host lane: the model the server holds, or does not, or nobody stated."""
    model = lane.model
    if lane.installed is False:
        return _Judgement(
            ready=False,
            verdict=probe_no_recovery_verdict(
                ProbePreconditionCondition.ROLE_MODEL_INSTALLED,
                facts={"role": role.value, "model": model, "role_model_installed": False},
            ),
        )
    if lane.installed is None:
        return _Judgement(
            ready=False,
            verdict=probe_no_recovery_verdict(
                ProbePreconditionCondition.RUNTIME_REACHABLE,
                facts={"role": role.value, "model": model, "role_model_installed_known": False},
            ),
        )
    return _Judgement(ready=True)


def _role_status(role: ModelRole, answer: RoleLane) -> LocalReaderRoleStatus:
    if isinstance(answer, ModelRunRefusal):
        return _status_row(role, _refusal_judgement(role, answer))
    if answer.reads_off_host:
        return LocalReaderRoleStatus(role=role, ready=True)
    judgement = _on_host_judgement(role, answer)
    return _status_row(role, judgement, model=answer.model, installed=answer.installed)


def _status_row(
    role: ModelRole,
    judgement: _Judgement,
    *,
    model: str | None = None,
    installed: bool | None = None,
) -> LocalReaderRoleStatus:
    verdict = judgement.verdict
    return LocalReaderRoleStatus(
        role=role,
        model=model,
        installed=installed,
        ready=judgement.ready,
        failed_condition_id=None if verdict is None else verdict.failed_condition_id,
    )


def _selected_roles(roles: Iterable[ModelRole] | None) -> tuple[ModelRole, ...]:
    return tuple(ModelRole) if roles is None else tuple(roles)


def _answer(lanes: Mapping[ModelRole, RoleLane], role: ModelRole) -> RoleLane:
    # A role the caller did not look up has no lane this read can judge.
    return lanes.get(role, ModelRunRefusal(code=ModelRunRefusalCode.SERVICE_UNAVAILABLE))


def read_local_reader_status(
    lanes: Mapping[ModelRole, RoleLane],
    *,
    roles: Iterable[ModelRole] | None = None,
) -> LocalReaderStatus:
    """Judge every role's selected lane into one projection.

    ``lanes`` is what :func:`read_role_lanes` resolved for each role. Reads
    nothing from the local AI or from this computer: nothing is started,
    pulled, loaded or measured.
    """
    role_rows = tuple(_role_status(role, _answer(lanes, role)) for role in _selected_roles(roles))
    by_role = {row.role: row for row in role_rows}
    for role in EXTRACTION_READER_ROLES:
        if role not in by_role:
            by_role[role] = _role_status(role, _answer(lanes, role))
    extraction_ready = all(by_role[role].ready for role in EXTRACTION_READER_ROLES)
    return LocalReaderStatus(
        roles=role_rows,
        extraction_ready=extraction_ready,
        document_readiness=(
            LocalReaderDocumentReadiness.ALL_DOCUMENTS
            if extraction_ready
            else LocalReaderDocumentReadiness.TEXT_LAYER_ONLY
        ),
        text_layer_model_fill_available=by_role[ModelRole.TEXT_EXTRACTION].ready,
    )
