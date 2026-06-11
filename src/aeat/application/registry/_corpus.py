"""Application services for registry corpus projections."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import get_args

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.config import Settings, load_settings
from ...core.i18n import SUPPORTED_OUTPUT_LANGUAGES, output_language, tr
from ...core.logging import get_logger
from ...core.topics import Topic, TopicCatalogue, load_topic_catalogue
from ...domain.manuals import (
    ManualId,
    ManualPart,
    ManualVerificationIssue,
    ManualVerificationReport,
    RuleKind,
    find_rules,
    iter_sections,
    load_manifest,
    load_manual,
    resolve_part_root,
    verify_manual_dir,
)
from ...domain.manuals import (
    load_catalogue as load_manual_catalogue,
)
from ...domain.manuals._errors import ManualNotFoundError
from ...domain.normatives import (
    NormativeReference,
    NormativeVerificationIssue,
    cite,
    find_articulo,
    find_reference,
    short_title,
)
from ...domain.normatives import (
    load_catalogue as load_normative_catalogue,
)
from ...domain.normatives import (
    verify_catalogue as verify_normative_catalogue,
)
from ...domain.normatives._errors import NormativeParseError
from ._errors import RegistryApplicationInputError

_LOGGER = get_logger(__name__)


class RegistryManualId(StrEnum):
    """Manual identifiers approved for the registry manual operator surface."""

    RENTA = "renta"
    IVA = "iva"


class RegistryTopicProjection(BaseModel):
    """Resolved topic content exposed by registry corpus services."""

    model_config = _STRICT_FROZEN

    slug: str = Field(min_length=1)
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    see_also: tuple[str, ...] = ()
    legal_refs: tuple[str, ...] = ()


class RegistryCitationReferenceProjection(BaseModel):
    """One normative reference row in the registry citations surface."""

    model_config = _STRICT_FROZEN

    id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    number: str = Field(min_length=1)
    title: str = Field(min_length=1)
    published_at: str = Field(min_length=10)
    boe_id: str = Field(min_length=1)
    boe_url: str = Field(min_length=1)
    tags: tuple[str, ...] = ()
    articulo_count: int = Field(ge=0)
    short_title: str = Field(min_length=1)
    topic_slugs: tuple[str, ...] = ()


class RegistryCitationArticleProjection(BaseModel):
    """One cited article projection in the registry citations surface."""

    model_config = _STRICT_FROZEN

    numero: str = Field(min_length=1)
    titulo: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    permalink: str = Field(min_length=1)
    cite: str = Field(min_length=1)


class RegistryCitationsListCommand(BaseModel):
    """Application command for listing registry citations."""

    model_config = _STRICT_FROZEN

    tag: str | None = None


class RegistryCitationShowCommand(BaseModel):
    """Application command for showing one registry citation."""

    model_config = _STRICT_FROZEN

    normative_id: str = Field(min_length=1)
    articulo: str | None = None


class RegistryCitationsListReport(BaseModel):
    """Typed report for registry citation listing."""

    model_config = _STRICT_FROZEN

    operation: str = "registry.citations.list"
    reference_count: int = Field(ge=0)
    tag_filter: str | None = None
    topic_count: int = Field(ge=0)
    topics: tuple[RegistryTopicProjection, ...] = ()
    references: tuple[RegistryCitationReferenceProjection, ...] = ()


class RegistryCitationShowReport(BaseModel):
    """Typed report for a single registry citation lookup."""

    model_config = _STRICT_FROZEN

    operation: str = "registry.citations.show"
    reference: RegistryCitationReferenceProjection
    articulo: RegistryCitationArticleProjection | None = None
    related_topics: tuple[RegistryTopicProjection, ...] = ()


class RegistryCorpusIssueProjection(BaseModel):
    """Normalized issue row for registry corpus verification reports."""

    model_config = _STRICT_FROZEN

    level: str = Field(min_length=1)
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
    """One discovered manual part row."""

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
    """Typed report for registry manual listing."""

    model_config = _STRICT_FROZEN

    operation: str = "registry.manuals.list"
    manual_filter: str | None = None
    year_filter: int | None = None
    part_count: int = Field(ge=0)
    parts: tuple[RegistryManualPartProjection, ...] = ()
    topic_count: int = Field(ge=0)
    topics: tuple[RegistryTopicProjection, ...] = ()


class RegistryManualSectionProjection(BaseModel):
    """One manual section projection."""

    model_config = _STRICT_FROZEN

    section_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    rule_count: int = Field(ge=0)
    paragraph_count: int = Field(ge=0)


class RegistryManualShowReport(BaseModel):
    """Typed report for one manual lookup."""

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
    """One manual rule projection."""

    model_config = _STRICT_FROZEN

    rule_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    section_id: str = Field(min_length=1)
    references_casillas: tuple[str, ...] = ()


class RegistryManualRulesReport(BaseModel):
    """Typed report for manual rule listing."""

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
    """Typed report for manual corpus verification."""

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
    """Return topic-backed citation references from the local corpus.

    Returns a :class:`RegistryCitationsListReport`.
    """
    resolved_command = command or RegistryCitationsListCommand()
    topics = _topic_projections(topic_catalogue, locale=locale)
    catalogue = load_normative_catalogue()
    references = tuple(catalogue.references.values())
    if resolved_command.tag is not None:
        needle = resolved_command.tag.strip().lower()
        references = tuple(reference for reference in references if needle in {tag.lower() for tag in reference.tags})
    rows = tuple(
        _citation_reference_projection(reference, topics=topics) for reference in sorted(references, key=_ref_id)
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
    """Return one topic-backed citation reference from the local corpus.

    Returns a :class:`RegistryCitationShowReport` with the matched
    normative reference and optional article detail.
    """
    topics = _topic_projections(topic_catalogue, locale=locale)
    catalogue = load_normative_catalogue()
    try:
        reference = find_reference(catalogue, command.normative_id)
        article = find_articulo(catalogue, reference.id, command.articulo) if command.articulo is not None else None
    # BROAD-EXCEPT-RATIONALE-CORPUS-LOOKUP-BOUNDARY:
    # find_reference/find_articulo surface KeyError, ValueError, and
    # catalogue-specific exceptions; warning-and-continue is the boundary
    # contract.
    except Exception:  # BROAD-EXCEPT-RATIONALE-CORPUS-LOOKUP-BOUNDARY
        _LOGGER.warning(
            "registry.citations.show failed",
            extra={
                "registry_service": "registry.citations.show",
                "registry_normative_id": command.normative_id,
                "registry_articulo": command.articulo or "",
            },
            exc_info=True,
        )
        raise
    _LOGGER.info(
        "registry.citations.show",
        extra={
            "registry_service": "registry.citations.show",
            "registry_normative_id": command.normative_id,
            "registry_articulo": command.articulo or "",
            "registry_topic_count": len(topics),
        },
    )
    return RegistryCitationShowReport(
        reference=_citation_reference_projection(reference, topics=topics),
        articulo=(
            RegistryCitationArticleProjection(
                numero=article.numero,
                titulo=_localized(article.titulo),
                summary=_localized(article.summary),
                permalink=str(article.permalink),
                cite=cite(reference, article),
            )
            if article is not None
            else None
        ),
        related_topics=_topics_for_reference(topics, reference_id=reference.id, articulo=command.articulo),
    )


def verify_registry_citations(
    *,
    topic_catalogue: TopicCatalogue | None = None,
    locale: str | None = None,
) -> RegistryCitationsVerificationReport:
    """Verify the local citation corpus and return a :class:`RegistryCitationsVerificationReport`."""
    topics = _topic_projections(topic_catalogue, locale=locale)
    report = verify_normative_catalogue()
    reference_count = 0
    try:
        catalogue = load_normative_catalogue()
    except NormativeParseError as exc:
        _LOGGER.warning(
            "registry citations verification: strict corpus load failed",
            extra={"error_type": type(exc).__name__, "error_message": str(exc)},
        )
    else:
        reference_count = len(catalogue.references)
    issues = tuple(_normative_issue_projection(issue) for issue in report.issues)
    return RegistryCitationsVerificationReport(
        reference_count=reference_count,
        issue_count=len(issues),
        issues=issues,
        passed=report.clean,
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
            raise RegistryApplicationInputError(
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
            raise RegistryApplicationInputError(
                translated_message="application.registry.errors.manual_section_not_found",
                context={
                    "registry_service": "registry.manuals.show",
                    "manual_id": command.manual.value,
                    "year": command.year,
                    "part": command.part.value,
                    "section": command.section,
                    "structure_available": True,
                },
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
    topic_catalogue: TopicCatalogue | None = None,
    locale: str | None = None,
) -> RegistryManualVerificationReport:
    """Verify one local manual part and return a typed application report.

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
    normalized = locale.lower().strip()
    if normalized not in SUPPORTED_OUTPUT_LANGUAGES:
        _LOGGER.warning(
            "registry.topic locale refused",
            extra={
                "registry_service": "registry.topics",
                "registry_locale": locale,
                "registry_allowed_locales": SUPPORTED_OUTPUT_LANGUAGES,
            },
        )
        raise RegistryApplicationInputError(
            translated_message="application.registry.errors.invalid_topic_locale",
            context={
                "registry_service": "registry.topics",
                "locale": locale,
                "allowed_locales": ", ".join(SUPPORTED_OUTPUT_LANGUAGES),
            },
        )
    return normalized


def _localized(text: Mapping[str, str]) -> str:
    """Resolve a multilingual normative field to the operator's language.

    Normative ``title`` / ``titulo`` / ``summary`` fields are
    :data:`LocalizedText` mappings. Citation projections are
    operator-facing and carry a single rendered string, so the field
    is flattened to the operator's output language, falling back to
    the authoritative ``es`` entry (guaranteed present by the
    normatives schema).
    """
    return text.get(output_language()) or text["es"]


def _citation_reference_projection(
    reference: NormativeReference,
    *,
    topics: tuple[RegistryTopicProjection, ...],
) -> RegistryCitationReferenceProjection:
    return RegistryCitationReferenceProjection(
        id=reference.id,
        kind=reference.kind.value,
        number=reference.number,
        title=_localized(reference.title),
        published_at=reference.published_at.isoformat(),
        boe_id=reference.boe_id,
        boe_url=str(reference.boe_url),
        tags=reference.tags,
        articulo_count=len(reference.articulos),
        short_title=short_title(reference),
        topic_slugs=tuple(topic.slug for topic in _topics_for_reference(topics, reference_id=reference.id)),
    )


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
    article_ref = f"{reference_id}:art-{articulo}" if articulo is not None else None
    for legal_ref in topic.legal_refs:
        if (legal_ref == reference_id or legal_ref.startswith(reference_prefix)) and (
            article_ref is None or legal_ref == article_ref
        ):
            return True
    return False


def _normative_issue_projection(issue: NormativeVerificationIssue) -> RegistryCorpusIssueProjection:
    return RegistryCorpusIssueProjection(
        level=issue.level,
        code=issue.code,
        message=issue.message,
        reference_id=issue.reference_id,
    )


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
    for manual_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        try:
            manual_id = registry_manual_id(manual_dir.name)
        except RegistryApplicationInputError:
            _LOGGER.debug("manual discovery: skipping unknown manual id %s", manual_dir.name)
            continue
        for year_dir in sorted(path for path in manual_dir.iterdir() if path.is_dir() and path.name.isdigit()):
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
    return tuple(path for path in sorted(year_dir.iterdir()) if path.is_dir())


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
        raise RegistryApplicationInputError(
            translated_message="application.registry.errors.invalid_manual_id",
            context={
                "registry_service": "registry.manuals",
                "manual_id": raw,
                "allowed_manual_ids": allowed,
            },
        ) from exc


def _domain_manual_id(manual_id: RegistryManualId) -> ManualId:
    return ManualId(manual_id.value)


def _manual_rule_kind(kind: str | None) -> RuleKind | None:
    if kind is None:
        return None
    match kind:
        case "computation":
            return "computation"
        case "applicability":
            return "applicability"
        case "valuation":
            return "valuation"
        case "deductibility":
            return "deductibility"
        case "formal_obligation":
            return "formal_obligation"
        case "procedural":
            return "procedural"
        case "other":
            return "other"
    allowed = tuple(str(value) for value in get_args(RuleKind))
    _LOGGER.warning(
        "registry.manuals.rules refused unknown rule kind",
        extra={
            "registry_service": "registry.manuals.rules",
            "registry_rule_kind": kind,
            "registry_allowed_rule_kinds": allowed,
        },
    )
    raise RegistryApplicationInputError(
        translated_message="application.registry.errors.invalid_manual_rule_kind",
        context={
            "registry_service": "registry.manuals.rules",
            "rule_kind": kind,
            "allowed_rule_kinds": allowed,
        },
    )


def _load_manual_manifest(
    *,
    manual_id: ManualId,
    year: int,
    part: ManualPart,
    settings: Settings | None,
):
    part_root = resolve_part_root(manual_id=manual_id, year=year, part=part, settings=settings)
    return load_manifest(part_root / "manifest.json"), part_root


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


def _ref_id(reference: NormativeReference) -> str:
    return reference.id


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
