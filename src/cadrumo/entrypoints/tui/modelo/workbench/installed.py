"""The workbench's production reader and actions for one declaration.

Every read goes through the form loading service against the session's pinned
authority and the profile's repositories; every action goes through the
declaration's lifecycle door, rebuilt on the calculation head and granting
verification report the latest read found, so Verify and File always act on the
revision the filer is looking at. The edit admission is taken when the form is
read -- opening one declaration's workbench is the start of its edit session --
and its baseline is the one every parse and apply is judged against; the door
renews it silently before submitting and refuses, keeping the staged changes,
when the declaration moved.

Parsing is the application's typed grammar in the filer's language. A refusal
comes back as the sentence that says how to fix the entry; the refused text is
never echoed or kept.

See Also:
    :class:`~cadrumo.domain.calculations.registry.bindings.CasillaObservation`
        The recorded operand and result trace, read without reevaluating the formula.
    :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`
        The pinned registry snapshot supplying the selected modelo revision.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from textual.screen import Screen

from .....application.modelo.action_errors import modelo_edit_refusal_error
from .....application.modelo.casilla_help import ModeloCasillaHelpCardV1, build_casilla_help_card
from .....application.modelo.declarations_workspace import DeclarationsWorkspaceDeclarationRefV1
from .....application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditAddressV1,
    ModeloEditAdmittedV1,
    ModeloEditBaselineV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditFindingSeverity,
    ModeloEditFindingV1,
    ModeloEditParsedValueV1,
    ModeloEditParseReason,
    ModeloEditParseRefusalV1,
    ModeloEditRefusedV1,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditStaleBaselineRefusalV1,
    ModeloScalarEditIntentV1,
)
from .....application.modelo.edit_parse_text import parse_refusal_text
from .....application.modelo.edit_parsing import ModeloEditParseRequestV1, parse_modelo_edit_lexeme
from .....application.modelo.edit_preflight import (
    CLEAR_OF_SOURCE_FED_CASILLA,
    INTENT_NOT_ADMITTED,
    NOTHING_TO_RESTORE,
    OPERATOR_LAYER_UNKNOWN,
    OVERRIDES_SOURCE_VALUE,
    REQUIRED_EMPTY,
    VALUE_REFUSED_PREFIX,
)
from .....application.modelo.value_presentation import format_casilla_value
from .....application.modelo.verification_actions import granting_verification_report
from .....application.modelo.work_form_models import (
    ModeloFormAddressV1,
    ModeloFormBindingAddressV1,
    ModeloFormCasillaAddressV1,
    ModeloFormField,
    edit_address,
)
from .....application.modelo.work_form_service import (
    ModeloWorkFormLoadV1,
    load_modelo_work_form,
    modelo_form_snapshot,
)
from .....core.casilla_id import CasillaId
from .....core.errors.error_codes import resolve_error_message
from .....core.errors.hierarchy import CadrumoError
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import output_language, tr
from .....core.identity.bucket import BucketId
from .....domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from .....domain.calculations.registry.bindings import CasillaObservation
from .....domain.calculations.registry.tax_id_format import runtime_tax_id_format
from .....domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from .....domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ...declarations.models import ModeloWorkspaceScreenFactoryV1
from ..lifecycle import ModeloLifecycleActionUnavailableError, ModeloWorkspaceLifecycleDoor
from ..m303_evidence import OrdinaryM303FilingEvidenceSubmission
from .export import offered_export_artefacts
from .ports import (
    WorkbenchCalculationEvidence,
    WorkbenchChange,
    WorkbenchChangeKind,
    WorkbenchExportOffer,
    WorkbenchExportRequest,
    WorkbenchFinding,
    WorkbenchParsed,
    WorkbenchParseOutcome,
    WorkbenchPreflight,
    WorkbenchRefused,
)
from .screen import ModeloWorkbenchScreen

if TYPE_CHECKING:
    from .....application.live.borrador_100 import Borrador100SnapshotRepository
    from .....application.modelo.operation_definitions import ModeloExportPublicResultV2
    from .....application.operations.frontend_projection import OperationPublicProjectionV1
    from .....domain.calculations.registry.authority import PinnedAuthorityOperation
    from .....domain.calculations.registry.schema import RegistrySnapshot
    from .....domain.deadlines.festivos import CalendarCCAA
    from ...operations.controller import OperationController

type LifecycleDoorFactory = Callable[[str | None, str | None], ModeloWorkspaceLifecycleDoor]
"""Build the declaration's lifecycle door on a calculation head and verification report."""

_M303: Final[str] = "303"
_EDIT_UNAVAILABLE_KEY: Final[str] = "application.modelo.lifecycle.refusal.edit_unavailable"
_SCALAR_KINDS: Final[Mapping[WorkbenchChangeKind, ModeloEditScalarIntentKind]] = MappingProxyType(
    {
        WorkbenchChangeKind.SET: ModeloEditScalarIntentKind.SET_TYPED_VALUE,
        WorkbenchChangeKind.CLEAR: ModeloEditScalarIntentKind.CLEAR_DECLARED_VALUE,
        WorkbenchChangeKind.RESTORE: ModeloEditScalarIntentKind.RESTORE_SOURCE_VALUE,
    }
)
WORDED_FINDING_CODES: Final[tuple[str, ...]] = (
    INTENT_NOT_ADMITTED,
    CLEAR_OF_SOURCE_FED_CASILLA,
    REQUIRED_EMPTY,
    NOTHING_TO_RESTORE,
)
"""The check's findings the review says in its own sentence; a refused value says how to fix it instead."""
#: Findings the review already states in its own words, so the check does not repeat them.
_STATED_BY_THE_REVIEW: Final[frozenset[str]] = frozenset({OPERATOR_LAYER_UNKNOWN, OVERRIDES_SOURCE_VALUE})
#: A binding input the filer supplied is removed whether they clear it or give it back to its source.
_BINDING_KINDS: Final[Mapping[WorkbenchChangeKind, ModeloEditBindingIntentKind]] = MappingProxyType(
    {
        WorkbenchChangeKind.SET: ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE,
        WorkbenchChangeKind.CLEAR: ModeloEditBindingIntentKind.REMOVE_OVERRIDE,
        WorkbenchChangeKind.RESTORE: ModeloEditBindingIntentKind.REMOVE_OVERRIDE,
    }
)


@dataclass(frozen=True, slots=True)
class WorkbenchRepositories:
    """The profile repositories one declaration's form is read from.

    ``borrador_snapshots`` is the profile's AEAT draft store, read to say when
    replayed AEAT data was imported; ``holiday_territory`` reads the profile's
    holiday territory afresh on each read, so a deadline shifts for the
    filer's own regional holidays and not the national ones only;
    ``bucket_events`` is the profile's event history, read to say when the
    latest file for the AEAT was created and whether it still matches.
    """

    work_units: WorkUnitCatalogueRepositoryProtocol
    calculations: CalculationRevisionCatalogueRepositoryProtocol
    verifications: VerificationReportCatalogueRepositoryProtocol
    borrador_snapshots: Borrador100SnapshotRepository | None = None
    holiday_territory: Callable[[], CalendarCCAA | None] | None = None
    bucket_events: BucketEventHistoryRepositoryProtocol | None = None


@dataclass(frozen=True, slots=True)
class _ReadState:
    """What the latest read found and every action is judged against."""

    baseline: ModeloEditBaselineV1 | None
    calculation_revision_id: str | None
    verification_report_id: str | None
    asks_m303_evidence: bool
    registry_revision_id: str
    #: The immutable operand traces of the calculation the form is showing.
    observations: tuple[CasillaObservation, ...]
    #: Why the declaration cannot be edited, in the filer's words; ``None`` when it can.
    edit_refusal: str | None = None


class InstalledModeloWorkbench:
    """Reads and acts on one declaration for the workbench, through the production services."""

    def __init__(
        self,
        *,
        bucket_id: BucketId,
        declaration: DeclarationsWorkspaceDeclarationRefV1,
        operation: PinnedAuthorityOperation,
        repositories: WorkbenchRepositories,
        door: LifecycleDoorFactory,
    ) -> None:
        """Bind the declaration, the pinned authority, its repositories and its door factory."""
        self._bucket_id = bucket_id
        self._declaration = declaration
        self._operation = operation
        self._repositories = repositories
        self._door_factory = door
        self._state: _ReadState | None = None
        self._snapshots: dict[str, RegistrySnapshot] = {}
        self._tax_id_format = runtime_tax_id_format(authority=operation)

    # -- reading -------------------------------------------------------------

    def _door(self) -> ModeloWorkspaceLifecycleDoor:
        state = self._state
        if state is None:
            return self._door_factory(None, None)
        return self._door_factory(state.calculation_revision_id, state.verification_report_id)

    def load(self, language: OutputLanguage) -> ModeloWorkFormLoadV1:
        """Admit an edit baseline, read the declaration's form and remember what the actions need."""
        admit = self._door_factory(None, None).edit_admission
        admission = None if admit is None else admit()
        declaration = self._declaration
        territory = self._repositories.holiday_territory
        loaded = load_modelo_work_form(
            self._bucket_id,
            declaration.modelo,
            declaration.filing_year,
            declaration.period,
            operation=self._operation,
            work_unit_repository=self._repositories.work_units,
            calculation_repository=self._repositories.calculations,
            verification_repository=self._repositories.verifications,
            admission=admission,
            language=language,
            borrador_snapshots=self._repositories.borrador_snapshots,
            holiday_territory=None if territory is None else territory(),
            bucket_events=self._repositories.bucket_events,
        )
        form = loaded.form
        head_id = form.calculation_revision_id
        head = None if head_id is None else self._repositories.calculations.load().get(head_id)
        report = (
            None if head_id is None else granting_verification_report(self._repositories.verifications.load(), head_id)
        )
        self._state = _ReadState(
            baseline=admission.baseline if isinstance(admission, ModeloEditAdmittedV1) else None,
            edit_refusal=(
                resolve_error_message(modelo_edit_refusal_error(admission.refusal))
                if isinstance(admission, ModeloEditRefusedV1)
                else None
            ),
            calculation_revision_id=head_id,
            verification_report_id=None if report is None else str(report.verification_report_id),
            asks_m303_evidence=str(declaration.modelo) == _M303
            and (head is None or head.filing_instance_evidence is None),
            registry_revision_id=str(form.registry_revision_id),
            observations=() if head is None else head.observations,
        )
        return loaded

    def edit_refusal(self) -> str | None:
        """Why the declaration last read cannot be edited, or ``None`` when it can or was not asked."""
        state = self._state
        return None if state is None else state.edit_refusal

    def help_card(self, casilla_id: CasillaId, language: OutputLanguage) -> ModeloCasillaHelpCardV1:
        """Assemble one casilla's help from the snapshot of the revision last read."""
        declaration = self._declaration
        state = self._state
        revision_id = None if state is None else state.registry_revision_id
        key = revision_id or ""
        snapshot = self._snapshots.get(key)
        if snapshot is None:
            snapshot = modelo_form_snapshot(
                self._operation,
                declaration.modelo,
                declaration.filing_year,
                declaration.period,
                revision_id
                or str(
                    self._operation.revision_for_context(
                        str(declaration.modelo),
                        filing_year=declaration.filing_year,
                        period=declaration.period.registry_token,
                    ).id
                ),
            )
            self._snapshots[key] = snapshot
        return build_casilla_help_card(
            casilla_id,
            snapshot=snapshot,
            operation=self._operation,
            language=language,
            on=declaration.period.end_date,
            observation=None
            if state is None
            else next((item for item in state.observations if item.casilla_id == casilla_id), None),
        )

    # -- editing -------------------------------------------------------------

    def parse(self, field: ModeloFormField, lexeme: str, language: OutputLanguage) -> WorkbenchParseOutcome:
        """Read what the filer typed through the application grammar of the field's address."""
        state = self._state
        if state is None or state.baseline is None:
            return WorkbenchRefused(message=tr("tui.modelo.workbench.editability.no_admission"))
        target = edit_address(field)
        address = (
            ModeloEditScalarAddressV1(casilla_id=target.casilla_id)
            if isinstance(target, ModeloFormCasillaAddressV1)
            else ModeloEditBindingAddressV1(binding_id=target.binding_id)
        )
        result = parse_modelo_edit_lexeme(
            ModeloEditParseRequestV1(address=address, entry_locale=language, lexeme=lexeme),
            baseline=state.baseline,
            tax_id_format=self._tax_id_format,
        )
        if isinstance(result, ModeloEditParsedValueV1):
            value = result.value
            display = "" if value is None else format_casilla_value(value, data_type=field.data_type, language=language)
            return WorkbenchParsed(value=value, display=display)
        refusal = result.refusal
        if isinstance(refusal, ModeloEditParseRefusalV1):
            return WorkbenchRefused(message=parse_refusal_text(refusal, language))
        return WorkbenchRefused(message=resolve_error_message(modelo_edit_refusal_error(refusal)))

    def _baseline(self) -> ModeloEditBaselineV1:
        state = self._state
        if state is None or state.baseline is None:
            raise ModeloLifecycleActionUnavailableError(translated_message=_EDIT_UNAVAILABLE_KEY)
        return state.baseline

    async def preflight(self, changes: tuple[WorkbenchChange, ...]) -> WorkbenchPreflight:
        """Check the staged changes against the declaration as it stands, naming what each finding concerns."""
        scalar, binding = _intents(changes)
        result = await self._door().preflight_edits(
            baseline=self._baseline(), scalar_intents=scalar, binding_intents=binding
        )
        if isinstance(result, ModeloEditRefusedV1):
            if isinstance(result.refusal, ModeloEditStaleBaselineRefusalV1):
                return WorkbenchPreflight(stale=True)
            message = resolve_error_message(modelo_edit_refusal_error(result.refusal))
            return WorkbenchPreflight(findings=(WorkbenchFinding(address=None, message=message, blocking=True),))
        language = OutputLanguage(output_language())
        return WorkbenchPreflight(
            findings=tuple(
                _finding(finding, language) for finding in result.findings if finding.code not in _STATED_BY_THE_REVIEW
            ),
            operator_entries_unknown=any(finding.code == OPERATOR_LAYER_UNKNOWN for finding in result.findings),
        )

    async def apply(self, changes: tuple[WorkbenchChange, ...]) -> OperationController:
        """Submit the staged changes as typed intents against the admitted baseline."""
        scalar, binding = _intents(changes)
        return await self._door().apply_edits(baseline=self._baseline(), scalar_intents=scalar, binding_intents=binding)

    # -- lifecycle -----------------------------------------------------------

    def calculation_evidence(self) -> WorkbenchCalculationEvidence | None:
        """Ask the ordinary Modelo 303 answers when the head records none."""
        state = self._state
        if state is None or not state.asks_m303_evidence:
            return None
        return WorkbenchCalculationEvidence(
            work_unit_id=str(self._declaration.work_unit_id), asks_modelo_390=self._door().asks_modelo_390
        )

    async def calculate(self, m303_evidence: OrdinaryM303FilingEvidenceSubmission | None = None) -> OperationController:
        """Recalculate, first recording the Modelo 303 answers the filer gave."""
        door = self._door()
        if m303_evidence is None:
            return await door.calculate()
        evidence = m303_evidence.existing_evidence
        if evidence is None:
            observed_at = m303_evidence.observed_at
            if observed_at is None:
                raise ModeloLifecycleActionUnavailableError(translated_message=_EDIT_UNAVAILABLE_KEY)
            evidence = await door.author_ordinary_m303_filing_evidence(
                joint_return_elected=m303_evidence.joint_return_elected, observed_at=observed_at
            )
        return await door.calculate(ordinary_m303_filing_evidence=evidence)

    async def verify(self) -> OperationController:
        """Verify the calculation last read."""
        return await self._door().verify()

    async def file(self) -> OperationController:
        """Record the verified calculation last read as filed locally."""
        return await self._door().file()

    def export_offer(self) -> WorkbenchExportOffer:
        """Offer what this installation can publish; a Modelo 303 asks its payment elections."""
        return WorkbenchExportOffer(
            artefacts=offered_export_artefacts(), asks_elections=str(self._declaration.modelo) == _M303
        )

    async def export(self, request: WorkbenchExportRequest) -> OperationController:
        """Export the verified calculation last read."""
        return await self._door().export(
            output_path=request.output_path,
            refund_election=request.refund_election,
            payment_election=request.payment_election,
            prior_domiciliation_election=request.prior_domiciliation_election,
            replace_existing=request.replace_existing,
            artefact=request.artefact,
        )

    async def export_result(self, projection: OperationPublicProjectionV1) -> ModeloExportPublicResultV2 | None:
        """Resolve one settled export's facts."""
        return await self._door().settled_export_result(projection)

    def refresh_product(self) -> None:
        """Capture a new product generation, so Declarations and search show what the operation changed."""
        refresh = self._door().refresh_after_success
        if refresh is not None:
            refresh()


def _intents(
    changes: tuple[WorkbenchChange, ...],
) -> tuple[tuple[ModeloScalarEditIntentV1, ...], tuple[ModeloBindingEditIntentV1, ...]]:
    """Turn staged changes into the typed intents of the edit contract, casilla and binding apart."""
    scalar: list[ModeloScalarEditIntentV1] = []
    binding: list[ModeloBindingEditIntentV1] = []
    for change in changes:
        address = change.address
        value = change.value if change.kind is WorkbenchChangeKind.SET else None
        if isinstance(address, ModeloFormCasillaAddressV1):
            scalar.append(
                ModeloScalarEditIntentV1(
                    address=ModeloEditScalarAddressV1(casilla_id=address.casilla_id),
                    kind=_SCALAR_KINDS[change.kind],
                    value=value,
                )
            )
        else:
            binding.append(
                ModeloBindingEditIntentV1(
                    address=ModeloEditBindingAddressV1(binding_id=address.binding_id),
                    kind=_BINDING_KINDS[change.kind],
                    value=value,
                )
            )
    return tuple(scalar), tuple(binding)


def _form_address(address: ModeloEditAddressV1 | None) -> ModeloFormAddressV1 | None:
    if isinstance(address, ModeloEditScalarAddressV1):
        return ModeloFormCasillaAddressV1(casilla_id=address.casilla_id)
    if isinstance(address, ModeloEditBindingAddressV1):
        return ModeloFormBindingAddressV1(binding_id=address.binding_id)
    return None


def _finding(finding: ModeloEditFindingV1, language: OutputLanguage) -> WorkbenchFinding:
    """Say one preflight finding in the filer's words; a refused value says how to fix it."""
    address = _form_address(finding.address)
    blocking = finding.severity is ModeloEditFindingSeverity.ERROR
    target = finding.address
    if finding.code.startswith(VALUE_REFUSED_PREFIX) and isinstance(
        target, ModeloEditScalarAddressV1 | ModeloEditBindingAddressV1
    ):
        refusal = ModeloEditParseRefusalV1(
            address=target,
            reason=ModeloEditParseReason(finding.code.removeprefix(VALUE_REFUSED_PREFIX)),
            message_arguments=finding.message_arguments,
        )
        return WorkbenchFinding(address=address, message=parse_refusal_text(refusal, language), blocking=blocking)
    return WorkbenchFinding(
        address=address, message=tr(f"tui.modelo.workbench.review.finding.{finding.code}"), blocking=blocking
    )


class ModeloWorkspaceDeclarationAdmissionError(CadrumoError):
    """An installed declaration cannot open a workbench from this generation."""


type DeclarationDoorFactory = Callable[
    [DeclarationsWorkspaceDeclarationRefV1, str | None, str | None], ModeloWorkspaceLifecycleDoor
]
"""Build one declaration's lifecycle door on a calculation head and verification report."""


def compose_installed_modelo_workbench_factory(
    *,
    bucket_id: BucketId,
    declarations: tuple[DeclarationsWorkspaceDeclarationRefV1, ...],
    operation: PinnedAuthorityOperation,
    repositories: Callable[[], WorkbenchRepositories],
    door: DeclarationDoorFactory,
) -> ModeloWorkspaceScreenFactoryV1:
    """Open a workbench for exactly the declarations this generation admitted.

    A declaration opens only when the generation lists it with the same
    coordinates it was selected with; a stale or duplicated one is refused
    before any screen is built. Each workbench reads its declaration afresh
    through its own reader, so it never shows an earlier generation's figures.
    """
    admitted = {str(declaration.work_unit_id): declaration for declaration in declarations}
    if len(admitted) != len(declarations):
        raise ModeloWorkspaceDeclarationAdmissionError("the generation carries duplicate declaration work identities")

    def create(declaration: DeclarationsWorkspaceDeclarationRefV1, /) -> Screen[None]:
        if admitted.get(str(declaration.work_unit_id)) != declaration:
            raise ModeloWorkspaceDeclarationAdmissionError(
                "the declaration target is not admitted by this workbench generation"
            )
        workbench = InstalledModeloWorkbench(
            bucket_id=bucket_id,
            declaration=declaration,
            operation=operation,
            repositories=repositories(),
            door=partial(door, declaration),
        )
        return ModeloWorkbenchScreen(workbench, actions=workbench)

    return create


__all__ = [
    "WORDED_FINDING_CODES",
    "DeclarationDoorFactory",
    "InstalledModeloWorkbench",
    "LifecycleDoorFactory",
    "ModeloWorkspaceDeclarationAdmissionError",
    "WorkbenchRepositories",
    "compose_installed_modelo_workbench_factory",
]
