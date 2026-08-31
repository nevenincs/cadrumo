"""Synthetic justificante PDF generator for the #44 parser test suite."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from ..provenance import SYNTHETIC_FIXTURE_PRODUCER
from ._generate_base import (
    _FIXTURES,
    _draw,
    _Fixture,
    _write_sidecar,
)
from ._generate_iva_corpus import (
    _MODELO_130_CORPUS_FIXTURES,
    _MODELO_303_CORPUS_FIXTURES,
    _MODELO_390_CORPUS_FIXTURES,
    _draw_modelo_130_corpus,
    _draw_modelo_303_corpus,
    _draw_modelo_390_corpus,
    _Modelo130CorpusFixture,
    _Modelo303CorpusFixture,
    _Modelo390CorpusFixture,
)
from ._generate_misc_a import (
    _MODELO_036_FIXTURES,
    _MODELO_115_FIXTURES,
    _MODELO_180_FIXTURES,
    _MODELO_193_FIXTURES,
    _MODELO_349_FIXTURES,
    _MODELO_369_FIXTURES,
    _MODELO_720_FIXTURES,
    _draw_modelo_036,
    _draw_modelo_115,
    _draw_modelo_180,
    _draw_modelo_193,
    _draw_modelo_349,
    _draw_modelo_369,
    _draw_modelo_720,
    _Modelo036Fixture,
    _Modelo115Fixture,
    _Modelo180Fixture,
    _Modelo193Fixture,
    _Modelo349Fixture,
    _Modelo369Fixture,
    _Modelo720Fixture,
)
from ._generate_misc_b import (
    _MODELO_123_FIXTURES,
    _MODELO_131_FIXTURES,
    _MODELO_184_FIXTURES,
    _MODELO_202_FIXTURES,
    _MODELO_232_FIXTURES,
    _MODELO_347_FIXTURES,
    _MODELO_840_FIXTURES,
    _draw_modelo_123,
    _draw_modelo_131,
    _draw_modelo_184,
    _draw_modelo_202,
    _draw_modelo_232,
    _draw_modelo_347,
    _draw_modelo_840,
    _Modelo123Fixture,
    _Modelo131Fixture,
    _Modelo184Fixture,
    _Modelo202Fixture,
    _Modelo232Fixture,
    _Modelo347Fixture,
    _Modelo840Fixture,
)
from ._generate_modelo_100_corpus import (
    _MODELO_100_CORPUS_FIXTURES,
    _draw_modelo_100_corpus,
    _Modelo100CorpusFixture,
)
from ._generate_modelo_100_current import (
    _MODELO_100_CURRENT_YEAR_FIXTURES,
    _draw_modelo_100_current_year,
    _Modelo100CurrentYearFixture,
)
from ._generate_modelo_111 import (
    _MODELO_111_FIXTURES,
    _draw_modelo_111,
    _Modelo111Fixture,
)
from ._generate_modelo_190 import (
    _MODELO_190_FIXTURES,
    _draw_modelo_190,
    _Modelo190Fixture,
)
from ._generate_modelo_390_english import (
    _MODELO_390_ENGLISH_FIXTURES,
    _draw_modelo_390_english,
    _Modelo390EnglishFixture,
)

__all__ = [
    "_FIXTURES",
    "_Fixture",
    "_Modelo036Fixture",
    "_Modelo100CorpusFixture",
    "_Modelo100CurrentYearFixture",
    "_Modelo111Fixture",
    "_Modelo115Fixture",
    "_Modelo123Fixture",
    "_Modelo130CorpusFixture",
    "_Modelo131Fixture",
    "_Modelo180Fixture",
    "_Modelo184Fixture",
    "_Modelo190Fixture",
    "_Modelo193Fixture",
    "_Modelo202Fixture",
    "_Modelo232Fixture",
    "_Modelo303CorpusFixture",
    "_Modelo347Fixture",
    "_Modelo349Fixture",
    "_Modelo369Fixture",
    "_Modelo390CorpusFixture",
    "_Modelo390EnglishFixture",
    "_Modelo720Fixture",
    "_Modelo840Fixture",
    "main",
]


def main() -> None:
    """Regenerate every fixture PDF in-place."""
    out_dir = Path(__file__).parent
    for fixture in _FIXTURES:
        target = out_dir / fixture.filename
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        # Deterministic metadata so file bytes are reproducible across runs.
        # invariant=True pins /CreationDate and /ModDate to 2000-01-01T00:00:00Z.
        c.setTitle(f"Justificante {fixture.modelo} {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic justificante fixture")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        _draw(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")

    for fixture in _MODELO_130_CORPUS_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Modelo 130 {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m130 corpus")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        _draw_modelo_130_corpus(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        _write_sidecar(target, "130", fixture.ejercicio, fixture.tax_id)

    for fixture in _MODELO_369_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 369 {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m369")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        _draw_modelo_369(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        _write_sidecar(target, "369", fixture.ejercicio, fixture.tax_id)

    for fixture in _MODELO_180_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 180 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m180")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        _draw_modelo_180(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        _write_sidecar(target, "180", fixture.ejercicio, fixture.tax_id)

    for fixture in _MODELO_036_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion censal Modelo 036 {fixture.event_kind}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion-censal fixture m036")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        _draw_modelo_036(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        _write_sidecar(target, "036", fixture.ejercicio, fixture.tax_id)

    for fixture in _MODELO_232_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 232 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m232")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        _draw_modelo_232(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        _write_sidecar(target, "232", fixture.ejercicio, fixture.tax_id)

    for fixture in _MODELO_349_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 349 {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m349")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        _draw_modelo_349(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        _write_sidecar(target, "349", fixture.ejercicio, fixture.tax_id)

    for fixture in _MODELO_123_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 123 {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m123")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        _draw_modelo_123(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        _write_sidecar(target, "123", fixture.ejercicio, fixture.tax_id)

    for fixture in _MODELO_840_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 840 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m840")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        _draw_modelo_840(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        _write_sidecar(target, "840", fixture.ejercicio, fixture.tax_id)

    for fixture in _MODELO_193_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 193 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m193")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        _draw_modelo_193(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        _write_sidecar(target, "193", fixture.ejercicio, fixture.tax_id)

    for fixture in _MODELO_720_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 720 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m720")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        _draw_modelo_720(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        _write_sidecar(target, "720", fixture.ejercicio, fixture.tax_id)

    for fixture in _MODELO_347_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 347 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m347")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        _draw_modelo_347(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        _write_sidecar(target, "347", fixture.ejercicio, fixture.tax_id)

    for fixture in _MODELO_184_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 184 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m184")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        _draw_modelo_184(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        _write_sidecar(target, "184", fixture.ejercicio, fixture.tax_id)

    for fixture in _MODELO_115_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 115 {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m115")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        _draw_modelo_115(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        _write_sidecar(target, "115", fixture.ejercicio, fixture.tax_id)

    for fixture in _MODELO_131_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 131 {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m131")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        _draw_modelo_131(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        _write_sidecar(target, "131", fixture.ejercicio, fixture.tax_id)

    for fixture in _MODELO_202_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 202 {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m202")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        _draw_modelo_202(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        _write_sidecar(target, "202", fixture.ejercicio, fixture.tax_id)

    for fixture in _MODELO_303_CORPUS_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Modelo 303 {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m303 corpus")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        _draw_modelo_303_corpus(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        _write_sidecar(target, "303", fixture.ejercicio, fixture.tax_id)

    for fixture in _MODELO_100_CURRENT_YEAR_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 100 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m100 current year")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        _draw_modelo_100_current_year(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        _write_sidecar(target, "100", fixture.ejercicio, fixture.tax_id)

    for fixture in _MODELO_100_CORPUS_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 100 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m100 annual corpus layout")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        _draw_modelo_100_corpus(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        # A layout replacement, not a formula specimen: its amounts are probes.
        _write_sidecar(target, "100", fixture.ejercicio, fixture.tax_id, role="parser_anchor")

    for fixture in _MODELO_111_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 111 {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m111 quarterly layout")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        _draw_modelo_111(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        _write_sidecar(target, "111", fixture.ejercicio, fixture.tax_id, role="parser_anchor")

    for fixture in _MODELO_390_ENGLISH_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Modelo 390 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m390 english render")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        _draw_modelo_390_english(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        _write_sidecar(target, "390", fixture.ejercicio, fixture.tax_id, role="parser_anchor")

    for fixture in _MODELO_190_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Modelo 190 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m190 resumen anual")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        _draw_modelo_190(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        _write_sidecar(target, "190", fixture.ejercicio, fixture.tax_id, role="parser_anchor")

    for fixture in _MODELO_390_CORPUS_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Modelo 390 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m390 corpus")
        c.setCreator("aeat fixture generator")
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        _draw_modelo_390_corpus(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")
        _write_sidecar(target, "390", fixture.ejercicio, fixture.tax_id)


if __name__ == "__main__":
    main()
