"""Generate deterministic synthetic N26 savings-statement PDF fixtures.

The fixture family is modeled on sanitized text dumps from real N26 savings
statements published in the upstream `portfolio-performance/portfolio` test
corpus. The committed PDFs are synthetic, but the page structure and row
patterns are grounded in that real template family.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from ...provenance import FIXTURE_PROVENANCE_SYNTHETIC, SYNTHETIC_FIXTURE_PRODUCER


@dataclass(frozen=True)
class _Fixture:
    filename: str
    title: str
    pages: tuple[tuple[str, ...], ...]


_COMMON_PAGE_WIDTH = 180 * mm
_LEFT = 18 * mm
_TOP = 24 * mm
_LINE = 5.8 * mm


_FIXTURES: tuple[_Fixture, ...] = (
    _Fixture(
        filename="n26-savings-2024-06.pdf",
        title="N26 savings statement 2024-06",
        pages=(
            (
                "Kontoauszug",
                "Nr. 06/2024",
                "01.06.2024 bis 30.06.2024",
                "",
                "Beschreibung Verbuchungsdatum Betrag",
                "Zinsertrag 01.06.2024 +252,16EUR",
                "Wertstellung 01.06.2024",
                "Abgeltungssteuer 01.06.2024 -63,04EUR",
                "Wertstellung 01.06.2024",
                "Solidaritaetszuschlag 01.06.2024 -3,46EUR",
                "Wertstellung 01.06.2024",
                "Max Mustermann 19.06.2024 +5.000,00EUR",
                "Gutschriften",
                "IBAN: DE99500502010123456789 | BIC: HELADEF1822",
                "Tagesgeld N26",
                "Wertstellung 19.06.2024",
                "",
                "Max Mustermann Kontotyp: Sparkonto Erstellt am",
                "Musterstrasse 123, 01234 Musterstadt IBAN: DE99100110010123456789 01.07.2024",
                "BIC: NTSBDEB1XXX",
                "N26 Bank AG | Voltairestrasse 8, 10179 Berlin, Deutschland | 1/5",
            ),
            (
                "Zusammenfassung",
                "Nr. 06/2024",
                "01.06.2024 bis 30.06.2024",
                "",
                "Beschreibung Betrag",
                "Dein alter Kontostand +79.062,36EUR",
                "Ausgehende Transaktionen -66,50EUR",
                "Einkommende Transaktionen +5.252,16EUR",
                "Gebuehren 0,00EUR",
                "Steuern -66,50EUR",
                "Zinsen +252,16EUR",
                "Dein neuer Kontostand +84.248,02EUR",
                "",
                "Max Mustermann Kontotyp: Sparkonto Erstellt am",
                "Musterstrasse 123, 01234 Musterstadt IBAN: DE99100110010123456789 01.07.2024",
                "BIC: NTSBDEB1XXX",
                "N26 Bank AG | Voltairestrasse 8, 10179 Berlin, Deutschland | 2/5",
            ),
            (
                "Uebersicht zu Gebuehren und Zinsen",
                "Nr. 06/2024",
                "01.06.2024 bis 30.06.2024",
                "",
                "Gebuehren 0,00EUR",
                "Steuer",
                "Abgeltungssteuer -63,04EUR",
                "Solidaritaetszuschlag -3,46EUR",
                "Gesamt -66,50EUR",
                "Zinsertrag +252,16EUR",
                "Gesamt +252,16EUR",
                "",
                "Max Mustermann Kontotyp: Sparkonto Erstellt am",
                "Musterstrasse 123, 01234 Musterstadt IBAN: DE99100110010123456789 01.07.2024",
                "BIC: NTSBDEB1XXX",
                "N26 Bank AG | Voltairestrasse 8, 10179 Berlin, Deutschland | 3/5",
            ),
            (
                "Kontoauszug",
                "01.06.2024 bis 30.06.2024",
                "Anmerkung",
                "",
                "Dies ist eine synthetische, sanitizierte Testversion eines N26 Kontoauszugs.",
                "Transaktionen werden nur nach endgueltiger Verbuchung angezeigt.",
                "Abweichungen zur App koennen durch Echtzeitdarstellung entstehen.",
                "",
                "Max Mustermann Kontotyp: Sparkonto Erstellt am",
                "Musterstrasse 123, 01234 Musterstadt IBAN: DE99100110010123456789 01.07.2024",
                "BIC: NTSBDEB1XXX",
                "N26 Bank AG | Voltairestrasse 8, 10179 Berlin, Deutschland | 4/5",
            ),
            (
                "Kontoauszug",
                "01.06.2024 bis 30.06.2024",
                "Vierteljaehrlicher Rechnungsabschluss inklusive Saldenmitteilung",
                "",
                "Bitte pruefe den ausgewiesenen Saldo und melde Einwendungen zeitnah.",
                "Diese Testseite ersetzt den rechtlichen Volltext der echten Bankvorlage.",
                "",
                "Max Mustermann Kontotyp: Sparkonto Erstellt am",
                "Musterstrasse 123, 01234 Musterstadt IBAN: DE99100110010123456789 01.07.2024",
                "BIC: NTSBDEB1XXX",
                "N26 Bank AG | Voltairestrasse 8, 10179 Berlin, Deutschland | 5/5",
            ),
        ),
    ),
    _Fixture(
        filename="n26-savings-2025-01.pdf",
        title="N26 savings statement 2025-01",
        pages=(
            (
                "Kontoauszug",
                "Nr. 01/2025",
                "01.01.2025 bis 31.01.2025",
                "",
                "Beschreibung Verbuchungsdatum Betrag",
                "Zinsertrag 01.01.2025 +8,55EUR",
                "Wertstellung 01.01.2025",
                "An Hauptkonto 11.01.2025 -3.000,00EUR",
                "Wertstellung 11.01.2025",
                "Von Hauptkonto 13.01.2025 +4.500,00EUR",
                "Wertstellung 13.01.2025",
                "Von Hauptkonto 20.01.2025 +3.500,00EUR",
                "Wertstellung 20.01.2025",
                "",
                "SQXMSn bDGjn Kontotyp: Sparkonto Erstellt am",
                "JJAdFxQBEAB 15, 5858 uUuCKAHVW IBAN: DE11111111111111111111 06.02.2025",
                "BIC: NTSBDEB1XXX",
                "N26 Bank AG | Voltairestrasse 8, 10179 Berlin, Deutschland | 1/4",
            ),
            (
                "Zusammenfassung",
                "Nr. 01/2025",
                "01.01.2025 bis 31.01.2025",
                "",
                "Beschreibung Betrag",
                "Dein alter Kontostand +8.000,00EUR",
                "Ausgehende Transaktionen -3.000,00EUR",
                "Einkommende Transaktionen +8.008,55EUR",
                "Gebuehren 0,00EUR",
                "Steuern 0,00EUR",
                "Zinsen +8,55EUR",
                "Dein neuer Kontostand +13.008,55EUR",
                "",
                "mocOPb hxSiY Kontotyp: Sparkonto Erstellt am",
                "RfqxEbroqHw 15, 3634 jYIZJxWAD IBAN: DE11111111111111111111 06.02.2025",
                "BIC: NTSBDEB1XXX",
                "N26 Bank AG | Voltairestrasse 8, 10179 Berlin, Deutschland | 2/4",
            ),
            (
                "Uebersicht zu Gebuehren und Zinsen",
                "Nr. 01/2025",
                "01.01.2025 bis 31.01.2025",
                "",
                "Gebuehren 0,00EUR",
                "Steuer 0,00EUR",
                "Zinsertrag +8,55EUR",
                "Gesamt +8,55EUR",
                "",
                "cywnGC sMnMy Kontotyp: Sparkonto Erstellt am",
                "cTFmzTaWpth 15, 5735 uRxokRbVp IBAN: DE11111111111111111111 06.02.2025",
                "BIC: NTSBDEB1XXX",
                "N26 Bank AG | Voltairestrasse 8, 10179 Berlin, Deutschland | 3/4",
            ),
            (
                "Kontoauszug",
                "01.01.2025 bis 31.01.2025",
                "Anmerkung",
                "",
                "Dies ist eine synthetische, sanitizierte Testversion eines N26 Kontoauszugs.",
                "Transaktionen werden nur nach endgueltiger Verbuchung angezeigt.",
                "",
                "cCHUhZ AEphn Kontotyp: Sparkonto Erstellt am",
                "TRJRUnOPuLq 15, 2603 kUeuNTSsi IBAN: DE11111111111111111111 06.02.2025",
                "BIC: NTSBDEB1XXX",
                "N26 Bank AG | Voltairestrasse 8, 10179 Berlin, Deutschland | 4/4",
            ),
        ),
    ),
    _Fixture(
        filename="n26-savings-2025-05.pdf",
        title="N26 savings statement 2025-05",
        pages=(
            (
                "Kontoauszug Nr. 5/2025",
                "01.05.2025 bis 31.05.2025",
                "",
                "Beschreibung Verbuchungsdatum Betrag",
                "Zinsertrag 01.05.2025 +6,60EUR",
                "Wertstellung 01.05.2025",
                "An Hauptkonto 04.05.2025 -500,00EUR",
                "Wertstellung 04.05.2025",
                "HpgbxT VoPcx 12.05.2025 +5.000,00EUR",
                "Gutschriften",
                "IBAN: AT111111111111111111 | BIC: BBBBAAAA",
                "Uebertrag N26",
                "Wertstellung 12.05.2025",
                "An Hauptkonto 26.05.2025 -5.000,00EUR",
                "Wertstellung 26.05.2025",
                "izFlhI yLNYL 27.05.2025 +5.000,00EUR",
                "Gutschriften",
                "IBAN: AT111111111111111111 | BIC: BBBBAAAA",
                "Uebertrag N26",
                "Wertstellung 27.05.2025",
                "An Hauptkonto 27.05.2025 -200,00EUR",
                "Wertstellung 27.05.2025",
                "",
                "WIvdQj KtUyI Kontotyp: Sparkonto Erstellt am",
                "CTMfRQAIWkd 15, 4547 jSAwIljoS IBAN: DE11111111111111111111 06.06.2025",
                "BIC: NTSBDEB1XXX 5/2025",
                "N26 Bank SE | Voltairestrasse 8, 10179 Berlin, Deutschland | 1/4",
            ),
            (
                "Uebersicht Nr. 5/2025",
                "01.05.2025 bis 31.05.2025",
                "",
                "Beschreibung Betrag",
                "Dein alter Kontostand +8.040,37EUR",
                "Ausgehende Transaktionen -5.700,00EUR",
                "Steuern 0,00EUR",
                "Gebuehren 0,00EUR",
                "Einkommende Transaktionen +10.006,60EUR",
                "Zinsertrag +6,60EUR",
                "Dein neuer Kontostand +12.346,97EUR",
                "",
                "sfERnV NWEBa Kontotyp: Sparkonto Erstellt am",
                "UQmZFOmYZRd 15, 3857 CgYZXFqTH IBAN: DE11111111111111111111 06.06.2025",
                "BIC: NTSBDEB1XXX 5/2025",
                "N26 Bank SE | Voltairestrasse 8, 10179 Berlin, Deutschland | 2/4",
            ),
            (
                "Uebersicht zu Gebuehren und Zinsen",
                "Nr. 5/2025",
                "01.05.2025 bis 31.05.2025",
                "",
                "Gebuehren 0,00EUR",
                "Steuern 0,00EUR",
                "Zinsen",
                "Zinsertrag +6,60EUR",
                "Gesamt +6,60EUR",
                "",
                "MrylvH Fuqud Kontotyp: Sparkonto Erstellt am",
                "vPaVTQhgElQ 15, 8498 wIJIlwpQD IBAN: DE11111111111111111111 06.06.2025",
                "BIC: NTSBDEB1XXX 5/2025",
                "N26 Bank SE | Voltairestrasse 8, 10179 Berlin, Deutschland | 3/4",
            ),
            (
                "Kontoauszug Nr. 5/2025",
                "01.05.2025 bis 31.05.2025",
                "Anmerkung",
                "",
                "Dies ist eine synthetische, sanitizierte Testversion eines N26 Kontoauszugs.",
                "Transaktionen werden nur nach endgueltiger Verbuchung angezeigt.",
                "",
                "EiWUEe YsCXq Kontotyp: Sparkonto Erstellt am",
                "WIRTqbEREeV 15, 7557 cftGphEll IBAN: DE11111111111111111111 06.06.2025",
                "BIC: NTSBDEB1XXX 5/2025",
                "N26 Bank SE | Voltairestrasse 8, 10179 Berlin, Deutschland | 4/4",
            ),
        ),
    ),
)


def _draw_page(c: canvas.Canvas, lines: tuple[str, ...]) -> None:
    """Render one page with deterministic text-only layout."""
    _, height = A4
    y = height - _TOP
    c.setFont("Helvetica", 10)
    for line in lines:
        c.drawString(_LEFT, y, line)
        y -= _LINE


def write_provenance_sidecar(pdf_path: Path) -> Path:
    """Write the provenance sidecar the fixture gates read for ``pdf_path``.

    Everything this generator emits is generator-produced, so the declaration
    is unconditional. It is written by the generator rather than by hand so it
    cannot drift from the bytes it describes.

    Returns:
        The sidecar path written, ``<stem>.json`` beside the PDF.
    """
    pdf_bytes = pdf_path.read_bytes()
    sidecar = pdf_path.with_suffix(".json")
    sidecar.write_text(
        json.dumps(
            {
                "provenance": FIXTURE_PROVENANCE_SYNTHETIC,
                "role": "parser_anchor",
                "output_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
                "output_size_bytes": len(pdf_bytes),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return sidecar


def main() -> None:
    """Regenerate every committed synthetic PDF fixture."""
    out_dir = Path(__file__).parent
    for fixture in _FIXTURES:
        target = out_dir / fixture.filename
        c = canvas.Canvas(str(target), pagesize=A4, pageCompression=0)
        c.setTitle(fixture.title)
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic N26 savings statement fixture")
        c.setCreator("aeat fixture generator")
        # Previously "reportlab", which carries no synthetic signal: the
        # provenance discriminator reads an unsignatured producer as evidence
        # of real origin, so these generated statements presented as real bank
        # documents to any gate that asked.
        c.setProducer(SYNTHETIC_FIXTURE_PRODUCER)
        for page_lines in fixture.pages:
            _draw_page(c, page_lines)
            c.showPage()
        c.save()
        sidecar = write_provenance_sidecar(target)
        print(f"wrote {target} + {sidecar.name}")


if __name__ == "__main__":
    main()
