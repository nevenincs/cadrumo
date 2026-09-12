"""Modelo 280 filing years 2022-2024, authored as one span.

Modelo 280 is the informativa for the plan de ahorro a largo plazo: one Tipo 1
record per declarante and one Tipo 2 per PALP holder, carrying the holder's
identity, the plan's apertura and extincion, the ejercicio amounts and the
accumulated ones.

WHY ONE SPAN, AND WHAT THAT CLAIM RESTS ON. Only one design is bundled --
``aeat-dr-280-2022``, whose window opens 2022-01-01 and does not close -- so the
span is a LEGAL claim, not a byte-identical one. The consolidated text of Orden
HAP/2118/2015 lists exactly three modifications to its anexo, where the disenos
de registro live: Orden HFP/1822/2016, Orden HAC/1276/2019 and Orden
HFP/1192/2022. Nothing after 2022. There is therefore no instrument by which the
2023 or 2024 design could differ from the 2022 one.

ACQUISITION PENDING, STATED RATHER THAN ASSUMED. Whether AEAT published a
``DR_280_2023.pdf`` or ``DR_280_2024.pdf`` that nobody fetched is an open
question this tree cannot answer: it holds one artefact and no negative-result
record for those URLs. If either exists, this span splits. The claim above is
"no amending orden exists", never "the three designs are byte-identical" -- the
second sentence would be a fabrication, because two of the three designs are not
here to compare.

THE SPAN'S LOWER BOUND IS LOAD-BEARING. Position 137 of Tipo 2, ``EXTINCION DEL
PLAN DE AHORRO A LARGO PLAZO``, was amended by Orden HFP/1192/2022 art. cuarto:
clave 3, extincion por fallecimiento del tomador, was added and clave 2 rewritten
to mean "en circunstancias distintas a las definidas en las claves 1 y 3". The
position did not move and the caption did not change -- the whole change is in
the Contenido cell. Folding a pre-2022 year into this span would carry clave 3
into an ejercicio where it did not exist.
"""

from __future__ import annotations

from pathlib import Path

from .casilla_shard_generation import WaveSpec, format_report, generate

_ROOT = Path(__file__).resolve().parents[3]
_CORPUS = _ROOT / "src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_280/files"
_REVISIONS = _ROOT / "src/cadrumo/_data/registry/aeat/modelos/280/revisions"

#: From ``[sources."aeat-dr-280-2022"]``. The run refuses any other binary.
DECLARED_SHA256 = "45cab8f0880dfc4094d6cc8905ae37efba0c10a568d49e8648e1c9a20b2a5701"

DECLARANTE = "Tipo 1 - Registro De Declarante"
DECLARADO = "Tipo 2 - Registro De Declarado"

HEADERS = {
    DECLARANTE: """# Modelo 280 RECORD Tipo 1 -- registro de declarante. One per declaration: the
# declarante's identity and contact, the complementaria/sustitutiva mechanics,
# and the two summary totals (importe total de aportaciones, base de
# retenciones).
#
# 10 casillas. THIS MODELO PRINTS NO BOX NUMBERS AT ALL -- not one bracket token
# appears anywhere in either record -- so every id is either a position range or
# a name the authoring edition chose. The four named ones (ejercicio,
# nif-declarante on this record; nif-declarado and apellidos-nombre-declarado on
# Tipo 2) are declared aliases in this wave, because no positional rule can
# produce a name and resemblance is not evidence.
#
# THE SEMANTIC PAYLOAD IS IN THE CONTENIDO COLUMN, not the caption. The
# Descripcion cell is a bare uppercase title; the claves, the conditional rules
# and the cross-references to positions 110 and 137 all live in Contenido. A
# caption-only drift check is blind to a meaning change on this design by
# construction, which is why Contenido is transcribed into the comment and
# compared as its own channel.
#
# POSITION 58, TIPO DE SOPORTE, IS DELIBERATELY NOT DECLARED. It exists in the
# design and in the export layout, and the prior edition declares no casilla for
# it. This edition holds that line rather than widening scope inside a
# carry-forward run.
#
# Tipo 1 tiles 1..500 exactly once with NO gap and NO overlap, asserted at
# generation.
#
# NOT MODELLED: the tipo-de-registro and modelo-declaracion constants, and the
# 316-byte BLANCOS filler -- which is 63% of the record.
#
# NOT CLAIMED: these casillas DECLARE the informativa; none of them computes it.""",
    DECLARADO: """# Modelo 280 RECORD Tipo 2 -- registro de declarado. One per PALP holder: the
# holder and any representante legal, the plan's identification and apertura, the
# clave de alta, the ejercicio amounts, the extincion block and the accumulated
# amounts.
#
# 17 casillas.
#
# THE DESIGN DOES NOT TILE AS THE READER RETURNS IT, and this wave declares why
# rather than working around it silently. AEAT writes "Este campo se subdivide en
# dos" over positions 176-186, which is really THREE parts -- 176 SIGNO,
# 177-184 ENTERO, 185-186 DECIMAL. The PDF reader's desglose nester has a count
# clause that refuses to make three where AEAT says two, correctly, so 177-184
# and 185-186 surface beside their own grandparent and the record sums 510
# against a declared 500. This wave declares that one group; every other
# containment in this or any record still refuses.
#
# POSITIONS 5 AND 9 ARE ECHOES OF TIPO 1 -- the design says of the ejercicio
# "consignar lo contenido en estas mismas posiciones del registro de tipo 1", and
# the NIF del declarante repeats likewise. The prior edition declares no casilla
# for either while declaring both on Tipo 1, and that asymmetry is a judgement
# this edition inherits rather than re-makes.
#
# POSITION 137 IS THE SPAN'S LOWER BOUND. Orden HFP/1192/2022 art. cuarto added
# clave 3 (fallecimiento del tomador) and rewrote clave 2 around it. The position
# and the caption are unchanged; the change is entirely in Contenido. That is why
# this span starts at 2022 and must not be extended earlier.
#
# Tipo 2 tiles 1..500 exactly once with NO gap and NO overlap, asserted at
# generation with the declared desglose group excluded from the sum.
#
# NOT MODELLED: the tipo-de-registro and modelo-declaracion constants and the
# 314-byte BLANCOS filler.
#
# NOT CLAIMED: no formula, binding or construct is attached, and no clave
# enumeration is modelled as a typed vocabulary -- the claves are transcribed as
# AEAT printed them and nothing resolves against them.""",
}

MODELO_280_2022_2024 = WaveSpec(
    design_path=_CORPUS / "DR_280_2022.pdf",
    prior_casillas_dir=_REVISIONS / "2025/casillas",
    out_dir=_REVISIONS / "2022-2024/casillas",
    revision_id="2022-2024",
    # The wave default. Rows that carry their own attribution keep it, because
    # this modelo varies legal_refs per row: art. 4 on the ejercicio, Orden
    # HFP/1822/2016 art. sexto on every euro amount, Orden HFP/1192/2022 art.
    # cuarto on the extincion pair.
    legal_refs='["orden-hap-2118-2015:art-1"]',
    carry_legal_refs=True,
    records=(DECLARANTE, DECLARADO),
    headers=HEADERS,
    # The sheet names are prose; the corpus numbers its slots tipo1/tipo2.
    record_stems={DECLARANTE: "tipo1", DECLARADO: "tipo2"},
    # Every id on this modelo is an authored slug. Nothing may be minted.
    id_scheme="carried",
    prior_glob="*.toml",
    # Read off the design: @18+9 is the declarado's NIF and @36+40 the name, so
    # these two slots carry the prior edition's names rather than their spans.
    number_aliases={
        DECLARANTE: {
            "tipo1.5-8": "tipo1.ejercicio",
            "tipo1.9-17": "tipo1.nif-declarante",
        },
        DECLARADO: {
            "tipo2.18-26": "tipo2.nif-declarado",
            "tipo2.36-75": "tipo2.apellidos-nombre-declarado",
        },
    },
    scope_skip_positions={
        DECLARANTE: frozenset({58}),
        DECLARADO: frozenset({5, 9}),
    },
    declared_desglose_parents={DECLARADO: {176: (177, 185)}},
    declared_sha256=DECLARED_SHA256,
)


def main() -> int:
    """Report the wave; pass --write to emit it."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    report = generate(MODELO_280_2022_2024, write=arguments.write)
    print(format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
