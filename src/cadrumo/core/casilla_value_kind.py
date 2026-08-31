"""Closed vocabulary for how an observed casilla value is meant to be read.

An observed casilla value is stored as text, because the carrier is evidence of
the ARTEFACT and text preserves the token AEAT actually wrote. Text alone cannot
say how to read it, so every consumer that wanted a number re-derived that by
attempting the conversion — and a conversion attempt is not a type test. On a
real Modelo 100 artefact two casillas answered that attempt with a plausible
wrong number: ``0065`` (clave, free text) parses as ``15`` and ``0167`` (epígrafe
IAE, free text) parses as ``22``. Neither is an amount, and nothing about the
token says so.

The parser already knows. It decides, from the AEAT dictionary row type or the
export field's declared ``data_type``, whether it is reading a number, a token,
or a yes/no marker — and then discards that decision by stringifying. This enum
is that decision carried forward, so a reader asks what the value IS rather than
guessing from what it looks like.

Not to be confused with two neighbouring vocabularies:

- ``ExportFieldDefinition.data_type`` is the registry's AUTHORING vocabulary for
  a fixed-width field (``money``, ``integer``, ``date``, ...). It is finer than
  this enum and describes the layout; this one describes how a value already read
  out of an artefact should be interpreted.
- ``ExtractionTargetDefinition.value_kind`` (``amount``/``text``/``enum``) is a
  PARSE DIRECTIVE for the declaration-PDF extractor, telling it how to read a
  captured token. It feeds this enum rather than duplicating it.
"""

from __future__ import annotations

from enum import StrEnum


class CasillaValueKind(StrEnum):
    """How the value on an observed casilla is meant to be read.

    Members carry the exact tokens the persisted carrier stores, so a member
    compares, hashes, and JSON-serialises identically to the string it replaces.
    """

    NUMERIC = "numeric"
    """An amount or count; the only kind a Decimal reader may accept.

    The stored text is the parser's own decimal rendering, not the artefact's
    spelling, because a fixed-width money field is written zero-padded and scaled
    by 100 and the padded form would enrol a hundredfold error.
    """

    TEXT = "text"
    """A free-text or coded field: an address, a referencia catastral, an IAE
    epígrafe, a date token, a modelo code.

    Some of these parse cleanly as decimals and mean nothing as numbers, which is
    the reason this enum exists rather than a try/except at each reader.
    """

    BOOLEAN = "boolean"
    """A yes/no marker, stored as the token AEAT wrote (``S``/``N``, ``0``/``1``).

    The AEAT token is kept rather than a Python ``bool`` repr, so ``1`` here is a
    marker and not the quantity one — a distinction a bare decimal reader loses.
    """


__all__ = ["CasillaValueKind"]
