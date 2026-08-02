"""Typed ``--json`` payload schemas for registry CLI commands.

Each class declared here is a strict
:class:`OutputSchema` subclass and is decorated
with :func:`register_schema` so the
JSON-contract test suite can enumerate every registry command surface this
module covers.

Field sets match the production payload dicts constructed in ``registry.py``
at their emit sites. All sequence fields use ``list`` rather than ``tuple``
because ``model_dump(mode='json')`` serialises pydantic tuples as JSON arrays.

The application layer remains authoritative for registry validation, oracle
audits, workbook verification, filed-state comparison, and parity tape
execution. These schemas document the CLI transport shape that enters
:class:`SchemaEnvelope` through
:func:`_emit_envelope`.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from ...domain.calculations.registry import (
    CrossReferenceApplicabilityDeclaracion,
    ExportLayoutId,
    LegalRefId,
    ParityScenario,
    ParityTape,
    ParityTapeStatus,
    RegistryFiledStateComparison,
    RelationId,
    SourceRefId,
    WorkbookArtefactReport,
    WorkbookParityRefId,
    WorkbookParityRunReport,
    WorkbookRunnerAvailability,
)
from ._schemas import OutputSchema, register_schema


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
    support_removal_decision_count: int = Field(ge=0)


@register_schema("registry.inspect")
class RegistryInspectResult(OutputSchema):
    """JSON envelope for ``aeat app registry inspect``.

    Projects :class:`RegistryTreeReport` returned by
    :func:`inspect_registry_tree` in full: the registry/source roots, every
    inventory count (bounded non-negative -- a count can never be negative,
    even though the canonical report does not itself declare that bound),
    and the typed :class:`RegistryRevisionDetailPayload` rows. A malformed or
    missing detail row, or an unrecognised top-level key, is refused rather
    than forwarded.
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


@register_schema("registry.verify")
class RegistryVerifyResult(OutputSchema):
    """JSON envelope for ``aeat app registry verify``.

    Projects the validated :class:`RegistryTreeReport` returned by
    :func:`verify_registry_tree` in full, at parity with
    :class:`RegistryInspectResult`. ``verified`` marks the fail-fast
    registry/corpus validation branch.
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


@register_schema("registry.audit_oracles")
class RegistryAuditOraclesResult(OutputSchema):
    """JSON envelope for ``aeat app registry audit-oracles``.

    Mirrors :class:`RegistryOracleAuditReport` from
    :func:`audit_registry_oracles`. The report
    aggregates
    :func:`audit_registry_oracle_bindings`
    failures, applicability declarations, and orphan oracle ids for one
    :class:`OracleEnvironment`.
    """

    environment: str
    registered_oracle_ids: list[str] = []
    failure_count: int = Field(ge=0)
    failures: list[str] = []
    applicability_declarations: list[CrossReferenceApplicabilityDeclaracion] = []
    orphan_oracle_ids: list[str] = []


@register_schema("registry.verify_filed_state")
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


@register_schema("registry.workbooks.verify")
class RegistryWorkbooksVerifyResult(OutputSchema):
    """JSON envelope for ``aeat app registry workbooks verify``.

    Mirrors
    :class:`WorkbookBackendVerificationReport`
    returned by :func:`verify_registry_workbooks`.
    ``runner`` reports workbook backend availability, ``reports`` carries
    per-workbook artefact scans, and ``modelo_coverage`` summarizes
    per-modelo workbook support.
    """

    root: str
    workbook_count: int
    scanned_count: int
    formula_workbook_count: int
    unsupported_xls_count: int
    failed_count: int
    runner: dict[str, object]
    reports: list[dict[str, object]] = []
    modelo_coverage: list[dict[str, object]] = []
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class var shadows ConfigDict descriptor;
    # mypy assignment check is incorrect.
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("registry.parity.run")
class RegistryParityRunResult(OutputSchema):
    """JSON envelope for ``aeat app registry parity run``.

    Mirrors :class:`ParityTape` returned by
    :func:`run_registry_parity`. The payload includes
    the :class:`ParityScenario`, scanned
    workbook artefact, runner availability, and the registry workbook parity
    run report; ``path`` is added by the CLI as the archive destination.
    """

    created_at: datetime
    scenario_path: str | None = None
    scenario: ParityScenario
    workbook: WorkbookArtefactReport
    runner: WorkbookRunnerAvailability
    report: WorkbookParityRunReport
    path: str | None = None


@register_schema("registry.parity.replay")
class RegistryParityReplayResult(OutputSchema):
    """JSON envelope for ``aeat app registry parity replay``.

    Mirrors :class:`ParityTapeReplayReport`
    returned by :func:`replay_registry_parity`.
    ``stored`` is the archived :class:`ParityTape`;
    ``current`` is the fresh replay tape, and ``differences`` lists the stable
    JSON paths that diverged.
    """

    tape_path: str
    scenario_id: str
    status: ParityTapeStatus
    differences: list[str] = []
    stored: ParityTape
    current: ParityTape
