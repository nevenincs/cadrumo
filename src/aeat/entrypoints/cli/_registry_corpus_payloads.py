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
# Shared sub-models (not registered — used as nested types)
# ---------------------------------------------------------------------------


class CitationReferencePayload(OutputSchema):
    """One citation reference row nested in citation results."""

    id: str
    kind: str
    number: str
    boe_id: str
    short_title: str


class CitationIssuePayload(OutputSchema):
    """One verification issue nested in citation verify results."""

    level: str
    code: str
    reference_id: str | None = None
    message: str


class ManualPartPayload(OutputSchema):
    """One manual part row nested in manuals list results."""

    manual_id: str
    year: int
    part: str
    root: str


class ManualIssuePayload(OutputSchema):
    """One verification issue nested in manual verify results."""

    level: str
    code: str
    reference_id: str | None = None
    message: str


class ManualRulePayload(OutputSchema):
    """One rule nested in manual rules results."""

    rule_id: str
    kind: str
    section_id: str
    references_casillas: list[str] = []


# ---------------------------------------------------------------------------
# Registered schemas
# ---------------------------------------------------------------------------


@register_schema("registry_corpus.citations.list")
class CitationListResult(OutputSchema):
    """JSON envelope for ``aeat app registry citations list``."""

    operation: str = "registry.citations.list"
    reference_count: int
    tag_filter: str | None = None
    topic_count: int
    references: list[dict] = []
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("registry_corpus.citations.show")
class CitationShowResult(OutputSchema):
    """JSON envelope for ``aeat app registry citations view``."""

    operation: str = "registry.citations.show"
    reference: dict = {}
    articulo: dict | None = None
    related_topics: list[dict] = []
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("registry_corpus.citations.verify")
class CitationVerifyResult(OutputSchema):
    """JSON envelope for ``aeat app registry citations verify``."""

    operation: str = "registry.citations.verify"
    reference_count: int
    issue_count: int
    passed: bool
    topic_count: int
    issues: list[dict] = []
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("registry_corpus.manuals.list")
class ManualListResult(OutputSchema):
    """JSON envelope for ``aeat app registry manuals list``."""

    operation: str = "registry.manuals.list"
    manual_filter: str | None = None
    year_filter: int | None = None
    part_count: int
    topic_count: int
    parts: list[dict] = []
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("registry_corpus.manuals.show")
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
    section: dict | None = None
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("registry_corpus.manuals.rules.list")
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
    rules: list[dict] = []
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("registry_corpus.manuals.verify")
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
    issues: list[dict] = []
    model_config = {"extra": "allow"}  # type: ignore[assignment]
