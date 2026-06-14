"""Typed ``--json`` payload schemas for registry-corpus CLI commands.

Each class declared here is a strict :class:`OutputSchema` subclass and is
decorated with :func:`register_schema` so the JSON-contract test suite can
enumerate every registry-corpus command surface this module covers.

Field sets match the production payload dicts constructed in
``_registry_corpus.py`` at their emit sites. All sequence fields use ``list``
rather than ``tuple`` because ``model_dump(mode='json')`` serialises pydantic
tuples as JSON arrays, and the strict ``OutputSchema`` base does not coerce
lists to tuples on re-validation.
"""

from __future__ import annotations

from ._schemas import OutputSchema, register_schema

# ---------------------------------------------------------------------------
# Registered schemas
# ---------------------------------------------------------------------------


@register_schema("registry.citations.list")
class CitationListResult(OutputSchema):
    """JSON envelope for ``aeat app registry citations list``."""

    operation: str = "registry.citations.list"
    reference_count: int
    tag_filter: str | None = None
    topic_count: int
    references: list[dict[str, object]] = []
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class-variable assignment triggers mypy
    # [assignment]; suppression is the only escape without a mypy plugin upgrade.
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("registry.citations.view")
class CitationShowResult(OutputSchema):
    """JSON envelope for ``aeat app registry citations view``."""

    operation: str = "registry.citations.show"
    reference: dict[str, object] = {}
    articulo: dict[str, object] | None = None
    related_topics: list[dict[str, object]] = []
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class-variable assignment triggers mypy
    # [assignment]; suppression is the only escape without a mypy plugin upgrade.
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("registry.citations.verify")
class CitationVerifyResult(OutputSchema):
    """JSON envelope for ``aeat app registry citations verify``."""

    operation: str = "registry.citations.verify"
    reference_count: int
    issue_count: int
    passed: bool
    topic_count: int
    issues: list[dict[str, object]] = []
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class-variable assignment triggers mypy
    # [assignment]; suppression is the only escape without a mypy plugin upgrade.
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("registry.manuals.list")
class ManualListResult(OutputSchema):
    """JSON envelope for ``aeat app registry manuals list``."""

    operation: str = "registry.manuals.list"
    manual_filter: str | None = None
    year_filter: int | None = None
    part_count: int
    topic_count: int
    parts: list[dict[str, object]] = []
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class-variable assignment triggers mypy
    # [assignment]; suppression is the only escape without a mypy plugin upgrade.
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("registry.manuals.view")
class ManualShowResult(OutputSchema):
    """JSON envelope for ``aeat app registry manuals view``."""

    operation: str = "registry.manuals.show"
    manual_id: str
    year: int
    part: str
    title: str | None = None
    source_pdf_url: str
    chapter_count: int
    section_count: int
    structure_available: bool
    topic_count: int
    section: dict[str, object] | None = None
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class-variable assignment triggers mypy
    # [assignment]; suppression is the only escape without a mypy plugin upgrade.
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("registry.manuals.rules")
class ManualRulesListResult(OutputSchema):
    """JSON envelope for ``aeat app registry manuals rules``."""

    operation: str = "registry.manuals.rules"
    manual_id: str
    year: int
    part: str
    kind_filter: str | None = None
    structure_available: bool
    rule_count: int
    topic_count: int
    rules: list[dict[str, object]] = []
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class-variable assignment triggers mypy
    # [assignment]; suppression is the only escape without a mypy plugin upgrade.
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("registry.manuals.verify")
class ManualVerifyResult(OutputSchema):
    """JSON envelope for ``aeat app registry manuals verify``."""

    operation: str = "registry.manuals.verify"
    manual_id: str
    year: int
    part: str
    issue_count: int
    error_count: int
    warning_count: int
    passed: bool
    topic_count: int
    issues: list[dict[str, object]] = []
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class-variable assignment triggers mypy
    # [assignment]; suppression is the only escape without a mypy plugin upgrade.
    model_config = {"extra": "allow"}  # type: ignore[assignment]
