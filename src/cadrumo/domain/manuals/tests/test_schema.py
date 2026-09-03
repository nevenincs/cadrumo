"""Unit tests for the strict pydantic v2 manual schema."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import AnyHttpUrl, ValidationError

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....tests.aeat_literal_fixtures import manual_practicos_url
from ..schema import (
    Chapter,
    FetchedManualPart,
    LLMProvenance,
    Manual,
    ManualCasillaReference,
    ManualId,
    ManualPart,
    Paragraph,
    Rule,
    RuleKind,
    RuleSource,
    Section,
    SectionRef,
    SectionSource,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_RENTA_2025_MANUAL_URL = manual_practicos_url("IRPF/IRPF-2025/ManualRenta2025Parte1_es_es.pdf")
_M130_CASILLA_01: CasillaId = validated_casilla_id("01", surface="_M130_CASILLA_01")


def _llm_provenance() -> LLMProvenance:
    return LLMProvenance(
        provider="anthropic",
        model="test-model",
        prompt_id="manual_rule_extract_v1",
        cache_hit=False,
        extracted_at=datetime(2026, 4, 12, 10, 0, 0, tzinfo=UTC),
    )


def _rule_source() -> RuleSource:
    return RuleSource(
        manual_url=AnyHttpUrl(_RENTA_2025_MANUAL_URL),
        page=142,
        paragraph=3,
    )


def _section_source() -> SectionSource:
    return SectionSource(
        manual_url=AnyHttpUrl(_RENTA_2025_MANUAL_URL),
        page=140,
    )


def _rule(rule_id: str = "renta-2025-part1-cap5-sec2-rule0001", kind: RuleKind = "computation") -> Rule:
    return Rule(
        rule_id=rule_id,
        manual_id=ManualId.RENTA,
        year=2025,
        part=ManualPart.PARTE_1,
        chapter_id="cap5",
        section_id="sec2",
        kind=kind,
        statement="Statement in Spanish.",
        applies_when=None,
        references_casillas=(ManualCasillaReference(modelo_id="130", casilla_id=_M130_CASILLA_01),),
        references_sections=(),
        references_legal_acts=("LEY_35_2006|art. 32",),
        source=_rule_source(),
        extracted_by=_llm_provenance(),
        definition_reviewed_by="gw",
        definition_reviewed_at=date(2026, 4, 12),
    )


def _section(section_id: str = "sec2") -> Section:
    return Section(
        section_id=section_id,
        chapter_id="cap5",
        title="Section Title",
        summary="Section Summary",
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
        title="Chapter Title",
        summary="Chapter Summary",
        sections=(SectionRef(section_id="sec2", relative_path="structure/sections/cap5/sec2.json"),),
    )


def _manual() -> Manual:
    return Manual(
        manual_id=ManualId.RENTA,
        year=2025,
        part=ManualPart.PARTE_1,
        title="Manual Title",
        summary="Manual Summary",
        source_pdf_url=AnyHttpUrl(_RENTA_2025_MANUAL_URL),
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
        """A rule with an empty statement must fail validation."""
        with pytest.raises(ValidationError, match=r"Rule.statement: missing authoritative Spanish text"):
            Rule(
                rule_id="renta-2025-part1-cap5-sec2-rule0002",
                manual_id=ManualId.RENTA,
                year=2025,
                part=ManualPart.PARTE_1,
                chapter_id="cap5",
                section_id="sec2",
                kind="computation",
                statement="   ",
                applies_when=None,
                references_casillas=(),
                references_sections=(),
                references_legal_acts=(),
                source=_rule_source(),
                extracted_by=_llm_provenance(),
                definition_reviewed_by="gw",
                definition_reviewed_at=date(2026, 4, 12),
            )

    def test_rule_rejects_blank_applies_when(self) -> None:
        """Optional applicability prose must not carry blank authoritative text."""
        with pytest.raises(ValidationError, match=r"Rule.applies_when: missing authoritative Spanish text"):
            Rule(
                rule_id="renta-2025-part1-cap5-sec2-rule0003",
                manual_id=ManualId.RENTA,
                year=2025,
                part=ManualPart.PARTE_1,
                chapter_id="cap5",
                section_id="sec2",
                kind="applicability",
                statement="Statement in Spanish.",
                applies_when="   ",
                references_casillas=(),
                references_sections=(),
                references_legal_acts=(),
                source=_rule_source(),
                extracted_by=_llm_provenance(),
                definition_reviewed_by="gw",
                definition_reviewed_at=date(2026, 4, 12),
            )

    def test_rule_rejects_legacy_scalar_casilla_reference(self) -> None:
        """Manual casilla references must be structured, not MODELO:CASILLA strings."""
        with pytest.raises(ValidationError, match=r"references_casillas"):
            Rule.model_validate(
                {
                    "rule_id": "renta-2025-part1-cap5-sec2-rule0003",
                    "manual_id": ManualId.RENTA,
                    "year": 2025,
                    "part": ManualPart.PARTE_1,
                    "chapter_id": "cap5",
                    "section_id": "sec2",
                    "kind": "computation",
                    "statement": "Statement.",
                    "applies_when": None,
                    "references_casillas": ("not-a-structured-casilla",),
                    "references_sections": (),
                    "references_legal_acts": (),
                    "source": _rule_source(),
                    "extracted_by": _llm_provenance(),
                    "definition_reviewed_by": "gw",
                    "definition_reviewed_at": date(2026, 4, 12),
                },
            )

    def test_paragraph_rejects_missing_spanish_text(self) -> None:
        """Paragraph prose is source corpus text and cannot be blank."""
        with pytest.raises(ValidationError, match=r"Paragraph.text: missing authoritative Spanish text"):
            Paragraph(paragraph_id="p1", text="   ", page=140)

    def test_rule_rejects_empty_reviewer(self) -> None:
        """Reviewer metadata must be a non-empty trimmed string."""
        with pytest.raises(ValidationError, match=r"at least 1 character"):
            Rule(
                rule_id="renta-2025-part1-cap5-sec2-rule0004",
                manual_id=ManualId.RENTA,
                year=2025,
                part=ManualPart.PARTE_1,
                chapter_id="cap5",
                section_id="sec2",
                kind="computation",
                statement="Statement.",
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
        with pytest.raises(ValidationError, match=r"greater than or equal to 2000"):
            Manual(
                manual_id=ManualId.RENTA,
                year=1999,
                part=ManualPart.PARTE_1,
                title="Title",
                summary="Summary",
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
        with pytest.raises(ValidationError, match=r"sha256"):
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
