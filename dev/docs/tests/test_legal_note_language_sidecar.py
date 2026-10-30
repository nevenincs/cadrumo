"""Docs annotation metadata is strict and cannot influence runtime authority."""

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema_references import LegalReference
from dev.registry.pipeline.authority_publication import authority_source_identity

from ..legal_note_languages import LEGAL_NOTE_LANGUAGES_RELPATH, apply_legal_note_languages, legal_note_language_ranges
from ..legal_reference_models import LegalNoteLanguageSpan, LegalProvisionRecord, LegalReferenceError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def _record() -> LegalProvisionRecord:
    return LegalProvisionRecord(
        legal_id="ley-example:art-1",
        kind="ley",
        document_id="BOE-A-2000-1",
        corpus_ref="corpus/normatives/html/example.html#art-1",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-2000-1#art-1",
        notes="Una nota revisada. English commentary.",
    )


def _write(root: Path, body: str) -> Path:
    path = root / LEGAL_NOTE_LANGUAGES_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_sidecar_joins_exact_annotations_by_id(tmp_path: Path) -> None:
    record = _record()
    _write(tmp_path, 'version = 1\n[[legal."ley-example:art-1"]]\nlanguage = "es"\ntext = "Una nota revisada."\n')
    joined = apply_legal_note_languages(tmp_path, (record,))
    assert joined == (
        replace(record, notes_language_spans=(LegalNoteLanguageSpan(text="Una nota revisada.", language="es"),)),
    )
    assert not record.notes_language_spans


def test_art36_catalogue_note_marks_only_the_exact_spanish_clause() -> None:
    note = (
        "LIRPF art 36: transmisiones a título lucrativo — se aplican las reglas del art. 35 tomando por "
        "importe real los valores del Impuesto sobre Sucesiones y Donaciones (sin exceder el valor de mercado). "
        "Base legal del cálculo de ganancia/pérdida por transmisión lucrativa en Modelo 100. AGENT-AUTHORED, "
        "grounded in the bundled authoritative ley-35-2006.html#a36; operator to confirm and re-stamp."
    )
    metadata = Path(__file__).parents[1] / "metadata/legal_note_languages.toml"
    from cadrumo.core.toml import parse_toml

    payload = parse_toml(metadata.read_text(encoding="utf-8"))
    span = LegalNoteLanguageSpan.model_validate(payload["legal"]["ley-35-2006:art-36"][0])

    assert legal_note_language_ranges(note, (span,)) == ((0, len(span.text), "es"),)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("version = 2\n[legal]\n", "version"),
        ("version = true\n[legal]\n", "version"),
        ("version = 1\nextra = true\n[legal]\n", "version"),
        ('version = 1\n[[legal.unknown]]\ntext = "Note"\nlanguage = "es"\n', "unknown legal_id"),
        ('version = 1\n[legal]\n"ley-example:art-1" = []\n', "non-empty"),
        ('version = 1\n[[legal."ley-example:art-1"]]\ntext = "Old note"\nlanguage = "es"\n', "exactly once"),
        ('version = 1\n[[legal."ley-example:art-1"]]\ntext = "Una"\nlanguage = "fr"\n', "invalid language"),
        (
            'version = 1\n[[legal."ley-example:art-1"]]\ntext = "Una"\nlanguage = "es"\nextra = true\n',
            "invalid language",
        ),
        ('version = 1\n[[legal."ley-example:art-1"]]\ntext = "Una"\ntext = "Una"\nlanguage = "es"\n', "cannot read"),
        (
            'version = 1\n[[legal."ley-example:art-1"]]\ntext = "Una"\nlanguage = "es"\n'
            '[[legal."ley-example:art-1"]]\ntext = "Una"\nlanguage = "es"\n',
            "duplicate spans",
        ),
        (
            'version = 1\n[[legal."ley-example:art-1"]]\ntext = "Una nota"\nlanguage = "es"\n'
            '[[legal."ley-example:art-1"]]\ntext = "nota revisada"\nlanguage = "es"\n',
            "overlap",
        ),
    ],
)
def test_invalid_sidecar_refuses_before_render(tmp_path: Path, body: str, message: str) -> None:
    _write(tmp_path, body)
    with pytest.raises(LegalReferenceError, match=message):
        apply_legal_note_languages(tmp_path, (_record(),))


def test_sidecar_ambiguous_substrings_refuse(tmp_path: Path) -> None:
    _write(tmp_path, 'version = 1\n[[legal."ley-example:art-1"]]\ntext = "aaa"\nlanguage = "es"\n')
    with pytest.raises(LegalReferenceError, match="exactly once"):
        apply_legal_note_languages(tmp_path, (replace(_record(), notes="aaaa"),))


def test_metadata_edit_preserves_runtime_snapshot_and_authority_identity(tmp_path: Path) -> None:
    record = _record()
    model = LegalReference.model_validate(
        {
            "id": record.legal_id,
            "evidence_tier": "legal_authority",
            "authority": "boe",
            "kind": record.kind,
            "document_id": record.document_id,
            "corpus_ref": record.corpus_ref,
            "permalink": record.permalink,
            "effective_from": date(2000, 1, 1),
            "review_status": "pending_review",
            "required_text": ("Artículo 1",),
            "notes": record.notes,
        }
    )
    registry_root = tmp_path / "src/cadrumo/_data/registry/aeat"
    registry_root.mkdir(parents=True)
    (registry_root / "legal.toml").write_text(
        '[legal."ley-example:art-1"]\nnotes = "Una nota revisada."\n', encoding="utf-8"
    )
    source_root = tmp_path / "src/cadrumo/_data"
    profile = source_root / "registry/cadrumo/user_profile/schema.toml"
    profile.parent.mkdir(parents=True)
    profile.write_text("version = 1\n", encoding="utf-8")
    snapshot = model.model_dump_json()
    identity = authority_source_identity(registry_root=registry_root, source_root=source_root)
    path = _write(
        tmp_path, 'version = 1\n[[legal."ley-example:art-1"]]\ntext = "Una nota revisada."\nlanguage = "es"\n'
    )
    first = apply_legal_note_languages(tmp_path, (record,))
    path.write_text(path.read_text(encoding="utf-8").replace('language = "es"', 'language = "en"'), encoding="utf-8")
    second = apply_legal_note_languages(tmp_path, (record,))
    assert first != second
    assert authority_source_identity(registry_root=registry_root, source_root=source_root) == identity
    assert "notes_language_spans" not in LegalReference.model_fields
    assert LegalReference.model_validate_json(snapshot).model_dump_json() == snapshot
    assert model.model_dump_json() == snapshot
