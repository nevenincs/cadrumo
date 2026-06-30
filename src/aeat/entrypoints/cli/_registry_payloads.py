"""Typed ``--json`` payload schemas for registry CLI commands.

Each class declared here is a strict
:class:`~aeat.entrypoints.cli._schemas.OutputSchema` subclass and is decorated
with :func:`~aeat.entrypoints.cli._schemas.register_schema` so the
JSON-contract test suite can enumerate every registry command surface this
module covers.

Field sets match the production payload dicts constructed in ``registry.py``
at their emit sites. All sequence fields use ``list`` rather than ``tuple``
because ``model_dump(mode='json')`` serialises pydantic tuples as JSON arrays.

The application layer remains authoritative for registry validation, oracle
audits, workbook verification, filed-state comparison, and parity tape
execution. These schemas document the CLI transport shape that enters
:class:`~aeat.entrypoints.cli._schemas.SchemaEnvelope`.
"""

from __future__ import annotations

from ._schemas import OutputSchema, register_schema


@register_schema("registry.inspect")
class RegistryInspectResult(OutputSchema):
    """JSON envelope for ``aeat app registry inspect``.

    Mirrors the inventory half of
    :class:`~aeat.application.registry.RegistryTreeReport` returned by
    :func:`~aeat.application.registry.inspect_registry_tree`. Extra fields carry
    per-revision detail rows such as
    :class:`~aeat.application.registry.RegistryRevisionDetailReport`.
    """

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
    modelos: list[str] = []
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class-variable assignment triggers mypy
    # [assignment]; suppression is the only escape without a mypy plugin upgrade.
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("registry.verify")
class RegistryVerifyResult(OutputSchema):
    """JSON envelope for ``aeat app registry verify``.

    Mirrors the validated :class:`~aeat.application.registry.RegistryTreeReport`
    returned by :func:`~aeat.application.registry.verify_registry_tree`.
    ``verified`` marks the fail-fast registry/corpus validation branch, while
    extra fields preserve the same detailed inventory available from inspect.
    """

    verified: bool
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
    modelos: list[str] = []
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class-variable assignment triggers mypy
    # [assignment]; suppression is the only escape without a mypy plugin upgrade.
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("registry.audit_oracles")
class RegistryAuditOraclesResult(OutputSchema):
    """JSON envelope for ``aeat app registry audit-oracles``.

    Mirrors :class:`~aeat.application.registry.RegistryOracleAuditReport` from
    :func:`~aeat.application.registry.audit_registry_oracles`. The report
    aggregates
    :func:`~aeat.domain.calculations.registry.audit_registry_oracle_bindings`
    failures, applicability declarations, and orphan oracle ids for one
    :class:`~aeat.domain.calculations.registry.OracleEnvironment`.
    """

    environment: str
    registered_oracle_ids: list[str] = []
    failure_count: int
    failures: list[str] = []
    applicability_declarations: list[dict[str, object]] = []
    orphan_oracle_ids: list[str] = []
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class-variable assignment triggers mypy
    # [assignment]; suppression is the only escape without a mypy plugin upgrade.
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("registry.verify_filed_state")
class RegistryVerifyFiledStateResult(OutputSchema):
    """JSON envelope for ``aeat app registry verify-filed-state``.

    Mirrors :class:`~aeat.application.registry.FiledStateVerificationReport`
    from :func:`~aeat.application.registry.verify_filed_state`. ``comparison``
    contains the
    :class:`~aeat.domain.calculations.registry.RegistryFiledStateComparison`
    between local registry calculation output and the captured filed AEAT
    observation.
    """

    observation_path: str
    source_observation_paths: list[str] = []
    comparison: dict[str, object]
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class var shadows ConfigDict descriptor;
    # mypy assignment check is incorrect.
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("registry.workbooks.verify")
class RegistryWorkbooksVerifyResult(OutputSchema):
    """JSON envelope for ``aeat app registry workbooks verify``.

    Mirrors
    :class:`~aeat.domain.calculations.registry.WorkbookBackendVerificationReport`
    returned by :func:`~aeat.application.registry.verify_registry_workbooks`.
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

    Mirrors :class:`~aeat.domain.calculations.registry.ParityTape` returned by
    :func:`~aeat.application.registry.run_registry_parity`. The payload includes
    the :class:`~aeat.domain.calculations.registry.ParityScenario`, scanned
    workbook artefact, runner availability, and the registry workbook parity
    run report; ``path`` is added by the CLI as the archive destination.
    """

    created_at: str
    scenario_path: str | None = None
    scenario: dict[str, object]
    workbook: dict[str, object]
    runner: dict[str, object]
    report: dict[str, object]
    path: str | None = None
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class var shadows ConfigDict descriptor;
    # mypy assignment check is incorrect.
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("registry.parity.replay")
class RegistryParityReplayResult(OutputSchema):
    """JSON envelope for ``aeat app registry parity replay``.

    Mirrors :class:`~aeat.domain.calculations.registry.ParityTapeReplayReport`
    returned by :func:`~aeat.application.registry.replay_registry_parity`.
    ``stored`` is the archived :class:`~aeat.domain.calculations.registry.ParityTape`;
    ``current`` is the fresh replay tape, and ``differences`` lists the stable
    JSON paths that diverged.
    """

    tape_path: str
    scenario_id: str
    status: str
    differences: list[str] = []
    stored: dict[str, object]
    current: dict[str, object]
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class var shadows ConfigDict descriptor;
    # mypy assignment check is incorrect.
    model_config = {"extra": "allow"}  # type: ignore[assignment]
