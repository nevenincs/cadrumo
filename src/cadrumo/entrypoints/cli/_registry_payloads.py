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

from ...core.json_contract import OutputSchema
from ...core.text_bounds import NonEmptyStr
from ...domain.calculations.registry.filed_state import RegistryFiledStateComparison
from ...domain.calculations.registry.ids import ExportLayoutId, LegalRefId, RelationId, SourceRefId, WorkbookParityRefId
from ...domain.calculations.registry.live_parity import ParityFieldVerdict, ParityVerdict


class RegistryWorkbookParityDetailPayload(OutputSchema):
    """One workbook-parity coverage row, mirroring :class:`RegistryWorkbookParityDetailReport`."""

    id: WorkbookParityRefId
    workbook_source: SourceRefId
    formula_coverage: str
    runner_required: bool
    output_cell_count: int


class RegistryRevisionDetailPayload(OutputSchema):
    """One modelo revision's registry inventory, mirroring :class:`RegistryRevisionDetailReport`."""

    modelo: NonEmptyStr
    revision: NonEmptyStr
    legal_refs: list[LegalRefId] = []
    source_refs: list[SourceRefId] = []
    export_layout_ids: list[ExportLayoutId] = []
    export_layout_count: int
    export_record_count: int
    export_field_count: int
    deadline_window_count: int
    deadline_periods: list[str] = []
    relation_ids: list[RelationId] = []
    relation_count: int
    relation_dependency_roles: list[str] = []
    filing_schedule_ids: list[str] = []
    filing_schedule_count: int
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
    registry/source roots, every inventory count (bounded non-negative by
    :class:`~application.registry.RegistryTreeReport`, which declares that
    bound because the counts are ``len()`` tallies; this schema is the wire
    shape of a report that already satisfies it), the typed
    :class:`RegistryRevisionDetailPayload`
    rows, and ``verified`` (only meaningful for ``verify``, which is the
    fail-fast registry/corpus validation branch; ``inspect`` always reports
    it ``True``, as :func:`inspect_registry_tree` does not validate). A
    malformed or missing detail row, or an unrecognised top-level key, is
    refused rather than forwarded.
    """

    registry_root: str
    source_root: str | None = None
    modelo_count: int
    revision_count: int
    legal_reference_count: int
    source_reference_count: int
    casilla_count: int
    formula_count: int
    extraction_profile_count: int
    cross_reference_count: int
    workbook_parity_ref_count: int
    verification_expectation_count: int
    application_link_count: int
    application_link_surfaces: list[str] = []
    relation_count: int
    relation_dependency_roles: list[str] = []
    filing_schedule_count: int
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


class RegistryReplayParityFieldPayload(OutputSchema):
    """One casilla comparison inside a replayed capture, mirroring :class:`ParityFieldComparison`.

    ``verdict`` carries the three field-level outcomes verbatim -- ``match``,
    ``mismatch``, ``unverifiable`` -- rather than a boolean, so an expected
    casilla the capture never observed stays distinguishable from agreement.
    """

    name: NonEmptyStr
    expected: str
    observed: str
    verdict: ParityFieldVerdict


class RegistryReplayParityPayloadResult(OutputSchema):
    """One bundled Renta WEB Open capture's parity outcome."""

    payload_name: NonEmptyStr
    scenario_id: str | None = None
    verdict: ParityVerdict
    narrative: NonEmptyStr
    raw_evidence_locator: str | None = None
    fields: list[RegistryReplayParityFieldPayload] = []


class RegistryReplayParityResult(OutputSchema):
    """JSON envelope for ``aeat app registry replay-parity``.

    Mirrors :class:`RentaWebOpenReplayParityReport`. ``registry_validated``
    records whether the guard-policy declaration came from a validated
    authority or a governance-grade tree read, so the envelope is never read as
    validated authority it does not carry.
    """

    corpus: str
    oracle_id: NonEmptyStr
    cross_reference_id: NonEmptyStr
    guard_policy_id: NonEmptyStr
    registry_validated: bool
    verdict: ParityVerdict
    compared_field_count: int
    matched_payload_count: int
    mismatched_payload_count: int
    unverifiable_payload_count: int
    blocked_payload_count: int
    payloads: list[RegistryReplayParityPayloadResult] = []
