"""Shared support for compiling AEAT record-design XSDs as validation oracles.

AEAT ships four of the six bundled Modelo 100 schemas with an invalid regular
expression: a backslash before U+00B7 MIDDLE DOT, the character in the Catalan
``l·l`` geminada, inside the ``tipo_ApeNom`` name-pattern family. XML Schema
regular expressions (XML Schema Part 2, Appendix F) permit an escape only
before a metacharacter or a recognised class letter, so libxml2 refuses the
whole schema and the 2020, 2021, 2024 and 2025 exercises will not compile as
shipped. Only 2022 and 2023 do.

A gate that compiles these schemas without handling that will silently cover
two of six revisions while appearing to cover all six, which is why
:func:`compile_record_design_schemas` refuses to return a short set rather than
reporting one.

The module is public rather than underscored because it is consumed from outside
this package: the filing export gate validates a rendered declaration against the
same compiled schemas. A cross-package consumer may not reach a private module,
and duplicating the compilation would put a second repair authority beside this
one, so the oracle is named publicly and shared.

The repair is deliberately split from the compilation. :func:`repair_xsd_regex_escapes`
is a pure text transformation that needs no XML toolchain, so its soundness
property is provable on its own; only :func:`compile_record_design_schema` needs
``lxml``, which it imports lazily.

Using the redacted submission fixture
-------------------------------------
``tests/fixtures/aeat-sede/submitted-files/modelo-100-2023-0A-redacted.xml`` is
the only real AEAT submission in the tree, and it is a sound STRUCTURAL oracle
and a dangerous VALUE one. Validating it against the 2023 schema yields exactly
15 errors, every one a facet or enumeration failure on a redacted value and NOT
ONE structural: element order, nesting and cardinality all hold, which is what
makes it trustworthy for shape and worthless for content.

Its redactor stamped each field's ordinal position into the placeholder it
wrote, formatted to the field's type -- ``SANITIZED_IDIOMA_1``,
``SANITIZED_DP_APENOM_D_5``, ``SANITIZED_TIPODECLARACION_88``, and for the
numeric fields the bare ordinal. So ``VERSION`` reads ``2.02`` only because
VERSION is the second field, not because the submission declares schema version
2.02. The proof is in its siblings: ``ECIVIL`` holds ``6`` where the schema
permits ``[1-4]`` and ``CL`` holds ``15`` where it enumerates ``1``-``5``. Values
outside their own declared range cannot be real, so every value in this fixture
is generated filler.

A gate consuming this fixture should therefore expect those 15 facet errors as
its baseline and assert the structural-error count is zero. Reading any value
out of it -- most temptingly the version -- reads the field's position instead.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast

from .....core.directory_scan import scan_directory
from .....core.resources import bundled_path

if TYPE_CHECKING:
    from lxml.etree import XMLSchema

__all__ = [
    "MODELO_100_XSD_ROOT",
    "SchemaCompilationError",
    "bundled_modelo_100_xsds",
    "compile_record_design_schema",
    "compile_record_design_schemas",
    "repair_xsd_regex_escapes",
]

MODELO_100_XSD_ROOT: Final = bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_100", "files")

# The characters an XSD regex escape may legally precede: the metacharacters of
# Appendix F, plus the single-letter character-class escapes. Anything else
# after a backslash is invalid and is what this module repairs.
_XSD_ESCAPABLE_METACHARACTERS: Final = frozenset(r".\?*+{}()[]|-^")
_XSD_CLASS_ESCAPE_LETTERS: Final = frozenset("nrtsSiIcCdDwWpP")

_ESCAPE = re.compile(r"\\(.)", re.DOTALL)
_ENCODING_DECLARATION = re.compile(r'encoding="[^"]+"')
_PATTERN_VALUE = re.compile(r'(<xs:pattern\s+value=")((?:[^"\\]|\\.)*)(")')


class SchemaCompilationError(RuntimeError):
    """Raised when a record-design schema set does not compile in full."""


def bundled_modelo_100_xsds() -> tuple[Path, ...]:
    """Return every bundled Modelo 100 record-design XSD, oldest filename first."""
    return scan_directory(MODELO_100_XSD_ROOT, pattern="*esquema-xsd*.xsd")


def _repair_pattern_value(value: str) -> str:
    """Drop backslashes that escape a character XSD regex does not allow escaping."""

    def unescape(match: re.Match[str]) -> str:
        escaped = cast(str, match.group(1))
        if escaped in _XSD_ESCAPABLE_METACHARACTERS or escaped in _XSD_CLASS_ESCAPE_LETTERS:
            return match.group(0)
        return escaped

    return _ESCAPE.sub(unescape, value)


def repair_xsd_regex_escapes(schema_text: str) -> tuple[str, int]:
    """Return ``schema_text`` with illegal ``xs:pattern`` escapes removed, and the repair count.

    Soundness
    ---------
    The transformation only ever makes a pattern MORE permissive, and that is
    what lets a repaired schema serve as an oracle: every violation it reports
    is a true violation, though it may miss some.

    The reason is local. Each edit rewrites ``\\X`` to ``X`` where ``X`` is a
    character XSD regex forbids escaping, so the sequence has no valid reading
    to narrow. Both positions such a sequence can occupy accept a superset
    afterwards: as an alternation branch it becomes the literal ``X`` where it
    previously denoted nothing legal, and inside a character class it adds
    ``X`` as a member and removes none. No edit deletes a branch, a class
    member, or a quantifier, so the repaired pattern accepts every string the
    original could have matched under any valid reading, plus ``X`` literally.

    A schema carrying no illegal escape is returned byte-identical with a count
    of zero, so the repair cannot perturb a schema that already compiles.

    Args:
        schema_text: The decoded XSD document.

    Returns:
        The repaired document and the number of escapes removed.
    """
    repairs = 0

    def repair(match: re.Match[str]) -> str:
        nonlocal repairs
        prefix, value, suffix = match.group(1), match.group(2), match.group(3)
        repaired_value = _repair_pattern_value(value)
        if repaired_value != value:
            repairs += len(_ESCAPE.findall(value)) - len(_ESCAPE.findall(repaired_value))
        return f"{prefix}{repaired_value}{suffix}"

    return _PATTERN_VALUE.sub(repair, schema_text), repairs


def _decoded(xsd: Path) -> str:
    """Return the schema text, normalised so a re-encoded document still parses."""
    raw = xsd.read_bytes().decode("iso-8859-1")
    return _ENCODING_DECLARATION.sub('encoding="UTF-8"', raw, count=1)


def compile_record_design_schema(xsd: Path) -> XMLSchema:
    """Compile one record-design XSD, repairing AEAT's illegal escapes first.

    Args:
        xsd: Path to a bundled record-design schema.

    Returns:
        The compiled schema, usable as a validation oracle.

    Raises:
        SchemaCompilationError: when the schema does not compile even repaired.
    """
    from lxml import etree

    repaired, _ = repair_xsd_regex_escapes(_decoded(xsd))
    try:
        return etree.XMLSchema(etree.fromstring(repaired.encode("utf-8")))
    except etree.LxmlError as exc:
        raise SchemaCompilationError(f"{xsd.name} does not compile even after escape repair: {exc}") from exc


def compile_record_design_schemas(xsds: Iterable[Path]) -> Mapping[Path, XMLSchema]:
    """Compile every schema in ``xsds``, refusing to return a partial set.

    A caller that silently accepted fewer compiled schemas than it asked for
    would validate a smaller surface than it reports covering, so a single
    failure fails the whole call and names every schema that did not compile.

    Args:
        xsds: The schemas to compile.

    Returns:
        Each requested path mapped to its compiled schema.

    Raises:
        SchemaCompilationError: when any schema fails, or when none were given.
    """
    requested = tuple(xsds)
    if not requested:
        raise SchemaCompilationError("no schemas requested; an empty compile set proves nothing")

    compiled: dict[Path, XMLSchema] = {}
    failures: list[str] = []
    for xsd in requested:
        try:
            compiled[xsd] = compile_record_design_schema(xsd)
        except SchemaCompilationError as exc:
            failures.append(str(exc))

    if failures:
        raise SchemaCompilationError(
            f"compiled {len(compiled)} of {len(requested)} record-design schemas; failures: " + "; ".join(failures),
        )
    return compiled
