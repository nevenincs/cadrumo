"""Typed ``--json`` payload schemas for registry-corpus CLI commands.

Each class declared here is a strict
:class:`OutputSchema` subclass and a deferred public schema target referenced
by production-authored CommandSpec so the
JSON-contract test suite can enumerate every registry-corpus command surface
this module covers.

Field sets match the production payload dicts constructed in
``_registry_corpus.py`` at their emit sites. All sequence fields use ``list``
rather than ``tuple`` because ``model_dump(mode='json')`` serialises pydantic
tuples as JSON arrays, and the strict ``OutputSchema`` base does not coerce
lists to tuples on re-validation.

The application registry facade remains the authority for legal-citation and
manual-corpus semantics. These payload classes validate the CLI transport shape
that enters :class:`SchemaEnvelope` through :func:`emit_envelope`.
"""

from __future__ import annotations

from ...application.registry.corpus import (
    RegistryCitationArticleProjection,
    RegistryCitationReferenceProjection,
    RegistryCorpusIssueProjection,
    RegistryTopicProjection,
)
from ...core.json_contract import OutputSchema

# ---------------------------------------------------------------------------
# Graph-declared schema targets
# ---------------------------------------------------------------------------


class CitationListResult(OutputSchema):
    """JSON envelope for ``aeat app registry citations list``.

    Mirrors :class:`RegistryCitationsListReport`:
    reviewed legal-reference rows are projected as
    :class:`RegistryCitationReferenceProjection`,
    alongside typed localized topic rows.
    """

    operation: str = "registry.citations.list"
    reference_count: int
    tag_filter: str | None = None
    topic_count: int
    topics: list[RegistryTopicProjection] = []
    references: list[RegistryCitationReferenceProjection] = []


class CitationShowResult(OutputSchema):
    """JSON envelope for ``aeat app registry citations view``.

    Validates :class:`RegistryCitationShowReport`
    under the CLI command path ``registry.citations.view``. The inner
    ``operation`` remains the application report's ``registry.citations.show``
    value and may include a
    :class:`RegistryCitationArticleProjection`.
    """

    operation: str = "registry.citations.show"
    reference: RegistryCitationReferenceProjection
    articulo: RegistryCitationArticleProjection | None = None
    related_topics: list[RegistryTopicProjection] = []


class CitationVerifyResult(OutputSchema):
    """JSON envelope for ``aeat app registry citations verify``.

    Mirrors
    :class:`RegistryCitationsVerificationReport`.
    Issue rows use
    :class:`RegistryCorpusIssueProjection`, and
    ``passed`` is the authority for whether the CLI exits successfully.
    """

    operation: str = "registry.citations.verify"
    reference_count: int
    issue_count: int
    passed: bool
    topic_count: int
    issues: list[RegistryCorpusIssueProjection] = []
    topics: list[RegistryTopicProjection] = []


class ManualListResult(OutputSchema):
    """JSON envelope for ``aeat app registry manuals list``.

    Mirrors :class:`RegistryManualsListReport`.
    ``parts`` contains discovered
    :class:`RegistryManualPartProjection` rows
    keyed by :class:`RegistryManualId`,
    :class:`ManualPart`, and tax year.
    """

    operation: str = "registry.manuals.list"
    manual_filter: str | None = None
    year_filter: int | None = None
    part_count: int
    topic_count: int
    parts: list[dict[str, object]] = []
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class-variable assignment triggers mypy
    # [assignment]; suppression is the only escape without a mypy plugin upgrade.
    model_config = {"extra": "allow"}  # type: ignore[assignment]  # reason: TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR: pydantic v2 model_config class-variable assignment triggers mypy [assignment]; suppression is...


class ManualShowResult(OutputSchema):
    """JSON envelope for ``aeat app registry manuals view``.

    Mirrors :class:`RegistryManualShowReport` for
    one local manual part. When extracted structure is available, ``section``
    carries a
    :class:`RegistryManualSectionProjection`;
    otherwise the report remains a manifest-level view over the source PDF.
    """

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
    model_config = {"extra": "allow"}  # type: ignore[assignment]  # reason: TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR: pydantic v2 model_config class-variable assignment triggers mypy [assignment]; suppression is...


class ManualRulesListResult(OutputSchema):
    """JSON envelope for ``aeat app registry manuals rules``.

    Mirrors :class:`RegistryManualRulesReport`.
    ``rules`` contains
    :class:`RegistryManualRuleProjection` rows whose
    manual casilla references are checked against
    :class:`ValidatedRegistryAuthority` by
    the application service.
    """

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
    model_config = {"extra": "allow"}  # type: ignore[assignment]  # reason: TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR: pydantic v2 model_config class-variable assignment triggers mypy [assignment]; suppression is...


class ManualVerifyResult(OutputSchema):
    """JSON envelope for ``aeat app registry manuals verify``.

    Mirrors :class:`RegistryManualVerificationReport`
    after manual-corpus validation and
    :class:`ValidatedRegistryAuthority`
    casilla cross-reference checks. Counts split total issues into error and
    warning severities; ``passed`` controls the command exit status.
    """

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
    model_config = {"extra": "allow"}  # type: ignore[assignment]  # reason: TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR: pydantic v2 model_config class-variable assignment triggers mypy [assignment]; suppression is...
