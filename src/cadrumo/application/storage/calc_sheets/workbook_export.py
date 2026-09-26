"""Application entry that materializes one modelo workbook through a transport port.

The plan is built here and the bytes are produced by an injected materializer, so
this module holds the sequence a caller needs -- resolve the authority snapshot,
build the one canonical plan, hand it to a transport, report what came back --
without naming a workbook library or a file system. A caller that wants an
``.xlsx`` payload composes the offline materializer; a caller that wants another
carrier composes that one, and the plan it receives is the same plan.

Nothing here writes the payload anywhere. Where an export file may be placed, and
under what confirmation, belongs to the export destination surface; this function
returns the bytes and the facts that identify them.

See Also:
    :func:`application.storage.calc_sheets.engine.build_export_plan`
        The one canonical plan builder this entry resolves its plan from.
    :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`
        The authority slice the plan is built from.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Protocol

from pydantic import BaseModel, Field, NonNegativeInt, PositiveInt, model_validator

from ....core.casilla_id import CasillaId
from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.filing_year import FilingYear
from ....core.identity.digest import ContentDigest
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.ids import ModeloId, RevisionId
from ....domain.calculations.registry.schema import RegistrySnapshot
from ...calculations.relation_prefill import resolve_relations_from_local_store
from .engine import build_export_plan
from .records import OperatorInputs, RelationValues, SheetExportPlan, TabName

type WorkbookSnapshotResolver = Callable[[ModeloId, Period], RegistrySnapshot]
"""Resolves the registry snapshot one workbook export is built from."""

type WorkbookPlanBuilder = Callable[..., SheetExportPlan]
"""Builds the export plan; the engine's builder unless a caller injects another."""


class SheetWorkbookMaterializer(Protocol):
    """Transport port that turns one export plan into a workbook payload.

    The port receives the plan and nothing else, which is what keeps the
    transports from disagreeing: a materializer cannot consult the registry, the
    ledger, or the operator's configuration, so everything the workbook says was
    decided once, by the plan builder.
    """

    def __call__(self, plan: SheetExportPlan, /) -> bytes:
        """Return the complete bytes of the workbook ``plan`` describes."""
        ...


class ModeloWorkbookExport(BaseModel):
    """One materialized modelo workbook and the facts that identify its bytes.

    The facts are validated against the payload they describe, so a caller
    logging or storing the digest cannot report a digest of something else. The
    payload carries taxpayer figures: it is returned to the caller, never written
    or logged here.
    """

    model_config = STRICT_FROZEN_CONFIG

    modelo: ModeloId
    revision: RevisionId
    period: str = Field(min_length=1, max_length=32)
    filing_year: FilingYear
    payload: bytes
    byte_size: PositiveInt
    sha256: ContentDigest
    #: The tabs every transport materializes, in the plan's write order.
    tab_names: tuple[str, ...] = Field(min_length=1)
    #: Distinct casillas the workbook carries, as an input cell or a live formula.
    casilla_count: NonNegativeInt

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _facts_describe_the_payload(self) -> ModeloWorkbookExport:
        if self.byte_size != len(self.payload):
            raise ValueError(
                f"workbook byte_size {self.byte_size} does not match the payload length {len(self.payload)}",
            )
        digest = hashlib.sha256(self.payload).hexdigest()
        if self.sha256 != digest:
            raise ValueError("workbook sha256 does not match the payload digest")
        return self


def resolve_published_snapshot(modelo: ModeloId, period: Period) -> RegistrySnapshot:
    """Resolve one snapshot from the published authority, as runtime reads it."""
    with bundled_indexed_authority().operation() as operation:
        return operation.snapshot(
            modelo,
            filing_year=period.filing_year,
            period=period.registry_token,
        )


def build_modelo_export_plan(
    snapshot: RegistrySnapshot,
    *,
    prefill_relations: bool,
    plan_builder: WorkbookPlanBuilder = build_export_plan,
) -> SheetExportPlan:
    """Build the workbook plan for ``snapshot``.

    Args:
        snapshot: The resolved
            :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`
            to export.
        prefill_relations: Resolve the snapshot's cross-revision relations from
            this installation's own prior filings and stamp their provenance onto
            the workbook. Left off, the relation cells stay blank rather than
            claiming a value no local filing supports.
        plan_builder: The plan builder; the engine's own unless injected.

    Returns:
        :class:`~application.storage.calc_sheets.records.SheetExportPlan`: The plan
        every transport materializes.
    """
    if prefill_relations:
        return plan_builder(
            snapshot,
            operator_inputs=OperatorInputs(),
            relation_resolver=resolve_relations_from_local_store,
        )
    return plan_builder(
        snapshot,
        operator_inputs=OperatorInputs(),
        relation_values=RelationValues(),
    )


def export_modelo_workbook(
    *,
    modelo: ModeloId,
    period: Period,
    materializer: SheetWorkbookMaterializer,
    prefill_relations: bool = False,
    snapshot_resolver: WorkbookSnapshotResolver = resolve_published_snapshot,
    plan_builder: WorkbookPlanBuilder = build_export_plan,
) -> ModeloWorkbookExport:
    """Materialize the workbook for one modelo and filing period.

    Args:
        modelo: The modelo to export.
        period: The filing period, which carries its own filing year.
        materializer: The transport that turns the plan into bytes.
        prefill_relations: Forwarded to :func:`build_modelo_export_plan`.
        snapshot_resolver: Resolves the registry snapshot; the published
            authority reader unless injected.
        plan_builder: Builds the plan; the engine's builder unless injected.

    Returns:
        :class:`ModeloWorkbookExport`: The payload with the modelo, revision,
        period, byte size, digest, tab names, and casilla count it carries.
    """
    snapshot = snapshot_resolver(modelo, period)
    plan = build_modelo_export_plan(snapshot, prefill_relations=prefill_relations, plan_builder=plan_builder)
    payload = materializer(plan)
    return ModeloWorkbookExport(
        modelo=snapshot.modelo.id,
        revision=snapshot.revision.id,
        period=plan.metadata.period.registry_token,
        filing_year=plan.metadata.filing_year,
        payload=payload,
        byte_size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        tab_names=tuple(tab.value for tab in TabName),
        casilla_count=len(_covered_casilla_ids(plan)),
    )


def _covered_casilla_ids(plan: SheetExportPlan) -> frozenset[CasillaId]:
    """Return every casilla the plan carries, as an input cell or a live formula."""
    from_values = {cell.casilla_id for cell in plan.value_cells if cell.casilla_id is not None}
    return frozenset(from_values | {cell.casilla_id for cell in plan.formula_cells})


__all__ = [
    "ModeloWorkbookExport",
    "SheetWorkbookMaterializer",
    "WorkbookPlanBuilder",
    "WorkbookSnapshotResolver",
    "build_modelo_export_plan",
    "export_modelo_workbook",
    "resolve_published_snapshot",
]
