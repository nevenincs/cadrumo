"""Application registry corpus projection tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ...domain.manuals import ManualId, ManualPart
from ..topics import load_topic_catalogue
from . import (
    RegistryApplicationInputError,
    RegistryManualId,
    RegistryManualRulesCommand,
    RegistryManualShowCommand,
    RegistryManualsListCommand,
    RegistryManualVerifyCommand,
    RegistryTopicProjection,
    list_registry_manual_rules,
    list_registry_manuals,
    registry_manual_id,
    show_registry_manual,
    verify_registry_citations,
    verify_registry_manual,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_citations_verification_report_consumes_topic_catalogue() -> None:
    report = verify_registry_citations()

    assert report.operation == "registry.citations.verify"
    assert report.topic_count == len(load_topic_catalogue().topics)
    assert {topic.slug for topic in report.topics} >= {"iva-regime", "casilla", "modelos"}
    assert report.issue_count == len(report.issues)


def test_manuals_list_report_discovers_real_corpus_parts_and_topics() -> None:
    report = list_registry_manuals(RegistryManualsListCommand(manual=None, year=None))

    assert report.operation == "registry.manuals.list"
    assert report.part_count == len(report.parts)
    assert report.topic_count == len(load_topic_catalogue().topics)
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
        topic.title = "changed"  # type: ignore[misc]

    with pytest.raises(ValidationError, match=r"Extra inputs"):
        RegistryTopicProjection.model_validate(
            {
                "slug": "iva-regime",
                "title": "IVA",
                "body": "IVA regime",
                "extra": "rejected",
            }
        )
