"""Typed lines of the native ``components`` role's protocol, decoded strictly and within bounds.

The role writes one JSON object per line on its standard output: ``started``
first, then ``phase``, ``progress``, ``notice`` and ``review`` events, and one
``result`` last. Every value is a closed code or a locale-neutral fact, so the
models below carry codes only; a surface words them from its catalogue. A line
that is too long, is not one JSON object, names an unknown type or code, or
carries a field this protocol does not declare is refused, never guessed. A
role that speaks another protocol or plan contract version belongs to another
build: :class:`ComponentsContractMismatchError` says so, so a surface reads the
items as not in this build instead of approving a plan it cannot read.

The client answers on the role's standard input with
:class:`ComponentsApprove` or :class:`ComponentsDecline` to a review, and
:data:`CANCEL_LINE` to stop a running setup or check.

A setup of an item another process is already setting up follows it: a
``following`` notice names the item and the digest of the plan that setup was
approved under, the other setup's phases, progress and notices follow, and the
result is the one it reached for the item. A follower is sent no review. Its
:data:`CANCEL_LINE` stops only the following, which ends ``busy``; the
``cancel`` command asks the followed setup itself to stop.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final, Literal

from pydantic import BaseModel, Field, NonNegativeInt, StringConstraints, TypeAdapter, ValidationError, model_validator

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ....application.dependency_contracts import (
    DependencyBlockedReason,
    DependencyCheckMode,
    DependencyHostName,
    DependencyItemId,
    DependencyItemKind,
    DependencyNote,
    DependencyRecoveryAction,
    DependencySetupStep,
    DependencyStaleReason,
    DependencyState,
    DependencyStatusRow,
    dependency_item_kind,
)
from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.identifier_grammar import NamespacedId
from ....core.model_catalogue import ModelSelectionAdvisory
from ....core.models import STRICT_FROZEN_CONFIG

__all__ = [
    "CANCEL_LINE",
    "COMPONENTS_PLAN_CONTRACT_VERSION",
    "COMPONENTS_PROTOCOL_VERSION",
    "MAX_LINE_BYTES",
    "ComponentsAnswer",
    "ComponentsApprove",
    "ComponentsCommand",
    "ComponentsContractMismatchError",
    "ComponentsDecline",
    "ComponentsDestination",
    "ComponentsEvent",
    "ComponentsLicence",
    "ComponentsLine",
    "ComponentsNoticeCode",
    "ComponentsNoticeLine",
    "ComponentsOutcome",
    "ComponentsPhaseLine",
    "ComponentsPlan",
    "ComponentsPlanEntry",
    "ComponentsPlanPart",
    "ComponentsProgressLine",
    "ComponentsResultLine",
    "ComponentsReviewLine",
    "ComponentsRow",
    "ComponentsSpace",
    "ComponentsStartedLine",
    "answer_line",
    "decode_components_line",
]

COMPONENTS_PROTOCOL_VERSION: Final = 1
"""The protocol version this client speaks; a ``started`` line naming another belongs to another build."""

COMPONENTS_PLAN_CONTRACT_VERSION: Final = 2
"""The plan contract this client reads; a plan of another version belongs to another build.

The version is folded into the plan digest, so a plan shape this client does not
know is never approved: the role and this client ship together.
"""

MAX_LINE_BYTES: Final = 1024 * 1024
"""The longest output line accepted, newline included; the role's largest line, a plan, is a few kilobytes."""

CANCEL_LINE: Final = b'{"type":"cancel"}\n'
"""The input line that stops a running setup or check at its next transfer chunk, or a follower's following."""

type _Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
type _Version = Annotated[str, StringConstraints(min_length=1, max_length=128)]
type _PartId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$", min_length=1, max_length=64)]
type _SpdxId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9.+-]*$", min_length=1, max_length=128)]
type _LicenceName = Annotated[str, StringConstraints(min_length=1, max_length=200)]
type _PhaseCode = Annotated[
    str, StringConstraints(pattern=r"^dependencies\.setup\.[a-z_]+\.[a-z]+$", min_length=1, max_length=128)
]


class ComponentsCommand(StrEnum):
    """The role's commands."""

    STATUS = "status"
    PLAN = "plan"
    SETUP = "setup"
    VERIFY = "verify"
    CANCEL = "cancel"
    REMOVE = "remove"


class ComponentsOutcome(StrEnum):
    """How a command ended, as one closed code."""

    OK = "ok"
    NOTHING_TO_DO = "nothing_to_do"
    COMPLETED = "completed"
    NEEDS_APPROVAL = "needs_approval"
    PLAN_CHANGED = "plan_changed"
    BUSY = "busy"
    REFUSED = "refused"
    FAILED = "failed"
    CANCELLED = "cancelled"
    CANCEL_REQUESTED = "cancel_requested"
    NOTHING_RUNNING = "nothing_running"
    REMOVED = "removed"
    INVALID_REQUEST = "invalid_request"

    @property
    def succeeded(self) -> bool:
        """Whether the command did what was asked; the role exits 0 exactly then."""
        return self in _SUCCEEDED


_SUCCEEDED: Final = frozenset(
    {
        ComponentsOutcome.OK,
        ComponentsOutcome.NOTHING_TO_DO,
        ComponentsOutcome.COMPLETED,
        ComponentsOutcome.CANCEL_REQUESTED,
        ComponentsOutcome.NOTHING_RUNNING,
        ComponentsOutcome.REMOVED,
    }
)


class ComponentsNoticeCode(StrEnum):
    """What a ``notice`` line says."""

    RETRYING = "retrying"
    WAITING_FOR_SERVER = "waiting_for_server"
    FOLLOWING = "following"
    CANCEL_REQUESTED = "cancel_requested"
    INPUT_REFUSED = "input_refused"


class ComponentsDestination(StrEnum):
    """Where a plan stores what it downloads; the codes are the storage categories' names."""

    PLAYWRIGHT_BROWSERS = "playwright-browsers"
    OLLAMA_MODELS = "ollama-models"
    LOCAL_AI_PROGRAM = "local-ai-program"


_RECOVERY_ACTION_PREFIX: Final = "operator.provision."
"""Each item's button runs the operator action named by this prefix and the item's id."""


class ComponentsRow(BaseModel):
    """One item's derived state as the role reports it: the state, exactly its reason, a note and one button."""

    model_config = STRICT_FROZEN_CONFIG

    item_id: DependencyItemId
    mode: DependencyCheckMode
    state: DependencyState
    stale_reason: DependencyStaleReason | None = None
    blocked_reason: DependencyBlockedReason | None = None
    failure_category: DependencyFailureCategory | None = None
    note: DependencyNote | None = None
    version: _Version | None = None
    size_estimate_bytes: NonNegativeInt | None = None
    recovery: DependencyRecoveryAction | None = None
    recovery_action_id: NamespacedId | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _names_its_own_action(self) -> ComponentsRow:
        if self.recovery_action_id is not None and self.recovery_action_id != _RECOVERY_ACTION_PREFIX + self.item_id:
            raise ValueError("a row's button names its own item's setup action")
        return self

    @property
    def kind(self) -> DependencyItemKind:
        """The item this row is for."""
        return dependency_item_kind(self.item_id)

    def status_row(self) -> DependencyStatusRow:
        """Return the row in the shape the surfaces' wording reads, refusing a reason its state does not carry."""
        return DependencyStatusRow.model_validate(
            {**self.model_dump(mode="python"), "kind": self.kind},
            strict=True,
        )


class ComponentsLicence(BaseModel):
    """The licence a planned model comes under: its SPDX identifier and its own title, which a notice names."""

    model_config = STRICT_FROZEN_CONFIG

    spdx_id: _SpdxId
    name: _LicenceName


_PROGRAM_PART: Final = "program"


class ComponentsPlanPart(BaseModel):
    """One part of the local AI's plan: its program, or the model one role reads with and its licence."""

    model_config = STRICT_FROZEN_CONFIG

    part_id: _PartId
    download_bytes: NonNegativeInt | None
    source_hosts: tuple[DependencyHostName, ...] = Field(min_length=1)
    destination: ComponentsDestination | None
    installs_outside_program: bool
    target_version: _Version | None
    advisories: tuple[ModelSelectionAdvisory, ...]
    licence: ComponentsLicence | None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _a_model_names_its_licence(self) -> ComponentsPlanPart:
        if (self.part_id == _PROGRAM_PART) != (self.licence is None):
            raise ValueError("each model part names its licence, and the program part names none")
        return self


class ComponentsPlanEntry(BaseModel):
    """What setting up one item will do."""

    model_config = STRICT_FROZEN_CONFIG

    item_id: DependencyItemId
    download_bytes: NonNegativeInt | None
    source_hosts: tuple[DependencyHostName, ...] = Field(min_length=1)
    destination: ComponentsDestination | None
    installs_outside_program: bool
    target_version: _Version | None
    advisories: tuple[ModelSelectionAdvisory, ...]
    parts: tuple[ComponentsPlanPart, ...]


class ComponentsSpace(BaseModel):
    """Free space on the storage volume against what the plan needs; unmeasured space is never enough."""

    model_config = STRICT_FROZEN_CONFIG

    free_bytes: NonNegativeInt | None
    required_bytes: NonNegativeInt
    sufficient: bool


class ComponentsPlan(BaseModel):
    """The plan a setup asks the person to approve, with the totals and free space the digest leaves out."""

    model_config = STRICT_FROZEN_CONFIG

    contract_version: Literal[2]
    entries: tuple[ComponentsPlanEntry, ...] = Field(min_length=1)
    known_download_bytes: NonNegativeInt
    has_unknown_size: bool
    installs_outside_program: bool
    space: ComponentsSpace


class ComponentsStartedLine(BaseModel):
    """The first line: the protocol version and the command the role runs."""

    model_config = STRICT_FROZEN_CONFIG

    type: Literal["started"]
    protocol: Literal[1]
    command: ComponentsCommand


class ComponentsPhaseLine(BaseModel):
    """An item reached a step of its setup or check."""

    model_config = STRICT_FROZEN_CONFIG

    type: Literal["phase"]
    phase_code: _PhaseCode
    item_id: DependencyItemId
    step: DependencySetupStep

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _code_names_item_and_step(self) -> ComponentsPhaseLine:
        if self.phase_code != f"dependencies.setup.{self.item_id}.{self.step.value}":
            raise ValueError("a phase code names its own item and step")
        return self


class ComponentsProgressLine(BaseModel):
    """Bytes an item holds so far out of its whole known download."""

    model_config = STRICT_FROZEN_CONFIG

    type: Literal["progress"]
    subject_code: DependencyItemId
    unit_code: Literal["bytes"]
    completed: NonNegativeInt
    total: NonNegativeInt

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _completed_within_total(self) -> ComponentsProgressLine:
        if self.total == 0 or self.completed > self.total:
            raise ValueError("progress counts bytes of a known, nonzero total")
        return self


class ComponentsNoticeLine(BaseModel):
    """A notice: a retry, a wait for the local AI server, a followed setup, an acknowledged cancel, a refused input.

    A ``following`` notice names the item another process is setting up and the
    digest of the plan that setup was approved under.
    """

    model_config = STRICT_FROZEN_CONFIG

    type: Literal["notice"]
    notice_code: ComponentsNoticeCode
    subject_code: DependencyItemId | None = None
    attempt: Annotated[int, Field(ge=1)] | None = None
    delay_ms: NonNegativeInt | None = None
    plan_digest: _Sha256Hex | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _carries_its_facts(self) -> ComponentsNoticeLine:
        retrying = self.notice_code is ComponentsNoticeCode.RETRYING
        if retrying != (self.attempt is not None and self.delay_ms is not None):
            raise ValueError("a retry notice carries its attempt and wait, and only it does")
        following = self.notice_code is ComponentsNoticeCode.FOLLOWING
        if following != (self.plan_digest is not None):
            raise ValueError("a following notice carries the followed plan's digest, and only it does")
        about_item = self.notice_code in {
            ComponentsNoticeCode.RETRYING,
            ComponentsNoticeCode.WAITING_FOR_SERVER,
            ComponentsNoticeCode.FOLLOWING,
        }
        if about_item != (self.subject_code is not None):
            raise ValueError("a retry, a server wait or a followed setup names its item, and only they do")
        return self


class ComponentsReviewLine(BaseModel):
    """The plan a setup asks the person to approve, and the digest an approval binds."""

    model_config = STRICT_FROZEN_CONFIG

    type: Literal["review"]
    plan_digest: _Sha256Hex
    plan: ComponentsPlan


class ComponentsResultLine(BaseModel):
    """The last line: how the command ended, every item's row and, where they apply, its plan and failure.

    A refusal before the engine could start, and an unreadable command line,
    carry no rows and no mode. A cancelled setup names the item it stopped at
    and the ``cancelled`` category. A setup that followed another reports that
    setup's result for the items it followed, with no plan of its own, and
    ``busy`` when it stopped following first.
    """

    model_config = STRICT_FROZEN_CONFIG

    type: Literal["result"]
    command: ComponentsCommand | None
    outcome: ComponentsOutcome
    mode: DependencyCheckMode | None = None
    rows: tuple[ComponentsRow, ...] = ()
    setup_complete: bool | None = None
    plan: ComponentsPlan | None = None
    plan_digest: _Sha256Hex | None = None
    item_id: DependencyItemId | None = None
    failure_category: DependencyFailureCategory | None = None
    items: tuple[DependencyItemId, ...] | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _consistent(self) -> ComponentsResultLine:
        if (self.plan is None) != (self.plan_digest is None):
            raise ValueError("a plan and its digest are reported together")
        if (self.command is None) != (self.outcome is ComponentsOutcome.INVALID_REQUEST):
            raise ValueError("only an unreadable command line names no command")
        if len({row.item_id for row in self.rows}) != len(self.rows):
            raise ValueError("a result reports each item's row once")
        if self.failure_category is not None and self.outcome not in {
            ComponentsOutcome.REFUSED,
            ComponentsOutcome.FAILED,
            ComponentsOutcome.CANCELLED,
        }:
            raise ValueError("only a refusal, a failure or a cancellation names a failure category")
        if self.outcome is ComponentsOutcome.CANCELLED and self.failure_category not in {
            None,
            DependencyFailureCategory.CANCELLED,
        }:
            raise ValueError("a cancellation names only the cancelled category")
        return self

    def status_rows(self) -> tuple[DependencyStatusRow, ...]:
        """Return every row in the shape the surfaces' wording reads."""
        return tuple(row.status_row() for row in self.rows)


type ComponentsEvent = ComponentsPhaseLine | ComponentsProgressLine | ComponentsNoticeLine
"""A line the role writes while it works."""

type ComponentsLine = (
    ComponentsStartedLine
    | ComponentsPhaseLine
    | ComponentsProgressLine
    | ComponentsNoticeLine
    | ComponentsReviewLine
    | ComponentsResultLine
)
"""Any line the role writes."""

_LINE: Final[TypeAdapter[ComponentsLine]] = TypeAdapter(
    Annotated[
        ComponentsStartedLine
        | ComponentsPhaseLine
        | ComponentsProgressLine
        | ComponentsNoticeLine
        | ComponentsReviewLine
        | ComponentsResultLine,
        Field(discriminator="type"),
    ]
)


class ComponentsContractMismatchError(Exception):
    """The role speaks a protocol or plan contract version this client does not: it belongs to another build."""


_FIELDS: Final[TypeAdapter[dict[str, object]]] = TypeAdapter(dict[str, object])


def _speaks_another_version(document: bytes) -> bool:
    try:
        fields = _FIELDS.validate_json(document)
        plan = fields.get("plan")
        plan_fields = _FIELDS.validate_python(plan) if isinstance(plan, dict) else {}
    except ValidationError:
        return False
    if fields.get("type") == "started" and fields.get("protocol") != COMPONENTS_PROTOCOL_VERSION:
        return True
    return "contract_version" in plan_fields and plan_fields["contract_version"] != COMPONENTS_PLAN_CONTRACT_VERSION


def decode_components_line(line: bytes) -> ComponentsLine:
    """Decode one output line, newline included, refusing anything this protocol does not declare.

    Raises:
        RefusalError: ``INVALID_FRAME`` for a line over :data:`MAX_LINE_BYTES`,
            one without its newline, or one that is not exactly one declared line.
        ComponentsContractMismatchError: The line is a ``started`` line of another
            protocol version, or carries a plan of another contract version.
    """
    if len(line) > MAX_LINE_BYTES or not line.endswith(b"\n"):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    try:
        return _LINE.validate_json(line[:-1])
    except ValidationError:
        if _speaks_another_version(line[:-1]):
            raise ComponentsContractMismatchError from None
        raise RefusalError(RefusalCode.INVALID_FRAME) from None


class ComponentsApprove(BaseModel):
    """Approves exactly the reviewed plan; the role computes it again and refuses one that changed."""

    model_config = STRICT_FROZEN_CONFIG

    type: Literal["approve"] = "approve"
    plan_digest: _Sha256Hex


class ComponentsDecline(BaseModel):
    """Declines the reviewed plan; nothing moves."""

    model_config = STRICT_FROZEN_CONFIG

    type: Literal["decline"] = "decline"


type ComponentsAnswer = ComponentsApprove | ComponentsDecline
"""A person's answer to a review."""


def answer_line(answer: ComponentsAnswer) -> bytes:
    """Return the input line that sends ``answer``."""
    return answer.model_dump_json().encode("utf-8") + b"\n"
