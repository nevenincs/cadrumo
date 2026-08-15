"""Registry-build gate: an authored fixed-width layout must cover its official design.

:func:`~._validate_export_exemption.validate_export_exemption_declarations`
refuses a revision that declares NO export layout. It cannot tell a complete
layout from a tenth of one, because it never reads the official record design:
it asks only whether the registry declared *something*. Modelo 714 is the worked
case -- five revisions each declaring 127 fields across 10 records against a
bundled AEAT design carrying 1,200+ positions across 12 records, two of which
(the ``714-00`` file envelope and ``714-Ingreso o Devolución``, which carries
forma de pago, IBAN and importe del ingreso) are not authored at all. It passed.
A filing generated from it would carry a blank NIF, a blank name, a blank IBAN
and a blank resumen block behind a perfectly valid digest.

This module closes that. For every revision declaring a fixed-width export
layout, it reads the official bundled design that layout itself cites and
refuses when a position the design requires has no authored slot.

What counts as required, and why it is read from the design
-----------------------------------------------------------

A fixed-width record is CONTIGUOUS: AEAT declares its whole byte extent and the
file carries every byte of it. So a position the layout does not declare is not
"optional", it is a datum the application can never write -- the slot emits fill
and the operator gets a structurally thin record behind a valid digest. The
default is therefore that every position is required, and omissibility must be
something the DESIGN says, never something a per-modelo allowlist asserts:

* a position AEAT marks ``OBLIGATORIO`` in its own obligatoriness column is
  required, and that marking overrides every omissibility signal below;
* a position AEAT reserves for itself ("Reservado para la Administración",
  "RESERVADO PARA LA A.E.A.T.") is omissible -- the filer must not write it;
* a position AEAT declares as fill ("BLANCOS", "Sin contenido", a blank
  constant) is omissible -- there is no datum there.

Everything else is required. Measured over the eighteen bundled designs backing
a fixed-width layout: 570 positions marked obligatorio, 266 administration-
reserved, 29 declared fill, 8,297 ordinary data positions.

Joining an authored record to its design sheet
----------------------------------------------

The registry declares no link between an authored ``ExportRecordDefinition`` and
the design sheet it renders, and the two vocabularies do not correspond: Modelo
714 writes ``record_type = "714-01"`` against a sheet named
``714-01 Patrimonio``, Modelo 390 writes ``page_01`` against ``Pág. 1``, Modelo
145 writes ``communication`` against ``PDF record design``, and Modelo 720's
records carry no discriminating name at all. **Matching those by name would be
inventing a mapping**, and a wrong mapping produces confident refusals against
positions the layout does write.

So the join is made on CONTENT, which is where a fixed-width record's identity
actually lives: AEAT declares each record's discriminating constants ("Constante
``<T``", "Constante ``714``", "Constante ``01000``") at exact offsets, and the
authored record declares the same bytes as ``literal`` fields. A record joins a
sheet when their declared constants agree at shared coordinates and contradict
at none, and the sheet takes the record whose agreement count is a unique
maximum.

**Where the join cannot be established the check does not guess and does not
pass.** It falls back to asking whether ANY record of the layout writes the
coordinate -- a strictly weaker question that can only under-report, never
over-report -- and the refusal says which mode produced it, so a reader is never
left thinking a fallback verdict is a per-record one. This is why an
unjoinable design still yields a usable, honest verdict rather than an
authoritative-looking wrong one.

A partial read never produces a pass
------------------------------------

:func:`~._record_design.extract_record_design` returns what it could read
alongside what it could not, and
:meth:`~._record_design_schema.RecordDesignExtraction.accept_partial` tolerates
the difference. The off-load-path coverage inventory in
``_record_design_coverage`` deliberately takes that tolerance, and its own
docstring records why: tightening it would make Modelo 232's legitimately
skipped ``TABLAS`` lookup tab refuse the whole modelo.

**This gate does not share that tolerance and does not need to.** It calls
:meth:`~._record_design_schema.RecordDesignExtraction.require_complete` and
converts the refusal into its own diagnostic, because a design whose record body
was skipped understates the modelo and would hand back an inflated coverage
figure that nothing downstream could tell from a real one -- the exact false
green this gate exists to remove. Modelo 232 is unaffected because it declares
no fixed-width layout and never reaches here; the tolerance in the advisory
instrument is left exactly as it was, for the consumer whose blast radius it was
written about.

An unreachable design binary is likewise a refusal, not a skip. The corpus
binaries live in the mandatory ``cadrumo_data`` companion namespace, so
"unreadable" is a broken installation rather than a supported configuration, and
reporting completeness over a file nobody read is the one outcome this module
must never produce.

See Also:
    :func:`~._validate_export_exemption.validate_export_exemption_declarations`
        The sibling that refuses a revision declaring no layout at all.
    :func:`~._record_design.extract_record_design`
        The official-design reader, and the completeness contract it returns.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from ....core import ExportLayoutFormat
from ....core.resources import resolve_corpus_binary
from .._export_field_kind import CasillaFieldKind
from ._errors import RegistryValidationError
from ._export import derive_export_layouts_from_bindings
from ._record_design import extract_record_design
from ._record_design_schema import RecordDesignField, RecordDesignSheet
from ._schema import ExportLayoutDefinition, ExportRecordDefinition, ModeloRevision, SourceReference

#: AEAT's own obligatoriness marking, read from the column its designs head
#: ``Oblig.`` (which the parser lands in ``RecordDesignField.validation``).
#: Matched with word boundaries so a prose "no obligatorio" elsewhere in a
#: validation cell is not mistaken for the marking itself.
_OBLIGATORIO: Final = re.compile(r"\bOBLIGATORI[OA]\b", re.IGNORECASE)

#: A position AEAT reserves for its own use. The filer must NOT write it, so its
#: absence from an authored layout is correct rather than a gap.
#:
#: Read from the field's DESCRIPTION only -- never from its validation or
#: contenido prose, which is where the word appears innocently. Modelo 720's
#: ``TIPO DE DERECHO REAL SOBRE INMUEBLE`` (25 bytes of taxpayer data) explains
#: itself with "se deberá indicar en el espacio reservado", and scanning that
#: prose excused a real datum from the check -- a silent pass, which is the one
#: direction this gate must never fail in. AEAT names an administration slot in
#: the description itself ("RESERVADO PARA LA A.E.A.T.", "Reservado para la
#: Administración"), so the description carries every genuine case.
_ADMINISTRATION_RESERVED: Final = re.compile(r"\breservad[oa]s?\b", re.IGNORECASE)

#: A position AEAT declares as fill rather than as a datum. Anchored to the whole
#: cell: a description that merely MENTIONS blancos while carrying a real field
#: ("Rellenar con blancos si no hay importe") still holds a datum, and matching
#: it loosely would excuse a slot that carries one.
_DECLARED_FILL: Final = re.compile(
    r"^\W*(?:constante\W{0,3})?(?:blancos?|sin\s+contenido|no\s+utilizad[oa]s?|libre)\W*$",
    re.IGNORECASE,
)

#: One record-discriminating constant, as AEAT quotes it in a design's
#: ``Contenido`` cell (``Constante "714"``, ``Constante '1'.``, ``Constante
#: «720».``). ONLY the quoted spelling is read: an unquoted "Constante 2021" or
#: "Constante. Blanco" does not delimit its own value, and guessing where the
#: value ends would put a wrong anchor into the join.
_QUOTED_CONSTANT: Final = re.compile(
    "[Cc]onstante\\W{0,3}[\"'«“‘]([^\"'»«”’‘“]{1,40})[\"'»”’]",
)

#: How many missing positions one sheet enumerates before the message says how
#: many more there are. The bundled design is the exhaustive worklist; this
#: message is the entry point into it, and a refusal listing a thousand
#: coordinates is one nobody reads.
_ENUMERATED_PER_RECORD: Final = 8


@dataclass(frozen=True, slots=True)
class _RequiredPosition:
    """One official position an authored layout must be able to write."""

    sheet: str
    offset: int
    length: int
    description: str
    obligatorio: bool


def _omissible_reason(field: RecordDesignField) -> str | None:
    """Return why the DESIGN says this position may go unwritten, else ``None``.

    Obligatoriness wins outright: a position AEAT marks ``OBLIGATORIO`` is
    required even when its description also mentions reserved space or fill,
    because the marking is the authority's direct statement about that slot and
    the prose around it is not.

    Every signal is read from the cell that NAMES the field, never from the
    explanatory prose beside it. An omissibility signal is the only thing here
    that can turn a real gap into a pass, so it is deliberately the hardest
    thing to trip.
    """
    if _OBLIGATORIO.search(field.validation or ""):
        return None
    if _ADMINISTRATION_RESERVED.search(field.description or ""):
        return "reserved for the Administración"
    for text in (field.description, field.content):
        if text and _DECLARED_FILL.match(text.strip()):
            return "declared fill"
    return None


def _required_positions(sheet: RecordDesignSheet) -> tuple[_RequiredPosition, ...]:
    return tuple(
        _RequiredPosition(
            sheet=sheet.name,
            offset=field.offset,
            length=field.length,
            description=field.description,
            obligatorio=bool(_OBLIGATORIO.search(field.validation or "")),
        )
        for field in sheet.fields
        if _omissible_reason(field) is None
    )


def _sheet_constants(sheet: RecordDesignSheet) -> dict[tuple[int, int], str]:
    """Return the discriminating constants AEAT declares, by exact coordinate."""
    constants: dict[tuple[int, int], str] = {}
    for field in sheet.fields:
        for text in (field.content, field.description):
            if not text:
                continue
            matched = _QUOTED_CONSTANT.search(text)
            if matched is not None:
                constants[(field.offset, field.length)] = matched.group(1).strip()
                break
    return constants


def _record_literals(record: ExportRecordDefinition) -> dict[tuple[int, int], str]:
    return {
        (field.offset, field.length): field.literal
        for field in record.fields
        if field.kind is CasillaFieldKind.LITERAL
        and field.literal is not None
        and field.offset is not None
        and field.length is not None
    }


def _record_written_positions(record: ExportRecordDefinition) -> set[tuple[int, int]]:
    return {
        (field.offset, field.length) for field in record.fields if field.offset is not None and field.length is not None
    }


def _join_record(
    sheet: RecordDesignSheet,
    records: Sequence[ExportRecordDefinition],
) -> ExportRecordDefinition | None:
    """Return the one authored record whose declared constants identify this sheet.

    Agreement is counted only over coordinates BOTH sides declare a constant at,
    and any contradiction there disqualifies the record outright -- Modelo 714's
    ``714-02`` writes ``"02000"`` where the ``714-01`` sheet declares ``"01000"``,
    which is precisely the byte AEAT uses to tell the two records apart.

    A unique maximum is required. Modelo 390's page records all agree on ``<T``
    and ``390``, so a merely-nonzero agreement would match every page to every
    sheet; the page discriminator breaks the tie, and where nothing does, the
    sheet stays unjoined rather than taking an arbitrary winner.
    """
    constants = _sheet_constants(sheet)
    if not constants:
        return None
    scored: list[tuple[int, ExportRecordDefinition]] = []
    for record in records:
        literals = _record_literals(record)
        shared = constants.keys() & literals.keys()
        if not shared:
            continue
        if any(constants[key] != literals[key] for key in shared):
            continue
        scored.append((len(shared), record))
    if not scored:
        return None
    best = max(score for score, _ in scored)
    winners = [record for score, record in scored if score == best]
    return winners[0] if len(winners) == 1 else None


def _design_sources(
    layout: ExportLayoutDefinition,
    source_refs: Mapping[str, SourceReference],
) -> tuple[SourceReference, ...]:
    return tuple(
        source
        for ref in layout.source_refs
        if (source := source_refs.get(ref)) is not None and source.kind == "record_design"
    )


def _read_design_sheets(source: SourceReference) -> tuple[RecordDesignSheet, ...] | str:
    """Return the source's sheets, or the reason no complete design could be read.

    ``require_complete`` rather than ``accept_partial``: a coverage figure
    derived from a partly-read design is inflated by exactly the records that
    were dropped, and nothing downstream can tell that from real coverage.
    """
    path = resolve_corpus_binary(*source.corpus_path.split("/"))
    if path is None:
        return (
            f"its official record design {source.id!r} ({source.corpus_path!r}) is not reachable in "
            f"this installation, so its coverage cannot be verified. The corpus binaries ship in the "
            f"mandatory cadrumo_data companion namespace; an unreachable design is a broken "
            f"installation, and reporting a layout complete against a file nobody read is the one "
            f"outcome this gate must never produce"
        )
    try:
        return extract_record_design(path).require_complete()
    except RegistryValidationError as exc:
        return (
            f"its official record design {source.id!r} could not be read in full, so its coverage "
            f"cannot be verified: {exc}. A coverage figure derived from a partly-read design is "
            f"inflated by exactly the records that were dropped"
        )


def _missing_report(
    sheets: Sequence[RecordDesignSheet],
    records: Sequence[ExportRecordDefinition],
) -> tuple[int, int, list[str]]:
    """Return ``(required, missing, per-sheet lines)`` for one design against one layout."""
    layout_written: set[tuple[int, int]] = set()
    for record in records:
        layout_written |= _record_written_positions(record)
    required_total = 0
    missing_total = 0
    lines: list[str] = []
    for sheet in sheets:
        required = _required_positions(sheet)
        required_total += len(required)
        joined = _join_record(sheet, records)
        written = _record_written_positions(joined) if joined is not None else layout_written
        missing = [position for position in required if (position.offset, position.length) not in written]
        missing_total += len(missing)
        if not missing:
            continue
        if joined is not None:
            scope = f"authored record {joined.id!r} (record_type {joined.record_type!r})"
        else:
            scope = (
                "NO authored record could be identified for this design record, so the check fell "
                "back to asking whether any record of the layout writes the coordinate -- a weaker "
                "question, so this count is a floor, not the whole gap"
            )
        shown = ", ".join(
            f"@{position.offset}+{position.length} "
            f"{'[OBLIGATORIO] ' if position.obligatorio else ''}{position.description!r}"
            for position in missing[:_ENUMERATED_PER_RECORD]
        )
        remainder = (
            f" and {len(missing) - _ENUMERATED_PER_RECORD} more" if len(missing) > _ENUMERATED_PER_RECORD else ""
        )
        lines.append(
            f"design record {sheet.name!r}: {len(missing)} of {len(required)} required positions "
            f"unwritten by {scope}; {shown}{remainder}"
        )
    return required_total, missing_total, lines


def _layout_failure(
    *,
    prefix: str,
    layout: ExportLayoutDefinition,
    source_refs: Mapping[str, SourceReference],
) -> str | None:
    design_sources = _design_sources(layout, source_refs)
    if not design_sources:
        return (
            f"{prefix}: fixed-width export layout {layout.id!r} cites no official record-design "
            f"source, so nothing states what a complete layout for it would contain and its "
            f"completeness cannot be verified. Cite the modelo's bundled Diseño de Registros in the "
            f"layout's source_refs"
        )
    sheets: list[RecordDesignSheet] = []
    for source in design_sources:
        read = _read_design_sheets(source)
        if isinstance(read, str):
            return f"{prefix}: fixed-width export layout {layout.id!r} cannot be checked because {read}"
        sheets.extend(read)
    required, missing, lines = _missing_report(sheets, layout.records)
    if not missing:
        return None
    coverage = 100.0 * (required - missing) / required if required else 0.0
    return (
        f"{prefix}: fixed-width export layout {layout.id!r} writes only {required - missing} of the "
        f"{required} positions its official record design requires ({coverage:.1f}% coverage), so a "
        f"filing generated from it would carry fill where AEAT expects data -- behind a digest that "
        f"is valid, because a digest locks bytes and asserts nothing about completeness. Required "
        f"means every position of the official design except the ones the design ITSELF declares "
        f"omissible (reserved for the Administración, or declared fill); a position AEAT marks "
        f"OBLIGATORIO is required regardless. There is no percentage floor and no exemption: author "
        f"the missing positions from the design at "
        f"{', '.join(repr(source.corpus_path) for source in design_sources)}. " + " | ".join(lines)
    )


def validate_export_layout_record_coverage(
    *,
    prefix: str,
    revision: ModeloRevision,
    source_refs: Mapping[str, SourceReference],
) -> list[str]:
    """Refuse every fixed-width layout that cannot write its official design.

    Resolves the revision's layouts the way snapshot build does -- through
    :func:`derive_export_layouts_from_bindings`, so binding-derived record fields
    count as written -- and checks each fixed-width one against the bundled AEAT
    record design it cites.

    A revision declaring no fixed-width layout yields nothing here. Modelo 100
    and Modelo 390's XML-dictionary siblings file through a dictionary and have
    no positional design to be measured against, and Modelo 720 assembles its
    records from ``binding_record`` selectors that
    :func:`derive_export_layouts_from_bindings` materialises before this runs.
    The revision that declares NO layout at all is the sibling gate's subject,
    not this one's: reporting it here too would put a second count into
    circulation for one defect.

    Failures accumulate rather than raising, so one load reports every
    incomplete layout instead of the first, and one failure covers one layout so
    the enumeration stays a worklist rather than a wall.

    Args:
        prefix: Caller-supplied ``modelo N revision R`` diagnostic prefix.
        revision: The :class:`ModeloRevision` under validation.
        source_refs: The registry source catalogue, keyed by source ID, used to
            resolve each layout's cited record-design binary.

    Returns:
        Accumulated diagnostics; empty when every fixed-width layout writes
        every position its official design requires.
    """
    failures: list[str] = []
    for layout in derive_export_layouts_from_bindings(revision):
        if layout.format is not ExportLayoutFormat.FIXED_WIDTH:
            continue
        failure = _layout_failure(prefix=prefix, layout=layout, source_refs=source_refs)
        if failure is not None:
            failures.append(failure)
    return failures


__all__ = ["validate_export_layout_record_coverage"]
