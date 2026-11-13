"""Drive each return a canonical persona owes through the Modelo workbench, over the persona's real profile.

The persona is replayed into a registered profile by the persona materialisation
support, under every registry horizon the persona table replays it at. Each
return it owes there is created, then opened in the production workbench screen
in a Textual pilot, and the filer's own keys take it through calculate (``c``),
the check (``F8``), the file for the AEAT (``e``) and recording the filing
(``F8``), answering the dialogs the workbench opens. Every operation the
workbench submits runs through the production supervisor composed over the
persona's profile, and the modal observes its real settlement.

What the persona's operator states on a return outside those keys -- the values
entered before the first calculation, the prior carries and prior figures it
attests, the work-income statements -- is submitted by the materialisation
support through the same registered operations, between the key presses, as the
persona table does.

The figures read are the casilla values of the form the workbench holds after
its own read, and the stage outcomes are those the workbench settled: the
operation's terminal condition the modal observed, the check's verdict on the
form read afterwards, and the export result screen.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import re
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from functools import cache
from pathlib import Path
from typing import Final

from pydantic import BaseModel
from textual.pilot import Pilot
from textual.widgets import Button, Input, Select, Static

from ......application.modelo.export_projection import ModeloExportPublicResultV3
from ......application.modelo.m303_attestation_operation import (
    MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID,
    ModeloWorkM303AttestationPublicResultV2,
    ModeloWorkM303AttestationRequest,
)
from ......application.modelo.m303_exonerado_390_applicability_attestation import (
    M303Exonerado390ApplicabilityAttestationAdmission,
)
from ......application.modelo.work_calculation_contracts import ModeloWorkCalculatePublicResultV3
from ......application.modelo.work_create_operation import (
    MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
    ModeloWorkCreateProjection,
    ModeloWorkCreateRequest,
    ModeloWorkCreateSuccess,
)
from ......application.modelo.work_form_field_vocabulary import (
    ModeloFormCasillaAddressV1,
    ModeloFormOrigin,
    ModeloFormScalar,
)
from ......application.modelo.work_form_findings import ModeloFormAttention
from ......application.modelo.work_form_models import (
    ModeloFormRepeatingBlock,
    ModeloWorkForm,
)
from ......application.modelo.work_form_next_step import ModeloFormNextAction, applicable_fields
from ......application.modelo.workbench_read import ModeloWorkbenchFormReadV1
from ......application.operations.error_detail import OperationErrorDetailV1, operation_error_detail_schema
from ......application.operations.frontend_contracts import (
    OperationCancellationResultV1,
    OperationDetachResultV1,
    OperationReviewProjectionResultV1,
)
from ......application.operations.frontend_projection import (
    OperationPublicProjectionV1,
    OperationReviewProjectionReferenceV1,
)
from ......application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationResultV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ......application.operations.models import OperationId, OperationRequest, OperationRevision
from ......application.operations.public_period import PublicPeriod
from ......core.config import override_settings
from ......core.modelo_export_artefact import ModeloExportArtefact
from ......core.operations import OperationTerminalCondition
from ......core.period import Period
from ......domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ......domain.calculations.registry.bindings import binding_source_modelo
from ......domain.modelos.verification_report import VerificationCompletenessStatus
from ......domain.period import calculation_filing_date
from ......tests.personas import (
    ExpectedValue,
    Persona,
    PersonaCatalogueError,
    YearEnvelope,
    YearToken,
    filed_period_order,
    read_persona,
    values_in_force,
)
from .....tests.persona_materialisation import (
    PERSONA_ACTOR,
    MaterialisedPersona,
    PersonaMaterialisationError,
    PersonaWorld,
    ReplayScope,
    attest_before_first_calculation,
    enter_return_work_inputs,
    materialised_persona,
    public_result,
    run_operation,
    settle_operation,
    state_after_calculation,
    year_envelope,
)
from .....tests.persona_prior_carries import attest_prior_carries
from .....tests.persona_rental_carries import attest_pending_rental_carries
from ....components.dialogs import ConfirmScreen
from ....components.host import ScreenHostApp
from ....operations.controller_port import OperationResponseControlPort
from ....refusal.panel import RefusalSlot
from ....tests.modelo_workbench_session import (
    RecordedSubmissions,
    application_lifecycle_door,
    application_workbench,
    workbench_read_ports,
)
from ....tests.settling import settle, settle_until
from ...export_result import ModeloExportResultScreen
from ...lifecycle import ModeloWorkspaceLifecycleDoor
from ...m303_evidence import OrdinaryM303FilingEvidenceScreen
from ..export import WorkbenchExportScreen
from ..factory import InstalledModeloWorkbench
from ..result import WorkbenchResultScreen
from ..screen import ModeloWorkbenchScreen

OUT_ENV: Final = "PERSONA_PILOT_OUT"
"""The JSON-lines file each pilot appends its rows to, when set."""
TREE_ENV: Final = "PERSONA_PILOT_TREE"
"""The commit the pilot ran, as the caller names it; the suite never asks version control."""
LOG_ENV: Final = "PERSONA_PILOT_LOG"
"""The path of the run log, as the caller names it."""

_SIZE: Final = (200, 60)
#: A calculation of a dense annual return over a full ledger takes well over the default settle wait.
_OPERATION_WAIT: Final = 900.0
_TUI_ACTOR: Final = "operator:tui-modelo"
_LAST_QUARTER: Final = "4T"


# -- the returns a persona owes, per replay horizon ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PilotReturn:
    """One return of a persona's replay under one horizon, and the stated values in force for it."""

    persona: str
    modelo: str
    year: int
    period: str
    horizon: int
    owed: bool
    values: tuple[ExpectedValue, ...]
    grounding: str

    @property
    def key(self) -> tuple[str, int, str]:
        """The return's ``(modelo, year, period)``."""
        return (self.modelo, self.year, self.period)


@dataclass(frozen=True, slots=True)
class PilotReplay:
    """One horizon a persona is replayed at, every return it runs there in chain order, and those it reports."""

    horizon: int
    returns: tuple[PilotReturn, ...]
    reported: frozenset[tuple[str, int, str]]


@cache
def pilot_envelope() -> YearEnvelope:
    """The registry's supported filing-year envelope."""
    with bundled_indexed_authority().operation() as operation:
        return year_envelope(operation)


def _resolved(token: YearToken, envelope: YearEnvelope) -> int | None:
    try:
        return token.resolve(envelope)
    except PersonaCatalogueError:
        return None


def _persona_at(persona_id: str, horizon: int, envelope: YearEnvelope) -> Persona:
    shifted = dataclasses.replace(envelope, horizon=horizon)
    try:
        return read_persona(persona_id, envelope=shifted, omit_below_floor=horizon != envelope.horizon)
    except PersonaCatalogueError:
        return read_persona(persona_id, envelope=envelope)


@cache
def _period_end(year: int, period: str) -> date:
    with bundled_indexed_authority().operation() as operation:
        return calculation_filing_date(Period.from_year_and_code(year, period), authority=operation)


def _chain_order(key: tuple[str, int, str]) -> tuple[int, int, int, str]:
    """Quarters and instalments before annual returns, by the end of their period, then by modelo."""
    modelo, year, period = key
    try:
        position = filed_period_order(period)
    except ValueError:
        position = filed_period_order(_LAST_QUARTER)
    try:
        ends = _period_end(year, period).toordinal()
    except ValueError:
        ends = 0
    return (year, position, ends, modelo)


def _grounding(values: Sequence[ExpectedValue]) -> str:
    if not values:
        return "none"
    for grounding in ("unverified", "cited", "verified"):
        if any(value.grounding == grounding for value in values):
            return grounding
    return values[0].grounding


def owed_returns(persona_id: str, horizon: int, envelope: YearEnvelope) -> list[PilotReturn]:
    """The returns the persona owes when replayed under ``horizon``, in chain order, as the persona table plans them.

    A return is owed when an obligation states it applicable, the persona's history files or calculates it, or a
    value is stated for it and no obligation states it not applicable. A return an obligation states not applicable
    that the persona states values for is a return with ``owed`` false. Only returns whose period ended before the
    persona's scenario day are taken.
    """
    persona = _persona_at(persona_id, horizon, envelope)
    shifted = dataclasses.replace(envelope, horizon=horizon)
    inside = tuple(value for value in persona.expectations.values if _resolved(value.year, shifted) is not None)
    stated: dict[tuple[str, int, str], list[ExpectedValue]] = {}
    for year, value in values_in_force(inside, shifted):
        found = stated.setdefault((value.modelo, year, value.period), [])
        if (
            value.casillas
            or value.roles
            or value.not_sourced
            or value.refusal is not None
            or value.counterparty is not None
        ):
            found.append(value)

    def obligations(*, applicable: bool) -> set[tuple[str, int, str]]:
        return {
            (item.modelo, year, period)
            for item in persona.expectations.obligations
            if item.applicable is applicable and (year := _resolved(item.year, shifted)) is not None
            for period in item.periods
        }

    history = {
        (block.modelo, year, period)
        for block in (*persona.filed_returns, *persona.calculated_returns)
        if (year := _resolved(block.year, shifted)) is not None
        for period in block.periods
    }
    not_applicable = obligations(applicable=False)
    owed = obligations(applicable=True) | history
    not_owed = ({key for key, found in stated.items() if found} & not_applicable) - owed
    keys = owed | (set(stated) - not_applicable) | not_owed
    today = persona.as_of.resolve(shifted)
    returns: list[PilotReturn] = []
    for key in sorted(keys, key=_chain_order):
        modelo, year, period = key
        if _period_end(year, period) >= today:
            continue
        values = tuple(stated.get(key, ()))
        returns.append(
            PilotReturn(
                persona=persona_id,
                modelo=modelo,
                year=year,
                period=period,
                horizon=horizon,
                owed=key not in not_owed,
                values=values,
                grounding=_grounding(values),
            )
        )
    return returns


def pilot_replays(persona_id: str, envelope: YearEnvelope) -> list[PilotReplay]:
    """Every horizon the persona's returns are reported at, newest first, each return at the newest that owes it.

    A replay runs its returns in chain order up to the last one it reports, since a later return reads the earlier
    ones filed locally and an earlier one reads nothing later.
    """
    replays: list[PilotReplay] = []
    taken: set[tuple[str, int, str]] = set()
    for horizon in range(envelope.horizon, envelope.floor - 1, -1):
        returns = owed_returns(persona_id, horizon, envelope)
        reported = frozenset(item.key for item in returns if item.key not in taken)
        if not reported:
            continue
        taken |= reported
        last = max(index for index, item in enumerate(returns) if item.key in reported)
        replays.append(PilotReplay(horizon=horizon, returns=tuple(returns[: last + 1]), reported=reported))
    return replays


@cache
def _sources(modelo: str) -> frozenset[str]:
    """Every modelo a revision of ``modelo`` reads, as its bindings and dependency classifications declare."""
    with bundled_indexed_authority().operation() as operation:
        revisions = [
            operation.revision(owner, revision_id) for owner, revision_id in operation.revision_ids() if owner == modelo
        ]
    return frozenset(
        {
            str(source)
            for revision in revisions
            for binding in revision.bindings
            if (source := binding_source_modelo(binding)) is not None
        }
        | {
            str(classification.source_modelo)
            for revision in revisions
            for classification in revision.dependency_classifications
        }
    )


def replay_scope(persona: Persona) -> ReplayScope:
    """The records scope when the persona holds a return history, else the full ledger, as the persona table takes."""
    if persona.filed_returns or persona.calculated_returns or persona.local_observations or persona.aeat_filings:
        return ReplayScope.RECORDS
    return ReplayScope.FULL


# -- the persona's profile as the workbench's runtime ---------------------------------------------------------------


class WorldOperation:
    """One workbench submission, settled by the production supervisor over the persona's profile.

    The supervisor runs on its own event loop off the app's, so a long calculation never stalls the pilot; the
    modal then observes the settled operation through the profile's observation and result services.
    """

    def __init__(self, world: PersonaWorld, operation_id: OperationId) -> None:
        """Bind the settled operation to the profile it ran on."""
        self._world = world
        self._operation_id = operation_id
        self.terminal: OperationPublicProjectionV1 | None = None

    @property
    def operation_id(self) -> OperationId:
        """The supervisor's identity of the operation."""
        return self._operation_id

    @property
    def actor_ref(self) -> str:
        """The actor the workbench submits as."""
        return _TUI_ACTOR

    async def start(self) -> OperationId:
        """The operation was admitted and run when it was submitted."""
        return self._operation_id

    async def observe(self, after_cursor: int, *, page_limit: int = 256) -> OperationObservationResultV1:
        """Read the operation's projection and events from the profile's observation service."""
        request = OperationObservationRequestV1(
            operation_id=self._operation_id, after_cursor=after_cursor, page_limit=page_limit
        )
        observation = self._world.services.observation

        def observe() -> OperationObservationResultV1:
            return asyncio.run(observation.observe(request))

        observed = await asyncio.to_thread(observe)
        if isinstance(observed, OperationObservationSuccessV1):
            self.terminal = observed.projection
        return observed

    async def settled_error_detail(self, projection: OperationPublicProjectionV1) -> OperationErrorDetailV1 | None:
        """Read the refusal or failure detail the operation recorded, as the runtime's result door serves it."""
        contract = projection.definition_contract
        request = OperationResultProjectionRequestV1(
            operation_id=projection.operation_id,
            terminal_revision=projection.revision,
            definition_contract_digest=contract.definition_contract_digest,
            result_schema=operation_error_detail_schema(),
        )
        resolved = await asyncio.to_thread(
            asyncio.run, self._world.services.result.resolve(request, OperationErrorDetailV1)
        )
        if not isinstance(resolved, OperationResultProjectionSuccessV1):
            return None
        detail = resolved.projection
        return detail if isinstance(detail, OperationErrorDetailV1) else None

    async def resolve_review[ReviewT: BaseModel](
        self, reference: OperationReviewProjectionReferenceV1, projection_type: type[ReviewT]
    ) -> OperationReviewProjectionResultV1[ReviewT]:
        """No workbench lifecycle operation this pilot runs presents a review."""
        raise AssertionError("a workbench lifecycle operation presents no review")

    async def response_control(
        self, *, interaction_id: str, revision: OperationRevision
    ) -> OperationResponseControlPort:
        """No workbench lifecycle operation this pilot runs asks a response."""
        raise AssertionError("a workbench lifecycle operation asks no response")

    async def cancel(self, *, expected_revision: OperationRevision) -> OperationCancellationResultV1:
        """The pilot never cancels a settled operation."""
        raise AssertionError("the pilot never cancels")

    async def detach(self, *, expected_revision: OperationRevision) -> OperationDetachResultV1:
        """The pilot never detaches a settled operation."""
        raise AssertionError("the pilot never detaches")


@dataclass
class WorldSubmissions:
    """Every operation the workbench submitted to the persona's profile, in order."""

    world: PersonaWorld
    operations: list[tuple[OperationRequest[BaseModel], WorldOperation]] = field(default_factory=list)

    def _settle(self, request: OperationRequest[BaseModel]) -> OperationId:
        async def settled() -> OperationId:
            submission = self.world.services.submission
            submitted = await submission.submit(request, actor_ref=_TUI_ACTOR)
            operation_id = submitted.receipt.operation_id
            await submission.start(operation_id)
            await submission.settled(operation_id)
            return operation_id

        return asyncio.run(settled())

    async def submit(self, request: OperationRequest[BaseModel]) -> WorldOperation:
        """Submit, start and settle one workbench request through the production supervisor."""
        operation_id = await asyncio.to_thread(self._settle, request)
        operation = WorldOperation(self.world, operation_id)
        self.operations.append((request, operation))
        return operation

    def latest(self) -> WorldOperation | None:
        """The operation submitted last, if any."""
        return self.operations[-1][1] if self.operations else None


def _m303_admission(
    world: PersonaWorld, work_unit_id: str
) -> Callable[[datetime], M303Exonerado390ApplicabilityAttestationAdmission]:
    """Admit the Modelo 390 exemption attestation the evidence dialog asks, as the runtime's door does."""

    def admit(observed_at: datetime) -> M303Exonerado390ApplicabilityAttestationAdmission:
        request = ModeloWorkM303AttestationRequest(
            profile_id=world.profile_id, work_unit_id=work_unit_id, observed_at=observed_at, actor=PERSONA_ACTOR
        )
        attested = run_operation(
            world,
            MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID,
            request,
            ModeloWorkM303AttestationPublicResultV2,
            subject=request.subject_ref,
        )
        return M303Exonerado390ApplicabilityAttestationAdmission(
            attachment_id=attested.attachment_id, sha256=attested.sha256
        )

    return admit


def world_workbench(world: PersonaWorld, work_unit_id: str) -> tuple[InstalledModeloWorkbench, WorldSubmissions]:
    """The production workbench of one stored declaration, acting through the supervisor over the persona's profile."""
    bucket_id = str(world.profile_id)
    operation = world.operation
    ports = workbench_read_ports(bucket_id, operation)
    unit = ports.work_units.load().work_units[work_unit_id]
    submissions = WorldSubmissions(world)
    contracts = world.registry.public_contract_set

    async def export_result(projection: OperationPublicProjectionV1) -> ModeloExportPublicResultV3:
        result = await asyncio.to_thread(public_result, world, projection)
        if not isinstance(result, ModeloExportPublicResultV3):
            raise TypeError(f"the export published {type(result).__name__}")
        return result

    def door(read: ModeloWorkbenchFormReadV1 | None) -> ModeloWorkspaceLifecycleDoor:
        base = application_lifecycle_door(
            work_unit_id=work_unit_id,
            bucket_id=bucket_id,
            ports=ports,
            operation=operation,
            contracts=contracts,
            submissions=RecordedSubmissions(),
            read=read,
        )
        return dataclasses.replace(
            base,
            submit_operation=submissions.submit,
            read_export_result=export_result,
            m303_exonerado_390_attestation_admission=_m303_admission(world, work_unit_id),
            profile_id=world.profile_id,
        )

    return application_workbench(unit, operation=operation, door_override=door), submissions


# -- one row of the frontend column ---------------------------------------------------------------------------------

PASSED: Final = "pass"
INCOMPLETE: Final = "incomplete"
REFUSED: Final = "refused"
NOT_OWED: Final = "not-owed"
NOT_REACHED: Final = "not-reached"
ERROR: Final = "error"


@dataclass
class PilotRow:
    """One line of the frontend column: a persona-level line when ``modelo`` is ``None``, else one return."""

    persona: str
    modelo: str | None = None
    year: int | None = None
    period: str | None = None
    loads: bool = True
    calculate: str | None = None
    verify: str | None = None
    export: str | None = None
    refusal_code: str | None = None
    figures: dict[str, str] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    differences: list[str] = field(default_factory=list)
    """Each stated casilla the workbench shows otherwise, as ``<label> expected <x> shown <y>``."""
    seconds: float = 0.0
    next_step: ModeloFormNextAction | None = None
    """The action the form served next where the workbench did not offer the check."""
    filed: bool = False
    """Whether the workbench recorded the return filed locally, so later returns read it filed."""
    cause: str | None = None
    """The one cause key of a row that differs from the persona table; ``None`` for a matched row."""
    cause_words: str = ""

    @property
    def label(self) -> str:
        """``persona modelo year period``, as a failure names the row."""
        return f"{self.persona} {self.modelo} {self.year} {self.period}"

    def reason(self) -> str:
        """The row's free text: its cause key, the differing casillas, what each stage said, then its time."""
        parts = [f"cause={self.cause}; {self.cause_words}".rstrip("; ")] if self.cause is not None else []
        parts += [f"differs: {'; '.join(self.differences)}"] if self.differences else []
        parts += self.reasons
        if self.modelo is not None:
            parts.append(f"{self.seconds:.1f}s in the workbench")
        return " | ".join(part for part in parts if part)

    def line(self, *, tree: str, log: str) -> str:
        """The row as one JSON line of the frontend intake, with exactly its keys."""
        return json.dumps(
            {
                "surface": "tui",
                "tree": tree,
                "persona": self.persona,
                "modelo": self.modelo,
                "year": self.year,
                "period": self.period,
                "loads": self.loads,
                "calculate": self.calculate,
                "verify": self.verify,
                "export": self.export,
                "refusal_code": self.refusal_code,
                "figures": self.figures,
                "reason": self.reason(),
                "log": log,
            },
            ensure_ascii=False,
        )


def write_rows(rows: Iterable[PilotRow]) -> None:
    """Append ``rows`` to the file :data:`OUT_ENV` names, when it names one."""
    out = os.environ.get(OUT_ENV, "")
    if not out:
        return
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    tree = os.environ.get(TREE_ENV, "")
    log = os.environ.get(LOG_ENV, "")
    # One write per call, so personas run in parallel workers append whole lines.
    text = "".join(row.line(tree=tree, log=log) + "\n" for row in rows)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)


# -- what the workbench shows ---------------------------------------------------------------------------------------


def _nonzero(value: ModeloFormScalar) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, Decimal | int):
        return value != 0
    return str(value).strip() != ""


def shown_figures(form: ModeloWorkForm) -> dict[str, ModeloFormScalar]:
    """Every casilla value the form shows, by casilla id; a repeated row's column only where one row holds it.

    A column of a group with exactly one row gives the casilla its figure where the scalar box shows none or zero, as
    the persona table reads a let property's single row; several rows give no single figure.
    """
    shown: dict[str, ModeloFormScalar] = {}
    for item in form.fields():
        address = item.address
        if isinstance(address, ModeloFormCasillaAddressV1):
            shown.setdefault(str(address.casilla_id), item.value)
    for page in form.pages:
        for section in page.sections:
            for block in section.blocks:
                if not isinstance(block, ModeloFormRepeatingBlock) or len(block.rows) != 1:
                    continue
                (row,) = block.rows
                for casilla, value in zip(block.column_casilla_ids, row.values, strict=False):
                    if casilla is not None and not _nonzero(shown.get(casilla)):
                        shown[casilla] = value
    return shown


def _decimal(value: object) -> Decimal | None:
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def stated_casillas(
    values: Sequence[ExpectedValue], operation: PinnedAuthorityOperation, form: ModeloWorkForm
) -> list[tuple[str, str | None, str]]:
    """Each stated amount as ``(label, casilla, amount)``; a role resolves in the edition the form shows.

    A role names the one casilla of the edition whose ``continuidad_id`` equals it, else whose ``semantic_role``
    does; none or several leave it unresolved, compared against no value.
    """
    casillas = (
        operation.revision(str(form.modelo), str(form.registry_revision_id)).casillas
        if any(value.roles for value in values)
        else ()
    )
    stated: list[tuple[str, str | None, str]] = []
    for value in values:
        stated += [(f"c{casilla}", casilla, amount) for casilla, amount in value.casillas]
        for key, amount in value.roles:
            matches = [str(item.id) for item in casillas if item.continuidad_id == key] or [
                str(item.id) for item in casillas if item.semantic_role == key
            ]
            casilla = matches[0] if len(matches) == 1 else None
            stated.append((f"role {key} (casilla {casilla})", casilla, amount))
    return stated


def casilla_differences(
    values: Sequence[ExpectedValue],
    shown: Mapping[str, ModeloFormScalar],
    operation: PinnedAuthorityOperation,
    form: ModeloWorkForm,
) -> list[str]:
    """Each stated casilla the form shows with another value, or not at all."""
    found: list[str] = []
    for label, casilla, amount in stated_casillas(values, operation, form):
        value = None if casilla is None else shown.get(casilla)
        if _decimal(value) != _decimal(amount):
            found.append(f"{label} expected {amount} shown {value}")
    return found


# -- the keys the filer presses -------------------------------------------------------------------------------------


@dataclass
class _Session:
    """One open workbench over one declaration, and what the pilot reads off it."""

    pilot: Pilot[None]
    screen: ModeloWorkbenchScreen
    submissions: WorldSubmissions
    plan: PilotReturn
    export_path: Path
    exported: ModeloExportPublicResultV3 | None = None
    export_shown: bool = False
    export_withheld: str = ""

    def notice(self) -> str:
        """The workbench's notice line."""
        return " ".join(str(self.screen.query_one("#wb-notice", Static).render()).split())

    def refusal(self) -> str:
        """The refusal sentence the workbench shows beneath its notice, if any."""
        slot = next(iter(self.screen.query("#wb-operation-refusal").results(RefusalSlot)), None)
        if slot is None or slot.refusal is None:
            return ""
        return " ".join((slot.refusal.sentence or "").split())

    def next_action(self) -> ModeloFormNextAction | None:
        """The next step the workbench's stepper offers."""
        load = self.screen._load
        return None if load is None else self.screen._progress(load).next_action

    async def press(self, key: str) -> WorldOperation | None:
        """Press ``key`` and answer every dialog it opens; the operation it submitted, or ``None`` for none."""
        before = len(self.submissions.operations)
        await self.pilot.press(key)
        await self.quiet()
        return self.submissions.latest() if len(self.submissions.operations) > before else None

    async def quiet(self) -> None:
        """Answer every dialog the workbench opens until it stands alone with nothing in flight."""
        app = self.pilot.app
        for _ in range(32):
            await settle(self.pilot, timeout=_OPERATION_WAIT)
            shown = app.screen
            if isinstance(shown, ConfirmScreen):
                await self.pilot.press("y")
            elif isinstance(shown, OrdinaryM303FilingEvidenceScreen):
                self._answer_m303(shown)
            elif isinstance(shown, WorkbenchExportScreen):
                self._answer_export(shown)
            elif isinstance(shown, ModeloExportResultScreen):
                result = shown._result
                self.exported = result if isinstance(result, ModeloExportPublicResultV3) else None
                self.export_shown = True
                await self.pilot.press("escape")
            elif isinstance(shown, WorkbenchResultScreen):
                await self.pilot.press("escape")
            elif isinstance(shown, ModeloWorkbenchScreen) and not self.screen._operation_in_flight:
                return
            else:
                await settle_until(self.pilot, lambda: True, "the workbench to settle", timeout=_OPERATION_WAIT)
        raise AssertionError(f"the workbench never came to rest; it shows {type(app.screen).__name__}")

    def _answer_m303(self, dialog: OrdinaryM303FilingEvidenceScreen) -> None:
        """No joint return; where the period asks the Modelo 390 exemption, its attestation observed at year end."""
        dialog.query_one("#m303-evidence-joint-return-elected", Select).value = "false"
        for entry in dialog.query("#m303-evidence-observed-at").results(Input):
            entry.value = datetime(self.plan.year, 12, 31, 12, tzinfo=UTC).isoformat()
        dialog.query_one("#m303-evidence-submit", Button).press()

    def _answer_export(self, dialog: WorkbenchExportScreen) -> None:
        """Ask for the file for the AEAT at the pilot's path, each settlement question at the default it served.

        When the dialog does not offer that file, the dialog is cancelled and the artefacts it offered are noted.
        """
        artefact = dialog.query_one("#export-artefact", Select)
        offered = [str(value) for _, value in artefact._options if value is not Select.NULL]
        if ModeloExportArtefact.FICHERO_BOE.value not in offered:
            self.export_withheld = f"the export dialog offers only {', '.join(offered)}"
            dialog.query_one("#export-cancel", Button).press()
            return
        artefact.value = ModeloExportArtefact.FICHERO_BOE.value
        dialog.query_one("#export-path", Input).value = str(self.export_path)
        dialog.query_one("#export-submit", Button).press()


def _code(terminal: OperationPublicProjectionV1 | None) -> str | None:
    if terminal is None:
        return None
    if terminal.terminal_condition is OperationTerminalCondition.REFUSED:
        return terminal.refusal_ref
    return terminal.failure_error_code


def _settled_stage(terminal: OperationPublicProjectionV1 | None) -> str:
    if terminal is None:
        return ERROR
    if terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED:
        return PASSED
    if terminal.terminal_condition is OperationTerminalCondition.REFUSED:
        return REFUSED
    return ERROR


@dataclass(frozen=True, slots=True)
class _Hooks:
    """What the persona's operator states on the return between the workbench's key presses."""

    before_calculate: Callable[[], None]
    after_calculate: Callable[[ModeloWorkCalculatePublicResultV3], bool]
    """Make the statements the calculation offers; whether the return must be calculated again to read them."""
    after_settled_calculation: Callable[[], bool]
    """Make the statements that need a settled calculation; whether the return must be calculated again."""


async def _press_calculate(session: _Session, hooks: _Hooks, row: PilotRow) -> ModeloWorkCalculatePublicResultV3 | None:
    """Press ``c`` once; the calculation the workbench settled, or ``None`` with the reason in ``row``."""
    await asyncio.to_thread(hooks.before_calculate)
    operation = await session.press("c")
    terminal = None if operation is None else operation.terminal
    stage = _settled_stage(terminal)
    row.calculate = stage
    if operation is None:
        row.reasons.append(f"calculate: the workbench submitted nothing: {session.notice()}")
        return None
    if stage != PASSED or terminal is None:
        row.refusal_code = _code(terminal)
        row.reasons.append(f"calculate: {row.refusal_code} {session.refusal() or session.notice()}")
        return None
    calculated = await asyncio.to_thread(public_result, session.submissions.world, terminal)
    if not isinstance(calculated, ModeloWorkCalculatePublicResultV3):
        row.calculate = ERROR
        row.reasons.append(f"calculate: published {type(calculated).__name__}")
        return None
    return calculated


async def _calculate_round(session: _Session, hooks: _Hooks, row: PilotRow) -> bool:
    """Calculate, and once more when the persona then states what the calculation offers, as the table does."""
    calculated = await _press_calculate(session, hooks, row)
    if calculated is None:
        return False
    if await asyncio.to_thread(hooks.after_calculate, calculated):
        return await _press_calculate(session, hooks, row) is not None
    return True


async def _calculate(session: _Session, hooks: _Hooks, row: PilotRow) -> bool:
    """Calculate with ``c``; again once the persona states what needs a settled calculation; whether it settled."""
    if not await _calculate_round(session, hooks, row):
        return False
    if await asyncio.to_thread(hooks.after_settled_calculation):
        return await _calculate_round(session, hooks, row)
    return True


def _to_fill(form: ModeloWorkForm | None) -> str:
    """What the form asks the filer to fill in: boxes that need input, then missing values only a note or finding names."""
    if form is None:
        return ""
    boxes = [
        str(getattr(item.address, "casilla_id", None) or getattr(item.address, "binding_id", "?"))
        for item in applicable_fields(form)
        if item.origin is ModeloFormOrigin.NEEDS_INPUT
    ]
    notes = [
        f"note {note.reason}/MISSING box {note.box or '-'} withholds_filing={str(note.withholds_filing).lower()}"
        + (f" fact {note.fact.sentence}" if note.fact is not None else "")
        for note in form.calculation_notes
        if note.attention is ModeloFormAttention.MISSING
    ]
    findings = [
        f"finding {issue.finding.casilla_id or '-'} {issue.finding.message_locale_key.rsplit('.', 1)[-1]}"
        for issue in form.issues
        if issue.attention is ModeloFormAttention.MISSING
    ]
    return ", ".join(dict.fromkeys([*boxes, *notes, *findings]))


async def _verify(session: _Session, row: PilotRow) -> None:
    action = session.next_action()
    if action is not ModeloFormNextAction.VERIFY:
        row.verify = NOT_REACHED
        row.next_step = action
        to_fill = _to_fill(session.screen.form) if action is ModeloFormNextAction.FILL else ""
        row.reasons.append(
            f"verify: not reached through the TUI: the served next action is {action}, ahead of VERIFY"
            + (f" (missing: {to_fill}; work_form_next_step.py _remaining_review_step)" if to_fill else "")
            + f": {session.notice()}"
        )
        return
    operation = await session.press("f8")
    terminal = None if operation is None else operation.terminal
    stage = _settled_stage(terminal)
    form = session.screen.form
    if stage == PASSED and form is not None:
        stage = PASSED if form.verification is VerificationCompletenessStatus.COMPLETE else INCOMPLETE
    row.verify = stage
    if stage != PASSED:
        row.refusal_code = row.refusal_code or _code(terminal)
        row.reasons.append(f"verify: {form.verification if form else None} {session.refusal() or session.notice()}")


async def _export(session: _Session, row: PilotRow) -> None:
    operation = await session.press("e")
    if operation is None:
        row.export = REFUSED
        row.reasons.append(f"export: withheld by the workbench: {session.export_withheld or session.notice()}")
        return
    terminal = operation.terminal
    stage = _settled_stage(terminal)
    if stage == PASSED and session.exported is None:
        stage = ERROR
        row.reasons.append("export: the result screen showed no result")
    row.export = stage
    if stage == PASSED and session.exported is not None:
        result = session.exported
        row.reasons.append(f"export: {result.export_format}, {result.byte_size} B, {result.completeness}")
    elif stage != PASSED:
        row.refusal_code = row.refusal_code or _code(terminal)
        row.reasons.append(f"export: {_code(terminal)} {session.refusal() or session.notice()}")


async def _record(session: _Session, row: PilotRow) -> None:
    """Record the filing locally where the stepper offers it, so later returns read it filed."""
    if session.next_action() is not ModeloFormNextAction.RECORD_AFTER_FILE:
        row.reasons.append(f"file: not offered ({session.next_action()})")
        return
    operation = await session.press("f8")
    terminal = None if operation is None else operation.terminal
    if _settled_stage(terminal) == PASSED:
        row.filed = True
        row.reasons.append("filed locally")
    else:
        row.reasons.append(f"file: {_code(terminal)} {session.refusal() or session.notice()}")


async def _drive(
    installed: InstalledModeloWorkbench,
    submissions: WorldSubmissions,
    plan: PilotReturn,
    hooks: _Hooks,
    export_path: Path,
    row: PilotRow,
) -> None:
    screen = ModeloWorkbenchScreen(installed, actions=installed)
    app = ScreenHostApp(screen)
    async with app.run_test(size=_SIZE) as pilot:
        await settle_until(
            pilot, lambda: screen.form is not None, "the workbench to read its declaration", timeout=_OPERATION_WAIT
        )
        session = _Session(pilot=pilot, screen=screen, submissions=submissions, plan=plan, export_path=export_path)
        calculated = await _calculate(session, hooks, row)
        form = screen.form
        if form is not None and form.calculation_revision_id is not None:
            world = submissions.world
            shown = shown_figures(form)
            row.figures = {casilla: str(value) for casilla, value in sorted(shown.items()) if _nonzero(value)}
            compared = [value for value in plan.values if value.counterparty is None]
            row.differences = casilla_differences(compared, shown, world.operation, form)
            if len(compared) != len(plan.values):
                row.reasons.append("counterparty values are compared in the written file only, not by this pilot")
        if not calculated:
            row.verify = row.verify or NOT_REACHED
            row.export = row.export or NOT_REACHED
        elif not plan.owed:
            row.verify = NOT_REACHED
            row.export = NOT_REACHED
            row.reasons.append(
                "not owed: the overview calendar suppresses it as not applicable, but the TUI shows nothing for it: its"
                " Declarations calendar is built without suppressed entries (build_overview_calendar show_suppressed"
                " False; DeclarationsCalendarProjectionV1 carries no suppressed rows), and the workbench calculates it"
            )
        else:
            await _verify(session, row)
            await _export(session, row)
            await _record(session, row)
        app.exit(None)


# -- one persona ----------------------------------------------------------------------------------------------------

_SETTLED = re.compile(r"^(?P<definition>\S+) settled (?P<condition>\S+) \((?P<code>[^)]*)\)")


def _refused_before_workbench(row: PilotRow, error: PersonaMaterialisationError, where: str) -> PilotRow:
    match = _SETTLED.match(str(error))
    row.calculate = REFUSED if match is not None else ERROR
    row.verify = NOT_REACHED
    row.export = NOT_REACHED
    row.refusal_code = None if match is None else match["code"] or None
    row.reasons.append(f"{where}: {' '.join(str(error).split())[:600]}")
    return row


def _create(world: PersonaWorld, plan: PilotReturn) -> str:
    created = settle_operation(
        world,
        MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
        ModeloWorkCreateRequest(
            profile_id=world.profile_id,
            modelo=plan.modelo,
            period=PublicPeriod(filing_year=plan.year, code=plan.period),
            actor=PERSONA_ACTOR,
        ),
    )
    if not isinstance(created, ModeloWorkCreateProjection) or not isinstance(created.outcome, ModeloWorkCreateSuccess):
        outcome = getattr(created, "outcome", None)
        raise PersonaMaterialisationError(f"create refused: {getattr(outcome, 'reason', type(created).__name__)}")
    return created.outcome.unit.work_unit_id


def _hooks(materialised: MaterialisedPersona, plan: PilotReturn, work_unit_id: str) -> _Hooks:
    world = materialised.world
    entered: list[bool] = []

    def before_calculate() -> None:
        if world.work_inputs and not entered:
            enter_return_work_inputs(world, work_unit_id)
            entered.append(True)

    def after_settled_calculation() -> bool:
        return plan.modelo == "100" and attest_pending_rental_carries(
            materialised.persona, world, work_unit_id, plan.year
        )

    return _Hooks(
        before_calculate=before_calculate,
        after_calculate=lambda calculated: state_after_calculation(world, calculated),
        after_settled_calculation=after_settled_calculation,
    )


def run_return(materialised: MaterialisedPersona, plan: PilotReturn, exports: Path) -> PilotRow:
    """Create the return, state what the persona states before calculating it, then drive it through the workbench."""
    started = time.monotonic()
    world = materialised.world
    row = PilotRow(persona=plan.persona, modelo=plan.modelo, year=plan.year, period=plan.period)
    try:
        work_unit_id = _create(world, plan)
    except PersonaMaterialisationError as error:
        return _refused_before_workbench(row, error, "create")
    try:
        if plan.modelo == "100":
            attest_prior_carries(materialised.persona, world, work_unit_id, plan.year)
        attest_before_first_calculation(
            world, modelo=plan.modelo, year=plan.year, period=plan.period, work_unit_id=work_unit_id
        )
    except PersonaMaterialisationError as error:
        return _refused_before_workbench(row, error, "statement before calculating")
    installed, submissions = world_workbench(world, work_unit_id)
    exports.mkdir(parents=True, exist_ok=True)
    export_path = exports / f"{plan.persona}-{plan.modelo}-{plan.year}-{plan.period}.txt"
    try:
        with override_settings(cadrumo_output_language="en"):
            asyncio.run(
                _drive(installed, submissions, plan, _hooks(materialised, plan, work_unit_id), export_path, row)
            )
    except PersonaMaterialisationError as error:
        row.calculate = row.calculate if row.calculate not in {None, PASSED} else ERROR
        row.reasons.append(f"statement after calculating: {' '.join(str(error).split())[:600]}")
    row.verify = row.verify or NOT_REACHED
    row.export = row.export or NOT_REACHED
    row.seconds = time.monotonic() - started
    return row


#: Refusals a return meets because an earlier return of its chain is not filed or not checked.
_CHAIN_REFUSALS: Final = frozenset({"REFUSED_MODELO_PRIOR_PERIOD_UNFILED", "REFUSED_MODELO_CROSS_PERIOD_CLEAN_STATE"})
_EDIT_REFUSED: Final = "REFUSED_MODELO_EDIT_REFUSED"
_REACHED: Final = frozenset({PASSED, INCOMPLETE, REFUSED})


def _matched(plan: PilotReturn, row: PilotRow) -> bool:
    """Whether the row settles as the persona table settles the return, as far as the workbench can show it.

    A grounded owed return calculates, checks complete and exports. A return whose values the persona leaves
    unverified matches once the check and the export reached their own verdict, which the table records as the
    application gives it. A return stated not owed never matches: the workbench does not show that verdict.
    """
    if row.differences or row.calculate != PASSED or not plan.owed:
        return False
    if plan.grounding == "unverified":
        return row.verify in _REACHED and row.export in _REACHED
    return row.verify == PASSED and row.export == PASSED


def _upstream(plan: PilotReturn, row: PilotRow, earlier: Sequence[tuple[PilotReturn, PilotRow]]) -> str | None:
    """The cause key of the first earlier return of its year the return reads that the workbench did not file.

    A return reads the same year's earlier returns of the other modelos its revisions source, and its own modelo's
    earlier periods where its refusal names the chain. Returns the table does not file either (not owed, unverified)
    are not counted.
    """
    reads = _sources(plan.modelo) - {plan.modelo}
    if row.refusal_code in _CHAIN_REFUSALS:
        reads |= {plan.modelo}
    for before, before_row in earlier:
        if (
            before.year != plan.year
            or before.modelo not in reads
            or not before.owed
            or before.grounding == "unverified"
            or before_row.filed
        ):
            continue
        cause = before_row.cause or "other:file_not_recorded"
        key = cause if cause.startswith("upstream:") else f"upstream:{cause}"
        row.cause_words = f"{before.modelo} {before.year} {before.period} is not filed through the TUI ({cause})"
        return key
    return None


def row_cause(plan: PilotReturn, row: PilotRow, earlier: Sequence[tuple[PilotReturn, PilotRow]]) -> str | None:
    """The one cause key of a row that differs from the persona table, or ``None`` for a matched row.

    An edit refused before calculating is its own cause; a return of a chain whose earlier return the workbench
    did not file carries that return's cause as ``upstream:<key>``; otherwise the row's own first defect names it.
    """
    if _matched(plan, row):
        return None
    if row.refusal_code == _EDIT_REFUSED and row.calculate != PASSED:
        return "edit_refused_no_detail"
    upstream = _upstream(plan, row, earlier)
    if upstream is not None:
        return upstream
    if not plan.owed:
        return "tui_calendar_omits_not_applicable_verdict"
    if row.calculate != PASSED:
        return f"other:calculate_{(row.refusal_code or row.calculate or ERROR).lower()}"
    if row.next_step is ModeloFormNextAction.CONFIRM:
        # An unconfirmed assumed value withholds filing; the form rightly asks for the confirmation first.
        return "assumed_value_unconfirmed"
    if row.next_step is not None:
        return f"next_step_{row.next_step.value}_before_verify"
    if row.differences:
        return "other:figures_differ"
    if row.verify != PASSED:
        return f"other:verify_{row.verify}"
    return f"export_{(row.refusal_code or row.export or ERROR).lower()}"


def run_persona(persona_id: str, tmp_path: Path) -> tuple[PilotRow, list[tuple[PilotReturn, PilotRow]]]:
    """Replay the persona at each horizon its returns are reported at, and drive every return through the workbench.

    Returns the persona-level row, whether every replay loaded, and each reported return with its row.
    """
    envelope = pilot_envelope()
    persona = read_persona(persona_id, envelope=envelope)
    scope = replay_scope(persona)
    loaded = PilotRow(persona=persona_id)
    reported: list[tuple[PilotReturn, PilotRow]] = []
    for replay in pilot_replays(persona_id, envelope):
        root = tmp_path / f"horizon-{replay.horizon}"
        try:
            with materialised_persona(persona_id, root, scope, reuse=True, horizon=replay.horizon) as materialised:
                for block in materialised.not_loaded:
                    loaded.reasons.append(f"horizon {replay.horizon}: not loaded {block.block}: {block.reason}")
                ran: list[tuple[PilotReturn, PilotRow]] = []
                for plan in replay.returns:
                    row = run_return(materialised, plan, root / "exports")
                    row.cause = row_cause(plan, row, ran)
                    ran.append((plan, row))
                    if plan.key in replay.reported:
                        reported.append((plan, row))
        except (PersonaMaterialisationError, PersonaCatalogueError) as error:
            loaded.loads = False
            loaded.reasons.append(f"horizon {replay.horizon}: {' '.join(str(error).split())[:600]}")
            done = {(plan.key) for plan, _ in reported}
            for plan in replay.returns:
                if plan.key in replay.reported and plan.key not in done:
                    reported.append(
                        (
                            plan,
                            PilotRow(
                                persona=persona_id,
                                modelo=plan.modelo,
                                year=plan.year,
                                period=plan.period,
                                calculate=ERROR,
                                verify=NOT_REACHED,
                                export=NOT_REACHED,
                                reasons=[f"replay under horizon {replay.horizon} failed"],
                                cause="other:replay_failed",
                            ),
                        )
                    )
    return loaded, reported


def row_failures(plan: PilotReturn, row: PilotRow) -> list[str]:
    """What makes the row differ from the persona table's verdict for it, each naming the row.

    Every stated casilla must show its value. An owed return whose stated values are grounded must calculate, check
    complete and export; a return stated not owed, or one whose values the persona leaves unverified, is a row the
    persona table does not count green on its stages, so only its figures and its calculation are held to it.
    """
    failures = [f"{row.label}: {difference}" for difference in row.differences]
    if row.calculate != PASSED:
        failures.append(f"{row.label}: calculate {row.calculate}: {row.reason()}")
        return failures
    if not plan.owed or plan.grounding == "unverified":
        return failures
    for stage, outcome in (("verify", row.verify), ("export", row.export)):
        if outcome != PASSED:
            failures.append(f"{row.label}: {stage} {outcome}: {row.reason()}")
    return failures
