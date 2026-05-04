"""Unit tests for the strict pydantic v2 schema and rule-id generator."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import AnyHttpUrl, ValidationError

from ...core.i18n import Translatable as tr  # noqa: N813
from . import (
    Chapter,
    FetchedManualPart,
    LLMProvenance,
    Manual,
    ManualId,
    ManualPart,
    Paragraph,
    Rule,
    RuleKind,
    RuleSource,
    Section,
    SectionRef,
    SectionSource,
    generate_rule_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _llm_provenance() -> LLMProvenance:
    return LLMProvenance(
        provider="anthropic",
        model="claude-opus-4-6",
        prompt_id="manual_rule_extract_v1",
        cache_hit=False,
        extracted_at=datetime(2026, 4, 12, 10, 0, 0, tzinfo=UTC),
    )


def _rule_source() -> RuleSource:
    return RuleSource(
        manual_url=AnyHttpUrl(
            "https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IRPF/"
            "IRPF-2025/ManualRenta2025Parte1_es_es.pdf"
        ),
        page=142,
        paragraph=3,
    )


def _section_source() -> SectionSource:
    return SectionSource(
        manual_url=AnyHttpUrl(
            "https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IRPF/"
            "IRPF-2025/ManualRenta2025Parte1_es_es.pdf"
        ),
        page=140,
    )


def _rule(rule_id: str = "renta-2025-parte1-cap5-sec2-rule0001", kind: RuleKind = RuleKind.OBLIGATION) -> Rule:
    return Rule(
        rule_id=rule_id,
        manual_id=ManualId.RENTA,
        year=2025,
        part=ManualPart.PARTE_1,
        chapter_id="cap5",
        section_id="sec2",
        kind=kind,
        statement=tr("manuals.test_schema.statement_121189"),
        applies_when=None,
        references_casillas=("MODELO_130:01",),
        references_sections=(),
        references_legal_acts=("Ley 35/2006, art. 32",),
        source=_rule_source(),
        extracted_by=_llm_provenance(),
        definition_reviewed_by="gw",
        definition_reviewed_at=date(2026, 4, 12),
    )


def _section(section_id: str = "sec2") -> Section:
    return Section(
        section_id=section_id,
        chapter_id="cap5",
        title=tr("manuals.test_schema.title_208795"),
        summary=tr("manuals.test_schema.summary_179171"),
        prose=(Paragraph(paragraph_id="p1", text="Texto", page=140),),
        rules=(),
        references_sections=(),
        references_legal_acts=(),
        source=_section_source(),
        definition_reviewed_by="gw",
        definition_reviewed_at=date(2026, 4, 12),
    )


def _chapter() -> Chapter:
    return Chapter(
        chapter_id="cap5",
        title=tr("manuals.test_schema.title_472764"),
        summary=tr("manuals.test_schema.summary_685481"),
        sections=(SectionRef(section_id="sec2", relative_path="structure/sections/cap5/sec2.json"),),
    )


def _manual() -> Manual:
    return Manual(
        manual_id=ManualId.RENTA,
        year=2025,
        part=ManualPart.PARTE_1,
        title=tr("manuals.test_schema.title_935553"),
        summary=tr("manuals.test_schema.summary_685481"),
        source_pdf_url=AnyHttpUrl(
            "https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IRPF/"
            "IRPF-2025/ManualRenta2025Parte1_es_es.pdf"
        ),
        source_html_url=None,
        fetched_at=datetime(2026, 4, 12, 0, 0, 0, tzinfo=UTC),
        definition_reviewed_by="gw",
        definition_reviewed_at=date(2026, 4, 12),
        chapters=(_chapter(),),
    )


class TestStrictSchema:
    """Models reject invalid inputs and accept well-formed ones."""

    def test_rule_happy_path(self) -> None:
        """A well-formed rule round-trips through model_validate_json."""
        rule = _rule()
        payload = rule.model_dump_json()
        reloaded = Rule.model_validate_json(payload)
        assert reloaded == rule

    def test_rule_rejects_missing_spanish_statement(self) -> None:
        """A rule with a statement lacking 'es' must fail validation."""
        with pytest.raises(ValidationError):
            Rule(
                rule_id="renta-2025-parte1-cap5-sec2-rule0002",
                manual_id=ManualId.RENTA,
                year=2025,
                part=ManualPart.PARTE_1,
                chapter_id="cap5",
                section_id="sec2",
                kind=RuleKind.OBLIGATION,
                statement=tr("translation"),
                applies_when=None,
                references_casillas=(),
                references_sections=(),
                references_legal_acts=(),
                source=_rule_source(),
                extracted_by=_llm_provenance(),
                definition_reviewed_by="gw",
                definition_reviewed_at=date(2026, 4, 12),
            )

    def test_rule_rejects_invalid_casilla_reference(self) -> None:
        """Casilla references must match the MODELO_NNN[:CODE] pattern."""
        with pytest.raises(ValidationError):
            Rule(
                rule_id="renta-2025-parte1-cap5-sec2-rule0003",
                manual_id=ManualId.RENTA,
                year=2025,
                part=ManualPart.PARTE_1,
                chapter_id="cap5",
                section_id="sec2",
                kind=RuleKind.OBLIGATION,
                statement=tr("manuals.test_schema.statement_994536"),
                applies_when=None,
                references_casillas=("not-a-modelo-id",),
                references_sections=(),
                references_legal_acts=(),
                source=_rule_source(),
                extracted_by=_llm_provenance(),
                definition_reviewed_by="gw",
                definition_reviewed_at=date(2026, 4, 12),
            )

    def test_rule_rejects_empty_reviewer(self) -> None:
        """Reviewer metadata must be a non-empty trimmed string."""
        with pytest.raises(ValidationError):
            Rule(
                rule_id="renta-2025-parte1-cap5-sec2-rule0004",
                manual_id=ManualId.RENTA,
                year=2025,
                part=ManualPart.PARTE_1,
                chapter_id="cap5",
                section_id="sec2",
                kind=RuleKind.OBLIGATION,
                statement=tr("manuals.test_schema.statement_994536"),
                applies_when=None,
                references_casillas=(),
                references_sections=(),
                references_legal_acts=(),
                source=_rule_source(),
                extracted_by=_llm_provenance(),
                definition_reviewed_by="   ",
                definition_reviewed_at=date(2026, 4, 12),
            )

    def test_manual_rejects_year_below_2000(self) -> None:
        """Year bounds guard against obviously bogus values."""
        with pytest.raises(ValidationError):
            Manual(
                manual_id=ManualId.RENTA,
                year=1999,
                part=ManualPart.PARTE_1,
                title=tr("manuals.test_schema.title_421077"),
                summary=tr("manuals.test_schema.summary_685481"),
                source_pdf_url=AnyHttpUrl("https://example.com/x.pdf"),
                source_html_url=None,
                fetched_at=datetime(2026, 4, 12, 0, 0, 0, tzinfo=UTC),
                definition_reviewed_by="gw",
                definition_reviewed_at=date(2026, 4, 12),
                chapters=(),
            )

    def test_manual_round_trip_preserves_structure(self) -> None:
        """Dump + reload must preserve a full Manual tree."""
        manual = _manual()
        payload = manual.model_dump_json()
        reloaded = Manual.model_validate_json(payload)
        assert reloaded == manual
        assert '"definition_reviewed_by"' in payload
        assert '"definition_reviewed_at"' in payload
        assert '"reviewed_by"' not in payload
        assert '"reviewed_at"' not in payload

    def test_fetched_manifest_rejects_bad_sha256(self) -> None:
        """sha256 must be a 64-char lower-case hex string."""
        with pytest.raises(ValidationError):
            FetchedManualPart(
                manual_id=ManualId.IVA,
                year=2025,
                part=ManualPart.SINGLE,
                source_pdf_url=AnyHttpUrl("https://example.com/iva.pdf"),
                relative_pdf_path="source.pdf",
                sha256="NOT_HEX",
                content_length=10,
                fetched_at=datetime(2026, 4, 12, 0, 0, 0, tzinfo=UTC),
            )


class TestRuleIds:
    """Deterministic rule-id generation."""

    def test_deterministic_for_fixed_inputs(self) -> None:
        """Same inputs always produce the same identifier."""
        first = generate_rule_id(
            manual_id=ManualId.RENTA,
            year=2025,
            part=ManualPart.PARTE_1,
            chapter_id="cap5",
            section_id="sec2",
            ordinal=7,
        )
        second = generate_rule_id(
            manual_id=ManualId.RENTA,
            year=2025,
            part=ManualPart.PARTE_1,
            chapter_id="cap5",
            section_id="sec2",
            ordinal=7,
        )
        assert first == second == "renta-2025-parte1-cap5-sec2-rule0007"

    def test_single_part_is_collapsed(self) -> None:
        """IVA (SINGLE) rule IDs omit the part segment."""
        assert (
            generate_rule_id(
                manual_id=ManualId.IVA,
                year=2025,
                part=ManualPart.SINGLE,
                chapter_id="cap3",
                section_id="sec1",
                ordinal=1,
            )
            == "iva-2025-cap3-sec1-rule0001"
        )

    def test_ordinal_must_be_positive(self) -> None:
        """Ordinals below 1 raise ValueError."""
        with pytest.raises(ValueError, match="ordinal must be >= 1"):
            generate_rule_id(
                manual_id=ManualId.IVA,
                year=2025,
                part=ManualPart.SINGLE,
                chapter_id="cap3",
                section_id="sec1",
                ordinal=0,
            )

    def test_empty_chapter_after_slug_rejected(self) -> None:
        """A chapter id that slugs to the empty string is rejected."""
        with pytest.raises(ValueError, match="chapter_id"):
            generate_rule_id(
                manual_id=ManualId.IVA,
                year=2025,
                part=ManualPart.SINGLE,
                chapter_id="---",
                section_id="sec1",
                ordinal=1,
            )
