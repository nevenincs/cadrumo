"""Modelo 036 filing years 2023 through 2025-02-02, authored as one span.

DO NOT RE-RUN THIS GENERATOR AGAINST THE LIVE TREE. Its writes are
all-or-nothing over the whole casillas directory and its renderer emits no
continuidad field, but on 2026-09-12 a later pass stamped a ``continuidad_id``
onto 423 of the 508 casillas it had produced. A re-run drops every
continuidad_id in that directory. It reports nothing when it does, because from
the generator's side the output looks exactly as it did the first time. Emit
into a scratch directory and diff; ``out_dir`` is a field, so
``dataclasses.replace(MODELO_036_2023_SPAN, out_dir=...)`` is the safe form.

A RE-RUN IS NOT THE ONLY THING THAT DELETES THEM, AND A WARNING THAT NAMES
ONLY THE RE-RUN IS WORSE THAN NONE -- it invites the reader to conclude the
stamps are safe so long as nobody runs this file. They are not. The same 423
rows are exposed from the other end by an identical-member DROP pass, whose
job is removing members equal to what they would inherit. The restatement
comparator strips lineage claims before comparing, so a row differing ONLY in
a continuidad attestation compares EQUAL, counts as ordinary restatement, and
sits inside the number that says it is droppable. Corpus-wide that population
is about 2,641 rows and this modelo is its largest single holder. A
lineage-only stub does not survive the merge either -- the casilla merge
replaces a stated row wholesale and never fills payload, so the stub emits
with id plus continuidad fields and then fails validation on number and
section. Until a field-level inheritance rule lands there is no safe
mechanical drop for any of these rows.

THE LIVE TREE AND THIS GENERATOR AGREE AGAIN, AT 530. Twenty rows whose box
number the extract malformed were merged into the live edition on 2026-09-12 by
targeted rewrites of the Pag. 9 and Pag. 2A shards, preserving every existing
row's continuidad_id. Three separate malformations produced one silent outcome:
eighteen lost the opening bracket (PAG9_LOST_BRACKETS), and A1 and A38 are a
parenthesis close and a leading space (PAG2A_MALFORMED_BRACKETS). Two further
rows, A3A and B3A, are the proven renumbering (PAG2AB_RENUMBERED) and emit
under their own design's number while carrying the successor's attributes.
NOTHING IS DEFERRED ON THIS WAVE ANY MORE: the count went four, then two, then
zero, each step by evidence rather than by decision.

Both merges RENAMED their shard, because each new row landed at the start or end
of the block and a shard is named for its first and last casilla. That is why
the attestation harvest is directory-wide rather than per-file, and why anything
keyed on a shard PATH rather than a row id would have missed those rows.

A whole-directory regeneration would still destroy all 423 continuidad_id, so
the warning above stands unchanged.

The declaracion censal. Its approving orden is Orden EHA/1274/2007 and the RD
1065/2007 framework; unlike an annual modelo it has no calendar plazo, because
its period_selector declares EVENT kinds -- alta, modificacion, baja -- anchored
to the event that triggers them rather than to a calendar period.

ONE SPAN, BOUNDED BY THE DESIGN'S OWN WINDOW. ``aeat-dr-036-2023`` declares
2023-01-01 to 2025-02-02, and the successor edition opens 2025-02-03, the day
Orden HAC/1526/2024 took effect and suppressed the modelo 037. The two spans meet
with no day uncovered and none served twice.

THERE IS NO ``aeat-dr-036-2024``. One design covers both full years and the
33-day tail of 2025. A wave deriving a source id from its edition year would emit
a ref that resolves to nothing.

WHAT THIS EDITION DECLINES, AND WHY IT IS NOT A GAP. 115 number groups that this
design prints are declared by NO edition -- 82 slots AEAT printed with no box
number at all, and 33 whose number is a comma list (``B1,B2``, ``300,301,302``).
Neither the lists nor their parts appear in the 2025 edition. Two of the 82 are
plainly deliberate rather than overlooked: the VERSION AAAMMDD constant and the
lugar-fecha-firma block. They are declined at parity, enumerated one by one
rather than swept by a rule, so a row that appears later REFUSES instead of
joining the declined set unnoticed.

TWO GROUPS ARE DEFERRED, AND THE COUNT CAME DOWN FROM FOUR BY EVIDENCE. ``A3A``
and ``B3A`` are date triples the 2025 edition carries as ``A3B``/``B3B`` with
position, length, type and caption all unchanged. That the change is a
RENUMBERING rather than a replacement is now proven, by a design pair this wave
originally did not compare: the corpus holds TWO files for the 2025 edition, a
provisional and a final, and the provisional still prints ``A3A``/``B3A`` while
the final prints ``A3B``/``B3B`` at the same 1846/1848/1850 and 1946/1948/1950,
the same 2/2/4 lengths, the same Num type and byte-identical captions. The label
is the only thing that moves, and it moves inside one edition's own publication
cycle. They stay listed here because the predecessor casillas are not yet
written, not because the question is still open.

``613`` AND ``614`` WERE DEFERRED ON A FALSE PREMISE AND ARE NOW DECLINED. This
wave recorded that they "have no 2025 counterpart at all". They do: both appear
twelve times in the 2025 FINAL design at identical positions, lengths and
captions, the only difference being the trailing 037 asterisk the final drops.
What they lack is an EDITION declaration, on either side -- and both editions
decline the identical block (604-615, 617, 619, 623-625, 627-632) while both
declaring the same sixteen 600-series numbers. Two independently authored
editions holding the same scope line is parity, which is a settled claim, not an
open one.
"""

from __future__ import annotations

from pathlib import Path

from .casilla_shard_generation import WaveSpec, format_report, generate

_ROOT = Path(__file__).resolve().parents[3]
_CORPUS = _ROOT / "src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_036/files"
_REVISIONS = _ROOT / "src/cadrumo/_data/registry/aeat/modelos/036/revisions"

#: From ``[sources."aeat-dr-036-2023"]``. The run refuses any other binary.
DECLARED_SHA256 = "3ecea6c06e3d280d946c619f621efe64d5334ffd0da44568f0c85b2fc8923cf2"

RECORDS = ('Pag. 1', 'Pag. 2A', 'Pag. 2B', 'Pag. 2C', 'Pag. 3', 'Pag. 4', 'Pag. 5', 'Pag. 6', 'Pag. 7', 'Pag. 8', 'Pag. 9')

#: The nine box-number forms this design prints, enumerated from it rather than
#: widened to fit. Under the record-oriented default every one of them fell
#: through to a position range -- a real box number replaced by a fabricated slot
#: id, silently.
NUMBER_GRAMMAR = (
    r"\[((?:[A-Z]?\d{1,4}(?:bis)?[A-Z]?|\d{1,4}\.[a-z])"
    r"(?:\s*,\s*(?:[A-Z]?\d{1,4}(?:bis)?[A-Z]?))*)\]"
)

HEADERS = {
    'Pag. 1': """# Modelo 036 RECORD Pag. 1 -- declaracion censal de alta, modificacion y baja.
#
# Emitted from aeat-dr-036-2023, whose window runs 2023-01-01 to 2025-02-02.
#
# ONE CASILLA PER PRINTED NUMBER, NOT PER DESIGN ROW. AEAT splits every date
# into dia, mes and ano rows under a single number, and repeats whole blocks --
# Pag. 8 prints 800, 801, 818 and 859 four times each, once per repetition of
# the socio block. The 2025 edition settled this and says so in its own
# comments; emitting per row instead would have written 263 casillas sharing 85
# ids, which is valid TOML and wrong. Each comment states the group's whole span
# and every component it covers.
#
# THE 037 ASTERISK IS TRANSCRIBED, NOT NORMALISED. A trailing ' *' marks a field
# that could be informed on a modelo 037, which Orden HAC/1526/2024 suppressed
# effective 2025-02-03. The design's own legend gives it that meaning, so it is
# part of what AEAT printed for these years and it is not in the 2025 captions.
#
# NOT MODELLED: the identifier envelope, the reservado runs, the CRLF terminator
# and the tipo-declaracion discriminant.
#
# NOT CLAIMED: these casillas DECLARE the censo; none computes anything. Modelo
# 036 carries no formula family at all.""",
    'Pag. 2A': """# Modelo 036 RECORD Pag. 2A -- declaracion censal de alta, modificacion y baja.
#
# Emitted from aeat-dr-036-2023, whose window runs 2023-01-01 to 2025-02-02.
#
# ONE CASILLA PER PRINTED NUMBER, NOT PER DESIGN ROW. AEAT splits every date
# into dia, mes and ano rows under a single number, and repeats whole blocks --
# Pag. 8 prints 800, 801, 818 and 859 four times each, once per repetition of
# the socio block. The 2025 edition settled this and says so in its own
# comments; emitting per row instead would have written 263 casillas sharing 85
# ids, which is valid TOML and wrong. Each comment states the group's whole span
# and every component it covers.
#
# THE 037 ASTERISK IS TRANSCRIBED, NOT NORMALISED. A trailing ' *' marks a field
# that could be informed on a modelo 037, which Orden HAC/1526/2024 suppressed
# effective 2025-02-03. The design's own legend gives it that meaning, so it is
# part of what AEAT printed for these years and it is not in the 2025 captions.
#
# NOT MODELLED: the identifier envelope, the reservado runs, the CRLF terminator
# and the tipo-declaracion discriminant.
#
# NOT CLAIMED: these casillas DECLARE the censo; none computes anything. Modelo
# 036 carries no formula family at all.""",
    'Pag. 2B': """# Modelo 036 RECORD Pag. 2B -- declaracion censal de alta, modificacion y baja.
#
# Emitted from aeat-dr-036-2023, whose window runs 2023-01-01 to 2025-02-02.
#
# ONE CASILLA PER PRINTED NUMBER, NOT PER DESIGN ROW. AEAT splits every date
# into dia, mes and ano rows under a single number, and repeats whole blocks --
# Pag. 8 prints 800, 801, 818 and 859 four times each, once per repetition of
# the socio block. The 2025 edition settled this and says so in its own
# comments; emitting per row instead would have written 263 casillas sharing 85
# ids, which is valid TOML and wrong. Each comment states the group's whole span
# and every component it covers.
#
# THE 037 ASTERISK IS TRANSCRIBED, NOT NORMALISED. A trailing ' *' marks a field
# that could be informed on a modelo 037, which Orden HAC/1526/2024 suppressed
# effective 2025-02-03. The design's own legend gives it that meaning, so it is
# part of what AEAT printed for these years and it is not in the 2025 captions.
#
# NOT MODELLED: the identifier envelope, the reservado runs, the CRLF terminator
# and the tipo-declaracion discriminant.
#
# NOT CLAIMED: these casillas DECLARE the censo; none computes anything. Modelo
# 036 carries no formula family at all.""",
    'Pag. 2C': """# Modelo 036 RECORD Pag. 2C -- declaracion censal de alta, modificacion y baja.
#
# Emitted from aeat-dr-036-2023, whose window runs 2023-01-01 to 2025-02-02.
#
# ONE CASILLA PER PRINTED NUMBER, NOT PER DESIGN ROW. AEAT splits every date
# into dia, mes and ano rows under a single number, and repeats whole blocks --
# Pag. 8 prints 800, 801, 818 and 859 four times each, once per repetition of
# the socio block. The 2025 edition settled this and says so in its own
# comments; emitting per row instead would have written 263 casillas sharing 85
# ids, which is valid TOML and wrong. Each comment states the group's whole span
# and every component it covers.
#
# THE 037 ASTERISK IS TRANSCRIBED, NOT NORMALISED. A trailing ' *' marks a field
# that could be informed on a modelo 037, which Orden HAC/1526/2024 suppressed
# effective 2025-02-03. The design's own legend gives it that meaning, so it is
# part of what AEAT printed for these years and it is not in the 2025 captions.
#
# NOT MODELLED: the identifier envelope, the reservado runs, the CRLF terminator
# and the tipo-declaracion discriminant.
#
# NOT CLAIMED: these casillas DECLARE the censo; none computes anything. Modelo
# 036 carries no formula family at all.""",
    'Pag. 3': """# Modelo 036 RECORD Pag. 3 -- declaracion censal de alta, modificacion y baja.
#
# Emitted from aeat-dr-036-2023, whose window runs 2023-01-01 to 2025-02-02.
#
# ONE CASILLA PER PRINTED NUMBER, NOT PER DESIGN ROW. AEAT splits every date
# into dia, mes and ano rows under a single number, and repeats whole blocks --
# Pag. 8 prints 800, 801, 818 and 859 four times each, once per repetition of
# the socio block. The 2025 edition settled this and says so in its own
# comments; emitting per row instead would have written 263 casillas sharing 85
# ids, which is valid TOML and wrong. Each comment states the group's whole span
# and every component it covers.
#
# THE 037 ASTERISK IS TRANSCRIBED, NOT NORMALISED. A trailing ' *' marks a field
# that could be informed on a modelo 037, which Orden HAC/1526/2024 suppressed
# effective 2025-02-03. The design's own legend gives it that meaning, so it is
# part of what AEAT printed for these years and it is not in the 2025 captions.
#
# NOT MODELLED: the identifier envelope, the reservado runs, the CRLF terminator
# and the tipo-declaracion discriminant.
#
# NOT CLAIMED: these casillas DECLARE the censo; none computes anything. Modelo
# 036 carries no formula family at all.""",
    'Pag. 4': """# Modelo 036 RECORD Pag. 4 -- declaracion censal de alta, modificacion y baja.
#
# Emitted from aeat-dr-036-2023, whose window runs 2023-01-01 to 2025-02-02.
#
# ONE CASILLA PER PRINTED NUMBER, NOT PER DESIGN ROW. AEAT splits every date
# into dia, mes and ano rows under a single number, and repeats whole blocks --
# Pag. 8 prints 800, 801, 818 and 859 four times each, once per repetition of
# the socio block. The 2025 edition settled this and says so in its own
# comments; emitting per row instead would have written 263 casillas sharing 85
# ids, which is valid TOML and wrong. Each comment states the group's whole span
# and every component it covers.
#
# THE 037 ASTERISK IS TRANSCRIBED, NOT NORMALISED. A trailing ' *' marks a field
# that could be informed on a modelo 037, which Orden HAC/1526/2024 suppressed
# effective 2025-02-03. The design's own legend gives it that meaning, so it is
# part of what AEAT printed for these years and it is not in the 2025 captions.
#
# NOT MODELLED: the identifier envelope, the reservado runs, the CRLF terminator
# and the tipo-declaracion discriminant.
#
# NOT CLAIMED: these casillas DECLARE the censo; none computes anything. Modelo
# 036 carries no formula family at all.""",
    'Pag. 5': """# Modelo 036 RECORD Pag. 5 -- declaracion censal de alta, modificacion y baja.
#
# Emitted from aeat-dr-036-2023, whose window runs 2023-01-01 to 2025-02-02.
#
# ONE CASILLA PER PRINTED NUMBER, NOT PER DESIGN ROW. AEAT splits every date
# into dia, mes and ano rows under a single number, and repeats whole blocks --
# Pag. 8 prints 800, 801, 818 and 859 four times each, once per repetition of
# the socio block. The 2025 edition settled this and says so in its own
# comments; emitting per row instead would have written 263 casillas sharing 85
# ids, which is valid TOML and wrong. Each comment states the group's whole span
# and every component it covers.
#
# THE 037 ASTERISK IS TRANSCRIBED, NOT NORMALISED. A trailing ' *' marks a field
# that could be informed on a modelo 037, which Orden HAC/1526/2024 suppressed
# effective 2025-02-03. The design's own legend gives it that meaning, so it is
# part of what AEAT printed for these years and it is not in the 2025 captions.
#
# NOT MODELLED: the identifier envelope, the reservado runs, the CRLF terminator
# and the tipo-declaracion discriminant.
#
# NOT CLAIMED: these casillas DECLARE the censo; none computes anything. Modelo
# 036 carries no formula family at all.""",
    'Pag. 6': """# Modelo 036 RECORD Pag. 6 -- declaracion censal de alta, modificacion y baja.
#
# Emitted from aeat-dr-036-2023, whose window runs 2023-01-01 to 2025-02-02.
#
# ONE CASILLA PER PRINTED NUMBER, NOT PER DESIGN ROW. AEAT splits every date
# into dia, mes and ano rows under a single number, and repeats whole blocks --
# Pag. 8 prints 800, 801, 818 and 859 four times each, once per repetition of
# the socio block. The 2025 edition settled this and says so in its own
# comments; emitting per row instead would have written 263 casillas sharing 85
# ids, which is valid TOML and wrong. Each comment states the group's whole span
# and every component it covers.
#
# THE 037 ASTERISK IS TRANSCRIBED, NOT NORMALISED. A trailing ' *' marks a field
# that could be informed on a modelo 037, which Orden HAC/1526/2024 suppressed
# effective 2025-02-03. The design's own legend gives it that meaning, so it is
# part of what AEAT printed for these years and it is not in the 2025 captions.
#
# NOT MODELLED: the identifier envelope, the reservado runs, the CRLF terminator
# and the tipo-declaracion discriminant.
#
# NOT CLAIMED: these casillas DECLARE the censo; none computes anything. Modelo
# 036 carries no formula family at all.""",
    'Pag. 7': """# Modelo 036 RECORD Pag. 7 -- declaracion censal de alta, modificacion y baja.
#
# Emitted from aeat-dr-036-2023, whose window runs 2023-01-01 to 2025-02-02.
#
# ONE CASILLA PER PRINTED NUMBER, NOT PER DESIGN ROW. AEAT splits every date
# into dia, mes and ano rows under a single number, and repeats whole blocks --
# Pag. 8 prints 800, 801, 818 and 859 four times each, once per repetition of
# the socio block. The 2025 edition settled this and says so in its own
# comments; emitting per row instead would have written 263 casillas sharing 85
# ids, which is valid TOML and wrong. Each comment states the group's whole span
# and every component it covers.
#
# THE 037 ASTERISK IS TRANSCRIBED, NOT NORMALISED. A trailing ' *' marks a field
# that could be informed on a modelo 037, which Orden HAC/1526/2024 suppressed
# effective 2025-02-03. The design's own legend gives it that meaning, so it is
# part of what AEAT printed for these years and it is not in the 2025 captions.
#
# NOT MODELLED: the identifier envelope, the reservado runs, the CRLF terminator
# and the tipo-declaracion discriminant.
#
# NOT CLAIMED: these casillas DECLARE the censo; none computes anything. Modelo
# 036 carries no formula family at all.""",
    'Pag. 8': """# Modelo 036 RECORD Pag. 8 -- declaracion censal de alta, modificacion y baja.
#
# Emitted from aeat-dr-036-2023, whose window runs 2023-01-01 to 2025-02-02.
#
# ONE CASILLA PER PRINTED NUMBER, NOT PER DESIGN ROW. AEAT splits every date
# into dia, mes and ano rows under a single number, and repeats whole blocks --
# Pag. 8 prints 800, 801, 818 and 859 four times each, once per repetition of
# the socio block. The 2025 edition settled this and says so in its own
# comments; emitting per row instead would have written 263 casillas sharing 85
# ids, which is valid TOML and wrong. Each comment states the group's whole span
# and every component it covers.
#
# THE 037 ASTERISK IS TRANSCRIBED, NOT NORMALISED. A trailing ' *' marks a field
# that could be informed on a modelo 037, which Orden HAC/1526/2024 suppressed
# effective 2025-02-03. The design's own legend gives it that meaning, so it is
# part of what AEAT printed for these years and it is not in the 2025 captions.
#
# NOT MODELLED: the identifier envelope, the reservado runs, the CRLF terminator
# and the tipo-declaracion discriminant.
#
# NOT CLAIMED: these casillas DECLARE the censo; none computes anything. Modelo
# 036 carries no formula family at all.""",
    'Pag. 9': """# Modelo 036 RECORD Pag. 9 -- declaracion censal de alta, modificacion y baja.
#
# Emitted from aeat-dr-036-2023, whose window runs 2023-01-01 to 2025-02-02.
#
# ONE CASILLA PER PRINTED NUMBER, NOT PER DESIGN ROW. AEAT splits every date
# into dia, mes and ano rows under a single number, and repeats whole blocks --
# Pag. 8 prints 800, 801, 818 and 859 four times each, once per repetition of
# the socio block. The 2025 edition settled this and says so in its own
# comments; emitting per row instead would have written 263 casillas sharing 85
# ids, which is valid TOML and wrong. Each comment states the group's whole span
# and every component it covers.
#
# THE 037 ASTERISK IS TRANSCRIBED, NOT NORMALISED. A trailing ' *' marks a field
# that could be informed on a modelo 037, which Orden HAC/1526/2024 suppressed
# effective 2025-02-03. The design's own legend gives it that meaning, so it is
# part of what AEAT printed for these years and it is not in the 2025 captions.
#
# NOT MODELLED: the identifier envelope, the reservado runs, the CRLF terminator
# and the tipo-declaracion discriminant.
#
# NOT CLAIMED: these casillas DECLARE the censo; none computes anything. Modelo
# 036 carries no formula family at all.""",
}

#: Declared by no edition; declined at parity with the 2025 sibling.
SCOPE_DECLINED = {
        'Pag. 1': frozenset({
            'pag. 1.11-18',
            'pag. 1.207-246',
            'pag. 1.247-248',
            'pag. 1.249-250',
            'pag. 1.251-254',
            'pag. 1.255',
            'pag. 1.256-380',
            'pag. 1.491-500',
        }),
        'Pag. 2A': frozenset({
            'pag. 2a.10',
            'pag. 2a.1343-1347',
            'pag. 2a.1499-1503',
            'pag. 2a.178-182',
            'pag. 2a.1844',
            'pag. 2a.1845',
            'pag. 2a.1991-2000',
            'pag. 2a.334-338',
            'pag. 2a.790-793',
            'pag. 2a.840-844',
            'pag. 2a.996-1000',
        }),
        'Pag. 2B': frozenset({
            'B1,B2',
            'pag. 2b.10',
            'pag. 2b.1060-1064',
            'pag. 2b.1407-1411',
            'pag. 2b.1563-1567',
            'pag. 2b.1942',
            'pag. 2b.1943',
            'pag. 2b.1944',
            'pag. 2b.1945',
            'pag. 2b.2091-2100',
            'pag. 2b.242-246',
            'pag. 2b.398-402',
            'pag. 2b.904-908',
        }),
        'Pag. 2C': frozenset({
            'pag. 2c.10',
            'pag. 2c.1283',
            'pag. 2c.1284',
            'pag. 2c.1391-1400',
            'pag. 2c.314-318',
            'pag. 2c.470-474',
            'pag. 2c.639-643',
            'pag. 2c.795-799',
        }),
        'Pag. 3': frozenset({
            '300,301,302',
            '311,312',
            '350,351,352',
            '361,362',
            'pag. 3.10',
            'pag. 3.1191-1200',
            'pag. 3.480',
            'pag. 3.956',
        }),
        'Pag. 4': frozenset({
            'pag. 4.10',
            'pag. 4.135-136',
            'pag. 4.137-142',
            'pag. 4.246-251',
            'pag. 4.418-423',
            'pag. 4.590-595',
            'pag. 4.764-769',
            'pag. 4.891-900',
        }),
        'Pag. 5': frozenset({
            '517,529,549,573,561',
            '521,533,553,581,565',
            '525,537,557,585,569',
            '530,531',
            '534,538,542,546,570',
            '535,539,543,547,571',
            '536,540,544,548,572',
            '550,554,558,562,566',
            '551,555,559,563,567',
            '552,556,560,564,568',
            '579, 580',
            '582,583',
            '741,742',
            'pag. 5.10',
            'pag. 5.273',
            'pag. 5.371-380',
        }),
        'Pag. 6': frozenset({
            '604,605,606,607,615',
            '608,617',
            '609,610,611,612,619',
            '623,624,625,627',
            '613',
            '614',
            '630,631,632',
            '643,644,645,647',
            'pag. 6.10',
            'pag. 6.391-400',
        }),
        'Pag. 7': frozenset({
            '750,751',
            '755,756',
            '910,911',
            '912,913',
            'pag. 7.10',
            'pag. 7.391-400',
        }),
        'Pag. 8': frozenset({
            '802,803,804',
            '819,820',
            '821,822',
            '823,824',
            '825,826',
            'pag. 8.10',
            'pag. 8.1791-1800',
        }),
        'Pag. 9': frozenset({
            'pag. 9.10',
            'pag. 9.1291-1300',
        }),
}

#: Withheld pending adjudication. NOT the same claim as declined.
DEFERRED: dict[str, frozenset[str]] = {}

#: EIGHTEEN Pag. 9 SLOTS WHOSE BOX NUMBER THE EXTRACT LOST. The sheet prints
#: [921] through [943]; the bundled extract prints them with the opening bracket
#: missing -- ``921]`` -- so NUMBER_GRAMMAR could not see a number and the rows
#: fell through to a positional slot id and into the declined set, where they
#: read as a scope decision rather than the extraction artefact they are. The
#: 2025 edition declares all twenty-four of 920-943 (suc-a..suc-f), so these
#: eighteen carry their attributes from it like any other row.
#:
#: Declared here rather than by widening the grammar: making the opening bracket
#: optional also matches the tail of ``[330 332]`` on Pag. 3, a space-separated
#: number PAIR, and the generator refused on it. The alias is per-row and
#: asserts nothing about any other label.
PAG9_LOST_BRACKETS = {
    'pag. 9.20-144': '921',
    'pag. 9.145-149': '922',
    'pag. 9.150-163': '923',
    'pag. 9.223-347': '925',
    'pag. 9.348-352': '926',
    'pag. 9.353-366': '927',
    'pag. 9.426-550': '929',
    'pag. 9.551-555': '930',
    'pag. 9.556-569': '931',
    'pag. 9.629-753': '933',
    'pag. 9.754-758': '934',
    'pag. 9.759-772': '935',
    'pag. 9.832-956': '937',
    'pag. 9.957-961': '938',
    'pag. 9.962-975': '939',
    'pag. 9.1035-1159': '941',
    'pag. 9.1160-1164': '942',
    'pag. 9.1165-1178': '943',
}

#: TWO MORE Pag. 2A SLOTS WHOSE BRACKET THE EXTRACT MALFORMED DIFFERENTLY.
#: Neither is a missing opening bracket, and that is the point: the same silent
#: outcome has three separate causes on this design, so the fix is per row.
#:
#:   @11+1     "residente en Espana / no residente en Espana  [A1)" -- the
#:             bracket is OPENED and closed with a PARENTHESIS.
#:   @1033+100 "dominio o direccion de internet [ A38]" -- the bracket is
#:             intact and holds a LEADING SPACE, which the grammar disallows.
#:
#: Both print identically in the 2023 and 2025 designs, and the 2025 edition
#: declares both (pf.identificacion-residencia-indicador and
#: pf.identificacion-dominio-internet-secundario), so they carry at design
#: parity like any other row. A grammar made tolerant of either shape would
#: also re-admit the tail of "[330 332]" on Pag. 3, which must stay a slug.
PAG2A_MALFORMED_BRACKETS = {
    "pag. 2a.11": "A1",
    "pag. 2a.1033-1132": "A38",
}


#: THE TWO PROVEN RENUMBERINGS. This design prints [A3A] and [B3A]; the 2025
#: edition declares the same two concepts as A3B and B3B. These rows therefore
#: EMIT their own design's number and CARRY the successor's attributes, which is
#: what carry_number_aliases does and what plain number_aliases cannot: aliasing
#: the number outright would make this edition assert that its design prints
#: A3B, which is false.
#:
#: Proven rather than assumed, from a design pair this wave originally failed to
#: compare. The corpus holds TWO files for the 2025 edition, a provisional and a
#: final. The provisional still prints A3A and B3A where the final prints A3B
#: and B3B, at the same 1846/1848/1850 and 1946/1948/1950, the same 2/2/4
#: lengths, the same Num type and byte-identical captions. The label is the only
#: thing that changes and it changes inside one edition's own publication cycle.
#: A replacement would require the concept to move; nothing moves here.
PAG2AB_RENUMBERED = {
    "Pag. 2A": {"A3A": "A3B"},
    "Pag. 2B": {"B3A": "B3B"},
}


MODELO_036_2023_SPAN = WaveSpec(
    design_path=_CORPUS / "03-036-diseno-de-registro-del-modelo-m036-ejercicio-2023-y-siguientes-107-kb-xlsx.xlsx",
    prior_casillas_dir=_REVISIONS / "2025-02-03-y-siguientes/casillas",
    out_dir=_REVISIONS / "2023-hasta-2025-02-02/casillas",
    revision_id="2023-hasta-2025-02-02",
    legal_refs='["rd-1065-2007:art-11", "orden-eha-1274-2007:art-1"]',
    carry_legal_refs=True,
    records=RECORDS,
    headers=HEADERS,
    id_scheme="carried",
    prior_glob="*.toml",
    number_grammar=NUMBER_GRAMMAR,
    carry_number_aliases=PAG2AB_RENUMBERED,
    number_aliases={
        'Pag. 9': PAG9_LOST_BRACKETS,
        'Pag. 2A': PAG2A_MALFORMED_BRACKETS,
    },
    collapse_rows_by_number=True,
    scope_declined_numbers=SCOPE_DECLINED,
    deferred_numbers=DEFERRED,
    declared_sha256=DECLARED_SHA256,
)


def main() -> int:
    """Report the wave; pass --write to emit it."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    print(format_report(generate(MODELO_036_2023_SPAN, write=arguments.write)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
