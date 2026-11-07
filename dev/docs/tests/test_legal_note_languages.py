"""Reviewed note language annotations must remain exact and visible to spelling."""

from collections import Counter
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from docutils.core import publish_parts
from pydantic import ValidationError

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.domain.calculations.registry.schema_references import LegalReference
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from dev.locales.signal_documentation_inventory import inventory_generated_document_file
from dev.paths import REPO_ROOT

from ..compile_slots import activate, compile_slots_educated, deactivate
from ..legal_catalogue import load_legal_provisions
from ..legal_catalogue_fields import record_from_table
from ..legal_page_rendering import catalogue_note_projection
from ..legal_reference import render_legal_reference
from ..legal_reference_models import LegalNoteLanguageSpan, LegalProvisionRecord, LegalReferenceError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def _record(note: str, *spans: LegalNoteLanguageSpan) -> LegalProvisionRecord:
    return LegalProvisionRecord(
        legal_id="ley-example:art-1",
        kind="ley",
        document_id="BOE-A-2000-1",
        corpus_ref="corpus/normatives/html/example.html#art-1",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-2000-1#art-1",
        notes=note,
        notes_language_spans=spans,
    )


def _inventory_rendered_record(
    tmp_path: Path, record: LegalProvisionRecord
) -> tuple[list[dict[str, object]], dict[str, dict[str, str]]]:
    rendered = render_legal_reference(tmp_path, records=(record,), language=OutputLanguage.EN).pages[0]
    page = tmp_path / rendered.output_relpath
    page.parent.mkdir(parents=True)
    page.write_text(rendered.rst, encoding="utf-8")
    values: dict[str, dict[str, str]] = {}
    findings: list[dict[str, object]] = []
    inventory_generated_document_file(page, tmp_path, Counter(), findings, values)
    return findings, values


def test_reviewed_span_checks_spanish_paraphrase_without_hiding_english_typo(tmp_path: Path) -> None:
    spanish = "La deducción se aplica en el período siguiente."
    record = _record(
        f"English commentary definately stays checked. {spanish}",
        LegalNoteLanguageSpan(text=spanish, language="es"),
    )
    findings, values = _inventory_rendered_record(tmp_path, record)

    assert not findings, findings
    assert spanish in values["es"].values()
    assert all(spanish not in text for text in values["en"].values())
    assert any("definately" in text for text in values["en"].values())


@pytest.mark.parametrize(
    ("note", "spans", "message"),
    [
        ("Changed note", (LegalNoteLanguageSpan(text="Old note", language="es"),), "exactly once"),
        ("Repeated. Repeated.", (LegalNoteLanguageSpan(text="Repeated.", language="es"),), "exactly once"),
        ("aaaa", (LegalNoteLanguageSpan(text="aaa", language="es"),), "exactly once"),
        (
            "Una nota revisada.",
            (
                LegalNoteLanguageSpan(text="Una nota", language="es"),
                LegalNoteLanguageSpan(text="nota revisada", language="en"),
            ),
            "overlap",
        ),
        ("Blank", (LegalNoteLanguageSpan(text=" ", language="es"),), "exactly once"),
    ],
)
def test_stale_ambiguous_and_overlapping_annotations_refuse_rendering(
    tmp_path: Path, note: str, spans: tuple[LegalNoteLanguageSpan, ...], message: str
) -> None:
    with pytest.raises(LegalReferenceError, match=message):
        render_legal_reference(tmp_path, records=(_record(note, *spans),))


def test_annotation_without_note_is_refused(tmp_path: Path) -> None:
    record = replace(_record("Note", LegalNoteLanguageSpan(text="Note", language="en")), notes=None)
    with pytest.raises(LegalReferenceError, match="exactly once"):
        render_legal_reference(tmp_path, records=(record,))


def test_unsupported_language_and_unknown_annotation_fields_are_refused() -> None:
    for payload in ({"text": "Note", "language": "fr"}, {"text": "Note", "language": "es", "extra": True}):
        with pytest.raises(ValidationError):
            LegalNoteLanguageSpan.model_validate(payload)


def test_catalogue_loader_refuses_docs_metadata() -> None:
    with pytest.raises(LegalReferenceError, match="unknown field"):
        record_from_table(
            Path("example.toml"),
            "ley-example:art-1",
            {
                "kind": "ley",
                "document_id": "BOE-A-2000-1",
                "corpus_ref": "corpus/normatives/html/example.html#art-1",
                "permalink": "https://www.boe.es/buscar/act.php?id=BOE-A-2000-1#art-1",
                "notes": "Una nota revisada.",
                "notes_language_spans": [{"text": "Una nota revisada.", "language": "es"}],
            },
        )


def test_registry_model_refuses_docs_annotations() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        LegalReference.model_validate(
            {
                "id": "ley-example:art-1",
                "evidence_tier": "legal_authority",
                "authority": "boe",
                "kind": "ley",
                "corpus_ref": "corpus/normatives/html/example.html#art-1",
                "document_id": "BOE-A-2000-1",
                "permalink": "https://www.boe.es/buscar/act.php?id=BOE-A-2000-1#art-1",
                "effective_from": date(filing_year_envelope().floor, 1, 1),
                "review_status": "pending_review",
                "required_text": ("Artículo 1",),
                "notes": "Changed note",
                "notes_language_spans": (LegalNoteLanguageSpan(text="Old note", language="es"),),
            }
        )


def test_explicit_english_span_overrides_source_quote_match(tmp_path: Path) -> None:
    text = "A shared phrase"
    record = replace(_record(text, LegalNoteLanguageSpan(text=text, language="en")), required_text=(text,))
    source = tmp_path / "src/cadrumo/_data/corpus/normatives/html/example.html.extracted.md"
    source.parent.mkdir(parents=True)
    source.write_text(text, encoding="utf-8")
    rst = render_legal_reference(tmp_path, records=(record,), language=OutputLanguage.ES).pages[0].rst
    assert f'<span lang="en">{text}</span>' in rst
    assert f'<span lang="es">{text}</span>' not in rst


def test_annotated_rst_markup_is_refused_instead_of_silently_discarding_language(tmp_path: Path) -> None:
    note = "Texto revisado. See https://example.test/law"
    with pytest.raises(LegalReferenceError, match="plain inline text"):
        render_legal_reference(tmp_path, records=(_record(note, LegalNoteLanguageSpan(text=note, language="es")),))


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_quoted_note_projection_preserves_page_typography_and_exact_language_span(
    tmp_path: Path, language: OutputLanguage
) -> None:
    spanish = 'Artículo "primero" y letra a\''
    note = f"English note: {spanish}. A & B and :doc:`literal` stay text."
    record = _record(note, LegalNoteLanguageSpan(text=spanish, language="es"))
    rendered = "\n".join(catalogue_note_projection(record, language, tmp_path, {}))
    paragraph = BeautifulSoup(rendered, "html.parser").find("p")
    assert paragraph is not None
    assert paragraph.get_text() == compile_slots_educated(note, language.value)
    span = paragraph.find("span", lang="es")
    assert span is not None
    start = note.index(spanish)
    assert span.get_text() == compile_slots_educated(note, language.value)[start : start + len(spanish)]
    assert paragraph.find("a") is None and paragraph.find("script") is None
    assert record.notes == note


def test_quoted_note_projection_keeps_each_compiled_language_typography(tmp_path: Path) -> None:
    spanish = 'La "cuota"'
    note = f"Agent's explanation: {spanish}."
    record = _record(note, LegalNoteLanguageSpan(text=spanish, language="es"))
    languages = [language.value for language in OutputLanguage]
    slots = activate(languages)
    try:
        rendered = "\n".join(catalogue_note_projection(record, OutputLanguage.EN, tmp_path, {}))
        for index, language in enumerate(languages):
            paragraph = BeautifulSoup(slots.resolved(rendered, index), "html.parser").find("p")
            assert paragraph is not None
            assert paragraph.get_text() == compile_slots_educated(note, language)
            assert paragraph.find("span", lang="es") is not None
    finally:
        deactivate()


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_quoted_note_matches_the_legacy_docutils_rendering(tmp_path: Path, language: OutputLanguage) -> None:
    spanish = 'La "cuota" y letra a\''
    note = f"Agent's note: {spanish}; A & B."
    old = _record(note)
    annotated = _record(note, LegalNoteLanguageSpan(text=spanish, language="es"))

    def paragraph(record: LegalProvisionRecord) -> str:
        projection = "\n".join(catalogue_note_projection(record, language, tmp_path, {}))
        source = ".. container::\n\n" + projection + "\n"
        parts = publish_parts(
            source,
            writer_name="html5",
            settings_overrides={"language_code": language.value, "smart_quotes": True, "report_level": 5},
        )
        element = BeautifulSoup(parts["html_body"], "html.parser").select_one("dd p")
        assert element is not None
        return element.get_text()

    assert paragraph(annotated) == paragraph(old)
    assert old.notes == annotated.notes == note


def test_quoted_note_inventory_checks_span_and_surrounding_prose_in_their_languages(tmp_path: Path) -> None:
    spanish = 'La "deducción" se aplica en el período siguiente.'
    note = f"English definately stays checked. {spanish}"
    record = _record(note, LegalNoteLanguageSpan(text=spanish, language="es"))
    findings, values = _inventory_rendered_record(tmp_path, record)
    assert not findings, findings
    assert any("deducción" in text for text in values["es"].values())
    assert all("deducción" not in text for text in values["en"].values())
    assert any("definately" in text for text in values["en"].values())


@pytest.mark.parametrize(
    "note",
    [
        'Quoted "text" with https://example.test/path',
        "Quoted 'text' with mailto:bad@example.test",
        'Quoted "text" with <script>alert(1)</script>',
        'Quoted "text"\nsecond line',
        'Quoted "text" -- more',
        'Quoted "text" ... more',
        'Quoted \\"text\\"',
    ],
)
def test_quoted_note_projection_keeps_existing_markup_and_offset_refusals(tmp_path: Path, note: str) -> None:
    record = _record(note, LegalNoteLanguageSpan(text=note, language="es"))
    with pytest.raises(LegalReferenceError, match="plain inline text"):
        catalogue_note_projection(record, OutputLanguage.EN, tmp_path, {})


def test_reviewed_madrid_batch_marks_only_the_three_reviewed_notes() -> None:
    records = load_legal_provisions(REPO_ROOT)
    reviewed_ids = {
        "madrid-dl-1-2010:art-2",
        "madrid-dl-1-2010:art-4",
        "madrid-dl-1-2010:art-18",
    }
    annotated = [record for record in records if record.legal_id in reviewed_ids]
    assert {record.legal_id for record in annotated} == reviewed_ids
    for record in annotated:
        assert record.notes is not None
        assert record.notes_language_spans == (LegalNoteLanguageSpan(text=record.notes, language="es"),)
