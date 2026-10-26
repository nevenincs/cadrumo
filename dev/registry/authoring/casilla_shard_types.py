"""Canonical casilla shard generation outcomes and authoring input."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


class GenerationRefusedError(Exception):
    """The design, the prior edition or the emission did not hold up."""


@dataclass(frozen=True)
class WaveSpec:
    """One revision's authoring run, declared rather than passed piecemeal."""

    design_path: Path
    prior_casillas_dir: Path
    out_dir: Path
    revision_id: str
    legal_refs: str
    records: tuple[str, ...]
    headers: Mapping[str, str]
    #: Section vocabulary for records whose rows have no prior counterpart.
    #: A record absent from this mapping cannot adjudicate: its unmatched rows
    #: are refused, which is the correct outcome for a record nobody has judged.
    adjudicated_sections: Mapping[str, tuple[str, ...]] = field(default_factory=dict[str, tuple[str, ...]])
    #: Records whose unnumbered rows are deliberately left undeclared, holding
    #: the scope line an earlier edition drew. Widening scope inside a
    #: carry-forward run is how an edition acquires rows nobody adjudicated.
    scope_skip_unnumbered: frozenset[str] = frozenset()
    #: Declared sha256 of the design binary, from the registry's own source
    #: catalogue. The run refuses a design that is not the artifact the
    #: registry cites.
    declared_sha256: str | None = None
    ratio_lengths: frozenset[int] = frozenset({5, 6})
    #: How a row that has no counterpart in the prior edition gets its ``id``.
    #:
    #: ``"segmento_number"`` builds it as ``<SEGMENTO>:<number>``, the convention
    #: on modelos whose every casilla belongs to a named record sheet.
    #:
    #: ``"carried"`` can mint none of its own, so an unmatched row is refused even
    #: where the wave declares a section. Modelo 036 names its casillas with
    #: editorial slugs -- ``pf.identificacion-residencia-indicador`` beside
    #: ``number = "A1"``, with no segmento at all -- and modelo 280 with a
    #: per-record stem unrelated to its sheet name. A slug encodes a section path
    #: and a chosen concept name; no design states one, so no generator may
    #: invent one.
    id_scheme: str = "segmento_number"
    #: Positional-id stem per record, where the sheet's own name will not do.
    #:
    #: An unnumbered slot takes its position range as its number, prefixed by a
    #: stem. The record-oriented designs name their sheets ``T22007000`` and the
    #: lowercased name is the stem. Modelo 280 names its sheets
    #: ``Tipo 1 - Registro De Declarante`` while its corpus uses ``tipo1``, so
    #: the derived number would carry spaces and a hyphen and match nothing in
    #: the edition being carried forward.
    record_stems: Mapping[str, str] = field(default_factory=dict[str, str])
    #: Carry each row's ``legal_refs`` from the prior edition instead of applying
    #: the wave-level list.
    #:
    #: Off by default, because a carried legal_ref can name an orden that does
    #: not reach the new edition's period -- the exact defect being repaired on
    #: modelo 190 right now. On by default would be silent; opt-in makes the wave
    #: say it checked. Where a row has no prior counterpart the wave list applies
    #: regardless, since there is nothing to carry.
    carry_legal_refs: bool = False
    #: Rows the design's reader hoisted out of a desglose group, declared per
    #: record as ``{parent_offset: (child_offset, ...)}``.
    #:
    #: A record whose sub-rows surface beside their own parent does not tile, and
    #: the generator refuses it. This is the ONLY way past that refusal, and it is
    #: deliberately a declaration rather than a heuristic: a heuristic that nests
    #: any contained span would also nest a genuine overlap defect, which is the
    #: thing the tiling check exists to find.
    #:
    #: Declaring a group asserts the author read the design and confirmed the
    #: nesting AEAT printed. Modelo 280's Tipo 2 needs one: AEAT writes "se
    #: subdivide en dos" over 176-186, which is really three parts (176 SIGNO,
    #: 177-184 ENTERO, 185-186 DECIMAL), so the reader's count clause declines the
    #: repair and leaves the two grandchildren at the surface.
    declared_desglose_parents: Mapping[str, Mapping[int, tuple[int, ...]]] = field(
        default_factory=dict[str, dict[int, tuple[int, ...]]]
    )
    #: How the prior edition's shards are found, as a glob with ``{segmento}``.
    #:
    #: The record-oriented default narrows by record because a box number is only
    #: unique WITHIN a record -- modelo 220 prints ``00562`` on three different
    #: ones -- so globbing the whole directory would collide. Modelo 280 names its
    #: shards after their casillas rather than their record and prefixes every
    #: number with its own record instead, so it globs everything and relies on
    #: the number for uniqueness.
    prior_glob: str = "c{segmento}+*.toml"
    #: Derived-number to prior-number aliases, per record.
    #:
    #: Some editions name a slot for what it MEANS rather than where it sits --
    #: modelo 280's declarante NIF is ``tipo1.nif-declarante``, not
    #: ``tipo1.9-17``. No positional rule can produce that name, so matching it is
    #: an author's assertion that the slot at these bytes is that concept, and it
    #: is declared here rather than guessed by resemblance.
    number_aliases: Mapping[str, Mapping[str, str]] = field(default_factory=dict[str, dict[str, str]])
    #: Renumbered rows: the number to LOOK UP in the prior edition, per record.
    #:
    #: Distinct from ``number_aliases``, which rewrites the number a row is
    #: EMITTED under. This one changes only where the prior edition's attributes
    #: are fetched from, leaving the emitted number as this design prints it.
    #:
    #: The difference is the whole point on a renumbering. Modelo 036's 2023
    #: design prints ``[A3A]`` and the 2025 edition declares the same concept as
    #: ``A3B`` -- same offsets, same lengths, same type, byte-identical captions,
    #: with the token changing between a PROVISIONAL and a FINAL file of that one
    #: edition, which is a relabelling rather than a concept moving. Aliasing the
    #: number outright would make this edition assert that its own design prints
    #: A3B, which is false. The row must say A3A and carry A3B's attributes.
    carry_number_aliases: Mapping[str, Mapping[str, str]] = field(default_factory=dict[str, dict[str, str]])
    #: Offsets deliberately left undeclared, per record.
    #:
    #: ``scope_skip_unnumbered`` is useless on a design where NOTHING is numbered;
    #: this names the individual slots instead. Modelo 280's Tipo 2 echoes the
    #: declarante's ejercicio and NIF from Tipo 1 and its prior edition declares
    #: no casilla for either, which is a scope line to hold, not a gap to fill.
    scope_skip_positions: Mapping[str, frozenset[int]] = field(default_factory=dict[str, frozenset[int]])
    #: The box-number grammar this design actually prints, as a regex with one
    #: capturing group, applied to the bracket token's INNER text.
    #:
    #: Default is the record-oriented one: three to six digits. Modelo 036 prints
    #: nine forms against that one -- ``[101]``, ``[65]``, ``[A31]``, ``[B3A]``,
    #: ``[716.a]``, ``[4774bis]``, ``[300,301,302]``, ``[379, 380]``, ``[B1,B2]``
    #: -- and a wave that does not declare them gets a REFUSAL on every row, not
    #: a silent position range. Widening the default instead would loosen every
    #: other modelo's grammar to admit whatever the loosest one needs.
    number_grammar: str | None = None
    #: Collapse design rows that share a box number into ONE casilla.
    #:
    #: A casilla is a CONCEPT, and some designs print one concept across several
    #: fixed-width rows. Modelo 036 splits every date into día, mes and año rows
    #: under a single number, and repeats whole blocks -- Pag. 8 prints numbers
    #: 800, 801, 818 and 859 four times each at a regular stride, once per
    #: repetition of the socio block. Its authored edition declares one casilla
    #: per number and says so in its own comments ("ONE casilla over the dia, mes
    #: and ano components, all printed under the single number 805").
    #:
    #: Off by default. Emitting per row on such a design does not fail loudly --
    #: it writes several casillas carrying the SAME id, which is caught only when
    #: the modelo is loaded, after the write.
    collapse_rows_by_number: bool = False
    #: Numbers the wave declines to declare, per record, listed one by one.
    #:
    #: An enumeration rather than a flag, deliberately. "Decline whatever has no
    #: counterpart in the prior edition" would also swallow the rows that need
    #: judgement -- a renumbered box looks exactly like an undeclared one from the
    #: matcher's side. Listing them means a row that appears later, or one whose
    #: number changes, REFUSES instead of joining the declined set unnoticed.
    #:
    #: Declining is a scope decision and belongs in the revision's own prose too;
    #: this field only stops the generator refusing what the author already
    #: judged.
    scope_declined_numbers: Mapping[str, frozenset[str]] = field(default_factory=dict[str, frozenset[str]])
    #: Numbers withheld because they need a judgement nobody has made yet.
    #:
    #: SEPARATE from ``scope_declined_numbers`` on purpose, and the distinction is
    #: the point rather than bookkeeping: "excluded at parity with the prior
    #: edition" and "awaiting adjudication" are different claims about the same
    #: absence, and collapsing them is exactly the silent under-declaration this
    #: corpus refuses everywhere else. A declined number is a decision; a deferred
    #: one is an open question, and it is reported as such so it cannot quietly
    #: become permanent.
    deferred_numbers: Mapping[str, frozenset[str]] = field(default_factory=dict[str, frozenset[str]])


@dataclass(frozen=True)
class RecordOutcome:
    """What one record sheet produced."""

    segmento: str
    filename: str
    emitted: int
    carried: int
    adjudicated: int
    out_of_scope: int
    tiled: int
    declared_total: int
    body: str


@dataclass
class GenerationReport:
    """Everything the run decided, including what it declined to decide."""

    outcomes: list[RecordOutcome] = field(default_factory=list)
    #: Shards in out_dir this run does not reproduce. Not refused: a wave may
    #: legitimately share a directory with rows it does not own -- modelo 220's
    #: two declaration headers sit in their own shard the money-closure wave
    #: never writes. Reported because the other cause is a shard left stale by a
    #: rename, and that one is a defect.
    orphaned_shards: list[str] = field(default_factory=list)
    #: Attested fields carried forward from rows already on disk -- fields this
    #: generator does not emit and cannot re-derive. Reported so a re-run that
    #: silently dropped them would show as a zero here rather than as nothing.
    attestations_restored: int = 0
    drift: list[str] = field(default_factory=list)
    #: Numbers withheld pending a judgement, reported so an open question cannot
    #: quietly become a permanent absence.
    deferred: list[str] = field(default_factory=list)
    #: Rows whose Contenido changed while the caption held. Reported apart from
    #: caption drift because they are different findings: a rewritten caption is
    #: a relabelling, a rewritten Contenido is usually a changed admissible
    #: domain -- a clave added, a conditional rule altered.
    content_drift: list[str] = field(default_factory=list)
    refusals: list[str] = field(default_factory=list)

    @property
    def total_emitted(self) -> int:
        """Return the number of casillas emitted across all records."""
        return sum(outcome.emitted for outcome in self.outcomes)
