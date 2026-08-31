"""Modelo 840's casillas declare their byte position, and every one is real.

WHY THIS FILE EXISTS. Modelo 840 has no export layout yet, so nothing in the
tree consumes a casilla-to-position attribution. It nonetheless HAS one: each
casilla in this revision is preceded by a comment naming the exact span AEAT
gives it, in the form ``# @530+1, type_code An. Clase de cuota ... [33].``. That
attribution is the whole input a future semantic map needs, and until this
module it was prose -- unparsed, unchecked, and free to drift from the design it
claims to describe.

WHAT IS ASSERTED. Every declared span resolves against the BUNDLED design, and
no two casillas claim the same bytes. Resolution allows a contiguous RUN of
design fields, not only a single one, because at least one casilla is
deliberately modelled that way: ``act.fecha-inicio-variacion-cese`` spans
``@810+8``, which AEAT prints as three fields -- ``@810+2`` day, ``@812+2``
month, ``@814+4`` year. Requiring a single field would fail that casilla for
being modelled the way its author documented.

WHAT IS NOT ASSERTED. Not every casilla carries a comment: ``decl.ejercicio``
and ``decl.tipo-declaracion`` are positioned in their fragment's header prose
instead. This module checks the claims that are MADE rather than requiring every
casilla to make one, so it cannot be satisfied by deleting comments -- the
anti-vacuity guard below is what stops that.

THE GROUND TRUTH IS THE DESIGN, NOT THIS FILE. No offset is typed here. Every
expectation is read from the bundled ``aeat-dr-840`` PDF, so the assertion is
"the comments agree with AEAT" rather than "the comments agree with a number
someone copied into a test".
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from .....core.resources._boundary import bundled_path
from ..record_design import extract_record_design
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CASILLAS = Path("src/cadrumo/_data/registry/aeat/modelos/840/revisions/2003-y-siguientes/casillas")
#: ``# @530+1, ...`` -- the span comment AEAT's own column order is copied into.
_SPAN = re.compile(r"^#\s*@(?P<offset>\d+)\+(?P<length>\d+)\b")
#: A bracketed casilla number as AEAT prints it in a design description.
_TAG = re.compile(r"\[(\d+)\]")
_ID = re.compile(r'^id = "(?P<id>[^"]+)"$')
#: Below this the parse has broken and every assertion would pass vacuously.
_MINIMUM_DECLARED = 100


def _declared_spans() -> dict[str, tuple[int, int]]:
    """Return ``casilla id -> (offset, length)`` as the fragments declare it."""
    spans: dict[str, tuple[int, int]] = {}
    for fragment in sorted(_CASILLAS.glob("*.toml")):
        pending: tuple[int, int] | None = None
        for raw in fragment.read_text(encoding="utf-8").splitlines():
            span = _SPAN.match(raw)
            if span is not None:
                pending = (int(span.group("offset")), int(span.group("length")))
                continue
            identifier = _ID.match(raw)
            if identifier is not None and pending is not None:
                spans[identifier.group("id")] = pending
                pending = None
    return spans


def _design_runs() -> dict[tuple[int, int], list[str]]:
    """Return every span the design JUSTIFIES: one field, or one tagged group.

    A single field always justifies its own span. A multi-field run justifies one
    only when every field in it carries the SAME bracketed casilla tag, which is
    AEAT's own signal that the fields are one box: the day, month and year of
    ``Fecha de inicio, variacion, cese u otras causas`` are each tagged ``[62]``,
    while ``Clase de cuota`` is ``[33]`` and the ``Provincial (provincia) Tabla``
    beside it is tagged not at all.

    Two earlier rules were wrong and are recorded because each failed silently.
    Admitting every tiling run made the span check unable to fail: the design
    tiles almost completely, so nearly any boundary-to-boundary span resolved.
    Requiring an identical description then rejected the real composite, whose
    three fields differ by the trailing ``Dia`` / ``Mes`` / ``Ano``.
    """
    _, catalogues = _committed_registry_tree()
    extraction = extract_record_design(bundled_path() / catalogues.sources["aeat-dr-840"].corpus_path)
    runs: dict[tuple[int, int], list[str]] = {}
    for sheet in extraction.sheets:
        fields = sorted(sheet.fields, key=lambda field: field.offset)
        for start in range(len(fields)):
            offset = fields[start].offset
            group = frozenset(_TAG.findall(fields[start].description or ""))
            length = 0
            for step in range(start, len(fields)):
                if fields[step].offset != offset + length:
                    break  # a hole ends the run; a run must tile
                same = frozenset(_TAG.findall(fields[step].description or "")) == group
                if step > start and not (group and same):
                    break  # only a shared, present tag continues a group
                length += fields[step].length
                runs.setdefault((offset, length), []).append(sheet.name)
    return runs


def test_every_declared_position_is_a_real_span_in_the_design() -> None:
    declared = _declared_spans()
    assert len(declared) >= _MINIMUM_DECLARED, (
        f"only {len(declared)} span comments parsed; the fragment format has changed "
        "and every assertion in this module would pass without checking anything"
    )

    runs = _design_runs()
    unreal = {casilla: span for casilla, span in declared.items() if span not in runs}

    assert not unreal, "these casillas claim bytes AEAT's design does not lay out that way: " + ", ".join(
        f"{c} @{o}+{n}" for c, (o, n) in sorted(unreal.items())
    )


def test_no_two_casillas_claim_the_same_bytes() -> None:
    """A duplicated span means two casillas would write over each other.

    Separate from the check above because a span can be perfectly real and still
    be claimed twice, and that error is invisible to a per-casilla test.
    """
    declared = _declared_spans()
    assert len(declared) >= _MINIMUM_DECLARED

    claimants: dict[tuple[int, int], list[str]] = {}
    for casilla, span in declared.items():
        claimants.setdefault(span, []).append(casilla)
    shared = {span: sorted(ids) for span, ids in claimants.items() if len(ids) > 1}

    assert not shared, "these byte spans are claimed by more than one casilla: " + "; ".join(
        f"@{o}+{n} by {ids}" for (o, n), ids in sorted(shared.items())
    )


def test_a_multi_field_span_is_accepted_only_where_the_fields_tile() -> None:
    """The run tolerance must not degrade into "any offset with any length".

    Without this, ``_design_runs`` could admit a span that starts at a real
    field and runs past a hole, and the first test would stop distinguishing a
    documented composite from a fabricated one.
    """
    runs = _design_runs()
    composite = (810, 8)

    assert composite in runs, "the documented day/month/year composite must resolve"
    assert (810, 7) not in runs, "a length that stops mid-field must not resolve"
    assert (811, 8) not in runs, "a span starting mid-field must not resolve"
    assert (530, 3) not in runs, (
        "a run spanning two DIFFERENTLY tagged fields must not resolve: @530 is "
        "Clase de cuota [33] and @531 is the Provincial Tabla, which carries no "
        "tag at all. Admitting it is what made the first assertion unable to fail"
    )
