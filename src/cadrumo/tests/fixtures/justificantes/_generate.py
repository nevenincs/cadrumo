"""Synthetic justificante PDF generator for the #44 parser test suite."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from ..provenance import SYNTHETIC_FIXTURE_PRODUCER
from .generate_base import (
    FIXTURES,
    draw,
    write_sidecar,
)
from .generate_iva_corpus import (
    MODELO_130_CORPUS_FIXTURES,
    MODELO_303_CORPUS_FIXTURES,
    MODELO_390_CORPUS_FIXTURES,
    Modelo130CorpusFixture,
    Modelo303CorpusFixture,
    Modelo390CorpusFixture,
    draw_modelo_130_corpus,
    draw_modelo_303_corpus,
    draw_modelo_390_corpus,
)
from .generate_misc_a import (
    MODELO_036_FIXTURES,
    MODELO_115_FIXTURES,
    MODELO_180_FIXTURES,
    MODELO_193_FIXTURES,
    MODELO_349_FIXTURES,
    MODELO_369_FIXTURES,
    MODELO_720_FIXTURES,
    draw_modelo_036,
    draw_modelo_115,
    draw_modelo_180,
    draw_modelo_193,
    draw_modelo_349,
    draw_modelo_369,
    draw_modelo_720,
)
from .generate_misc_b import (
    MODELO_123_FIXTURES,
    MODELO_131_FIXTURES,
    MODELO_184_FIXTURES,
    MODELO_202_FIXTURES,
    MODELO_232_FIXTURES,
    MODELO_347_FIXTURES,
    MODELO_840_FIXTURES,
    Modelo123Fixture,
    Modelo131Fixture,
    Modelo184Fixture,
    Modelo202Fixture,
    Modelo232Fixture,
    Modelo347Fixture,
    Modelo840Fixture,
    draw_modelo_123,
    draw_modelo_131,
    draw_modelo_184,
    draw_modelo_202,
    draw_modelo_232,
    draw_modelo_347,
    draw_modelo_840,
)
from .generate_modelo_100_corpus import (
    MODELO_100_CORPUS_FIXTURES,
    Modelo100CorpusFixture,
    draw_modelo_100_corpus,
)
from .generate_modelo_100_current import (
    MODELO_100_CURRENT_YEAR_FIXTURES,
    Modelo100CurrentYearFixture,
    draw_modelo_100_current_year,
)
from .generate_modelo_111 import (
    MODELO_111_FIXTURES,
    Modelo111Fixture,
    draw_modelo_111,
)
from .generate_modelo_190 import (
    MODELO_190_FIXTURES,
    Modelo190Fixture,
    draw_modelo_190,
)
from .generate_modelo_390_english import (
    MODELO_390_ENGLISH_FIXTURES,
    Modelo390EnglishFixture,
    draw_modelo_390_english,
)

__all__ = [
    "Modelo100CorpusFixture",
    "Modelo100CurrentYearFixture",
    "Modelo111Fixture",
    "Modelo123Fixture",
    "Modelo130CorpusFixture",
    "Modelo131Fixture",
    "Modelo184Fixture",
    "Modelo190Fixture",
    "Modelo202Fixture",
    "Modelo232Fixture",
    "Modelo303CorpusFixture",
    "Modelo347Fixture",
    "Modelo390CorpusFixture",
    "Modelo390EnglishFixture",
    "Modelo840Fixture",
    "main",
]


def main() -> None:
    """Regenerate every fixture PDF in-place."""
    out_dir = Path(__file__).parent
    for fixture in FIXTURES:
        target = out_dir / fixture.filename
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        # Deterministic metadata so file bytes are reproducible across runs.
        # invariant=True pins /CreationDate and /ModDate to 2000-01-01T00:00:00Z.
        c.setTitle(f"Justificante {fixture.modelo} {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic justificante fixture")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        draw(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")

    for fixture in MODELO_130_CORPUS_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Modelo 130 {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m130 corpus")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        draw_modelo_130_corpus(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        write_sidecar(target, "130", fixture.ejercicio, fixture.tax_id)

    for fixture in MODELO_369_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 369 {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m369")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        draw_modelo_369(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        write_sidecar(target, "369", fixture.ejercicio, fixture.tax_id)

    for fixture in MODELO_180_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 180 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m180")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        draw_modelo_180(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        write_sidecar(target, "180", fixture.ejercicio, fixture.tax_id)

    for fixture in MODELO_036_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion censal Modelo 036 {fixture.event_kind}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion-censal fixture m036")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        draw_modelo_036(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        write_sidecar(target, "036", fixture.ejercicio, fixture.tax_id)

    for fixture in MODELO_232_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 232 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m232")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        draw_modelo_232(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        write_sidecar(target, "232", fixture.ejercicio, fixture.tax_id)

    for fixture in MODELO_349_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 349 {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m349")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        draw_modelo_349(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        write_sidecar(target, "349", fixture.ejercicio, fixture.tax_id)

    for fixture in MODELO_123_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 123 {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m123")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        draw_modelo_123(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        write_sidecar(target, "123", fixture.ejercicio, fixture.tax_id)

    for fixture in MODELO_840_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 840 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m840")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        draw_modelo_840(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        write_sidecar(target, "840", fixture.ejercicio, fixture.tax_id)

    for fixture in MODELO_193_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 193 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m193")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        draw_modelo_193(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        write_sidecar(target, "193", fixture.ejercicio, fixture.tax_id)

    for fixture in MODELO_720_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 720 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m720")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        draw_modelo_720(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        write_sidecar(target, "720", fixture.ejercicio, fixture.tax_id)

    for fixture in MODELO_347_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 347 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m347")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        draw_modelo_347(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        write_sidecar(target, "347", fixture.ejercicio, fixture.tax_id)

    for fixture in MODELO_184_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 184 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m184")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        draw_modelo_184(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        write_sidecar(target, "184", fixture.ejercicio, fixture.tax_id)

    for fixture in MODELO_115_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 115 {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m115")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        draw_modelo_115(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        write_sidecar(target, "115", fixture.ejercicio, fixture.tax_id)

    for fixture in MODELO_131_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 131 {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m131")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        draw_modelo_131(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        write_sidecar(target, "131", fixture.ejercicio, fixture.tax_id)

    for fixture in MODELO_202_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 202 {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m202")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        draw_modelo_202(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        write_sidecar(target, "202", fixture.ejercicio, fixture.tax_id)

    for fixture in MODELO_303_CORPUS_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Modelo 303 {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m303 corpus")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        draw_modelo_303_corpus(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        write_sidecar(target, "303", fixture.ejercicio, fixture.tax_id)

    for fixture in MODELO_100_CURRENT_YEAR_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 100 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m100 current year")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        draw_modelo_100_current_year(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        write_sidecar(target, "100", fixture.ejercicio, fixture.tax_id)

    for fixture in MODELO_100_CORPUS_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 100 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m100 annual corpus layout")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        draw_modelo_100_corpus(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        # A layout replacement, not a formula specimen: its amounts are probes.
        write_sidecar(target, "100", fixture.ejercicio, fixture.tax_id, role="parser_anchor")

    for fixture in MODELO_111_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 111 {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m111 quarterly layout")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        draw_modelo_111(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        write_sidecar(target, "111", fixture.ejercicio, fixture.tax_id, role="parser_anchor")

    for fixture in MODELO_390_ENGLISH_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Modelo 390 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m390 english render")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        draw_modelo_390_english(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        write_sidecar(target, "390", fixture.ejercicio, fixture.tax_id, role="parser_anchor")

    for fixture in MODELO_190_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Modelo 190 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m190 resumen anual")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        draw_modelo_190(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        write_sidecar(target, "190", fixture.ejercicio, fixture.tax_id, role="parser_anchor")

    for fixture in MODELO_390_CORPUS_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Modelo 390 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m390 corpus")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        draw_modelo_390_corpus(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        write_sidecar(target, "390", fixture.ejercicio, fixture.tax_id)


if __name__ == "__main__":
    main()
