"""Synthetic justificante fixtures for IVA and pagos-fraccionados corpus models."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from ....core.money import round_to_cents
from ._generate_base import _SEDE_ORIGIN


def _fmt_spanish(d: Decimal) -> str:
    """Format a Decimal as Spanish-locale monetary string (e.g. Decimal(‘5000.00’) -> ‘5.000,00’)."""
    s: str = f"{d:,.2f}"
    # Python locale-independent: ‘5,000.00’ â†’ ‘5.000,00’
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


@dataclass(frozen=True)
class _Modelo303CorpusFixture:
    """Synthetic M303 corpus fixture with formula-consistent casilla values.

    Formula DAG (standard single-regime, territorio comÃºn, no prior-period comp):
      46 = 27 - 45   [modelo-303-iva-resultado-regimen-general, Orden EHA/3786/2008 art. 1]
      64 = 46 + 0 + 0   [modelo-303-iva-suma-resultados, c58=0, c76=0, Orden HAC/819/2024 art. 1]
      66 = 64 Ã— 100 / 100 = 64   [modelo-303-iva-atribuible-estado, c65=100, Orden HAC/819/2024 art. 1]
      69 = 66 + 0 + 0 - 0 = 66   [modelo-303-iva-resultado, c77=0, c68=0, c78=0, Orden HAC/819/2024 art. 1]
      71 = 69 - 0 + 0 = 69   [modelo-303-iva-resultado-final, c70=0, c109=0, Orden HAC/819/2024 art. 1]

    Leaf inputs:
      c27 = Total cuota devengada (manual, form box 27)
      c29 = IVA deducible ops interiores corrientes (manual, form box 29)
      c45 = Total a deducir (manual, form box 45)
      c65 = 100 (% atribuible Estado, manual, territorio comÃºn = 100%)

    With no prior-period compensation and no other regimes:
      resultado-regimen-general = c27 - c45        [box 46]
      suma-resultados           = c46              [box 64 = 46 + 0 + 0]
      atribuible-estado         = c46              [box 66 = 64 Ã— 100/100]
      compensacion-aplicada     = 0                [min(0, max(0, 46)) = 0 when 46 > 0]
      resultado                 = c46              [box 69 = 66 + 0 + 0 - 0]
      resultado-final           = c46              [box 71 = 69 - 0 + 0]
      compensacion-generada     = 0                [max(0, -resultado) = 0 when resultado > 0]
      compensacion-disponible   = 0                [pendiente-posteriores + generada = 0]

    ``new_template`` distinguishes the post-2022 Modelo 303 profiles (True) from
    the 2022 profile (False, legacy fixtures 2021â€“2022).
    The new closure chain (boxes 64/66/71) applies only for new_template=True.

    Registry source:
      src/cadrumo/_data/registry/aeat/modelos/303/revisions/2023/revision.toml
      src/cadrumo/_data/registry/aeat/modelos/303/revisions/2022/revision.toml
    """

    filename: str
    ejercicio: str
    periodo: str
    tax_id: str
    new_template: bool  # True = 2023+ profile; False = 2009 (legacy) profile
    c27: Decimal  # Total cuota devengada (leaf input, box 27)
    c29: Decimal  # IVA deducible ops interiores cuota (leaf input, box 29)
    c45: Decimal  # Total a deducir (leaf input, box 45)
    # Derived via _compute_m303_closure:
    c46: Decimal  # Resultado regimen general = c27 - c45        [box 46]
    c64: Decimal  # Suma de resultados = c46 (no otros regÃ­menes) [box 64, 2023+ only]
    c66: Decimal  # Atribuible Estado = c64 (c65=100%)            [box 66, 2023+ only]
    c69: Decimal  # Resultado autoliquidacion = c66 - 0           [box 69 / iva.resultado]
    c71: Decimal  # Resultado final = c69 (no ajustes)            [box 71, 2023+ only]
    # Justificante receipt fields â€” required by the sidecar roundtrip test.
    # csv must match SANITIZED{modelo}{ejercicio} to satisfy _CSV_SYNTHETIC_RE.
    csv: str = ""
    presented_at: str = "2024-01-01 10:00:00"


def _compute_m303_closure(c27: Decimal, c45: Decimal) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
    """Compute M303 closure casillas from leaf inputs c27 (devengada) and c45 (deducible).

    Formula chain (no prior-period compensation, no other regimes, territorio comÃºn c65=100):
      c46 = c27 - c45                     [modelo-303-iva-resultado-regimen-general]
      c64 = c46 + 0 + 0                   [modelo-303-iva-suma-resultados; c58=0, c76=0]
      c66 = c64 Ã— 100 / 100 = c64         [modelo-303-iva-atribuible-estado; c65=100]
      c69 = c66 + 0 + 0 - 0 = c66        [modelo-303-iva-resultado; c77=0, c68=0, c78=0]
      c71 = c69 - 0 + 0 = c69            [modelo-303-iva-resultado-final; c70=0, c109=0]

    Returns (c46, c64, c66, c69, c71) all rounded to money-2 (2 decimal places).

    Arithmetic grounded in Orden EHA/3786/2008 art. 1 (box 46) and Orden HAC/819/2024
    art. 1 (boxes 64/66/69/71). Registry formula expressions in the explicit post-2022 revisions.
    """
    c46: Decimal = round_to_cents(c27 - c45)
    # Standard single-regime: c58=0, c76=0 â†’ c64 = c46
    c64: Decimal = round_to_cents(c46)
    # territorio comÃºn: c65=100 â†’ c66 = c64 Ã— 100 / 100 = c64
    c66: Decimal = round_to_cents(c64)
    # No importation IVA (c77=0), no joint-taxation (c68=0), no prior compensation (c78=0):
    #   c69 = c66 - 0 = c66
    c69: Decimal = round_to_cents(c66)
    # No prior filings (c70=0), no returns (c109=0): c71 = c69
    c71: Decimal = round_to_cents(c69)
    return c46, c64, c66, c69, c71


_MODELO_303_CORPUS_FIXTURES: tuple[_Modelo303CorpusFixture, ...] = (
    # --- 2022 (legacy) revision: 2021-2T through 2022-4T ---
    _Modelo303CorpusFixture(
        filename="303/2021-2T.pdf",
        ejercicio="2021",
        periodo="2T",
        tax_id="Y0000001S",
        new_template=False,
        c27=Decimal("12000.00"),
        c29=Decimal("7800.00"),
        c45=Decimal("7800.00"),
        c46=_compute_m303_closure(Decimal("12000.00"), Decimal("7800.00"))[0],
        c64=_compute_m303_closure(Decimal("12000.00"), Decimal("7800.00"))[1],
        c66=_compute_m303_closure(Decimal("12000.00"), Decimal("7800.00"))[2],
        c69=_compute_m303_closure(Decimal("12000.00"), Decimal("7800.00"))[3],
        c71=_compute_m303_closure(Decimal("12000.00"), Decimal("7800.00"))[4],
    ),
    _Modelo303CorpusFixture(
        filename="303/2021-3T.pdf",
        ejercicio="2021",
        periodo="3T",
        tax_id="Y0000001S",
        new_template=False,
        c27=Decimal("13200.00"),
        c29=Decimal("8400.00"),
        c45=Decimal("8400.00"),
        c46=_compute_m303_closure(Decimal("13200.00"), Decimal("8400.00"))[0],
        c64=_compute_m303_closure(Decimal("13200.00"), Decimal("8400.00"))[1],
        c66=_compute_m303_closure(Decimal("13200.00"), Decimal("8400.00"))[2],
        c69=_compute_m303_closure(Decimal("13200.00"), Decimal("8400.00"))[3],
        c71=_compute_m303_closure(Decimal("13200.00"), Decimal("8400.00"))[4],
    ),
    _Modelo303CorpusFixture(
        filename="303/2021-4T.pdf",
        ejercicio="2021",
        periodo="4T",
        tax_id="Y0000001S",
        new_template=False,
        c27=Decimal("14400.00"),
        c29=Decimal("9000.00"),
        c45=Decimal("9000.00"),
        c46=_compute_m303_closure(Decimal("14400.00"), Decimal("9000.00"))[0],
        c64=_compute_m303_closure(Decimal("14400.00"), Decimal("9000.00"))[1],
        c66=_compute_m303_closure(Decimal("14400.00"), Decimal("9000.00"))[2],
        c69=_compute_m303_closure(Decimal("14400.00"), Decimal("9000.00"))[3],
        c71=_compute_m303_closure(Decimal("14400.00"), Decimal("9000.00"))[4],
    ),
    _Modelo303CorpusFixture(
        filename="303/2022-1T.pdf",
        ejercicio="2022",
        periodo="1T",
        tax_id="Y0000001S",
        new_template=False,
        c27=Decimal("12600.00"),
        c29=Decimal("8100.00"),
        c45=Decimal("8100.00"),
        c46=_compute_m303_closure(Decimal("12600.00"), Decimal("8100.00"))[0],
        c64=_compute_m303_closure(Decimal("12600.00"), Decimal("8100.00"))[1],
        c66=_compute_m303_closure(Decimal("12600.00"), Decimal("8100.00"))[2],
        c69=_compute_m303_closure(Decimal("12600.00"), Decimal("8100.00"))[3],
        c71=_compute_m303_closure(Decimal("12600.00"), Decimal("8100.00"))[4],
    ),
    _Modelo303CorpusFixture(
        filename="303/2022-2T.pdf",
        ejercicio="2022",
        periodo="2T",
        tax_id="Y0000001S",
        new_template=False,
        c27=Decimal("15000.00"),
        c29=Decimal("9600.00"),
        c45=Decimal("9600.00"),
        c46=_compute_m303_closure(Decimal("15000.00"), Decimal("9600.00"))[0],
        c64=_compute_m303_closure(Decimal("15000.00"), Decimal("9600.00"))[1],
        c66=_compute_m303_closure(Decimal("15000.00"), Decimal("9600.00"))[2],
        c69=_compute_m303_closure(Decimal("15000.00"), Decimal("9600.00"))[3],
        c71=_compute_m303_closure(Decimal("15000.00"), Decimal("9600.00"))[4],
    ),
    _Modelo303CorpusFixture(
        filename="303/2022-3T.pdf",
        ejercicio="2022",
        periodo="3T",
        tax_id="Y0000001S",
        new_template=False,
        c27=Decimal("16200.00"),
        c29=Decimal("10200.00"),
        c45=Decimal("10200.00"),
        c46=_compute_m303_closure(Decimal("16200.00"), Decimal("10200.00"))[0],
        c64=_compute_m303_closure(Decimal("16200.00"), Decimal("10200.00"))[1],
        c66=_compute_m303_closure(Decimal("16200.00"), Decimal("10200.00"))[2],
        c69=_compute_m303_closure(Decimal("16200.00"), Decimal("10200.00"))[3],
        c71=_compute_m303_closure(Decimal("16200.00"), Decimal("10200.00"))[4],
    ),
    _Modelo303CorpusFixture(
        filename="303/2022-4T.pdf",
        ejercicio="2022",
        periodo="4T",
        tax_id="Y0000001S",
        new_template=False,
        c27=Decimal("18000.00"),
        c29=Decimal("11400.00"),
        c45=Decimal("11400.00"),
        c46=_compute_m303_closure(Decimal("18000.00"), Decimal("11400.00"))[0],
        c64=_compute_m303_closure(Decimal("18000.00"), Decimal("11400.00"))[1],
        c66=_compute_m303_closure(Decimal("18000.00"), Decimal("11400.00"))[2],
        c69=_compute_m303_closure(Decimal("18000.00"), Decimal("11400.00"))[3],
        c71=_compute_m303_closure(Decimal("18000.00"), Decimal("11400.00"))[4],
    ),
    # --- Explicit post-2022 revision family: 2023-1T onward ---
    _Modelo303CorpusFixture(
        filename="303/2023-1T.pdf",
        ejercicio="2023",
        periodo="1T",
        tax_id="Y0000001S",
        new_template=True,
        c27=Decimal("12600.00"),
        c29=Decimal("8100.00"),
        c45=Decimal("8100.00"),
        c46=_compute_m303_closure(Decimal("12600.00"), Decimal("8100.00"))[0],
        c64=_compute_m303_closure(Decimal("12600.00"), Decimal("8100.00"))[1],
        c66=_compute_m303_closure(Decimal("12600.00"), Decimal("8100.00"))[2],
        c69=_compute_m303_closure(Decimal("12600.00"), Decimal("8100.00"))[3],
        c71=_compute_m303_closure(Decimal("12600.00"), Decimal("8100.00"))[4],
    ),
    _Modelo303CorpusFixture(
        filename="303/2023-2T.pdf",
        ejercicio="2023",
        periodo="2T",
        tax_id="Y0000001S",
        new_template=True,
        c27=Decimal("13800.00"),
        c29=Decimal("8700.00"),
        c45=Decimal("8700.00"),
        c46=_compute_m303_closure(Decimal("13800.00"), Decimal("8700.00"))[0],
        c64=_compute_m303_closure(Decimal("13800.00"), Decimal("8700.00"))[1],
        c66=_compute_m303_closure(Decimal("13800.00"), Decimal("8700.00"))[2],
        c69=_compute_m303_closure(Decimal("13800.00"), Decimal("8700.00"))[3],
        c71=_compute_m303_closure(Decimal("13800.00"), Decimal("8700.00"))[4],
    ),
    _Modelo303CorpusFixture(
        filename="303/2023-3T.pdf",
        ejercicio="2023",
        periodo="3T",
        tax_id="Y0000001S",
        new_template=True,
        c27=Decimal("15000.00"),
        c29=Decimal("9300.00"),
        c45=Decimal("9300.00"),
        c46=_compute_m303_closure(Decimal("15000.00"), Decimal("9300.00"))[0],
        c64=_compute_m303_closure(Decimal("15000.00"), Decimal("9300.00"))[1],
        c66=_compute_m303_closure(Decimal("15000.00"), Decimal("9300.00"))[2],
        c69=_compute_m303_closure(Decimal("15000.00"), Decimal("9300.00"))[3],
        c71=_compute_m303_closure(Decimal("15000.00"), Decimal("9300.00"))[4],
    ),
    _Modelo303CorpusFixture(
        filename="303/2023-4T.pdf",
        ejercicio="2023",
        periodo="4T",
        tax_id="Y0000001S",
        new_template=True,
        c27=Decimal("16800.00"),
        c29=Decimal("10500.00"),
        c45=Decimal("10500.00"),
        c46=_compute_m303_closure(Decimal("16800.00"), Decimal("10500.00"))[0],
        c64=_compute_m303_closure(Decimal("16800.00"), Decimal("10500.00"))[1],
        c66=_compute_m303_closure(Decimal("16800.00"), Decimal("10500.00"))[2],
        c69=_compute_m303_closure(Decimal("16800.00"), Decimal("10500.00"))[3],
        c71=_compute_m303_closure(Decimal("16800.00"), Decimal("10500.00"))[4],
    ),
    _Modelo303CorpusFixture(
        filename="303/2024-1T.pdf",
        ejercicio="2024",
        periodo="1T",
        tax_id="Y0000001S",
        new_template=True,
        c27=Decimal("13200.00"),
        c29=Decimal("8400.00"),
        c45=Decimal("8400.00"),
        c46=_compute_m303_closure(Decimal("13200.00"), Decimal("8400.00"))[0],
        c64=_compute_m303_closure(Decimal("13200.00"), Decimal("8400.00"))[1],
        c66=_compute_m303_closure(Decimal("13200.00"), Decimal("8400.00"))[2],
        c69=_compute_m303_closure(Decimal("13200.00"), Decimal("8400.00"))[3],
        c71=_compute_m303_closure(Decimal("13200.00"), Decimal("8400.00"))[4],
    ),
    _Modelo303CorpusFixture(
        filename="303/2024-2T.pdf",
        ejercicio="2024",
        periodo="2T",
        tax_id="Y0000001S",
        new_template=True,
        c27=Decimal("14400.00"),
        c29=Decimal("9000.00"),
        c45=Decimal("9000.00"),
        c46=_compute_m303_closure(Decimal("14400.00"), Decimal("9000.00"))[0],
        c64=_compute_m303_closure(Decimal("14400.00"), Decimal("9000.00"))[1],
        c66=_compute_m303_closure(Decimal("14400.00"), Decimal("9000.00"))[2],
        c69=_compute_m303_closure(Decimal("14400.00"), Decimal("9000.00"))[3],
        c71=_compute_m303_closure(Decimal("14400.00"), Decimal("9000.00"))[4],
    ),
    _Modelo303CorpusFixture(
        filename="303/2024-3T.pdf",
        ejercicio="2024",
        periodo="3T",
        tax_id="Y0000001S",
        new_template=True,
        c27=Decimal("16200.00"),
        c29=Decimal("10200.00"),
        c45=Decimal("10200.00"),
        c46=_compute_m303_closure(Decimal("16200.00"), Decimal("10200.00"))[0],
        c64=_compute_m303_closure(Decimal("16200.00"), Decimal("10200.00"))[1],
        c66=_compute_m303_closure(Decimal("16200.00"), Decimal("10200.00"))[2],
        c69=_compute_m303_closure(Decimal("16200.00"), Decimal("10200.00"))[3],
        c71=_compute_m303_closure(Decimal("16200.00"), Decimal("10200.00"))[4],
    ),
    _Modelo303CorpusFixture(
        filename="303/2024-4T.pdf",
        ejercicio="2024",
        periodo="4T",
        tax_id="Y0000001S",
        new_template=True,
        c27=Decimal("18000.00"),
        c29=Decimal("11400.00"),
        c45=Decimal("11400.00"),
        c46=_compute_m303_closure(Decimal("18000.00"), Decimal("11400.00"))[0],
        c64=_compute_m303_closure(Decimal("18000.00"), Decimal("11400.00"))[1],
        c66=_compute_m303_closure(Decimal("18000.00"), Decimal("11400.00"))[2],
        c69=_compute_m303_closure(Decimal("18000.00"), Decimal("11400.00"))[3],
        c71=_compute_m303_closure(Decimal("18000.00"), Decimal("11400.00"))[4],
    ),
)


def _draw_modelo_303_corpus(c: canvas.Canvas, fixture: _Modelo303CorpusFixture) -> None:
    """Render a synthetic M303 corpus fixture page onto ``c``.

    Layout uses named_label format compatible with the M303 declaracion_pdf
    extraction profile.  Each casilla row prints:
      "<label text> <spanish_formatted_amount>"
    where the label text is verbatim from the named_label_pattern in the
    extraction profile, so the named_label parser captures the trailing amount.

    Two profile variants:
    - new_template=True (post-2022 Modelo 303): 12-casilla profile including
      boxes 27, 29, 37, 45, iva.resultado-regimen-general, 64, 66,
      iva.compensacion-pendiente-periodos-anteriores,
      iva.compensacion-aplicada-periodo,
      iva.compensacion-pendiente-periodos-posteriores,
      iva.resultado, and 71.
    - new_template=False (2022 legacy): 4-casilla profile â€”
      boxes 27, 29, 45, and iva.resultado-regimen-general only.

    Formula consistency (both revisions):
      c46 = c27 - c45   [modelo-303-iva-resultado-regimen-general, Orden EHA/3786/2008 art. 1]
      c69 = c46          [no prior-period compensation]

    Label text grounded in the extraction profile patterns:
    - '27': 'Total\\s+cuota\\s+devengada'
    - '29': 'Por\\s+cuotas\\s+soportadas\\s+en\\s+operaciones\\s+interiores\\s+corrientes'
    - '37': 'En\\s+adquisiciones\\s+intracomunitarias\\s+de\\s+bienes\\s+y\\s+servicios\\s+corrientes'
    - '45': 'Total\\s+a\\s+deducir'
    - 'iva.resultado-regimen-general': 'Resultado\\s+r[eÃ©]gimen\\s+general\\s+\\(27\\s*-\\s*45\\)'
    - '64': 'Suma\\s+de\\s+resultados'
    - '66': 'Atribuible\\s+a\\s+la\\s+Administraci[oÃ³]n\\s+del\\s+Estado'
    - 'iva.compensacion-pendiente-periodos-anteriores':
        'Cuotas\\s+a\\s+compensar\\s+pendientes\\s+de\\s+periodos\\s+anteriores'
    - 'iva.compensacion-aplicada-periodo':
        'Cuotas\\s+a\\s+compensar\\s+de\\s+periodos\\s+anteriores\\s+aplicadas\\s+en\\s+este\\s+periodo'
    - 'iva.compensacion-pendiente-periodos-posteriores':
        'Cuotas\\s+a\\s+compensar\\s+de\\s+periodos\\s+previos\\s+pendientes\\s+para\\s+periodos\\s+posteriores\\s+\\(110\\s*-\\s*78\\)'
    - 'iva.resultado': 'Resultado\\s+de\\s+la\\s+autoliquidaci[oÃ³]n\\s+\\(66[^\\)]*\\)'
    - '71': 'Resultado\\s+\\(69\\s*-\\s*70\\s*\\+\\s*109\\)'

    Non-tautology: _compute_m303_closure replicates the arithmetic of the real
    engine. If the registry formula changes and the fixtures are not regenerated,
    test_verification_chain_m303 will fail. Engine and fixture are computed
    independently (engine: runtime TOML evaluation; fixture: formula replicated
    at generation time).
    """
    _, height = A4
    y: float = height - 25 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        20 * mm,
        y,
        "Impuesto sobre el Valor Anadido  Modelo 303",
    )
    y -= 10 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"Ejercicio: {fixture.ejercicio}   Periodo: {fixture.periodo}")
    y -= 8 * mm
    c.drawString(20 * mm, y, f"NIF: {fixture.tax_id}")
    y -= 10 * mm

    # Named-label rows: label text verbatim from the extraction profile pattern.
    # Accents stripped to stay within ASCII-safe pdfplumber extraction path.
    # Value follows on the same line after a space; named_label parser captures it.
    zero_fmt: str = _fmt_spanish(Decimal("0.00"))

    # box 27 â€” Total cuota devengada (leaf input, profile pattern: 'Total\s+cuota\s+devengada')
    c.drawString(20 * mm, y, f"Total cuota devengada {_fmt_spanish(fixture.c27)}")
    y -= 6 * mm

    # box 29 â€” cuotas soportadas interiores corrientes
    c.drawString(
        20 * mm,
        y,
        f"Por cuotas soportadas en operaciones interiores corrientes {_fmt_spanish(fixture.c29)}",
    )
    y -= 6 * mm

    if fixture.new_template:
        # box 37 â€” intracomunitaria (zero â€” simple case, no intracommunity)
        c.drawString(
            20 * mm,
            y,
            f"En adquisiciones intracomunitarias de bienes y servicios corrientes {zero_fmt}",
        )
        y -= 6 * mm

    # box 45 â€” Total a deducir (leaf input, profile pattern: 'Total\s+a\s+deducir')
    c.drawString(20 * mm, y, f"Total a deducir {_fmt_spanish(fixture.c45)}")
    y -= 6 * mm

    # iva.resultado-regimen-general (box 46) â€” computed: c27 - c45
    # Profile pattern: 'Resultado\s+r[eÃ©]gimen\s+general\s+\(27\s*-\s*45\)'
    c.drawString(
        20 * mm,
        y,
        f"Resultado regimen general (27 - 45) {_fmt_spanish(fixture.c46)}",
    )
    y -= 6 * mm

    if fixture.new_template:
        # box 64 â€” Suma de resultados (computed: c46 + c58 + c76; c58=c76=0 â†’ c46)
        # Profile pattern: 'Suma\s+de\s+resultados'
        c.drawString(20 * mm, y, f"Suma de resultados {_fmt_spanish(fixture.c64)}")
        y -= 6 * mm

        # box 66 â€” Atribuible a la Administracion del Estado (computed: c64 Ã— c65/100; c65=100 â†’ c64)
        # Profile pattern: 'Atribuible\s+a\s+la\s+Administraci[oÃ³]n\s+del\s+Estado'
        c.drawString(20 * mm, y, f"Atribuible a la Administracion del Estado {_fmt_spanish(fixture.c66)}")
        y -= 6 * mm

        # iva.compensacion-pendiente-periodos-anteriores (box 110) â€” zero (no carry-forward)
        # Profile: 'Cuotas\s+a\s+compensar\s+pendientes\s+de\s+periodos\s+anteriores'
        c.drawString(
            20 * mm,
            y,
            f"Cuotas a compensar pendientes de periodos anteriores {zero_fmt}",
        )
        y -= 6 * mm

        # iva.compensacion-aplicada-periodo (box 78) â€” zero (c46 > 0, no prior compensation)
        # Profile: 'Cuotas\s+a\s+compensar\s+de\s+periodos\s+anteriores\s+aplicadas\s+en\s+este\s+periodo'
        c.drawString(
            20 * mm,
            y,
            f"Cuotas a compensar de periodos anteriores aplicadas en este periodo {zero_fmt}",
        )
        y -= 6 * mm

        # iva.compensacion-pendiente-periodos-posteriores (box 87) â€” zero
        # Profile (regex):
        # 'Cuotas\s+a\s+compensar\s+de\s+periodos\s+previos\s+pendientes\s+'
        # 'para\s+periodos\s+posteriores\s+\(110\s*-\s*78\)'
        c.drawString(
            20 * mm,
            y,
            f"Cuotas a compensar de periodos previos pendientes para periodos posteriores (110 - 78) {zero_fmt}",
        )
        y -= 6 * mm

        # iva.resultado (box 69) â€” = c46 - 0 = c46
        # Profile: 'Resultado\s+de\s+la\s+autoliquidaci[oÃ³]n\s+\(66[^\)]*\)'
        c.drawString(
            20 * mm,
            y,
            f"Resultado de la autoliquidacion (66 - 78) {_fmt_spanish(fixture.c69)}",
        )
        y -= 6 * mm

        # box 71 â€” Resultado (69 - 70 + 109) â€” Orden HAC/819/2024 art. 1 Â§6
        # Profile: 'Resultado\s+\(69\s*-\s*70\s*\+\s*109\)'
        c.drawString(
            20 * mm,
            y,
            f"Resultado (69 - 70 + 109) {_fmt_spanish(fixture.c71)}",
        )
        y -= 6 * mm

    y -= 4 * mm
    c.drawString(20 * mm, y, "Ejemplar para el obligado tributario")
    y -= 8 * mm
    # Justificante receipt fields required by the sidecar roundtrip test.
    # Codigo Seguro de Verificacion: the sidecar expects SANITIZED303{ejercicio}.
    # Fecha y hora de presentacion: required by _extract_presented_at (YYYY-MM-DD HH:MM:SS shape).
    # Verification URL: required by _extract_verification_url.
    csv_val = fixture.csv if fixture.csv else f"SANITIZED303{fixture.ejercicio}"
    c.drawString(
        20 * mm,
        y,
        f"Codigo Seguro de Verificacion: {csv_val}",
    )
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Fecha y hora de presentacion: {fixture.presented_at}")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha de alta de la actividad: 01-01-1900")
    y -= 6 * mm
    c.drawString(
        20 * mm,
        y,
        _SEDE_ORIGIN,
    )


@dataclass(frozen=True)
class _Modelo130CorpusFixture:
    """Synthetic M130 corpus fixture with formula-consistent casilla values.

    Values are derived by running the real calculation engine
    (calculate_registry_snapshot) with the listed leaf inputs and zero-valued
    bindings for previous-period carry-forwards, producing the closure casilla 19
    by formula:
      04 = max(0, 03 * 20%)             [modelo-130-pago-fraccionado-directa]
      07 = 04 - 05 - 06                 [modelo-130-resultado-apartado-i]
      09 = 08 * 2%                      [modelo-130-pago-fraccionado-agrario]
      11 = 09 - 10                      [modelo-130-resultado-apartado-ii]
      12 = max(0, 07 + 11)              [modelo-130-suma-parciales]
      13 = 100 (prev_year_income=0 â‰¤ 9000) [modelo-130-minoracion-rendimientos-netos]
      14 = 12 - 13                      [modelo-130-neto-tras-minoracion]
      17 = (14 - 15) - 16               [modelo-130-diferencia; 01=0 â†’ 01>0 condition false]
      19 = 17 - 18                      [modelo-130-resultado-final]

    Leaf inputs printed in the PDF:
      03 = rendimiento neto (bound, non-previous_filing â†’ supplied via inputs)
      19 = resultado final (computed, closure casilla â€” printed so extractor captures it)

    All other casillas (01, 02, 05, 06, 08, 10, 15, 16, 18) are absent (zero by default).

    Registry source: src/cadrumo/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/
      formulas/0001-formulas.toml, formulas/0002-formulas.toml, parameters/0001-parameters.toml
    """

    filename: str
    ejercicio: str
    periodo: str
    tax_id: str
    c03: Decimal  # rendimiento neto (leaf input)
    c19: Decimal  # resultado final (engine-derived closure)
    # Justificante receipt fields â€” required by the sidecar roundtrip test.
    # csv must match SANITIZED{modelo}{ejercicio} to satisfy _CSV_SYNTHETIC_RE.
    csv: str = ""
    presented_at: str = "2024-01-01 10:00:00"


def _compute_m130_closure(c03: Decimal) -> Decimal:
    """Compute M130 closure casilla 19 from rendimiento neto c03.

    Formula chain (all other leaf inputs = 0, prev_year_income binding = 0):
      c04 = max(0, c03 * 20%)         [irpf.direct_estimation_fractional_payment_rate = 20%]
      c07 = c04 - 0 - 0 = c04
      c09 = 0 * 2% = 0
      c11 = 0 - 0 = 0
      c12 = max(0, c04 + 0) = c04
      c13 = 100                        [prev_year_income=0 â‰¤ 9000 â†’ 100 EUR minoraciÃ³n]
      c14 = c04 - 100
      c17 = (c14 - 0) - 0 = c14       [c01=0 â†’ condition c01>0 is False; standard subtraction]
      c19 = c17 - 0 = c17 = c14
    Returns c19 rounded to 2 decimal places (money-2 rounding).

    Arithmetic grounded in:
      registry formulas/0001-formulas.toml (all formula expressions)
      registry parameters/0001-parameters.toml (rate 20%, rate 2%)
      registry formulas/0002-formulas.toml (casilla 13 step function, 100 at â‰¤9000)
    """
    # c04 = max(0, c03 * 20/100)
    rate: Decimal = Decimal("20") / Decimal("100")
    c04: Decimal = max(Decimal("0"), round_to_cents(c03 * rate))
    # c07 = c04 - 0 - 0
    c07: Decimal = c04
    # c12 = max(0, c07 + 0)
    c12: Decimal = max(Decimal("0"), c07)
    # c13 = 100 (prev_year_income=0 â‰¤ 9000)
    c13: Decimal = Decimal("100.00")
    # c14 = c12 - c13
    c14: Decimal = round_to_cents(c12 - c13)
    # c17 = (c14 - 0) - 0 = c14  [c01=0 â†’ standard path]
    c17: Decimal = c14
    # c19 = c17 - 0
    c19: Decimal = round_to_cents(c17)
    return c19


_MODELO_130_CORPUS_FIXTURES: tuple[_Modelo130CorpusFixture, ...] = (
    _Modelo130CorpusFixture(
        filename="130/2021-2T.pdf",
        ejercicio="2021",
        periodo="2T",
        tax_id="Y0000001S",
        c03=Decimal("5000.00"),
        c19=_compute_m130_closure(Decimal("5000.00")),
    ),
    _Modelo130CorpusFixture(
        filename="130/2021-3T.pdf",
        ejercicio="2021",
        periodo="3T",
        tax_id="Y0000001S",
        c03=Decimal("7500.00"),
        c19=_compute_m130_closure(Decimal("7500.00")),
    ),
    _Modelo130CorpusFixture(
        filename="130/2021-4T.pdf",
        ejercicio="2021",
        periodo="4T",
        tax_id="Y0000001S",
        c03=Decimal("10000.00"),
        c19=_compute_m130_closure(Decimal("10000.00")),
    ),
    _Modelo130CorpusFixture(
        filename="130/2022-1T.pdf",
        ejercicio="2022",
        periodo="1T",
        tax_id="Y0000001S",
        c03=Decimal("5200.00"),
        c19=_compute_m130_closure(Decimal("5200.00")),
    ),
    _Modelo130CorpusFixture(
        filename="130/2022-2T.pdf",
        ejercicio="2022",
        periodo="2T",
        tax_id="Y0000001S",
        c03=Decimal("7800.00"),
        c19=_compute_m130_closure(Decimal("7800.00")),
    ),
    _Modelo130CorpusFixture(
        filename="130/2022-3T.pdf",
        ejercicio="2022",
        periodo="3T",
        tax_id="Y0000001S",
        c03=Decimal("9100.00"),
        c19=_compute_m130_closure(Decimal("9100.00")),
    ),
    _Modelo130CorpusFixture(
        filename="130/2022-4T.pdf",
        ejercicio="2022",
        periodo="4T",
        tax_id="Y0000001S",
        c03=Decimal("11000.00"),
        c19=_compute_m130_closure(Decimal("11000.00")),
    ),
    _Modelo130CorpusFixture(
        filename="130/2023-1T.pdf",
        ejercicio="2023",
        periodo="1T",
        tax_id="Y0000001S",
        c03=Decimal("5400.00"),
        c19=_compute_m130_closure(Decimal("5400.00")),
    ),
    _Modelo130CorpusFixture(
        filename="130/2023-2T.pdf",
        ejercicio="2023",
        periodo="2T",
        tax_id="Y0000001S",
        c03=Decimal("8100.00"),
        c19=_compute_m130_closure(Decimal("8100.00")),
    ),
    _Modelo130CorpusFixture(
        filename="130/2023-3T.pdf",
        ejercicio="2023",
        periodo="3T",
        tax_id="Y0000001S",
        c03=Decimal("10500.00"),
        c19=_compute_m130_closure(Decimal("10500.00")),
    ),
    _Modelo130CorpusFixture(
        filename="130/2023-4T.pdf",
        ejercicio="2023",
        periodo="4T",
        tax_id="Y0000001S",
        c03=Decimal("13000.00"),
        c19=_compute_m130_closure(Decimal("13000.00")),
    ),
    _Modelo130CorpusFixture(
        filename="130/2024-1T.pdf",
        ejercicio="2024",
        periodo="1T",
        tax_id="Y0000001S",
        c03=Decimal("5600.00"),
        c19=_compute_m130_closure(Decimal("5600.00")),
    ),
    _Modelo130CorpusFixture(
        filename="130/2024-2T.pdf",
        ejercicio="2024",
        periodo="2T",
        tax_id="Y0000001S",
        c03=Decimal("8400.00"),
        c19=_compute_m130_closure(Decimal("8400.00")),
    ),
    _Modelo130CorpusFixture(
        filename="130/2024-3T.pdf",
        ejercicio="2024",
        periodo="3T",
        tax_id="Y0000001S",
        c03=Decimal("11200.00"),
        c19=_compute_m130_closure(Decimal("11200.00")),
    ),
    _Modelo130CorpusFixture(
        filename="130/2024-4T.pdf",
        ejercicio="2024",
        periodo="4T",
        tax_id="Y0000001S",
        c03=Decimal("14000.00"),
        c19=_compute_m130_closure(Decimal("14000.00")),
    ),
)

_M130_BOX_X = 464.0  # x-position for box number text

_M130_VAL_X = 535.0  # x-position for value text (right of box number)

_M130_ROW_STEP = 14.0  # vertical spacing between casilla rows (points)


def _draw_modelo_130_corpus(c: canvas.Canvas, fixture: _Modelo130CorpusFixture) -> None:
    """Render a synthetic M130 corpus fixture page onto ``c``.

    Layout mirrors the real AEAT-generated M130 PDF structure in the region
    relevant to the bbox_anchored extractor:
    - A ``NIF Presentador: <tax_id>`` line so ``_extract_tax_id`` succeeds.
    - Ejercicio and Periodo header fields.
    - Box numbers at x=464 (within anchor_x_min=450, anchor_x_max=480).
    - Spanish-formatted amounts at x=535 on the same y-row.

    Only casillas 03 (rendimiento neto, leaf input) and 19 (resultado final,
    engine-derived closure) are printed. All other casillas are absent and
    treated as zero by the verification chain engine.

    Formula consistency:
      c19 = _compute_m130_closure(c03)
      which mirrors the registry formula chain (formulas/0001-formulas.toml,
      formulas/0002-formulas.toml, parameters/0001-parameters.toml).

    Non-tautology: the _compute_m130_closure function replicates the arithmetic
    of the real engine. If the registry formula changes and the fixture is not
    regenerated, test_verification_chain_m130 will fail â€” the test cannot pass
    trivially because the engine result and the fixture are computed independently
    (engine: runtime TOML evaluation; fixture: hand-replicated formula at
    generation time).
    """
    _, height = A4
    y: float = height - 25 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, "Impuesto sobre la Renta de las Personas Fisicas  Modelo 130")
    y -= 10 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"Ejercicio: {fixture.ejercicio}   Periodo: {fixture.periodo}")
    y -= 8 * mm
    # NIF line: _TAX_ID_RE matches "NIF Presentador: <tax_id>"
    c.drawString(20 * mm, y, f"NIF Presentador: {fixture.tax_id}")
    y -= 8 * mm
    c.drawString(20 * mm, y, "Actividades economicas en estimacion directa")
    y -= 10 * mm

    # Casilla rows: box number at _M130_BOX_X, value at _M130_VAL_X, same y-row.
    # Box numbers 01-19 are printed at the correct x-range so the bbox_anchored
    # extractor can find them. Only boxes with non-zero values are printed;
    # absent boxes are implicitly zero in the engine.
    casilla_rows: tuple[tuple[str, Decimal], ...] = (
        ("03", fixture.c03),
        ("19", fixture.c19),
    )
    for box_num, value in casilla_rows:
        # reportlab y is from bottom; pdfplumber top is from page top.
        # Place box number and value on the same reportlab y coordinate.
        c.setFont("Helvetica", 10)
        c.drawString(_M130_BOX_X, y, box_num)
        c.drawString(_M130_VAL_X, y, _fmt_spanish(value))
        y -= _M130_ROW_STEP
    y -= 4 * mm
    c.drawString(20 * mm, y, "Ejemplar para el obligado tributario")
    y -= 8 * mm
    # Justificante receipt fields required by the sidecar roundtrip test.
    # Codigo Seguro de Verificacion: the sidecar expects SANITIZED130{ejercicio}.
    # Fecha y hora de presentacion: required by _extract_presented_at (YYYY-MM-DD HH:MM:SS shape).
    # Verification URL: required by _extract_verification_url.
    csv_val = fixture.csv if fixture.csv else f"SANITIZED130{fixture.ejercicio}"
    c.drawString(
        20 * mm,
        y,
        f"Codigo Seguro de Verificacion: {csv_val}",
    )
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Fecha y hora de presentacion: {fixture.presented_at}")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha de alta de la actividad: 01-01-1900")
    y -= 6 * mm
    c.drawString(
        20 * mm,
        y,
        _SEDE_ORIGIN,
    )


@dataclass(frozen=True)
class _Modelo390CorpusFixture:
    """Synthetic M390 corpus fixture with formula-consistent casilla values.

    The closure casilla ``iva.anual.resultado-regimen-general`` (form box 65) is
    derived from the registry formula:
      box65 = box47 - box64
            = (box06 + box04 + box02 + box26) - (box49 + box26)

    Where:
      box02 = iva.anual.repercutido.super-reducido   (4% rate, leaf input)
      box04 = iva.anual.repercutido.reducido          (10% rate, leaf input)
      box06 = iva.anual.repercutido.general           (21% rate, leaf input)
      box26 = iva.anual.autorepercutido.intracomunitaria (intracom 21%, leaf input)
      box49 = iva.anual.soportado.interiores          (total ded. interiores, leaf input)

    Computed:
      box47 = box06 + box04 + box02 + box26           [cuota-devengada-total]
      box64 = box49 + box26                            [cuota-deducible-total]
      box65 = box47 - box64                            [resultado-regimen-general]

    No intracomunitaria (box26=0) in the simple-case fixture.
    No compensation carry-forwards (97/662 = 0).

    Registry source: src/cadrumo/_data/registry/aeat/modelos/390/revisions/2010-y-siguientes/
      formulas/0001-formulas.toml (modelo-390-iva-anual-cuota-devengada-total,
      modelo-390-iva-anual-cuota-deducible-total,
      modelo-390-iva-anual-resultado-regimen-general)
    Legal refs: ley-37-1992:art-88, art-90, art-91, art-92; orden-eha-3111-2009:art-1
    """

    filename: str
    ejercicio: str
    tax_id: str
    c06: Decimal  # repercutido.general 21% (leaf input, box 06)
    c04: Decimal  # repercutido.reducido 10% (leaf input, box 04)
    c02: Decimal  # repercutido.super-reducido 4% (leaf input, box 02)
    c26: Decimal  # autorepercutido.intracomunitaria (leaf input, box 26)
    c49: Decimal  # soportado.interiores (leaf input, box 49)
    # Derived via _compute_m390_closure:
    c47: Decimal  # cuota-devengada-total = c06 + c04 + c02 + c26
    c64: Decimal  # cuota-deducible-total = c49 + c26
    c65: Decimal  # resultado-regimen-general = c47 - c64
    # Justificante receipt fields â€” required by the sidecar roundtrip test.
    # csv must match SANITIZED{modelo}{ejercicio} to satisfy _CSV_SYNTHETIC_RE.
    csv: str = ""
    presented_at: str = "2024-01-01 10:00:00"


def _compute_m390_closure(
    c06: Decimal,
    c04: Decimal,
    c02: Decimal,
    c26: Decimal,
    c49: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    """Compute M390 closure casillas from leaf inputs.

    Formula chain (no compensation carry-forward):
      c47 = c06 + c04 + c02 + c26    [modelo-390-iva-anual-cuota-devengada-total]
      c64 = c49 + c26                 [modelo-390-iva-anual-cuota-deducible-total]
      c65 = c47 - c64                 [modelo-390-iva-anual-resultado-regimen-general]

    All values rounded to money-2 (2 decimal places) consistent with registry
    rounding declarations.

    Arithmetic grounded in Orden EHA/3111/2009 art. 1 and the registry formula
    expressions in formulas/0001-formulas.toml.
    """
    c47: Decimal = round_to_cents(c06 + c04 + c02 + c26)
    c64: Decimal = round_to_cents(c49 + c26)
    c65: Decimal = round_to_cents(c47 - c64)
    return c47, c64, c65


def _m390_fixture(
    filename: str,
    ejercicio: str,
    tax_id: str,
    c06: Decimal,
    c49: Decimal,
) -> _Modelo390CorpusFixture:
    """Construct a simple-case M390 fixture (no reduced/super-reduced/intracomunitaria).

    c04=c02=c26=0 for all specimens in this suite (no reduced-rate activities,
    no intracomunitaria acquisitions).  c47/c64/c65 are derived via the formula.
    """
    _zero: Decimal = Decimal("0.00")
    c47, c64, c65 = _compute_m390_closure(c06, _zero, _zero, _zero, c49)
    return _Modelo390CorpusFixture(
        filename=filename,
        ejercicio=ejercicio,
        tax_id=tax_id,
        c06=c06,
        c04=_zero,
        c02=_zero,
        c26=_zero,
        c49=c49,
        c47=c47,
        c64=c64,
        c65=c65,
    )


_MODELO_390_CORPUS_FIXTURES: tuple[_Modelo390CorpusFixture, ...] = (
    _m390_fixture("390/2022-0A.pdf", "2022", "Y0000001S", Decimal("10500.00"), Decimal("8400.00")),
    _m390_fixture("390/2023-0A.pdf", "2023", "Y0000001S", Decimal("12600.00"), Decimal("9800.00")),
)

_M390_BOX_X = 414.0  # x-position for box number text (within anchor 407-425)

_M390_VAL_X = 480.0  # x-position for value text (right of box number)

_M390_ROW_STEP = 14.0  # vertical spacing between casilla rows (points)


def _draw_modelo_390_corpus(c: canvas.Canvas, fixture: _Modelo390CorpusFixture) -> None:
    """Render a synthetic M390 corpus fixture page onto ``c``.

    Layout mirrors the real AEAT-generated M390 PDF structure in the region
    relevant to the extraction profile:

    Leaf casillas (bbox_anchored, anchor_x_min=407, anchor_x_max=425):
      Box numbers at x=414 (within anchor window), Spanish-formatted amounts
      at x=480 (right_of_number offset) on the same y-row.
      Boxes printed: 06 (c06), 04 (c04), 02 (c02), 26 (c26), 49 (c49).
      Zero-value boxes are printed so the extractor can read them; absent boxes
      would default to zero in the engine anyway, but printing them confirms
      formula-consistency for all five inputs.

    Computed casillas (named_label, profile patterns verbatim):
      "Total cuotas IVA y recargo de equivalencia <amount>"      [box 47 / cuota-devengada-total]
      "Suma de deducciones <amount>"                              [box 64 / cuota-deducible-total]
      "Resultado regimen general (47 - 64) <amount>"             [box 65 / resultado-regimen-general]

    Formula consistency:
      c47 = c06 + c04 + c02 + c26   [cuota-devengada-total]
      c64 = c49 + c26               [cuota-deducible-total]
      c65 = c47 - c64               [resultado-regimen-general]

    Non-tautology: _compute_m390_closure replicates the arithmetic of the real
    engine. If the registry formula changes and the fixtures are not regenerated,
    test_verification_chain_m390_engine_recomputes_cuota_devengada_deducible will
    fail â€” the test cannot pass trivially because the engine result and the fixture
    are computed independently (engine: runtime TOML evaluation; fixture:
    formula replicated at generation time).

    Accents stripped to stay within the ASCII-safe pdfplumber extraction path,
    consistent with all prior synthetic corpus fixtures in this suite.

    NIF line: _TAX_ID_RE matches "NIF: <tax_id>" (consistent with M303 corpus layout).
    """
    _, height = A4
    y: float = height - 25 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        20 * mm,
        y,
        "Impuesto sobre el Valor Anadido  Modelo 390",
    )
    y -= 10 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"Ejercicio: {fixture.ejercicio}   Periodo: 0A")
    y -= 8 * mm
    c.drawString(20 * mm, y, f"NIF: {fixture.tax_id}")
    y -= 12 * mm

    # Leaf casillas: box number at _M390_BOX_X (within anchor 407-425), value at _M390_VAL_X.
    # Print all five leaf inputs (including zeros) so the extractor captures them.
    # Profile bbox_anchor: box_number_pattern = "^NN$", value_offset = "right_of_number"
    leaf_rows: tuple[tuple[str, Decimal], ...] = (
        ("06", fixture.c06),  # repercutido.general 21%
        ("04", fixture.c04),  # repercutido.reducido 10%
        ("02", fixture.c02),  # repercutido.super-reducido 4%
        ("26", fixture.c26),  # autorepercutido.intracomunitaria
        ("49", fixture.c49),  # soportado.interiores (deducible)
    )
    for box_num, value in leaf_rows:
        c.setFont("Helvetica", 10)
        c.drawString(_M390_BOX_X, y, box_num)
        c.drawString(_M390_VAL_X, y, _fmt_spanish(value))
        y -= _M390_ROW_STEP

    y -= 4 * mm

    # Named-label rows: label text verbatim from the extraction profile pattern.
    # Profile patterns (accents stripped):
    #   cuota-devengada-total:    'Total\s+cuotas\s+IVA\s+y\s+recargo\s+de\s+equivalencia'
    #   cuota-deducible-total:    'Suma\s+de\s+deducciones'
    #   resultado-regimen-general:'Resultado\s+r[eÃ©]gimen\s+general\s+\(47\s*-\s*64\)'
    c.drawString(
        20 * mm,
        y,
        f"Total cuotas IVA y recargo de equivalencia {_fmt_spanish(fixture.c47)}",
    )
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Suma de deducciones {_fmt_spanish(fixture.c64)}")
    y -= 6 * mm
    c.drawString(
        20 * mm,
        y,
        f"Resultado regimen general (47 - 64) {_fmt_spanish(fixture.c65)}",
    )
    y -= 10 * mm
    c.drawString(20 * mm, y, "Ejemplar para el obligado tributario")
    y -= 8 * mm
    # Justificante receipt fields required by the sidecar roundtrip test.
    # Codigo Seguro de Verificacion: the sidecar expects SANITIZED390{ejercicio}.
    # Fecha y hora de presentacion: required by _extract_presented_at (YYYY-MM-DD HH:MM:SS shape).
    # Verification URL: required by _extract_verification_url.
    csv_val = fixture.csv if fixture.csv else f"SANITIZED390{fixture.ejercicio}"
    c.drawString(
        20 * mm,
        y,
        f"Codigo Seguro de Verificacion: {csv_val}",
    )
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Fecha y hora de presentacion: {fixture.presented_at}")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha de alta de la actividad: 01-01-1900")
    y -= 6 * mm
    c.drawString(
        20 * mm,
        y,
        _SEDE_ORIGIN,
    )
