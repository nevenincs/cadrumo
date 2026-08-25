"""Application services for registry corpus projections.

Citation services project :class:`TopicCatalogue` entries and reviewed
registry legal references into operator-facing reports.
Manual services project extracted manual parts, rules, and verification
results. Manual verification can receive a
:class:`ValidatedRegistryAuthority` so manual casilla references are
checked against the same validated registry authority as runtime
registry workflows.

All services are local and read-only: they load bundled topic, registry,
and manual catalogues, then return strict report records for the CLI
layer. They do not fetch manuals, mutate registry TOML, or emit bucket
events.

See Also:
    :class:`RegistryCitationsListReport`,
    :class:`RegistryManualsListReport`,
    :class:`RegistryManualRulesReport`,
    :class:`RegistryManualVerificationReport`, and
    :class:`RegistryCorpusIssueProjection`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from cadrumo.domain.calculations.registry.schema_references import LegalReference, RegistryExternalLink

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import ActionEvidenceProvenance, NoRecoveryOutcome
from ...core.config import Settings, coerce_output_language_setting, load_settings
from ...core.directory_scan import scan_directory
from ...core.errors import BaseSeverity
from ...core.i18n import SUPPORTED_OUTPUT_LANGUAGES, output_language, tr
from ...core.logging import get_logger
from ...core.topics import Topic, TopicCatalogue, load_topic_catalogue
from ...domain.calculations.registry.authority import (
    ValidatedRegistryAuthority,
    bundled_authority,
)
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.ids import LegalRefId
from ...domain.calculations.registry.legal import verify_legal_catalogue
from ...domain.manuals import (
    ManualCasillaReference,
    ManualId,
    ManualNotFoundError,
    ManualPart,
    ManualVerificationIssue,
    ManualVerificationReport,
    find_rules,
    iter_sections,
    load_manual,
    verify_manual_dir,
)
from ...domain.manuals import (
    load_catalogue as load_manual_catalogue,
)
from ._corpus_manual_helpers import load_manual_manifest as _load_manual_manifest
from ._corpus_manual_helpers import (
    manual_report_with_registry_casilla_issues as _manual_report_with_registry_casilla_issues,
)
from ._corpus_manual_helpers import manual_rule_kind as _manual_rule_kind
from .errors import RegistryApplicationInputError, RegistryPreconditionCondition, registry_terminal_refusal

_LOGGER = get_logger(__name__)

_ProjectionText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
_ProjectionDateText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10)]


class RegistryManualId(StrEnum):
    """Manual identifiers approved for the registry manual operator surface.

    These values intentionally narrow the wider :class:`ManualId` domain to the
    manual families exposed by ``aeat app registry manuals``.
    """

    RENTA = "renta"
    IVA = "iva"


class RegistryTopicProjection(BaseModel):
    """Resolved :class:`Topic` content exposed by registry corpus services.

    Topic projections attach localized explanatory text and related legal refs
    to citation and manual reports without widening those report contracts to
    the full :class:`TopicCatalogue`.
    """

    model_config = _STRICT_FROZEN

    slug: _ProjectionText
    title: _ProjectionText
    body: _ProjectionText
    see_also: tuple[_ProjectionText, ...] = ()
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)


class RegistryCitationReferenceProjection(BaseModel):
    """One legal document row in the registry citations surface.

    The row is derived from reviewed registry :class:`LegalReference` entries
    grouped by document id, preserving the document id for article lookup and
    topic cross-linking.
    """

    model_config = _STRICT_FROZEN

    id: _ProjectionText
    kind: _ProjectionText
    number: _ProjectionText
    title: _ProjectionText
    published_at: _ProjectionDateText
    boe_id: _ProjectionText
    boe_url: RegistryExternalLink
    tags: tuple[_ProjectionText, ...] = ()
    articulo_count: int = Field(ge=0)
    short_title: _ProjectionText
    topic_slugs: tuple[_ProjectionText, ...] = ()


class RegistryCitationArticleProjection(BaseModel):
    """One cited article projection in the registry citations surface.

    Built from the current reviewed registry :class:`LegalReference` entry and
    its bundled authoritative corpus permalink.
    """

    model_config = _STRICT_FROZEN

    numero: _ProjectionText
    titulo: _ProjectionText
    summary: _ProjectionText
    permalink: RegistryExternalLink
    cite: _ProjectionText


class RegistryCitationsListCommand(BaseModel):
    """Application command for listing registry citations."""

    model_config = _STRICT_FROZEN

    tag: str | None = None


class RegistryCitationShowCommand(BaseModel):
    """Application command for showing one registry citation."""

    model_config = _STRICT_FROZEN

    legal_id: str = Field(min_length=1)
    articulo: str | None = None


class RegistryCitationsListReport(BaseModel):
    """Typed report for registry citation listing.

    Carries rendered :class:`RegistryTopicProjection` rows and
    :class:`RegistryCitationReferenceProjection` rows from the reviewed legal
    catalogue.
    """

    model_config = _STRICT_FROZEN

    operation: str = "registry.citations.list"
    reference_count: int = Field(ge=0)
    tag_filter: str | None = None
    topic_count: int = Field(ge=0)
    topics: tuple[RegistryTopicProjection, ...] = ()
    references: tuple[RegistryCitationReferenceProjection, ...] = ()


class RegistryCitationShowReport(BaseModel):
    """Typed report for a single registry citation lookup.

    Carries one :class:`RegistryCitationReferenceProjection`, optional
    article detail, and related :class:`RegistryTopicProjection` rows.
    """

    model_config = _STRICT_FROZEN

    operation: str = "registry.citations.show"
    reference: RegistryCitationReferenceProjection
    articulo: RegistryCitationArticleProjection | None = None
    related_topics: tuple[RegistryTopicProjection, ...] = ()


class RegistryCorpusIssueProjection(BaseModel):
    """Normalized issue row for registry corpus verification reports.

    Used by citation verification and manual verification so CLI payloads carry
    one stable issue shape even though the underlying domain issues come from
    different registry and corpus verifiers. ``level`` shares
    :class:`~cadrumo.core.errors.BaseSeverity` with every other diagnostic and
    validation issue in the project.
    """

    model_config = _STRICT_FROZEN

    level: BaseSeverity
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    reference_id: str | None = None


class RegistryCitationsVerificationReport(BaseModel):
    """Typed report for registry citation corpus verification."""

    model_config = _STRICT_FROZEN

    operation: str = "registry.citations.verify"
    reference_count: int = Field(ge=0)
    issue_count: int = Field(ge=0)
    issues: tuple[RegistryCorpusIssueProjection, ...] = ()
    passed: bool
    topic_count: int = Field(ge=0)
    topics: tuple[RegistryTopicProjection, ...] = ()


class RegistryManualPartProjection(BaseModel):
    """One discovered local :class:`ManualPart` row."""

    model_config = _STRICT_FROZEN

    manual_id: str = Field(min_length=1)
    year: int = Field(ge=2000, le=2100)
    part: str = Field(min_length=1)
    root: str = Field(min_length=1)


class RegistryManualsListCommand(BaseModel):
    """Application command for listing registry manuals."""

    model_config = _STRICT_FROZEN

    manual: RegistryManualId | None = None
    year: int | None = Field(default=None, ge=2000, le=2100)


class RegistryManualShowCommand(BaseModel):
    """Application command for showing one registry manual."""

    model_config = _STRICT_FROZEN

    manual: RegistryManualId
    year: int = Field(ge=2000, le=2100)
    part: ManualPart = ManualPart.SINGLE
    section: str | None = None


class RegistryManualRulesCommand(BaseModel):
    """Application command for listing registry manual rules."""

    model_config = _STRICT_FROZEN

    manual: RegistryManualId
    year: int = Field(ge=2000, le=2100)
    part: ManualPart = ManualPart.SINGLE
    kind: str | None = None


class RegistryManualVerifyCommand(BaseModel):
    """Application command for verifying one registry manual part."""

    model_config = _STRICT_FROZEN

    manual: RegistryManualId
    year: int = Field(ge=2000, le=2100)
    part: ManualPart = ManualPart.SINGLE


class RegistryManualsListReport(BaseModel):
    """Typed report for registry manual listing.

    Carries discovered :class:`RegistryManualPartProjection` rows plus
    topic projections shared with the citation surfaces.
    """

    model_config = _STRICT_FROZEN

    operation: str = "registry.manuals.list"
    manual_filter: str | None = None
    year_filter: int | None = None
    part_count: int = Field(ge=0)
    parts: tuple[RegistryManualPartProjection, ...] = ()
    topic_count: int = Field(ge=0)
    topics: tuple[RegistryTopicProjection, ...] = ()


class RegistryManualSectionProjection(BaseModel):
    """One extracted manual section projection."""

    model_config = _STRICT_FROZEN

    section_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    rule_count: int = Field(ge=0)
    paragraph_count: int = Field(ge=0)


class RegistryManualShowReport(BaseModel):
    """Typed report for one manual lookup.

    When extracted structure is absent, manifest metadata still populates the
    report with ``structure_available=False`` and zero section/chapter counts.
    """

    model_config = _STRICT_FROZEN

    operation: str = "registry.manuals.show"
    manual_id: str = Field(min_length=1)
    year: int = Field(ge=2000, le=2100)
    part: str = Field(min_length=1)
    title: str | None = None
    source_pdf_url: str = Field(min_length=1)
    chapter_count: int = Field(ge=0)
    section_count: int = Field(ge=0)
    structure_available: bool
    section: RegistryManualSectionProjection | None = None
    topic_count: int = Field(ge=0)
    topics: tuple[RegistryTopicProjection, ...] = ()


class RegistryManualRuleProjection(BaseModel):
    """One manual rule projection.

    ``references_casillas`` preserves typed :class:`ManualCasillaReference`
    values so verification can cross-check the rule against
    :class:`ValidatedRegistryAuthority`.
    """

    model_config = _STRICT_FROZEN

    rule_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    section_id: str = Field(min_length=1)
    references_casillas: tuple[ManualCasillaReference, ...] = ()


class RegistryManualRulesReport(BaseModel):
    """Typed report for manual rule listing.

    Projects manual rules into :class:`RegistryManualRuleProjection`
    rows while preserving typed :class:`ManualCasillaReference`
    references for registry cross-checking.
    """

    model_config = _STRICT_FROZEN

    operation: str = "registry.manuals.rules"
    manual_id: str = Field(min_length=1)
    year: int = Field(ge=2000, le=2100)
    part: str = Field(min_length=1)
    kind_filter: str | None = None
    structure_available: bool
    rule_count: int = Field(ge=0)
    rules: tuple[RegistryManualRuleProjection, ...] = ()
    topic_count: int = Field(ge=0)
    topics: tuple[RegistryTopicProjection, ...] = ()


class RegistryManualVerificationReport(BaseModel):
    """Typed report for manual corpus verification.

    Summarizes a :class:`ManualVerificationReport` as normalized
    :class:`RegistryCorpusIssueProjection` rows for the application
    surface.
    """

    model_config = _STRICT_FROZEN

    operation: str = "registry.manuals.verify"
    manual_id: str = Field(min_length=1)
    year: int = Field(ge=2000, le=2100)
    part: str = Field(min_length=1)
    issue_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    passed: bool
    issues: tuple[RegistryCorpusIssueProjection, ...] = ()
    topic_count: int = Field(ge=0)
    topics: tuple[RegistryTopicProjection, ...] = ()


def list_registry_citations(
    command: RegistryCitationsListCommand | None = None,
    *,
    topic_catalogue: TopicCatalogue | None = None,
    locale: str | None = None,
) -> RegistryCitationsListReport:
    """Return topic-backed citation references from the reviewed legal catalogue.

    Returns a :class:`RegistryCitationsListReport`.
    """
    resolved_command = command or RegistryCitationsListCommand()
    topics = _topic_projections(topic_catalogue, locale=locale)
    authority = bundled_authority()
    references_by_document = _legal_references_by_document(authority.catalogues.legal.values())
    if resolved_command.tag is not None:
        needle = resolved_command.tag.strip().lower()
        references_by_document = {
            document_id: references
            for document_id, references in references_by_document.items()
            if _legal_group_matches_tag(document_id, references, topics=topics, needle=needle)
        }
    rows = tuple(
        _citation_reference_projection(document_id, references, topics=topics)
        for document_id, references in sorted(references_by_document.items())
    )
    _LOGGER.info(
        "registry.citations.list",
        extra={
            "registry_service": "registry.citations.list",
            "registry_reference_count": len(rows),
            "registry_topic_count": len(topics),
            "registry_tag_filter": resolved_command.tag or "",
        },
    )
    return RegistryCitationsListReport(
        reference_count=len(rows),
        tag_filter=resolved_command.tag,
        topic_count=len(topics),
        topics=topics,
        references=rows,
    )


def show_registry_citation(
    command: RegistryCitationShowCommand,
    *,
    topic_catalogue: TopicCatalogue | None = None,
    locale: str | None = None,
) -> RegistryCitationShowReport:
    """Return one topic-backed citation reference from the reviewed legal catalogue.

    Returns a :class:`RegistryCitationShowReport` with the matched
    legal document and optional article detail.
    """
    topics = _topic_projections(topic_catalogue, locale=locale)
    authority = bundled_authority()
    legal = authority.catalogues.legal
    references_by_document = _legal_references_by_document(legal.values())
    try:
        document_id, references, article_reference = _resolve_legal_citation(
            legal,
            references_by_document=references_by_document,
            command=command,
        )
    except KeyError as exc:
        _LOGGER.warning(
            "registry.citations.show failed",
            extra={
                "registry_service": "registry.citations.show",
                "registry_legal_id": command.legal_id,
                "registry_articulo": command.articulo or "",
            },
            exc_info=True,
        )
        raise _citation_not_found_error(command) from exc
    _LOGGER.info(
        "registry.citations.show",
        extra={
            "registry_service": "registry.citations.show",
            "registry_legal_id": command.legal_id,
            "registry_articulo": command.articulo or "",
            "registry_topic_count": len(topics),
        },
    )
    return RegistryCitationShowReport(
        reference=_citation_reference_projection(document_id, references, topics=topics),
        articulo=(_citation_article_projection(article_reference) if article_reference is not None else None),
        related_topics=_topics_for_reference(topics, reference_id=document_id, articulo=command.articulo),
    )


def verify_registry_citations(
    *,
    topic_catalogue: TopicCatalogue | None = None,
    locale: str | None = None,
) -> RegistryCitationsVerificationReport:
    """Verify the reviewed legal catalogue and return a :class:`RegistryCitationsVerificationReport`."""
    topics = _topic_projections(topic_catalogue, locale=locale)
    authority = bundled_authority()
    try:
        verify_legal_catalogue(
            authority.catalogues.legal,
            source_root=authority.source_root,
        )
    except RegistryValidationError as exc:
        _LOGGER.warning(
            "registry citations verification: strict legal catalogue check failed",
            extra={"error_type": type(exc).__name__, "error_message": str(exc)},
        )
        issues = _legal_validation_issue_projections(exc)
    else:
        issues = ()
    return RegistryCitationsVerificationReport(
        reference_count=len(authority.catalogues.legal),
        issue_count=len(issues),
        issues=issues,
        passed=not issues,
        topic_count=len(topics),
        topics=topics,
    )


def list_registry_manuals(
    command: RegistryManualsListCommand | None = None,
    *,
    settings: Settings | None = None,
    topic_catalogue: TopicCatalogue | None = None,
    locale: str | None = None,
) -> RegistryManualsListReport:
    """Return discovered local manual parts as a :class:`RegistryManualsListReport`."""
    resolved_command = command or RegistryManualsListCommand()
    topics = _topic_projections(topic_catalogue, locale=locale)
    parts = _discover_manual_parts(settings=settings)
    if resolved_command.manual is not None:
        parts = tuple(entry for entry in parts if entry[0] == resolved_command.manual)
    if resolved_command.year is not None:
        parts = tuple(entry for entry in parts if entry[1] == resolved_command.year)
    rows = tuple(_manual_part_projection(*entry) for entry in parts)
    _LOGGER.info(
        "registry.manuals.list",
        extra={
            "registry_service": "registry.manuals.list",
            "registry_manual_filter": resolved_command.manual.value if resolved_command.manual is not None else "",
            "registry_year_filter": resolved_command.year if resolved_command.year is not None else "",
            "registry_part_count": len(rows),
            "registry_topic_count": len(topics),
        },
    )
    return RegistryManualsListReport(
        manual_filter=resolved_command.manual.value if resolved_command.manual is not None else None,
        year_filter=resolved_command.year,
        part_count=len(rows),
        parts=rows,
        topic_count=len(topics),
        topics=topics,
    )


def show_registry_manual(
    command: RegistryManualShowCommand,
    *,
    settings: Settings | None = None,
    topic_catalogue: TopicCatalogue | None = None,
    locale: str | None = None,
) -> RegistryManualShowReport:
    """Return one local manual part as a :class:`RegistryManualShowReport`."""
    topics = _topic_projections(topic_catalogue, locale=locale)
    manual_id = _domain_manual_id(command.manual)
    try:
        manual = load_manual(manual_id, command.year, command.part, settings=settings)
    except ManualNotFoundError:
        if command.section is not None:
            manual_key = f"{command.manual.value}/{command.year}/{command.part.value}"
            _LOGGER.warning(
                "registry.manuals.show refused section without extracted structure",
                extra={
                    "registry_service": "registry.manuals.show",
                    "registry_manual_id": command.manual.value,
                    "registry_year": command.year,
                    "registry_part": command.part.value,
                    "registry_section": command.section,
                    "registry_structure_available": False,
                },
            )
            raise registry_terminal_refusal(
                condition=RegistryPreconditionCondition.MANUAL_SECTION_STRUCTURE_AVAILABLE,
                translated_message="application.registry.errors.manual_section_requires_structure",
                context={
                    "registry_service": "registry.manuals.show",
                    "manual_id": command.manual.value,
                    "year": command.year,
                    "part": command.part.value,
                    "section": command.section,
                    "manual_key": manual_key,
                    "structure_available": False,
                },
                facts={"manual_structure_available": False, "section_requested": True},
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                outcome=NoRecoveryOutcome.SAFETY,
            ) from None
        manifest, _part_root = _load_manual_manifest(
            manual_id=manual_id,
            year=command.year,
            part=command.part,
            settings=settings,
        )
        return RegistryManualShowReport(
            manual_id=manifest.manual_id.value,
            year=manifest.year,
            part=manifest.part.value,
            title=None,
            source_pdf_url=str(manifest.source_pdf_url),
            chapter_count=0,
            section_count=0,
            structure_available=False,
            section=None,
            topic_count=len(topics),
            topics=topics,
        )
    section_count = sum(len(chapter.sections) for chapter in manual.chapters)
    section_projection: RegistryManualSectionProjection | None = None
    if command.section is not None:
        matched = next(
            (section for section in iter_sections(manual, settings=settings) if section.section_id == command.section),
            None,
        )
        if matched is None:
            _LOGGER.warning(
                "registry.manuals.show refused unknown section",
                extra={
                    "registry_service": "registry.manuals.show",
                    "registry_manual_id": command.manual.value,
                    "registry_year": command.year,
                    "registry_part": command.part.value,
                    "registry_section": command.section,
                    "registry_structure_available": True,
                },
            )
            raise registry_terminal_refusal(
                condition=RegistryPreconditionCondition.MANUAL_SECTION_DECLARED,
                translated_message="application.registry.errors.manual_section_not_found",
                context={
                    "registry_service": "registry.manuals.show",
                    "manual_id": command.manual.value,
                    "year": command.year,
                    "part": command.part.value,
                    "section": command.section,
                    "structure_available": True,
                },
                facts={"manual_structure_available": True, "requested_section_declared": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.OPERATOR_DECISION,
            )
        section_projection = RegistryManualSectionProjection(
            section_id=matched.section_id,
            title=matched.title,
            rule_count=len(matched.rules),
            paragraph_count=len(matched.prose),
        )
    return RegistryManualShowReport(
        manual_id=manual.manual_id.value,
        year=manual.year,
        part=manual.part.value,
        title=manual.title,
        source_pdf_url=str(manual.source_pdf_url),
        chapter_count=len(manual.chapters),
        section_count=section_count,
        structure_available=True,
        section=section_projection,
        topic_count=len(topics),
        topics=topics,
    )


def list_registry_manual_rules(
    command: RegistryManualRulesCommand,
    *,
    settings: Settings | None = None,
    topic_catalogue: TopicCatalogue | None = None,
    locale: str | None = None,
) -> RegistryManualRulesReport:
    """Return manual rules as a typed application report.

    Returns a :class:`RegistryManualRulesReport` with the matched rules
    and whether the manual structure was available for lookup.
    """
    topics = _topic_projections(topic_catalogue, locale=locale)
    kind = _manual_rule_kind(command.kind)
    manual_id = _domain_manual_id(command.manual)
    try:
        catalogue = load_manual_catalogue([(manual_id, command.year, command.part)], settings=settings)
    except ManualNotFoundError:
        _load_manual_manifest(manual_id=manual_id, year=command.year, part=command.part, settings=settings)
        rules = ()
        structure_available = False
    else:
        rules = tuple(find_rules(catalogue, kind=kind))
        structure_available = True
    return RegistryManualRulesReport(
        manual_id=manual_id.value,
        year=command.year,
        part=command.part.value,
        kind_filter=command.kind,
        structure_available=structure_available,
        rule_count=len(rules),
        rules=tuple(
            RegistryManualRuleProjection(
                rule_id=rule.rule_id,
                kind=rule.kind,
                section_id=rule.section_id,
                references_casillas=tuple(rule.references_casillas),
            )
            for rule in rules
        ),
        topic_count=len(topics),
        topics=topics,
    )


def verify_registry_manual(
    command: RegistryManualVerifyCommand,
    *,
    settings: Settings | None = None,
    registry_authority: ValidatedRegistryAuthority | None = None,
    topic_catalogue: TopicCatalogue | None = None,
    locale: str | None = None,
) -> RegistryManualVerificationReport:
    """Verify one local manual part and return a typed application report.

    Args:
        command: Manual verification command to execute.
        settings: Optional application settings override.
        registry_authority: Optional :class:`ValidatedRegistryAuthority` used to
            validate manual casilla references against registry snapshots.
        topic_catalogue: Optional topic catalogue used to attach topic projections.
        locale: Optional output locale for topic projection text.

    Returns a :class:`RegistryManualVerificationReport` with verification
    findings for the requested manual part.
    """
    topics = _topic_projections(topic_catalogue, locale=locale)
    manual_id = _domain_manual_id(command.manual)
    report = verify_manual_dir(
        manual_id=manual_id,
        year=command.year,
        part=command.part,
        settings=settings,
    )
    report = _manual_report_with_registry_casilla_issues(
        report,
        settings=settings,
        registry_authority=registry_authority,
    )
    return _manual_verification_report(report, topics=topics)


def _topic_projections(
    topic_catalogue: TopicCatalogue | None,
    *,
    locale: str | None,
) -> tuple[RegistryTopicProjection, ...]:
    catalogue = topic_catalogue or load_topic_catalogue()
    resolved_locale = _registry_topic_locale(locale)
    return tuple(_topic_projection(topic, locale=resolved_locale) for topic in catalogue.topics)


def _topic_projection(topic: Topic, *, locale: str) -> RegistryTopicProjection:
    return RegistryTopicProjection(
        slug=topic.slug,
        title=tr(topic.title_key, locale=locale),
        body=tr(topic.body_key, locale=locale),
        see_also=topic.see_also,
        legal_refs=topic.legal_refs,
    )


def _registry_topic_locale(locale: str | None) -> str:
    if locale is None:
        return output_language()
    normalized = coerce_output_language_setting(locale)
    if normalized is None:
        _LOGGER.warning(
            "registry.topic locale refused",
            extra={
                "registry_service": "registry.topics",
                "registry_locale": locale,
                "registry_allowed_locales": SUPPORTED_OUTPUT_LANGUAGES,
            },
        )
        raise registry_terminal_refusal(
            condition=RegistryPreconditionCondition.TOPIC_OUTPUT_LANGUAGE_SUPPORTED,
            translated_message="application.registry.errors.invalid_topic_locale",
            context={
                "registry_service": "registry.topics",
                # tr() reserves "locale" as its rendering-locale meta-kwarg,
                # so the refused input must travel as locale_code to reach
                # the message's interpolation slot.
                "locale_code": locale,
                "allowed_locales": ", ".join(SUPPORTED_OUTPUT_LANGUAGES),
            },
            facts={"output_language_supported": False},
            provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        )
    return normalized.value


_LEGAL_KIND_LABELS: Mapping[str, str] = {
    "ley": "Ley",
    "real_decreto": "Real Decreto",
    "real_decreto_legislativo": "Real Decreto Legislativo",
    "real_decreto_ley": "Real Decreto-ley",
    "orden": "Orden",
    "reglamento": "Reglamento",
    "acuerdo_internacional": "Acuerdo internacional",
    "directiva": "Directiva",
    "manual": "Manual",
    "instruction": "Instruccion",
}

_LEGAL_REF_SUFFIX_PREFIXES = (
    "art-",
    "da-",
    "dd-",
    "df-",
    "dt-",
    "apartado-",
    "anexo-",
    "aprobacion",
    "amendment",
)


def _citation_reference_projection(
    document_id: str,
    references: tuple[LegalReference, ...],
    *,
    topics: tuple[RegistryTopicProjection, ...],
) -> RegistryCitationReferenceProjection:
    reference = references[0]
    related_topics = _topics_for_legal_references(topics, references=references)
    tags = _legal_group_tags(document_id, references, topics=related_topics)
    return RegistryCitationReferenceProjection(
        id=document_id,
        kind=reference.kind,
        number=_legal_document_number(document_id),
        title=_legal_document_title(document_id, reference),
        published_at=(reference.published_at or reference.effective_from).isoformat(),
        boe_id=reference.document_id,
        boe_url=_base_permalink(reference),
        tags=tags,
        articulo_count=len(references),
        short_title=_legal_document_title(document_id, reference),
        topic_slugs=tuple(topic.slug for topic in related_topics),
    )


def _citation_article_projection(reference: LegalReference) -> RegistryCitationArticleProjection:
    return RegistryCitationArticleProjection(
        numero=_legal_article_number(reference),
        titulo=_legal_article_title(reference),
        summary=reference.notes or _legal_cite(reference),
        permalink=reference.permalink,
        cite=_legal_cite(reference),
    )


def _legal_references_by_document(
    references: Iterable[LegalReference],
) -> dict[str, tuple[LegalReference, ...]]:
    grouped: dict[str, list[LegalReference]] = {}
    for reference in references:
        grouped.setdefault(_legal_document_id(reference), []).append(reference)
    return {
        document_id: tuple(sorted(values, key=_legal_reference_sort_key)) for document_id, values in grouped.items()
    }


def _resolve_legal_citation(
    legal: Mapping[str, LegalReference],
    *,
    references_by_document: Mapping[str, tuple[LegalReference, ...]],
    command: RegistryCitationShowCommand,
) -> tuple[str, tuple[LegalReference, ...], LegalReference | None]:
    if command.legal_id in legal and command.articulo is None:
        article_reference = legal[command.legal_id]
        document_id = _legal_document_id(article_reference)
        return document_id, references_by_document[document_id], article_reference
    document_id = _legal_document_id_from_input(command.legal_id)
    references = references_by_document[document_id]
    if command.articulo is None:
        return document_id, references, None
    ref_id = _legal_ref_id_for_article(document_id, command.articulo)
    return document_id, references, legal[ref_id]


def _citation_not_found_error(command: RegistryCitationShowCommand) -> RegistryApplicationInputError:
    return registry_terminal_refusal(
        condition=RegistryPreconditionCondition.CITATION_REFERENCE_AVAILABLE,
        translated_message="application.registry.errors.citation_not_found",
        context={
            "registry_service": "registry.citations.show",
            "legal_id": command.legal_id,
            "articulo": command.articulo,
        },
        facts={
            "citation_reference_available": False,
            "article_requested": command.articulo is not None,
        },
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def _legal_ref_id_for_article(document_id: str, articulo: str) -> str:
    normalized = articulo.strip()
    if normalized.startswith(_LEGAL_REF_SUFFIX_PREFIXES):
        return f"{document_id}:{normalized}"
    return f"{document_id}:art-{normalized}"


def _legal_document_id(reference: LegalReference) -> str:
    return _legal_document_id_from_input(reference.id)


def _legal_document_id_from_input(ref_id: str) -> str:
    return ref_id.split(":", 1)[0]


def _legal_reference_sort_key(reference: LegalReference) -> tuple[str, str]:
    return (_legal_article_number(reference), reference.id)


def _legal_document_number(document_id: str) -> str:
    parts = document_id.split("-")
    if len(parts) >= 3 and parts[0] in {"ley", "rd", "rdl", "rdleg"}:
        return f"{parts[-2]}/{parts[-1]}"
    if "rdleg" in parts:
        rdleg_index = parts.index("rdleg")
        if len(parts) > rdleg_index + 2:
            return f"{parts[rdleg_index + 1]}/{parts[rdleg_index + 2]}"
    if len(parts) >= 4 and parts[0] == "real" and parts[1] == "decreto" and parts[2] == "ley":
        return f"{parts[-2]}/{parts[-1]}"
    if len(parts) >= 4 and parts[0] == "orden" and parts[1].isalpha():
        return f"{parts[1].upper()}/{parts[-2]}/{parts[-1]}"
    return document_id


def _legal_document_title(document_id: str, reference: LegalReference) -> str:
    label = _LEGAL_KIND_LABELS.get(reference.kind, reference.kind.replace("_", " ").title())
    return f"{label} {_legal_document_number(document_id)}"


def _legal_article_number(reference: LegalReference) -> str:
    if reference.article:
        return reference.article
    if reference.section:
        return reference.section
    suffix = reference.id.split(":", 1)[1] if ":" in reference.id else reference.id
    for prefix in _LEGAL_REF_SUFFIX_PREFIXES:
        if suffix.startswith(prefix):
            return suffix.removeprefix(prefix)
    return suffix


def _legal_article_title(reference: LegalReference) -> str:
    if reference.article:
        return f"Art. {reference.article}"
    if reference.section:
        return reference.section
    return _legal_article_number(reference)


def _legal_cite(reference: LegalReference) -> str:
    document_id = _legal_document_id(reference)
    title = _legal_document_title(document_id, reference)
    if reference.article:
        cite = f"{title}, art. {reference.article}"
    elif reference.section:
        cite = f"{title}, {reference.section}"
    else:
        cite = title
    return f"{cite} ({reference.document_id})"


def _base_permalink(reference: LegalReference) -> RegistryExternalLink:
    return reference.permalink.split("#", 1)[0]


def _topics_for_legal_references(
    topics: tuple[RegistryTopicProjection, ...],
    *,
    references: tuple[LegalReference, ...],
) -> tuple[RegistryTopicProjection, ...]:
    refs = frozenset(reference.id for reference in references)
    document_ids = frozenset(_legal_document_id(reference) for reference in references)
    return tuple(
        topic
        for topic in topics
        if any(
            legal_ref in refs
            or legal_ref in document_ids
            or any(legal_ref.startswith(f"{document_id}:") for document_id in document_ids)
            for legal_ref in topic.legal_refs
        )
    )


def _legal_group_tags(
    document_id: str,
    references: tuple[LegalReference, ...],
    *,
    topics: tuple[RegistryTopicProjection, ...],
) -> tuple[str, ...]:
    tokens = {document_id, *(part for part in document_id.split("-") if part)}
    tokens.update(reference.kind for reference in references)
    tokens.update(topic.slug for topic in topics)
    return tuple(sorted(tokens))


def _legal_group_matches_tag(
    document_id: str,
    references: tuple[LegalReference, ...],
    *,
    topics: tuple[RegistryTopicProjection, ...],
    needle: str,
) -> bool:
    related_topics = _topics_for_legal_references(topics, references=references)
    haystack = _legal_group_tags(document_id, references, topics=related_topics)
    return any(needle in item.lower() for item in haystack)


def _topics_for_reference(
    topics: tuple[RegistryTopicProjection, ...],
    *,
    reference_id: str,
    articulo: str | None = None,
) -> tuple[RegistryTopicProjection, ...]:
    return tuple(
        topic for topic in topics if _topic_mentions_reference(topic, reference_id=reference_id, articulo=articulo)
    )


def _topic_mentions_reference(
    topic: RegistryTopicProjection,
    *,
    reference_id: str,
    articulo: str | None,
) -> bool:
    reference_prefix = f"{reference_id}:"
    article_ref = _legal_ref_id_for_article(reference_id, articulo) if articulo is not None else None
    for legal_ref in topic.legal_refs:
        if (legal_ref == reference_id or legal_ref.startswith(reference_prefix)) and (
            article_ref is None or legal_ref == article_ref
        ):
            return True
    return False


def _legal_validation_issue_projections(error: RegistryValidationError) -> tuple[RegistryCorpusIssueProjection, ...]:
    message = str(error)
    failures = tuple(
        line.strip().removeprefix("-").strip() for line in message.splitlines() if line.strip().startswith("-")
    ) or (message,)
    return tuple(
        RegistryCorpusIssueProjection(
            level=BaseSeverity.ERROR,
            code="legal-catalogue-validation",
            message=failure,
            reference_id=_legal_issue_reference_id(failure),
        )
        for failure in failures
    )


def _legal_issue_reference_id(message: str) -> str | None:
    marker = "legal reference "
    if marker in message:
        tail = message.split(marker, 1)[1]
        if tail.startswith("'"):
            return tail.split("'", 2)[1]
    marker = "legal catalogue key "
    if marker in message:
        tail = message.split(marker, 1)[1]
        if tail.startswith("'"):
            return tail.split("'", 2)[1]
    return None


def _manual_issue_projection(issue: ManualVerificationIssue) -> RegistryCorpusIssueProjection:
    return RegistryCorpusIssueProjection(
        level=issue.level,
        code=issue.code,
        message=issue.message,
    )


def _discover_manual_parts(
    *,
    settings: Settings | None = None,
) -> tuple[tuple[RegistryManualId, int, ManualPart, Path], ...]:
    resolved = settings or load_settings()
    root = resolved.aeat_manuals_root
    if not root.exists():
        return ()
    discovered: list[tuple[RegistryManualId, int, ManualPart, Path]] = []
    for manual_dir in (path for path in scan_directory(root) if path.is_dir()):
        try:
            manual_id = registry_manual_id(manual_dir.name)
        except RegistryApplicationInputError:
            _LOGGER.debug("manual discovery: skipping unknown manual id %s", manual_dir.name)
            continue
        for year_dir in (path for path in scan_directory(manual_dir) if path.is_dir() and path.name.isdigit()):
            year = int(year_dir.name)
            for part_dir in _manual_part_dirs(year_dir):
                part = _manual_part_from_dir(year_dir=year_dir, part_dir=part_dir)
                if part is None:
                    _LOGGER.debug("manual discovery: skipping unknown manual part %s", part_dir.name)
                    continue
                discovered.append((manual_id, year, part, part_dir))
    return tuple(discovered)


def _manual_part_dirs(year_dir: Path) -> tuple[Path, ...]:
    if (year_dir / "manifest.json").exists() or (year_dir / "structure" / "manual.json").exists():
        return (year_dir,)
    return tuple(path for path in scan_directory(year_dir) if path.is_dir())


def _manual_part_from_dir(*, year_dir: Path, part_dir: Path) -> ManualPart | None:
    if part_dir == year_dir:
        return ManualPart.SINGLE
    try:
        return ManualPart(part_dir.name)
    except ValueError:
        return None


def _manual_part_projection(
    manual_id: RegistryManualId,
    year: int,
    part: ManualPart,
    root: Path,
) -> RegistryManualPartProjection:
    return RegistryManualPartProjection(
        manual_id=manual_id.value,
        year=year,
        part=part.value,
        root=root.as_posix(),
    )


def registry_manual_id(value: str | RegistryManualId | ManualId) -> RegistryManualId:
    """Resolve an operator-facing registry manual id.

    Returns a :class:`RegistryManualId`.
    """
    raw = value.value if isinstance(value, ManualId | RegistryManualId) else value
    try:
        return RegistryManualId(raw)
    except ValueError as exc:
        allowed = tuple(item.value for item in RegistryManualId)
        _LOGGER.warning(
            "registry.manuals refused unknown manual id",
            extra={
                "registry_service": "registry.manuals",
                "registry_manual_id": raw,
                "registry_allowed_manual_ids": allowed,
            },
        )
        raise registry_terminal_refusal(
            condition=RegistryPreconditionCondition.MANUAL_ID_SUPPORTED,
            translated_message="application.registry.errors.invalid_manual_id",
            context={
                "registry_service": "registry.manuals",
                "manual_id": raw,
                "allowed_manual_ids": allowed,
            },
            facts={"manual_id_supported": False},
            provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        ) from exc


def _domain_manual_id(manual_id: RegistryManualId) -> ManualId:
    return ManualId(manual_id.value)


def _manual_verification_report(
    report: ManualVerificationReport,
    *,
    topics: tuple[RegistryTopicProjection, ...],
) -> RegistryManualVerificationReport:
    error_issues = report.errors
    warning_issues = report.warnings
    issues = tuple(_manual_issue_projection(issue) for issue in report.issues)
    return RegistryManualVerificationReport(
        manual_id=report.manual_id.value,
        year=report.year,
        part=report.part.value,
        issue_count=len(issues),
        error_count=len(error_issues),
        warning_count=len(warning_issues),
        passed=not error_issues,
        issues=issues,
        topic_count=len(topics),
        topics=topics,
    )


__all__ = [
    "RegistryCitationArticleProjection",
    "RegistryCitationReferenceProjection",
    "RegistryCitationShowCommand",
    "RegistryCitationShowReport",
    "RegistryCitationsListCommand",
    "RegistryCitationsListReport",
    "RegistryCitationsVerificationReport",
    "RegistryCorpusIssueProjection",
    "RegistryManualId",
    "RegistryManualPartProjection",
    "RegistryManualRuleProjection",
    "RegistryManualRulesCommand",
    "RegistryManualRulesReport",
    "RegistryManualSectionProjection",
    "RegistryManualShowCommand",
    "RegistryManualShowReport",
    "RegistryManualVerificationReport",
    "RegistryManualVerifyCommand",
    "RegistryManualsListCommand",
    "RegistryManualsListReport",
    "RegistryTopicProjection",
    "list_registry_citations",
    "list_registry_manual_rules",
    "list_registry_manuals",
    "registry_manual_id",
    "show_registry_citation",
    "show_registry_manual",
    "verify_registry_citations",
    "verify_registry_manual",
]
