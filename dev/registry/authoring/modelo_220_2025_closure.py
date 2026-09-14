"""Modelo 220 revision 2025: the money-closure casillas of the group declaration.

The settlement chain of the consolidated group -- from the base imponible previa
through the cuota integra, the bonificaciones and deducciones, the cuota liquida,
the cuota diferencial and the resultado de la autoliquidacion, to the liquido a
ingresar o a devolver and its split between the Estado and the administraciones
forales.

Six record sheets of the 2025 diseno, authored from that design rather than
carried from the 2024 edition. Five of the six did not move at the 2024/2025
boundary; the sixth, liquidacion (I), grew seventy-one bytes inside its tramo run
and is the reason this wave exists as a generated one.
"""

from __future__ import annotations

from pathlib import Path

from .casilla_shard_generation import WaveSpec, format_report, generate

_ROOT = Path(__file__).resolve().parents[3]
_CORPUS = _ROOT / "src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_220/files"
_REVISIONS = _ROOT / "src/cadrumo/_data/registry/aeat/modelos/220/revisions"

#: From ``[sources."aeat-dr-220-2025"]`` in the registry's own source catalogue.
#: The run refuses a design binary that is not this artifact.
DECLARED_SHA256 = "69c3a234e96eb4485a31c65209348bbcede0a49a8c143223c952000784f3f2df"

HEADERS = {
    "T22007000": """# Modelo 220 RECORD T22007000 -- liquidacion (I): from the base imponible previa of
# the group through the compensacion of bases imponibles negativas to the base
# imponible and the cuota integra del grupo.
#
# 56 casillas. Forty-six carry a real AEAT box number; ten are unnumbered tramo slots
# whose NUMBER IS THEIR POSITION RANGE, and those ten are why this record is authored
# from the 2025 design rather than copied from 2024.
#
# THE RECORD GREW 71 BYTES AT THE 2024/2025 BOUNDARY, 991 -> 1062, and the growth is
# inside the tramo run, not appended after it. Ords 55-64 now carry three rate scales
# where 2024 carried one: the cooperative tramos, a regimen especial for entidades
# navieras en funcion del tonelaje, and a second pair for resultados extracooperativos.
# The tipo de gravamen slots also widened from 5 to 6 bytes and their declared
# precision changed from "tres enteros, dos decimales" to "2 enteros, 4 decimales".
#
# THREE 2024 IDS ARE ARITHMETICALLY WRONG HERE and were recomputed, not carried:
# .803-807 -> .803-808, .808-824 -> .809-825, .825-829 -> .826-831. Because the id IS
# the position range, copying the 2024 file would have validated cleanly and placed
# every rate one byte off with one byte too few. Six further slots (.832-848 through
# .895-900) have no 2024 counterpart at all.
#
# .786-802 KEPT ITS POSITION AND CHANGED ITS MEANING: 2024 read "Tramo base imponible 1",
# 2025 reads "Tramo 1 - Base imponible (en grupo de cooperativas resultados
# cooperativos)". The slot is unmoved, so a position-keyed carry-forward would not have
# noticed. The concept is the same tramo and the attributes are carried deliberately,
# not by default.
#
# T22007000 tiles 1..1062 exactly once with NO gap and NO overlap, asserted at generation.
#
# NOT MODELLED: the modelo and pagina identifier envelope, the pagina-complementaria
# mechanics, the reservado run and the end-of-record marker.
#
# NOT CLAIMED: these casillas DECLARE the liquidacion; none of them computes it. No
# formula, construct or binding is attached, and the tramo rate slots are declared as
# slots, not as rates -- the design states no scale's values.""",
    "T22009000": """# Modelo 220 RECORD T22009000 -- liquidacion (II): from the cuota integra through the
# bonificaciones, the deducciones por doble imposicion and the otras deducciones to the
# cuota liquida, the cuota diferencial and the resultado de la autoliquidacion.
#
# 63 casillas, every one carrying a real AEAT box number and a `segmento`.
#
# EVERY OFFSET, LENGTH AND TYPE IS UNCHANGED FROM 2024 -- all 63 verified identical at
# generation. Four captions changed, and each is AEAT relocating a feeder schedule
# rather than editing a concept: [03251] and [03261] now cite pag. 12 bis, [00588] cites
# pag. 14, 14 bis y 14 ter, and [00436] cites pag. 14 sexies. The captions below are
# transcribed from the 2025 design, so they carry the 2025 pointers.
#
# AEAT BREAKS THE "fi" LIGATURE ACROSS A SPACE on this family -- "Bonifi caciones",
# "Transparencia fi scal", "especifi cas" -- and misspells "Pago fracionado" and "Cuota
# liquida". Transcribed as printed in the fragment comments, corrected only in the
# operator-facing labels.
#
# T22009000 tiles 1..1248 exactly once with NO gap and NO overlap, asserted at generation.
#
# NOT MODELLED: the modelo and pagina identifier envelope, the pagina-complementaria
# mechanics, the reservado run and the end-of-record marker.
#
# NOT CLAIMED: these casillas DECLARE the liquidacion; none of them computes it. The
# record is a settlement chain and NOT ONE of those relations is modelled here.""",
    "T22009001": """# Modelo 220 RECORD T22009001 -- liquidacion (III): the liquido a ingresar o a devolver,
# the complementaria adjustments, the art. 19.1 LIS fraccionamiento option and the
# conversion of activos por impuesto diferido.
#
# 36 casillas. THIS RECORD HAS NO 2024 COUNTERPART IN THE TREE -- it was withheld there,
# and the reason was recorded rather than scheduled away.
#
# THE WITHHOLDING REASON STILL STANDS AND IS NOT RESOLVED HERE. Boxes 02796 and 02797
# carry BYTE-IDENTICAL descriptions in the 2025 design exactly as in 2024, both ending
# "Estado.", at adjacent offsets 220 and 237. The pair immediately above them, 02794 and
# 02795, splits the same concept "Estado" / "D. Forales / Navarra (totales)", so the
# pattern says one of 02796/02797 should be the foral column and AEAT has repeated the
# wrong suffix. THE 2025 DESIGN DOES NOT FIX THIS; it was checked, not assumed.
#
# WHAT CHANGED IS THE DISPOSITION, NOT THE EVIDENCE. Both boxes are declared with their
# captions transcribed exactly as printed -- identical, both ending "Estado." -- and NO
# jurisdiction, label or ordering distinction is asserted between them. That declares
# what AEAT printed without guessing what AEAT meant. Withholding the whole record
# instead left [00621] and [00622], the liquido a ingresar o a devolver and the terminal
# numbers of the entire return, with no home on the record that computes them; the group
# reached them only indirectly through T220DID00 and T22016000.
#
# T22009001 tiles 1..789 exactly once with NO gap and NO overlap, asserted at generation.
#
# NOT MODELLED: the modelo and pagina identifier envelope, the pagina-complementaria
# mechanics, the reservado run and the end-of-record marker.
#
# NOT CLAIMED: no formula, construct or binding is attached, and no jurisdiction is
# asserted on 02796/02797.""",
    "T22016000": """# Modelo 220 RECORD T22016000 -- tributacion conjunta al Estado y a las administraciones
# forales del Pais Vasco y Navarra: the foral split of the group's liquidacion.
#
# 110 casillas, every one carrying a real AEAT box number. A regular 28-concept by
# 5-territory grid -- Araba, Gipuzkoa, Bizkaia, Navarra, and the total of the territorios
# forales.
#
# EVERY OFFSET, LENGTH AND TYPE IS UNCHANGED FROM 2024 -- all 110 verified identical at
# generation, including the tail at 2001..2154. The caption changes are the devengo year
# only, 2024 -> 2025.
#
# SIXTY UNNUMBERED ROWS ARE DELIBERATELY NOT DECLARED. They carry the volumenes de
# operaciones realizados en cada territorio that FEED the foral percentages. The 2024
# edition declined them and this edition holds that line: they are a separate authoring
# scope, and widening scope inside a carry-forward wave is how an edition acquires rows
# nobody adjudicated. They are absent, not forgotten.
#
# AEAT BREAKS THE "fi" LIGATURE on this family -- "insufi ciencia". Transcribed as printed.
#
# T22016000 tiles 1..2927 exactly once with NO gap and NO overlap, asserted at generation.
#
# NOT MODELLED: the identifier envelope, the reservado runs and the end-of-record marker.
#
# NOT CLAIMED: these casillas DECLARE the foral split; none of them computes it. No
# percentage, apportionment rule or formula is modelled here.""",
    "T22016001": """# Modelo 220 RECORD T22016001 -- continuation of the foral split, carrying the closing
# concepts of the tributacion conjunta grid through to [02813].
#
# 30 casillas, every one carrying a real AEAT box number.
#
# EVERY OFFSET, LENGTH AND TYPE IS UNCHANGED FROM 2024 -- all 30 verified identical at
# generation. Only the sheet header line differs.
#
# T22016001 tiles 1..687 exactly once with NO gap and NO overlap, asserted at generation.
#
# NOT MODELLED: the identifier envelope, the reservado run and the end-of-record marker.
#
# NOT CLAIMED: these casillas DECLARE the foral split; none of them computes it.""",
    "T220DID00": """# Modelo 220 RECORD T220DID00 -- documento de ingreso o devolucion.
#
# 31 casillas. This record is HETEROGENEOUS where the liquidacion records are uniform:
# alongside money it carries the devengo dates, the period code, the NIF and name of the
# declarante, an IBAN, and the single-letter markers D, I, A and C that AEAT prints in
# place of a box number for importe a devolver, importe a ingresar, abono and
# compensacion. Those letters ARE the box number and are declared as such.
#
# EVERY OFFSET, LENGTH AND TYPE IS UNCHANGED FROM 2024 -- all 31 verified identical at
# generation. The only caption change is ord 10's Contenido constant, 2024 -> 2025.
#
# THE BOX NUMBER IS NOT ALWAYS AT THE END OF THE CAPTION on this record: ord 18 reads
# "Liquidacion (3) - Cuota integra del grupo [00562]. {DID_liq_CI}", with the number
# mid-line and a form placeholder after it. Numbers are located anywhere in the caption,
# never by position in the string.
#
# T220DID00 tiles 1..720 exactly once with NO gap and NO overlap, asserted at generation.
#
# NOT MODELLED: the identifier envelope, the reservado runs and the end-of-record marker.
#
# NOT CLAIMED: these casillas DECLARE the documento de ingreso o devolucion; none of them
# computes it, and no bank-account validation or settlement behaviour is attached.""",
}

MODELO_220_2025_CLOSURE = WaveSpec(
    design_path=_CORPUS / "01-220-ejercicio-2025.xlsx",
    prior_casillas_dir=_REVISIONS / "2024/casillas",
    out_dir=_REVISIONS / "2025/casillas",
    revision_id="2025",
    legal_refs='["orden-hac-529-2026:art-6-3", "ley-27-2014:art-124"]',
    records=(
        "T22007000",
        "T22009000",
        "T22009001",
        "T22016000",
        "T22016001",
        "T220DID00",
    ),
    headers=HEADERS,
    # The judgement, stated as rules rather than transcribed per row: which
    # section vocabulary a record belongs to, and how a declared width maps to a
    # data type. A 17-byte N/Num slot on these records is an amount; the 6-byte
    # tipo de gravamen is a rate.
    adjudicated_sections={
        "T22007000": ("liquidacion", "base_imponible_y_cuota_integra_del_grupo"),
        "T22009001": ("liquidacion", "liquidacion_del_grupo"),
    },
    # Scope parity with the 2024 edition. T22016000's unnumbered
    # volumen-de-operaciones rows FEED the foral percentages and were declined
    # there; widening scope inside a carry-forward run is how an edition acquires
    # rows nobody adjudicated.
    scope_skip_unnumbered=frozenset({"T22016000"}),
    declared_sha256=DECLARED_SHA256,
)


def main() -> int:
    """Report the wave; pass --write to emit it."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    report = generate(MODELO_220_2025_CLOSURE, write=arguments.write)
    print(format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
