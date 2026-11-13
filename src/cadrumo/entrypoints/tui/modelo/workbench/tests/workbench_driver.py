"""A thin driver of the production Modelo workbench over a materialised persona's profile.

The driver opens the workbench screen of one stored declaration in a Textual
pilot, composed over the persona's registered profile: every operation the
workbench submits runs through the production supervisor, and the modal
observes its real settlement. It reads what the screen shows (the next action
the form serves, the casilla values, how the last pressed step settled) and
presses the key the workbench names for a served action, answering the dialogs
that key opens with the answers its caller supplies.

It decides nothing about a return: which step comes next, whether a result is
expected and what a difference means belong to the caller.
"""

from __future__ import annotations

import asyncio
import dataclasses
import re
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
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
from ......application.modelo.work_form_field_vocabulary import (
    ModeloFormCasillaAddressV1,
    ModeloFormOrigin,
    ModeloFormScalar,
)
from ......application.modelo.work_form_findings import ModeloFormAttention
from ......application.modelo.work_form_models import ModeloFormRepeatingBlock, ModeloWorkForm
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
from ......core.modelo_export_artefact import ModeloExportArtefact
from ......core.operations import OperationTerminalCondition
from ......domain.modelos.verification_report import VerificationCompletenessStatus
from .....tests.persona_materialisation import PERSONA_ACTOR, PersonaWorld, public_result, run_operation
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
from ..screen_constants import FINDINGS_KEY, NEXT_KEYS

_SIZE: Final = (200, 60)
#: A calculation of a dense annual return over a full ledger takes well over the default settle wait.
_OPERATION_WAIT: Final = 900.0
_TUI_ACTOR: Final = "operator:tui-modelo"
_FUNCTION_KEY: Final = re.compile(r"F\d+")


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
        """No workbench lifecycle operation this driver runs presents a review."""
        raise AssertionError("a workbench lifecycle operation presents no review")

    async def response_control(
        self, *, interaction_id: str, revision: OperationRevision
    ) -> OperationResponseControlPort:
        """No workbench lifecycle operation this driver runs asks a response."""
        raise AssertionError("a workbench lifecycle operation asks no response")

    async def cancel(self, *, expected_revision: OperationRevision) -> OperationCancellationResultV1:
        """The driver never cancels a settled operation."""
        raise AssertionError("the driver never cancels")

    async def detach(self, *, expected_revision: OperationRevision) -> OperationDetachResultV1:
        """The driver never detaches a settled operation."""
        raise AssertionError("the driver never detaches")


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


# -- what the caller answers and what the screen shows ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DialogAnswers:
    """What the filer answers in the dialogs a pressed key opens."""

    m303_joint_return_elected: bool
    """The Modelo 303 evidence dialog's joint-return question."""
    m303_observed_at: datetime
    """When the Modelo 390 exemption attestation was observed, where that dialog asks it."""
    export_artefact: ModeloExportArtefact
    """The artefact asked for in the export dialog; the dialog is cancelled when it does not offer it."""
    export_path: Path


@dataclass(frozen=True, slots=True)
class ShownOutcome:
    """How one pressed step settled, as the workbench showed it."""

    action: ModeloFormNextAction
    submitted: bool
    """Whether the key submitted an operation; ``False`` when the workbench withheld it."""
    terminal: OperationPublicProjectionV1 | None
    """The settled operation the modal observed."""
    refusal: str
    """The refusal sentence the workbench shows beneath its notice, if any."""
    notice: str
    """The workbench's notice line after the step."""
    verification: VerificationCompletenessStatus | None
    """The verification status on the form the workbench read afterwards."""
    export: ModeloExportPublicResultV3 | None = None
    """The export result screen's result, when one was shown."""
    export_offered: tuple[str, ...] = ()
    """The artefacts the export dialog offered, when it did not offer the one asked for."""

    @property
    def condition(self) -> OperationTerminalCondition | None:
        """The operation's terminal condition, or ``None`` when nothing settled."""
        return None if self.terminal is None else self.terminal.terminal_condition

    @property
    def code(self) -> str | None:
        """The refusal reference of a refused operation, else its failure code."""
        if self.terminal is None:
            return None
        if self.terminal.terminal_condition is OperationTerminalCondition.REFUSED:
            return self.terminal.refusal_ref
        return self.terminal.failure_error_code


def _shown(value: ModeloFormScalar) -> bool:
    """Whether a box shows anything: a blank, unticked or zero box shows nothing."""
    if value is None or value is False:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, Decimal | int):
        return value != 0
    return str(value).strip() != ""


def _pilot_key(key: str) -> str:
    return key.lower() if _FUNCTION_KEY.fullmatch(key) else key


class WorkbenchDriver:
    """One open workbench over one declaration: what it serves and shows, and the keys it names."""

    def __init__(
        self,
        pilot: Pilot[None],
        screen: ModeloWorkbenchScreen,
        submissions: WorldSubmissions,
        answers: DialogAnswers,
    ) -> None:
        """Bind the driver to the open screen and the dialog answers its caller supplies."""
        self._pilot = pilot
        self._screen = screen
        self._submissions = submissions
        self._answers = answers
        self._outcome: ShownOutcome | None = None
        self._exported: ModeloExportPublicResultV3 | None = None
        self._export_offered: tuple[str, ...] = ()

    @property
    def world(self) -> PersonaWorld:
        """The persona's profile the workbench acts on."""
        return self._submissions.world

    def form(self) -> ModeloWorkForm | None:
        """The form the workbench holds after its latest read."""
        return self._screen.form

    def calculated(self) -> bool:
        """Whether the form the workbench holds carries a calculation."""
        form = self._screen.form
        return form is not None and form.calculation_revision_id is not None

    def served_next_action(self) -> ModeloFormNextAction | None:
        """The next action the workbench's stepper offers, from the form it read."""
        load = self._screen._load
        return None if load is None else self._screen._progress(load).next_action

    def _key_for(self, action: ModeloFormNextAction) -> str:
        """The key the workbench names for ``action``; the findings key where only findings lead to what is left."""
        load = self._screen._load
        if load is not None and action is self.served_next_action() and self._screen._progress(load).findings_lead:
            return FINDINGS_KEY
        return NEXT_KEYS[action]

    async def press_for(self, action: ModeloFormNextAction) -> ShownOutcome:
        """Press the key the workbench names for ``action`` and answer every dialog it opens; how it settled."""
        key = self._key_for(action)
        self._exported = None
        self._export_offered = ()
        before = len(self._submissions.operations)
        if key:
            await self._pilot.press(_pilot_key(key))
            await self._quiet()
        submitted = len(self._submissions.operations) > before
        operation = self._submissions.latest() if submitted else None
        form = self._screen.form
        self._outcome = ShownOutcome(
            action=action,
            submitted=submitted,
            terminal=None if operation is None else operation.terminal,
            refusal=self.refusal(),
            notice=self.notice(),
            verification=None if form is None else form.verification,
            export=self._exported,
            export_offered=self._export_offered,
        )
        return self._outcome

    def shown_outcome(self) -> ShownOutcome | None:
        """How the step pressed last settled, or ``None`` before any press."""
        return self._outcome

    def shown_figures(self) -> dict[str, str]:
        """Every casilla value the form shows, by casilla id, as text; boxes showing nothing are left out.

        A column of a repeated group with exactly one row gives the casilla its value where the box itself shows
        none; several rows show no single value for it.
        """
        form = self._screen.form
        if form is None:
            return {}
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
                        if casilla is not None and not _shown(shown.get(casilla)):
                            shown[casilla] = value
        return {casilla: str(value) for casilla, value in sorted(shown.items()) if _shown(value)}

    def shown_missing(self) -> tuple[str, ...]:
        """What the form asks the filer to fill in: boxes that need input, then notes and findings naming a value."""
        form = self._screen.form
        if form is None:
            return ()
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
        return tuple(dict.fromkeys([*boxes, *notes, *findings]))

    def notice(self) -> str:
        """The workbench's notice line."""
        return " ".join(str(self._screen.query_one("#wb-notice", Static).render()).split())

    def refusal(self) -> str:
        """The refusal sentence the workbench shows beneath its notice, if any."""
        slot = next(iter(self._screen.query("#wb-operation-refusal").results(RefusalSlot)), None)
        if slot is None or slot.refusal is None:
            return ""
        return " ".join((slot.refusal.sentence or "").split())

    async def _quiet(self) -> None:
        """Answer every dialog the workbench opens until it stands alone with nothing in flight."""
        app = self._pilot.app
        for _ in range(32):
            await settle(self._pilot, timeout=_OPERATION_WAIT)
            shown = app.screen
            if isinstance(shown, ConfirmScreen):
                await self._pilot.press("y")
            elif isinstance(shown, OrdinaryM303FilingEvidenceScreen):
                self._answer_m303(shown)
            elif isinstance(shown, WorkbenchExportScreen):
                self._answer_export(shown)
            elif isinstance(shown, ModeloExportResultScreen):
                result = shown._result
                self._exported = result if isinstance(result, ModeloExportPublicResultV3) else None
                await self._pilot.press("escape")
            elif isinstance(shown, WorkbenchResultScreen):
                await self._pilot.press("escape")
            elif isinstance(shown, ModeloWorkbenchScreen) and not self._screen._operation_in_flight:
                return
            else:
                await settle_until(self._pilot, lambda: True, "the workbench to settle", timeout=_OPERATION_WAIT)
        raise AssertionError(f"the workbench never came to rest; it shows {type(app.screen).__name__}")

    def _answer_m303(self, dialog: OrdinaryM303FilingEvidenceScreen) -> None:
        dialog.query_one("#m303-evidence-joint-return-elected", Select).value = str(
            self._answers.m303_joint_return_elected
        ).lower()
        for entry in dialog.query("#m303-evidence-observed-at").results(Input):
            entry.value = self._answers.m303_observed_at.isoformat()
        dialog.query_one("#m303-evidence-submit", Button).press()

    def _answer_export(self, dialog: WorkbenchExportScreen) -> None:
        artefact = dialog.query_one("#export-artefact", Select)
        offered = tuple(str(value) for _, value in artefact._options if value is not Select.NULL)
        wanted = self._answers.export_artefact.value
        if wanted not in offered:
            self._export_offered = offered
            dialog.query_one("#export-cancel", Button).press()
            return
        artefact.value = wanted
        dialog.query_one("#export-path", Input).value = str(self._answers.export_path)
        dialog.query_one("#export-submit", Button).press()


@asynccontextmanager
async def open_workbench(
    world: PersonaWorld, work_unit_id: str, answers: DialogAnswers
) -> AsyncGenerator[WorkbenchDriver]:
    """Open the workbench of ``work_unit_id`` over the persona's profile, once it has read its declaration."""
    installed, submissions = world_workbench(world, work_unit_id)
    screen = ModeloWorkbenchScreen(installed, actions=installed)
    app = ScreenHostApp(screen)
    async with app.run_test(size=_SIZE) as pilot:
        await settle_until(
            pilot, lambda: screen.form is not None, "the workbench to read its declaration", timeout=_OPERATION_WAIT
        )
        yield WorkbenchDriver(pilot, screen, submissions, answers)
        app.exit(None)
