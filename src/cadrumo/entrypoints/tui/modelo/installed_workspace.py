"""Production handoff from admitted Declarations rows to Modelo workspace pages.

The installed workbench captures its Declarations and Modelo projections before
it mounts the Declarations destination.  This module joins those immutable
facts without resolving persistence, registry, or network authority again.
"""

from __future__ import annotations

from collections.abc import Mapping

from textual.screen import Screen

from ....application.modelo.declarations_workspace import DeclarationsWorkspaceDeclarationRefV1
from ....application.modelo.workspace_models import ModeloWorkspaceProjectionV1
from ....core.identity import BucketId
from ..declarations.models import ModeloWorkspaceScreenFactoryV1
from .routes import WORKSPACE_SELECTION_OUTCOME, resolve_destination
from .view.controller import ModeloWorkspaceReadSession, open_workspace_read_session


class ModeloWorkspaceDeclarationAdmissionError(ValueError):
    """An installed declaration cannot open a workspace from this generation."""


def compose_installed_modelo_workspace_factory(
    *,
    bucket_id: BucketId,
    declarations: tuple[DeclarationsWorkspaceDeclarationRefV1, ...],
    projections: tuple[ModeloWorkspaceProjectionV1, ...],
) -> ModeloWorkspaceScreenFactoryV1:
    """Bind one generation's admitted declarations to canonical read sessions.

    A declaration reaches the existing Modelo pages only when one captured
    workspace projection names its exact hidden work identity and visible
    address.  The relation is deliberately total in both directions: a stale
    declaration, an unrelated projection, or a duplicate target is refused
    before any Textual screen is constructed.
    """
    declaration_by_work_unit = _admitted_declarations(declarations)
    session_by_work_unit = _admitted_sessions(
        bucket_id=bucket_id,
        declarations=declaration_by_work_unit,
        projections=projections,
    )

    def create(declaration: DeclarationsWorkspaceDeclarationRefV1, /) -> Screen[None]:
        admitted = declaration_by_work_unit.get(declaration.work_unit_id)
        if admitted != declaration:
            raise ModeloWorkspaceDeclarationAdmissionError(
                "the declaration target is not admitted by this Modelo workspace generation"
            )
        try:
            session = session_by_work_unit[declaration.work_unit_id]
        except KeyError as error:
            raise ModeloWorkspaceDeclarationAdmissionError(
                "the admitted declaration has no canonical Modelo workspace session"
            ) from error
        return resolve_destination(WORKSPACE_SELECTION_OUTCOME)(session)

    return create


def _admitted_declarations(
    declarations: tuple[DeclarationsWorkspaceDeclarationRefV1, ...],
) -> Mapping[str, DeclarationsWorkspaceDeclarationRefV1]:
    rows = {str(declaration.work_unit_id): declaration for declaration in declarations}
    if len(rows) != len(declarations):
        raise ModeloWorkspaceDeclarationAdmissionError("the generation carries duplicate declaration work identities")
    return rows


def _admitted_sessions(
    *,
    bucket_id: BucketId,
    declarations: Mapping[str, DeclarationsWorkspaceDeclarationRefV1],
    projections: tuple[ModeloWorkspaceProjectionV1, ...],
) -> Mapping[str, ModeloWorkspaceReadSession]:
    sessions: dict[str, ModeloWorkspaceReadSession] = {}
    for projection in projections:
        target = projection.target
        work_unit_id = target.work_unit_id
        if target.bucket_id != bucket_id or work_unit_id is None or target.work_state is None:
            raise ModeloWorkspaceDeclarationAdmissionError(
                "a Modelo workspace projection does not name one current declaration target"
            )
        declaration = declarations.get(str(work_unit_id))
        if declaration is None or (
            target.modelo,
            target.filing_year,
            target.period,
            target.work_state,
        ) != (
            declaration.modelo,
            declaration.filing_year,
            declaration.period,
            declaration.state,
        ):
            raise ModeloWorkspaceDeclarationAdmissionError(
                "a Modelo workspace projection contradicts its admitted declaration target"
            )
        if work_unit_id in sessions:
            raise ModeloWorkspaceDeclarationAdmissionError("the generation carries duplicate Modelo workspace targets")
        sessions[str(work_unit_id)] = open_workspace_read_session(projection)
    return sessions


__all__ = ["ModeloWorkspaceDeclarationAdmissionError", "compose_installed_modelo_workspace_factory"]
