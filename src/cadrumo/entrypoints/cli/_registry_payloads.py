"""Typed ``--json`` payload schemas for registry CLI commands.

Each class declared here is a strict
:class:`OutputSchema` subclass and a deferred public schema target referenced
by production-authored CommandSpec so the
JSON-contract test suite can enumerate every registry command surface this
module covers.

Field sets match the production payload dicts constructed in ``registry.py``
at their emit sites. All sequence fields use ``list`` rather than ``tuple``
because ``model_dump(mode='json')`` serialises pydantic tuples as JSON arrays.

The application layer remains authoritative for registry validation and
filed-state comparison. These schemas document the CLI transport shape that enters
:class:`SchemaEnvelope` through
:func:`emit_envelope`.
"""

from __future__ import annotations

from pydantic import Field

from ...core.json_contract import OutputSchema
from cadrumo.domain.calculations.registry.filed_state import RegistryFiledStateComparison
from cadrumo.domain.calculations.registry.ids import ExportLayoutId, LegalRefId, RelationId, SourceRefId, WorkbookParityRefId


class RegistryWorkbookParityDetailPayload(OutputSchema):
    """One workbook-parity coverage row, mirroring :class:`RegistryWorkbookParityDetailReport`."""

    id: WorkbookParityRefId
    workbook_source: SourceRefId
    formula_coverage: str
    runner_required: bool
    output_cell_count: int = Field(ge=0)


class RegistryRevisionDetailPayload(OutputSchema):
    """One modelo revision's registry inventory, mirroring :class:`RegistryRevisionDetailReport`."""

    modelo: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    legal_refs: list[LegalRefId] = []
    source_refs: list[SourceRefId] = []
    export_layout_ids: list[ExportLayoutId] = []
    export_layout_count: int = Field(ge=0)
    export_record_count: int = Field(ge=0)
    export_field_count: int = Field(ge=0)
    deadline_window_count: int = Field(ge=0)
    deadline_periods: list[str] = []
    relation_ids: list[RelationId] = []
    relation_count: int = Field(ge=0)
    relation_dependency_roles: list[str] = []
    filing_schedule_ids: list[str] = []
    filing_schedule_count: int = Field(ge=0)
    portal_guard_policy_ids: list[str] = []
    workbook_parity: list[RegistryWorkbookParityDetailPayload] = []


class RegistryInspectResult(OutputSchema):
    """JSON envelope shared by ``aeat app registry inspect`` and ``... verify``.

    Both commands project the same :class:`RegistryTreeReport` shape in
    full -- ``inspect`` from :func:`inspect_registry_tree`, ``verify`` from
    the validated result of :func:`verify_registry_tree` -- so one schema is
    referenced under both command paths (the pattern
    :class:`~cadrumo.entrypoints.cli._payloads_modelo_reconcile.ModeloReconcileResult`
    already established for ``modelo reconcile pull``/``file``). Carries the
    registry/source roots, every inventory count (bounded non-negative -- a
    count can never be negative, even though the canonical report does not
    itself declare that bound), the typed :class:`RegistryRevisionDetailPayload`
    rows, and ``verified`` (only meaningful for ``verify``, which is the
    fail-fast registry/corpus validation branch; ``inspect`` always reports
    it ``True``, as :func:`inspect_registry_tree` does not validate). A
    malformed or missing detail row, or an unrecognised top-level key, is
    refused rather than forwarded.
    """

    registry_root: str
    source_root: str | None = None
    modelo_count: int = Field(ge=0)
    revision_count: int = Field(ge=0)
    legal_reference_count: int = Field(ge=0)
    source_reference_count: int = Field(ge=0)
    casilla_count: int = Field(ge=0)
    formula_count: int = Field(ge=0)
    extraction_profile_count: int = Field(ge=0)
    cross_reference_count: int = Field(ge=0)
    workbook_parity_ref_count: int = Field(ge=0)
    verification_expectation_count: int = Field(ge=0)
    application_link_count: int = Field(ge=0)
    application_link_surfaces: list[str] = []
    relation_count: int = Field(ge=0)
    relation_dependency_roles: list[str] = []
    filing_schedule_count: int = Field(ge=0)
    modelos: list[str] = []
    revision_details: list[RegistryRevisionDetailPayload] = []
    verified: bool
    verified_invariant_families: list[str] = []
    unverified_invariant_families: list[str] = []


class RegistryVerifyFiledStateResult(OutputSchema):
    """JSON envelope for ``aeat app registry verify-filed-state``.

    Mirrors :class:`FiledStateVerificationReport`
    from :func:`verify_filed_state`. ``comparison``
    contains the
    :class:`RegistryFiledStateComparison`
    between local registry calculation output and the captured filed AEAT
    observation.
    """

    observation_path: str
    source_observation_paths: list[str] = []
    comparison: RegistryFiledStateComparison
