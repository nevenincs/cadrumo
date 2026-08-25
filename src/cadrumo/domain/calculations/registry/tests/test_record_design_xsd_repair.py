"""Prove the record-design XSD escape repair is sound, load-bearing, and complete.

The soundness property under test is that the repair only ever makes a pattern
MORE permissive. That is what lets a repaired schema serve as a validation
oracle: every violation it reports is a true violation.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from lxml import etree

from .record_design_xsd_support import (
    SchemaCompilationError,
    bundled_modelo_100_xsds,
    compilerecord_design_schema,
    compilerecord_design_schemas,
    repair_xsd_regex_escapes,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MIDDLE_DOT = "·"
_GEMINADA_PATTERN = re.compile(
    r'<xs:simpleType name="tipo_Nombre48L">.*?<xs:pattern\s+value="([^"]*)"',
    re.DOTALL,
)


def _schema_text(xsd: Path) -> str:
    return xsd.read_bytes().decode("iso-8859-1")


def _compiles_unrepaired(xsd: Path) -> bool:
    """Compile the schema exactly as AEAT ships it."""
    raw = re.sub(r'encoding="[^"]+"', 'encoding="UTF-8"', _schema_text(xsd), count=1)
    try:
        etree.XMLSchema(etree.fromstring(raw.encode("utf-8")))
    except etree.LxmlError:
        return False
    return True


def _single_pattern_schema(pattern_value: str) -> etree.XMLSchema:
    """Wrap one pattern in a minimal schema so values can be validated against it."""
    document = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
        '<xs:element name="v"><xs:simpleType><xs:restriction base="xs:string">'
        f'<xs:pattern value="{pattern_value}"/>'
        "</xs:restriction></xs:simpleType></xs:element></xs:schema>"
    )
    return etree.XMLSchema(etree.fromstring(document.encode("utf-8")))


def _accepts(schema: etree.XMLSchema, candidate: str) -> bool:
    return bool(schema.validate(etree.fromstring(f"<v>{candidate}</v>".encode())))


def test_the_bundled_schemas_are_discoverable() -> None:
    """The corpus every assertion below reads is present.

    Without this, a corpus that failed to resolve would make the compile
    assertions pass over an empty set.
    """
    xsds = bundled_modelo_100_xsds()

    assert len(xsds) == 6, f"expected six bundled Modelo 100 XSDs, found {[p.name for p in xsds]}"
    for xsd in xsds:
        assert _schema_text(xsd).strip(), f"{xsd.name} is empty"


def test_the_repair_is_load_bearing_for_exactly_the_schemas_that_need_it() -> None:
    """A schema fails to compile as shipped if and only if the repair changes it.

    This is the anti-tautology control. It states a relation rather than a count,
    so an AEAT corpus refresh that fixes some or all of the schemas keeps it
    honest instead of reddening it spuriously -- but it still proves the repair
    does real work, because it asserts at least one schema needs repairing.
    """
    needs_repair = {xsd for xsd in bundled_modelo_100_xsds() if repair_xsd_regex_escapes(_schema_text(xsd))[1]}
    fails_as_shipped = {xsd for xsd in bundled_modelo_100_xsds() if not _compiles_unrepaired(xsd)}

    assert needs_repair, "no bundled schema carries an illegal escape; this repair would be dead code"
    assert needs_repair == fails_as_shipped, (
        "the set of schemas needing repair diverged from the set that fails to compile: "
        f"needs repair {sorted(p.name for p in needs_repair)}, "
        f"fails as shipped {sorted(p.name for p in fails_as_shipped)}"
    )


def test_every_bundled_schema_compiles_after_repair() -> None:
    """The escape is the only libxml2 incompatibility in the bundled corpus.

    Asserts which schemas compiled, not merely how many: a count alone cannot
    tell six of six from six attempts with four silently skipped.
    """
    xsds = bundled_modelo_100_xsds()

    compiled = compilerecord_design_schemas(xsds)

    assert set(compiled) == set(xsds), (
        f"compiled a different set than requested; missing {sorted(p.name for p in set(xsds) - set(compiled))}"
    )
    assert all(schema is not None for schema in compiled.values()), "a requested schema mapped to no compiled schema"


def test_the_repair_is_a_byte_level_no_op_on_a_schema_that_already_compiles() -> None:
    """A schema with no illegal escape is returned untouched.

    The repair therefore cannot narrow a schema that already works, which is the
    strongest available evidence that it does not perturb valid patterns.
    """
    untouched = [xsd for xsd in bundled_modelo_100_xsds() if _compiles_unrepaired(xsd)]

    assert untouched, "no bundled schema compiles as shipped; this control cannot discriminate"
    for xsd in untouched:
        original = _schema_text(xsd)
        repaired, repairs = repair_xsd_regex_escapes(original)
        assert repairs == 0
        assert repaired == original


def test_the_repair_only_deletes_backslashes() -> None:
    """Every edit removes one backslash and changes nothing else.

    This is the structural half of the permissiveness proof: no branch, class
    member, or quantifier can be lost if the only deleted characters are
    backslashes that preceded a character XSD regex forbids escaping.
    """
    for xsd in bundled_modelo_100_xsds():
        original = _schema_text(xsd)
        repaired, repairs = repair_xsd_regex_escapes(original)

        assert len(repaired) == len(original) - repairs, f"{xsd.name} changed by more than backslash removal"
        assert repaired.replace("\\", "") == original.replace("\\", ""), (
            f"{xsd.name} lost or gained a non-backslash character"
        )
        assert repaired.count("\\" + _MIDDLE_DOT) == 0


def test_legal_escapes_survive_the_repair() -> None:
    """Escapes XSD regex does permit are preserved, not stripped along with the rest."""
    document = '<xs:pattern value="([A-Z]|\\s|\\.|\\-|\\(|\\)|\\\\|\\d|\\p{L}|\\' + _MIDDLE_DOT + ')+"/>'

    repaired, repairs = repair_xsd_regex_escapes(document)

    assert repairs == 1
    for legal in ("\\s", "\\.", "\\-", "\\(", "\\)", "\\d", "\\p{L}"):
        assert legal in repaired, f"legal escape {legal!r} was stripped"
    assert "\\" + _MIDDLE_DOT not in repaired


def test_the_repaired_pattern_accepts_the_geminada_and_still_refuses_out_of_class() -> None:
    """The escaped character becomes acceptable literally, without opening the pattern up.

    The plain-name case is the positive control: if it ever stops accepting, the
    probe is broken rather than the schema strict, and every refusal below would
    be meaningless.
    """
    needing_repair = [xsd for xsd in bundled_modelo_100_xsds() if not _compiles_unrepaired(xsd)]
    assert needing_repair, "no schema needs repair; this control cannot discriminate"

    repaired, _ = repair_xsd_regex_escapes(_schema_text(needing_repair[0]))
    match = _GEMINADA_PATTERN.search(repaired)
    assert match is not None, "tipo_Nombre48L carries no xs:pattern; the corpus shape changed"
    schema = _single_pattern_schema(match.group(1))

    assert _accepts(schema, "PUJOL"), "positive control failed: a plain uppercase name must validate"
    assert _accepts(schema, f"PARAL{_MIDDLE_DOT}LEL"), "the repaired pattern still rejects the geminada"
    assert not _accepts(schema, "AB@CD"), "the repair made the pattern accept an out-of-class character"
    assert not _accepts(schema, "jose"), "the repair widened the pattern beyond its declared case"


def test_compiling_a_set_refuses_to_return_a_partial_result(tmp_path: Path) -> None:
    """A schema that cannot compile fails the whole call rather than shrinking the set.

    Returning the schemas that happened to work would validate a smaller surface
    than the caller believes it covers -- the defect this helper exists to close.
    """
    broken = tmp_path / "broken.xsd"
    broken.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
        '<xs:element name="v" type="xs:NoSuchType"/>'
        "</xs:schema>",
        encoding="utf-8",
    )
    requested = (*bundled_modelo_100_xsds(), broken)

    with pytest.raises(SchemaCompilationError) as excinfo:
        compilerecord_design_schemas(requested)

    message = str(excinfo.value)
    assert f"compiled {len(requested) - 1} of {len(requested)}" in message
    assert "broken.xsd" in message


def test_compiling_an_empty_set_refuses() -> None:
    """An empty compile set would report success while covering nothing."""
    with pytest.raises(SchemaCompilationError, match="empty compile set proves nothing"):
        compilerecord_design_schemas(())


def test_compiling_one_schema_names_the_file_it_could_not_repair(tmp_path: Path) -> None:
    """A single-schema failure identifies the schema, not just the libxml2 error."""
    broken = tmp_path / "unrepairable.xsd"
    broken.write_text("<not-a-schema/>", encoding="utf-8")

    with pytest.raises(SchemaCompilationError, match=re.escape("unrepairable.xsd")):
        compilerecord_design_schema(broken)
