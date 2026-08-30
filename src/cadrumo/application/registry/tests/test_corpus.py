"""Application registry corpus projection tests."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from ....core import CasillaId, validated_casilla_id
from ....core.config import override_settings
from ....core.errors import build_error_envelope
from ....core.external_constants import OutputLanguage
from ....core.i18n import SUPPORTED_OUTPUT_LANGUAGES
from ....core.resources import resources
from ....core.topics import Topic, TopicCatalogue
from ....domain.manuals.schema import ManualId, ManualPart
from ..corpus import (
    RegistryCitationArticleProjection,
    RegistryCitationReferenceProjection,
    RegistryCitationShowCommand,
    RegistryCitationsListCommand,
    RegistryManualId,
    RegistryManualRulesCommand,
    RegistryManualShowCommand,
    RegistryManualsListCommand,
    RegistryManualVerifyCommand,
    RegistryTopicProjection,
    list_registry_citations,
    list_registry_manual_rules,
    list_registry_manuals,
    registry_manual_id,
    show_registry_citation,
    show_registry_manual,
    verify_registry_citations,
    verify_registry_manual,
)
from ..errors import RegistryApplicationInputError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_RENTA_2025_BORRADOR_RENTA_FAMILIAR_CASILLA: CasillaId = validated_casilla_id("0695")
_UNDECLARED_MANUAL_RULE_CASILLA: CasillaId = validated_casilla_id("not-real")


def _topic_catalogue_for_legal_ref() -> TopicCatalogue:
    return TopicCatalogue(
        topics=(
            Topic(
                slug="irpf-deduction",
                title_key="topic.irpf-regime.title",
                body_key="topic.irpf-regime.body",
                legal_refs=("ley-35-2006:art-32",),
            ),
        ),
    )


def test_citations_verification_report_consumes_topic_catalogue() -> None:
    report = verify_registry_citations()

    assert report.operation == "registry.citations.verify"
    assert report.passed is True
    assert report.issue_count == 0
    assert report.topic_count == len(resources().topics.singleton.topics)
    assert {topic.slug for topic in report.topics} >= {"iva-regime", "casilla", "modelos", "sii", "verifactu"}
    assert "sii-verifactu" not in {topic.slug for topic in report.topics}
    assert report.issue_count == len(report.issues)


def test_citations_list_projects_topic_slugs_from_current_legal_catalogue() -> None:
    report = list_registry_citations(
        RegistryCitationsListCommand(tag="irpf"),
        topic_catalogue=_topic_catalogue_for_legal_ref(),
        locale="es",
    )

    assert report.operation == "registry.citations.list"
    assert report.reference_count == 1
    assert report.topic_count == 1
    assert report.references[0].id == "ley-35-2006"
    assert report.references[0].articulo_count >= 1
    assert report.references[0].topic_slugs == ("irpf-deduction",)
    assert report.topics[0].slug == "irpf-deduction"
    assert report.topics[0].title == "Régimen IRPF"


def test_citation_show_projects_article_and_related_topics_from_current_legal_catalogue() -> None:
    report = show_registry_citation(
        RegistryCitationShowCommand(legal_id="ley-35-2006", articulo="32"),
        topic_catalogue=_topic_catalogue_for_legal_ref(),
        locale="es",
    )

    assert report.operation == "registry.citations.show"
    assert report.reference.id == "ley-35-2006"
    assert report.articulo is not None
    assert report.articulo.numero == "32"
    assert report.articulo.cite == "Ley 35/2006, art. 32 (BOE-A-2006-20764)"
    assert tuple(topic.slug for topic in report.related_topics) == ("irpf-deduction",)


def test_citation_show_command_rejects_retired_normative_id_field() -> None:
    with pytest.raises(ValidationError):
        RegistryCitationShowCommand.model_validate({"normative_id": "ley-35-2006", "articulo": "32"})


def test_citation_show_preserves_current_legislative_decree_kind_for_trlirnr() -> None:
    report = show_registry_citation(
        RegistryCitationShowCommand(legal_id="trlirnr-rdleg-5-2004", articulo="25.1.a"),
        locale="es",
    )

    assert report.reference.id == "trlirnr-rdleg-5-2004"
    assert report.reference.kind == "real_decreto_legislativo"
    assert report.reference.number == "5/2004"
    assert report.reference.title == "Real Decreto Legislativo 5/2004"
    assert report.articulo is not None
    assert report.articulo.cite == "Real Decreto Legislativo 5/2004, art. 25.1.a (BOE-A-2004-4527)"


def test_topic_projection_resolves_central_output_language_override() -> None:
    with override_settings(cadrumo_output_language="en"):
        report = list_registry_manuals(RegistryManualsListCommand(manual=RegistryManualId.RENTA, year=2025))

    topics = {topic.slug: topic for topic in report.topics}
    assert topics["iva-regime"].title == "IVA regime"
    assert topics["iva-regime"].body.startswith("IVA regime applicable to the taxpayer")


def test_topic_projection_accepts_explicit_supported_locale() -> None:
    report = list_registry_manuals(
        RegistryManualsListCommand(manual=RegistryManualId.RENTA, year=2025),
        locale=" ES ",
    )

    topics = {topic.slug: topic for topic in report.topics}
    assert topics["iva-regime"].title == "Régimen IVA"
    assert topics["iva-regime"].body.startswith("Régimen IVA aplicable al contribuyente")


def test_topic_projection_accepts_output_language_enum() -> None:
    report = list_registry_manuals(
        RegistryManualsListCommand(manual=RegistryManualId.RENTA, year=2025),
        locale=OutputLanguage.EN,
    )

    topics = {topic.slug: topic for topic in report.topics}
    assert topics["iva-regime"].title == "IVA regime"


@pytest.mark.parametrize("locale", ("", "zz"))
def test_topic_projection_rejects_invalid_string_locale_with_application_error(
    caplog: pytest.LogCaptureFixture,
    locale: str,
) -> None:
    caplog.set_level(logging.WARNING, logger="cadrumo.application.registry.corpus")

    with pytest.raises(RegistryApplicationInputError) as exc_info:
        list_registry_manuals(
            RegistryManualsListCommand(manual=RegistryManualId.RENTA, year=2025),
            locale=locale,
        )

    assert exc_info.value.translated_message == "application.registry.errors.invalid_topic_locale"
    envelope = build_error_envelope(exc_info.value)
    assert envelope.code == "REFUSED_APPLICATION_REGISTRY_INPUT"
    assert envelope.context == {
        "registry_service": "registry.topics",
        "locale_code": locale,
        "allowed_locales": ", ".join(SUPPORTED_OUTPUT_LANGUAGES),
    }
    records = [record for record in caplog.records if getattr(record, "registry_service", "") == "registry.topics"]
    assert len(records) == 1
    record = records[0]
    assert record.levelno == logging.WARNING
    assert record.__dict__["registry_locale"] == locale
    assert record.__dict__["registry_allowed_locales"] == SUPPORTED_OUTPUT_LANGUAGES


def test_topic_projection_refuses_boolean_locale_with_application_error(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="cadrumo.application.registry.corpus")

    with pytest.raises(RegistryApplicationInputError) as exc_info:
        list_registry_manuals(
            RegistryManualsListCommand(manual=RegistryManualId.RENTA, year=2025),
            locale=cast(str, True),
        )

    assert exc_info.value.context == {
        "registry_service": "registry.topics",
        "locale_code": True,
        "allowed_locales": ", ".join(SUPPORTED_OUTPUT_LANGUAGES),
    }


def test_registry_input_error_builds_central_error_envelope() -> None:
    error = RegistryApplicationInputError(
        "manual rule kind must be one of ('computation',); got 'bad'",
        context={
            "registry_service": "registry.manuals.rules",
            "rule_kind": "bad",
        },
    )

    envelope = build_error_envelope(error)

    assert envelope.code == "REFUSED_APPLICATION_REGISTRY_INPUT"
    assert envelope.category == "REFUSED"
    assert envelope.context == {
        "registry_service": "registry.manuals.rules",
        "rule_kind": "bad",
    }


def test_manual_rule_kind_refusal_uses_structured_registry_logging(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="cadrumo.application.registry.corpus")

    with pytest.raises(RegistryApplicationInputError) as exc_info:
        list_registry_manual_rules(
            RegistryManualRulesCommand(
                manual=RegistryManualId.RENTA,
                year=2025,
                kind="not-a-kind",
            ),
        )

    assert exc_info.value.translated_message == "application.registry.errors.invalid_manual_rule_kind"
    assert exc_info.value.context is not None
    assert exc_info.value.context["rule_kind"] == "not-a-kind"
    records = [
        record for record in caplog.records if getattr(record, "registry_service", "") == "registry.manuals.rules"
    ]
    assert len(records) == 1
    record = records[0]
    assert record.levelno == logging.WARNING
    assert record.__dict__["registry_rule_kind"] == "not-a-kind"
    assert "formal_obligation" in record.__dict__["registry_allowed_rule_kinds"]


def test_citation_missing_article_uses_structured_registry_logging(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="cadrumo.application.registry.corpus")

    with pytest.raises(RegistryApplicationInputError) as exc_info:
        show_registry_citation(
            RegistryCitationShowCommand(
                legal_id="ley-35-2006",
                articulo="999",
            ),
        )

    assert exc_info.value.translated_message == "application.registry.errors.citation_not_found"
    assert exc_info.value.context == {
        "registry_service": "registry.citations.show",
        "legal_id": "ley-35-2006",
        "articulo": "999",
    }
    records = [
        record for record in caplog.records if getattr(record, "registry_service", "") == "registry.citations.show"
    ]
    assert len(records) == 1
    record = records[0]
    assert record.levelno == logging.WARNING
    assert record.__dict__["registry_legal_id"] == "ley-35-2006"
    assert record.__dict__["registry_articulo"] == "999"


def test_manuals_list_report_discovers_real_corpus_parts_and_topics() -> None:
    report = list_registry_manuals(RegistryManualsListCommand(manual=None, year=None))

    assert report.operation == "registry.manuals.list"
    assert report.part_count == len(report.parts)
    assert report.topic_count == len(resources().topics.singleton.topics)
    assert report.part_count >= 1
    assert {part.manual_id for part in report.parts} >= {"iva", "renta"}


def test_manuals_list_report_filters_by_year() -> None:
    report = list_registry_manuals(RegistryManualsListCommand(year=2025))

    assert report.year_filter == 2025
    assert report.part_count == len(report.parts)
    assert all(part.year == 2025 for part in report.parts)


def test_manuals_list_report_rows_verify_against_canonical_corpus() -> None:
    report = list_registry_manuals(RegistryManualsListCommand(manual=RegistryManualId.RENTA, year=2025))
    listed_part = next(part for part in report.parts if part.part == ManualPart.PARTE_1.value)

    verification = verify_registry_manual(
        RegistryManualVerifyCommand(
            manual=RegistryManualId(listed_part.manual_id),
            year=listed_part.year,
            part=ManualPart(listed_part.part),
        ),
    )

    assert verification.manual_id == listed_part.manual_id
    assert verification.year == listed_part.year
    assert verification.part == listed_part.part


def _write_extracted_renta_part1_with_rule(root: Path, *, casilla_id: CasillaId) -> None:
    part_root = root / "renta" / "2025" / "part1"
    structure = part_root / "structure"
    source_url = "https://example.invalid/synthetic/renta-2025-part1.pdf"
    part_root.mkdir(parents=True)
    (part_root / "source.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
    (part_root / "manifest.json").write_text(
        json.dumps(
            {
                "content_length": 12,
                "fetched_at": "2026-01-01T00:00:00Z",
                "manual_id": "renta",
                "part": "part1",
                "relative_pdf_path": "source.pdf",
                "sha256": "0" * 64,
                "source_pdf_url": source_url,
                "synthetic": True,
                "year": 2025,
            },
        ),
        encoding="utf-8",
    )
    (structure / "manual.json").parent.mkdir(parents=True, exist_ok=True)
    (structure / "manual.json").write_text(
        json.dumps(
            {
                "manual_id": "renta",
                "year": 2025,
                "part": "part1",
                "title": "Manual practico Renta 2025",
                "summary": "Resumen",
                "source_pdf_url": source_url,
                "source_html_url": None,
                "fetched_at": "2026-01-01T00:00:00Z",
                "definition_reviewed_by": "gw",
                "definition_reviewed_at": "2026-01-01",
            },
        ),
        encoding="utf-8",
    )
    (structure / "chapters.json").write_text(
        json.dumps(
            [
                {
                    "chapter_id": "cap1",
                    "title": "Capitulo 1",
                    "summary": "Resumen",
                    "sections": [
                        {
                            "section_id": "sec1",
                            "relative_path": "structure/sections/cap1/sec1.json",
                        },
                    ],
                },
            ],
        ),
        encoding="utf-8",
    )
    section_payload = {
        "section_id": "sec1",
        "chapter_id": "cap1",
        "title": "Rendimientos",
        "summary": "Resumen",
        "prose": [],
        "rules": [
            {
                "rule_id": "renta-2025-part1-cap1-sec1-rule0001",
                "manual_id": "renta",
                "year": 2025,
                "part": "part1",
                "chapter_id": "cap1",
                "section_id": "sec1",
                "kind": "computation",
                "statement": "Regla Renta",
                "applies_when": None,
                "references_casillas": [{"modelo_id": "100", "casilla_id": casilla_id}],
                "references_sections": [],
                "references_legal_acts": ["LEY_35_2006|art. 1"],
                "source": {
                    "manual_url": source_url,
                    "page": 1,
                    "paragraph": 1,
                },
                "extracted_by": {
                    "provider": "anthropic",
                    "model": "test-model",
                    "prompt_id": "manual_rule_extract_v1",
                    "cache_hit": False,
                    "extracted_at": "2026-01-01T00:00:00Z",
                },
                "definition_reviewed_by": "gw",
                "definition_reviewed_at": "2026-01-01",
            },
        ],
        "references_sections": [],
        "references_legal_acts": [],
        "source": {
            "manual_url": source_url,
            "page": 1,
        },
        "definition_reviewed_by": "gw",
        "definition_reviewed_at": "2026-01-01",
    }
    (structure / "sections" / "cap1").mkdir(parents=True, exist_ok=True)
    (structure / "sections" / "cap1" / "sec1.json").write_text(
        json.dumps(section_payload),
        encoding="utf-8",
    )


def test_manual_verify_accepts_registry_resolved_casilla_reference(tmp_path: Path) -> None:
    _write_extracted_renta_part1_with_rule(
        tmp_path,
        casilla_id=_RENTA_2025_BORRADOR_RENTA_FAMILIAR_CASILLA,
    )

    with override_settings(aeat_manuals_root=tmp_path):
        report = verify_registry_manual(
            RegistryManualVerifyCommand(
                manual=RegistryManualId.RENTA,
                year=2025,
                part=ManualPart.PARTE_1,
            ),
        )

    assert report.passed is True
    assert report.error_count == 0
    assert report.issues == ()


def test_manual_verify_rejects_dangling_registry_casilla_reference(tmp_path: Path) -> None:
    _write_extracted_renta_part1_with_rule(tmp_path, casilla_id=_UNDECLARED_MANUAL_RULE_CASILLA)

    with override_settings(aeat_manuals_root=tmp_path):
        report = verify_registry_manual(
            RegistryManualVerifyCommand(
                manual=RegistryManualId.RENTA,
                year=2025,
                part=ManualPart.PARTE_1,
            ),
        )

    assert report.passed is False
    assert report.error_count == 1
    assert report.issues[0].code == "dangling-casilla-ref"
    assert "not-real" in report.issues[0].message
    assert "revision(s) ('2025',)" in report.issues[0].message


def _write_unextracted_renta_part1(root: Path) -> None:
    """Write a synthetic RENTA 2025 part1 manual: manifest + source.pdf, no extracted structure/.

    The bundled corpus is now fully extracted, so the 'manual without extracted
    structure' contracts are exercised against this synthetic part rather than a
    real corpus part whose extraction state changes.
    """
    part_root = root / "renta" / "2025" / "part1"
    part_root.mkdir(parents=True)
    (part_root / "source.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
    (part_root / "manifest.json").write_text(
        json.dumps(
            {
                "content_length": 12,
                "fetched_at": "2026-01-01T00:00:00Z",
                "manual_id": "renta",
                "part": "part1",
                "relative_pdf_path": "source.pdf",
                "sha256": "0" * 64,
                "source_pdf_url": "https://example.invalid/synthetic/renta-2025-part1.pdf",
                "synthetic": True,
                "year": 2025,
            },
        ),
        encoding="utf-8",
    )


def test_manuals_list_report_rows_show_manifest_metadata_without_structure(tmp_path: Path) -> None:
    _write_unextracted_renta_part1(tmp_path)
    with override_settings(aeat_manuals_root=tmp_path):
        report = list_registry_manuals(RegistryManualsListCommand(manual=RegistryManualId.RENTA, year=2025))
        listed_part = next(part for part in report.parts if part.part == ManualPart.PARTE_1.value)

        manual = show_registry_manual(
            RegistryManualShowCommand(
                manual=RegistryManualId(listed_part.manual_id),
                year=listed_part.year,
                part=ManualPart(listed_part.part),
            ),
        )

    assert manual.manual_id == listed_part.manual_id
    assert manual.year == listed_part.year
    assert manual.part == listed_part.part
    assert manual.source_pdf_url.startswith("https://")
    assert manual.structure_available is False
    assert manual.chapter_count == 0
    assert manual.section_count == 0


def test_manuals_view_refuses_section_when_structure_is_not_extracted_with_localized_error(tmp_path: Path) -> None:
    _write_unextracted_renta_part1(tmp_path)
    with override_settings(aeat_manuals_root=tmp_path):
        report = list_registry_manuals(RegistryManualsListCommand(manual=RegistryManualId.RENTA, year=2025))
        listed_part = next(part for part in report.parts if part.part == ManualPart.PARTE_1.value)

        with pytest.raises(RegistryApplicationInputError) as exc_info:
            show_registry_manual(
                RegistryManualShowCommand(
                    manual=RegistryManualId(listed_part.manual_id),
                    year=listed_part.year,
                    part=ManualPart(listed_part.part),
                    section="missing-section",
                ),
            )

    assert exc_info.value.translated_message == "application.registry.errors.manual_section_requires_structure"
    assert exc_info.value.context == {
        "registry_service": "registry.manuals.show",
        "manual_id": listed_part.manual_id,
        "year": listed_part.year,
        "part": listed_part.part,
        "section": "missing-section",
        "manual_key": f"{listed_part.manual_id}/{listed_part.year}/{listed_part.part}",
        "structure_available": False,
    }


def test_manuals_list_report_rows_rules_returns_extracted_rule_report(tmp_path: Path) -> None:
    _write_unextracted_renta_part1(tmp_path)
    with override_settings(aeat_manuals_root=tmp_path):
        report = list_registry_manuals(RegistryManualsListCommand(manual=RegistryManualId.RENTA, year=2025))
        listed_part = next(part for part in report.parts if part.part == ManualPart.PARTE_1.value)

        rules = list_registry_manual_rules(
            RegistryManualRulesCommand(
                manual=RegistryManualId(listed_part.manual_id),
                year=listed_part.year,
                part=ManualPart(listed_part.part),
            ),
        )

    assert rules.manual_id == listed_part.manual_id
    assert rules.year == listed_part.year
    assert rules.part == listed_part.part
    assert rules.structure_available is False
    assert rules.rule_count == 0
    assert rules.rules == ()


def test_registry_manual_id_rejects_out_of_scope_domain_manual_with_application_error() -> None:
    with pytest.raises(RegistryApplicationInputError) as exc_info:
        registry_manual_id(ManualId.SOCIEDADES)

    assert exc_info.value.translated_message == "application.registry.errors.invalid_manual_id"
    assert exc_info.value.context == {
        "registry_service": "registry.manuals",
        "manual_id": ManualId.SOCIEDADES.value,
        "allowed_manual_ids": ("renta", "iva"),
    }


def test_manual_rule_kind_validation_uses_application_error() -> None:
    with pytest.raises(RegistryApplicationInputError) as exc_info:
        list_registry_manual_rules(
            RegistryManualRulesCommand(
                manual=RegistryManualId.RENTA,
                year=2025,
                kind="not-a-kind",
            ),
        )

    assert exc_info.value.translated_message == "application.registry.errors.invalid_manual_rule_kind"


def test_registry_topic_projection_is_strict_and_frozen() -> None:
    topic = RegistryTopicProjection(
        slug="iva-regime",
        title="IVA",
        body="IVA regime",
        legal_refs=("ley-37-1992:art-1",),
    )

    with pytest.raises(ValidationError, match=r"frozen"):
        topic.title = "changed"

    with pytest.raises(ValidationError, match=r"Extra inputs"):
        RegistryTopicProjection.model_validate(
            {
                "slug": "iva-regime",
                "title": "IVA",
                "body": "IVA regime",
                "extra": "rejected",
                "legal_refs": ("ley-37-1992:art-1",),
            },
        )

    with pytest.raises(ValidationError, match=r"legal_refs"):
        RegistryTopicProjection.model_validate(
            {
                "slug": "iva-regime",
                "title": "IVA",
                "body": "IVA regime",
            }
        )

    with pytest.raises(ValidationError, match=r"title"):
        RegistryTopicProjection(
            slug="iva-regime",
            title="   ",
            body="IVA regime",
            legal_refs=("ley-37-1992:art-1",),
        )

    with pytest.raises(ValidationError, match=r"legal_refs"):
        RegistryTopicProjection(
            slug="iva-regime",
            title="IVA",
            body="IVA regime",
            legal_refs=("   ",),
        )

    with pytest.raises(ValidationError, match=r"legal_refs"):
        RegistryTopicProjection(
            slug="iva-regime",
            title="IVA",
            body="IVA regime",
            legal_refs=("Ley-37-1992:art-1",),
        )


def test_registry_citation_projections_reject_blank_authoritative_text() -> None:
    with pytest.raises(ValidationError, match=r"title"):
        RegistryCitationReferenceProjection(
            id="ley-35-2006",
            kind="ley",
            number="35/2006",
            title="   ",
            published_at="2006-11-29",
            boe_id="BOE-A-2006-20764",
            boe_url="https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764",
            tags=("irpf",),
            articulo_count=1,
            short_title="Ley 35/2006",
            topic_slugs=("irpf",),
        )

    with pytest.raises(ValidationError, match=r"summary"):
        RegistryCitationArticleProjection(
            numero="32",
            titulo="Art. 32",
            summary="   ",
            permalink="https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a32",
            cite="Ley 35/2006, art. 32 (BOE-A-2006-20764)",
        )


def test_registry_citation_projections_require_canonical_external_links() -> None:
    with pytest.raises(ValidationError, match=r"boe_url"):
        RegistryCitationReferenceProjection(
            id="ley-35-2006",
            kind="ley",
            number="35/2006",
            title="Ley 35/2006",
            published_at="2006-11-29",
            boe_id="BOE-A-2006-20764",
            boe_url="not-a-url",
            articulo_count=1,
            short_title="Ley 35/2006",
        )

    with pytest.raises(ValidationError, match=r"permalink"):
        RegistryCitationArticleProjection(
            numero="32",
            titulo="Art. 32",
            summary="Rendimientos del trabajo.",
            permalink="http://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a32",
            cite="Ley 35/2006, art. 32 (BOE-A-2006-20764)",
        )

    projection = RegistryCitationArticleProjection(
        numero="32",
        titulo="Art. 32",
        summary="Rendimientos del trabajo.",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a32",
        cite="Ley 35/2006, art. 32 (BOE-A-2006-20764)",
    )

    assert str(projection.permalink).endswith("#a32")
