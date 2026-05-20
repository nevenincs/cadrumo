"""Application registry corpus projection tests."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from aeat.core.resources import resources

from ...core.config import override_settings
from ...core.errors import build_error_envelope
from ...domain.manuals import ManualId, ManualPart
from ...domain.normatives import NormativeNotFoundError
from ..topics import Topic, TopicCatalogue
from . import (
    RegistryApplicationInputError,
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

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _write_valid_normative(root: Path) -> None:
    (root / "ley-35-2006.json").write_text(
        json.dumps(
            {
                "id": "ley-35-2006",
                "kind": "ley",
                "number": "35/2006",
                "title": {"es": "Ley 35/2006"},
                "published_at": "2006-11-29",
                "boe_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764",
                "boe_id": "BOE-A-2006-20764",
                "articulos": [
                    {
                        "numero": "32",
                        "titulo": {"es": "Reducciones"},
                        "summary": {"es": "Resumen."},
                        "permalink": "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a32",
                    }
                ],
                "tags": ["irpf"],
                "last_reviewed_at": "2026-04-12",
                "reviewed_by": "wgergely",
            }
        ),
        encoding="utf-8",
    )


def _topic_catalogue_for_normative() -> TopicCatalogue:
    return TopicCatalogue(
        topics=(
            Topic(
                slug="irpf-deduction",
                title_key="topic.irpf-regime.title",
                body_key="topic.irpf-regime.body",
                legal_refs=("ley-35-2006:art-32",),
            ),
        )
    )


def test_citations_verification_report_consumes_topic_catalogue() -> None:
    report = verify_registry_citations()

    assert report.operation == "registry.citations.verify"
    assert report.topic_count == len(resources().topics.singleton.topics)
    assert {topic.slug for topic in report.topics} >= {"iva-regime", "casilla", "modelos"}
    assert report.issue_count == len(report.issues)


def test_citations_list_projects_topic_slugs_from_valid_registry_corpus(tmp_path: Path) -> None:
    _write_valid_normative(tmp_path)

    with override_settings(aeat_normatives_root=tmp_path):
        report = list_registry_citations(
            RegistryCitationsListCommand(tag="irpf"),
            topic_catalogue=_topic_catalogue_for_normative(),
            locale="es",
        )

    assert report.operation == "registry.citations.list"
    assert report.reference_count == 1
    assert report.topic_count == 1
    assert report.references[0].id == "ley-35-2006"
    assert report.references[0].topic_slugs == ("irpf-deduction",)
    assert report.topics[0].slug == "irpf-deduction"
    assert report.topics[0].title == "Régimen IRPF"


def test_citation_show_projects_article_and_related_topics(tmp_path: Path) -> None:
    _write_valid_normative(tmp_path)

    with override_settings(aeat_normatives_root=tmp_path):
        report = show_registry_citation(
            RegistryCitationShowCommand(normative_id="ley-35-2006", articulo="32"),
            topic_catalogue=_topic_catalogue_for_normative(),
            locale="es",
        )

    assert report.operation == "registry.citations.show"
    assert report.reference.id == "ley-35-2006"
    assert report.articulo is not None
    assert report.articulo.numero == "32"
    assert report.articulo.cite == "Ley 35/2006, art. 32 (BOE-A-2006-20764)"
    assert tuple(topic.slug for topic in report.related_topics) == ("irpf-deduction",)


def test_topic_projection_resolves_central_output_language_override() -> None:
    with override_settings(aeat_output_language="en"):
        report = list_registry_manuals(RegistryManualsListCommand(manual=RegistryManualId.RENTA, year=2025))

    topics = {topic.slug: topic for topic in report.topics}
    assert topics["iva-regime"].title == "IVA regime"
    assert topics["iva-regime"].body.startswith("VAT regime applicable to the taxpayer")


def test_topic_projection_accepts_explicit_supported_locale() -> None:
    report = list_registry_manuals(
        RegistryManualsListCommand(manual=RegistryManualId.RENTA, year=2025),
        locale="es",
    )

    topics = {topic.slug: topic for topic in report.topics}
    assert topics["iva-regime"].title == "Régimen IVA"
    assert topics["iva-regime"].body.startswith("Régimen IVA aplicable al contribuyente")


def test_topic_projection_rejects_unknown_locale_with_application_error(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="aeat.application.registry._corpus")

    with pytest.raises(RegistryApplicationInputError, match=r"registry topic locale") as exc_info:
        list_registry_manuals(
            RegistryManualsListCommand(manual=RegistryManualId.RENTA, year=2025),
            locale="zz",
        )

    envelope = build_error_envelope(exc_info.value)
    assert envelope.code == "REFUSED_APPLICATION_REGISTRY_INPUT"
    assert envelope.context == {
        "registry_service": "registry.topics",
        "locale": "zz",
        "allowed_locales": "('es', 'en', 'ca', 'hu')",
    }
    records = [record for record in caplog.records if getattr(record, "registry_service", "") == "registry.topics"]
    assert len(records) == 1
    record = records[0]
    assert record.levelno == logging.WARNING
    assert record.__dict__["registry_locale"] == "zz"
    assert record.__dict__["registry_allowed_locales"] == ("es", "en", "ca", "hu")


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
    caplog.set_level(logging.WARNING, logger="aeat.application.registry._corpus")

    with pytest.raises(RegistryApplicationInputError, match=r"manual rule kind"):
        list_registry_manual_rules(
            RegistryManualRulesCommand(
                manual=RegistryManualId.RENTA,
                year=2025,
                kind="not-a-kind",
            )
        )

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
    tmp_path: Path,
) -> None:
    caplog.set_level(logging.WARNING, logger="aeat.application.registry._corpus")
    _write_valid_normative(tmp_path)

    with (
        override_settings(aeat_normatives_root=tmp_path),
        pytest.raises(NormativeNotFoundError, match=r"999|articulo"),
    ):
        show_registry_citation(
            RegistryCitationShowCommand(
                normative_id="ley-35-2006",
                articulo="999",
            )
        )

    records = [
        record for record in caplog.records if getattr(record, "registry_service", "") == "registry.citations.show"
    ]
    assert len(records) == 1
    record = records[0]
    assert record.levelno == logging.WARNING
    assert record.__dict__["registry_normative_id"] == "ley-35-2006"
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
        )
    )

    assert verification.manual_id == listed_part.manual_id
    assert verification.year == listed_part.year
    assert verification.part == listed_part.part


def test_manuals_list_report_rows_show_manifest_metadata_without_structure() -> None:
    report = list_registry_manuals(RegistryManualsListCommand(manual=RegistryManualId.RENTA, year=2025))
    listed_part = next(part for part in report.parts if part.part == ManualPart.PARTE_1.value)

    manual = show_registry_manual(
        RegistryManualShowCommand(
            manual=RegistryManualId(listed_part.manual_id),
            year=listed_part.year,
            part=ManualPart(listed_part.part),
        )
    )

    assert manual.manual_id == listed_part.manual_id
    assert manual.year == listed_part.year
    assert manual.part == listed_part.part
    assert manual.source_pdf_url.startswith("https://")
    assert manual.structure_available is False
    assert manual.chapter_count == 0
    assert manual.section_count == 0


def test_manuals_list_report_rows_rules_returns_extracted_rule_report() -> None:
    report = list_registry_manuals(RegistryManualsListCommand(manual=RegistryManualId.RENTA, year=2025))
    listed_part = next(part for part in report.parts if part.part == ManualPart.PARTE_1.value)

    rules = list_registry_manual_rules(
        RegistryManualRulesCommand(
            manual=RegistryManualId(listed_part.manual_id),
            year=listed_part.year,
            part=ManualPart(listed_part.part),
        )
    )

    assert rules.manual_id == listed_part.manual_id
    assert rules.year == listed_part.year
    assert rules.part == listed_part.part
    assert rules.structure_available is False
    assert rules.rule_count == 0
    assert rules.rules == ()


def test_registry_manual_id_rejects_out_of_scope_domain_manual_with_application_error() -> None:
    with pytest.raises(RegistryApplicationInputError, match=r"registry manual"):
        registry_manual_id(ManualId.SOCIEDADES)


def test_manual_rule_kind_validation_uses_application_error() -> None:
    with pytest.raises(RegistryApplicationInputError, match=r"manual rule kind"):
        list_registry_manual_rules(
            RegistryManualRulesCommand(
                manual=RegistryManualId.RENTA,
                year=2025,
                kind="not-a-kind",
            )
        )


def test_registry_topic_projection_is_strict_and_frozen() -> None:
    topic = RegistryTopicProjection(
        slug="iva-regime",
        title="IVA",
        body="IVA regime",
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
            }
        )
