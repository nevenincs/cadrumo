"""Typed ``--json`` payload schemas for registry CLI commands.

Each class declared here is a strict :class:`OutputSchema` subclass and is
decorated with :func:`register_schema` so the JSON-contract test suite can
enumerate every registry command surface this module covers.

Field sets match the production payload dicts constructed in ``registry.py``
at their emit sites. All sequence fields use ``list`` rather than ``tuple``
because ``model_dump(mode='json')`` serialises pydantic tuples as JSON arrays.
"""

from __future__ import annotations

from ._schemas import OutputSchema, register_schema


@register_schema("registry.inspect")
class RegistryInspectResult(OutputSchema):
    """JSON envelope for ``aeat app registry inspect``."""

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
    """JSON envelope for ``aeat app registry verify``."""

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

    Mirrors ``RegistryOracleAuditReport.model_dump(mode='json')``.
    Sequence fields are typed as ``list[...]`` because tuples serialise
    to JSON arrays and the strict envelope does not coerce arrays back
    to tuples on re-validation.
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

    Mirrors ``FiledStateVerificationReport.model_dump(mode='json')``.
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

    Mirrors ``WorkbookBackendVerificationReport.model_dump(mode='json')``.
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

    Mirrors ``ParityTape.model_dump(mode='json')``.
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

    Mirrors ``ParityTapeReplayReport.model_dump(mode='json')``.
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
