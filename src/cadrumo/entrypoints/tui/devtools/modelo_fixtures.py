"""Deterministic, storage-free visual fixtures for production Modelo screens."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Never

from textual.app import App

from ....application.modelo.edit_contract import ModeloEditCompatibilityTupleV1, ModeloEditMutationFamily
from ....application.modelo.edit_services import modelo_edit_request_schema_identity, modelo_edit_result_schema_identity
from ....application.modelo.work_addressing import ModeloExactWorkUnitTarget, ModeloVisibleFilingTarget
from ....application.modelo.work_review import build_modelo_work_review
from ....application.modelo.workspace import resolve_static_inspection_result
from ....application.modelo.workspace_models import (
    ModeloWorkspaceExactWorkUnitTargetV1,
    ModeloWorkspaceVisibleFilingTargetV1,
)
from ....application.operations.registry import OperationSchemaIdentityV1
from ....core.external_constants import OutputLanguage
from ....core.config import load_settings
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.temporal import select_revision
from ....domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.verification_report import VerificationReportCatalogue
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ..components.host import ScreenHostApp
from ..modelo.edit.controller import ModeloEditController
from ..modelo.edit.screen import ModeloEditScreen
from ..modelo.routes import resolve_destination
from ..modelo.view.controller import admit_workspace_session
from ..modelo.view.models import ModeloWorkspaceDestinationIdV1
from ..modelo.view.work_review import ModeloWorkReviewApp
from ..modelo.view.work_select import ModeloWorkSelectApp

if TYPE_CHECKING:
    from collections.abc import Callable as Mutation

    from ....core.secure_object_write import SecureObjectWrite

_BUCKET = "00000000-0000-4000-8000-000000000001"
_AT = datetime(2026, 9, 3, 10, tzinfo=UTC)
_DIGEST = "a" * 64


def _language() -> OutputLanguage:
    """Use the runner's display language so editor parsing cannot diverge."""
    return OutputLanguage(str(load_settings().cadrumo_output_language))


class ModeloFixtureScenario(StrEnum):
    """Stable visual state names for the later central-registry merge."""

    READY = "ready"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    VALIDATION_FAILURE = "validation_failure"


@dataclass(frozen=True, slots=True)
class ModeloFixtureSpec:
    """One production surface, visual scenario, and interfaces it paints."""

    surface_id: str
    scenario: ModeloFixtureScenario
    interfaces: tuple[str, ...]
    build: Callable[[], App[Any]]

    @property
    def fixture_id(self) -> str:
        """Return the stable compound identity proposed to the central registry."""
        return f"{self.surface_id}--{self.scenario.value}"


@dataclass(frozen=True, slots=True)
class _WorkRepository:
    catalogue: WorkUnitCatalogue

    @property
    def bucket_id(self) -> str:
        return _BUCKET

    def exists(self) -> bool:
        return bool(len(self.catalogue))

    def load(self) -> WorkUnitCatalogue:
        return self.catalogue

    def load_revisioned(self) -> tuple[WorkUnitCatalogue, str]:
        return self.catalogue, _DIGEST

    def save(self, _catalogue: WorkUnitCatalogue) -> Never:
        raise RuntimeError("visual fixtures are read-only")

    def mutate(self, _mutation: Mutation[[WorkUnitCatalogue], WorkUnitCatalogue]) -> Never:
        raise RuntimeError("visual fixtures are read-only")

    def save_with_secure_object_writes(
        self,
        _catalogue: WorkUnitCatalogue,
        _extra_writes: tuple[SecureObjectWrite, ...],
        *,
        expected_revision_id: str | None = None,
    ) -> Never:
        raise RuntimeError("visual fixtures are read-only")

    def to_secure_object_write(
        self,
        _catalogue: WorkUnitCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> Never:
        raise RuntimeError("visual fixtures are read-only")


@dataclass(frozen=True, slots=True)
class _CalculationRepository:
    catalogue: CalculationRevisionCatalogue = CalculationRevisionCatalogue()

    @property
    def bucket_id(self) -> str:
        return _BUCKET

    def exists(self) -> bool:
        return bool(len(self.catalogue))

    def load(self) -> CalculationRevisionCatalogue:
        return self.catalogue

    def load_revisioned(self) -> tuple[CalculationRevisionCatalogue, str]:
        return self.catalogue, _DIGEST

    def save(self, _catalogue: CalculationRevisionCatalogue) -> Never:
        raise RuntimeError("visual fixtures are read-only")

    def save_with_secure_object_writes(
        self,
        _catalogue: CalculationRevisionCatalogue,
        _extra_writes: tuple[SecureObjectWrite, ...],
        *,
        expected_revision_id: str | None = None,
    ) -> Never:
        raise RuntimeError("visual fixtures are read-only")

    def to_secure_object_write(
        self,
        _catalogue: CalculationRevisionCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> Never:
        raise RuntimeError("visual fixtures are read-only")


@dataclass(frozen=True, slots=True)
class _VerificationRepository:
    catalogue: VerificationReportCatalogue = VerificationReportCatalogue()

    @property
    def bucket_id(self) -> str:
        return _BUCKET

    def exists(self) -> bool:
        return bool(len(self.catalogue))

    def load(self) -> VerificationReportCatalogue:
        return self.catalogue

    def save(self, _catalogue: VerificationReportCatalogue) -> Never:
        raise RuntimeError("visual fixtures are read-only")


def _unit() -> WorkUnit:
    period = Period.from_year_and_code(2026, "1T")
    modelo = ModeloCode("130")
    revision = select_revision(
        bundled_authority().validate_modelo(modelo), filing_year=2026, period=period.registry_token
    ).id
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET,
            modelo=modelo,
            filing_year=2026,
            period=period,
            revision_id=revision,
        ),
        bucket_id=_BUCKET,
        modelo=modelo,
        filing_year=2026,
        period=period,
        revision_id=revision,
        name="Modelo 130 · 1T 2026",
        created_at=_AT,
        updated_at=_AT,
    )


def _catalogue() -> WorkUnitCatalogue:
    return WorkUnitCatalogue.from_work_units((_unit(),))


def _workspace_app(destination: ModeloWorkspaceDestinationIdV1) -> App[Any]:
    result = resolve_static_inspection_result(
        ModeloWorkspaceVisibleFilingTargetV1(
            target=ModeloVisibleFilingTarget(
                modelo="130",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
            )
        ),
        bucket_id=_BUCKET,
        catalogue_repository=_WorkRepository(_catalogue()),
        authority=bundled_authority(),
        output_language=_language(),
    )
    session, refusal = admit_workspace_session(result)
    if session is None:
        raise RuntimeError(f"fixture workspace admission refused: {refusal!r}")
    return ScreenHostApp(resolve_destination(destination)(session))


def _review_app() -> App[Any]:
    unit = _unit()
    review = build_modelo_work_review(
        unit.bucket_id,
        unit.modelo,
        unit.filing_year,
        unit.period,
        authority=bundled_authority(),
        work_unit_repository=_WorkRepository(_catalogue()),
        calculation_repository=_CalculationRepository(),
        verification_repository=_VerificationRepository(),
    )
    return ModeloWorkReviewApp(review)


def _edit_app(*, invalid: bool = False) -> App[Any]:
    unit = _unit()
    work = _catalogue()
    calculations = CalculationRevisionCatalogue()
    controller = ModeloEditController.for_locale(_language())
    identity = OperationSchemaIdentityV1(
        schema_id="modelo.fixture.workspace-refresh",
        schema_version=1,
        schema_fingerprint=_DIGEST,
    )
    admitted = controller.admit(
        ModeloWorkspaceExactWorkUnitTargetV1(
            target=ModeloExactWorkUnitTarget(work_unit_id=unit.work_unit_id, bucket_id=unit.bucket_id)
        ),
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        bucket_id=unit.bucket_id,
        work_catalogue=work,
        calculation_catalogue=calculations,
        compatibility=ModeloEditCompatibilityTupleV1(
            contract_set_digest=_DIGEST,
            operation_definition_id="modelo.calculate",
            definition_contract_digest=_DIGEST,
            request_schema=modelo_edit_request_schema_identity(),
            result_schema=modelo_edit_result_schema_identity(),
            review_projection_contract_version=None,
            review_schema=None,
            workspace_refresh_target_schema=identity,
            financial_operand_schema=identity,
        ),
    )
    if not admitted:
        raise RuntimeError(f"fixture editor admission refused: {controller.refusal_message_key}")
    if invalid:
        casilla = controller.fields().casilla_ids()[0]
        controller.fields().submit_lexeme(casilla, "invalid-number")
    return ScreenHostApp(ModeloEditScreen(controller, catalogues=lambda: (work, calculations)))


_WORKSPACE_INTERFACES = {
    "modelo.workspace.overview": "cadrumo.entrypoints.tui.modelo.view.overview.ModeloWorkspaceOverviewScreen",
    "modelo.workspace.inputs": "cadrumo.entrypoints.tui.modelo.view.inputs.ModeloWorkspaceInputsScreen",
    "modelo.workspace.results": "cadrumo.entrypoints.tui.modelo.view.results.ModeloWorkspaceResultsScreen",
    "modelo.workspace.provenance": "cadrumo.entrypoints.tui.modelo.view.provenance.ModeloWorkspaceProvenanceScreen",
    "modelo.workspace.verification": (
        "cadrumo.entrypoints.tui.modelo.view.verification.ModeloWorkspaceVerificationScreen"
    ),
    "modelo.workspace.filing": "cadrumo.entrypoints.tui.modelo.view.filing.ModeloWorkspaceFilingScreen",
}


MODELO_FIXTURES: tuple[ModeloFixtureSpec, ...] = tuple(
    ModeloFixtureSpec(
        surface_id=destination.replace("modelo.workspace.", "modelo-"),
        scenario=(
            ModeloFixtureScenario.EMPTY
            if destination in {"modelo.workspace.results", "modelo.workspace.provenance"}
            else ModeloFixtureScenario.UNAVAILABLE
            if destination in {"modelo.workspace.verification", "modelo.workspace.filing"}
            else ModeloFixtureScenario.READY
        ),
        interfaces=(interface,),
        build=lambda destination=destination: _workspace_app(destination),
    )
    for destination, interface in _WORKSPACE_INTERFACES.items()
) + (
    ModeloFixtureSpec(
        "modelo-edit",
        ModeloFixtureScenario.READY,
        ("cadrumo.entrypoints.tui.modelo.edit.screen.ModeloEditScreen",),
        _edit_app,
    ),
    ModeloFixtureSpec(
        "modelo-edit",
        ModeloFixtureScenario.VALIDATION_FAILURE,
        ("cadrumo.entrypoints.tui.modelo.edit.screen.ModeloEditScreen",),
        lambda: _edit_app(invalid=True),
    ),
    ModeloFixtureSpec(
        "modelo-work-review",
        ModeloFixtureScenario.READY,
        (
            "cadrumo.entrypoints.tui.modelo.view.work_review.ModeloWorkReviewApp",
            "cadrumo.entrypoints.tui.modelo.view.work_review.ModeloWorkReviewScreen",
        ),
        _review_app,
    ),
    ModeloFixtureSpec(
        "modelo-work-select",
        ModeloFixtureScenario.READY,
        (
            "cadrumo.entrypoints.tui.modelo.view.work_select.ModeloWorkSelectApp",
            "cadrumo.entrypoints.tui.modelo.view.work_select.ModeloWorkSelectScreen",
        ),
        lambda: ModeloWorkSelectApp((_unit(),)),
    ),
    ModeloFixtureSpec(
        "modelo-work-select",
        ModeloFixtureScenario.EMPTY,
        (
            "cadrumo.entrypoints.tui.modelo.view.work_select.ModeloWorkSelectApp",
            "cadrumo.entrypoints.tui.modelo.view.work_select.ModeloWorkSelectScreen",
        ),
        lambda: ModeloWorkSelectApp(()),
    ),
)


def resolve_modelo_fixture(fixture_id: str) -> ModeloFixtureSpec:
    """Resolve one exact fixture identity or refuse with the accepted set."""
    matches = tuple(spec for spec in MODELO_FIXTURES if spec.fixture_id == fixture_id)
    if len(matches) != 1:
        accepted = ", ".join(spec.fixture_id for spec in MODELO_FIXTURES)
        raise KeyError(f"unknown Modelo fixture {fixture_id!r}; accepted: {accepted}")
    return matches[0]


__all__ = ["MODELO_FIXTURES", "ModeloFixtureScenario", "ModeloFixtureSpec", "resolve_modelo_fixture"]
