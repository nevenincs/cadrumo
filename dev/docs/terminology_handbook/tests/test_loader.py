"""Strict round-trip, derivation, and validation tests for the loader.

There is no external numeric oracle for terminology, so these tests
prove STRUCTURE: a populated multi-language multi-term concept fragment
round-trips through the loader into a strict frozen
:class:`~dev.docs.terminology_handbook.ConceptRecord` with every field preserved
(every defaultable field set non-default); ``narrower`` is derived from
authored ``broader`` inverses; malformed and partial fragments raise; and
the validation-hook seam runs supplied validators over the assembled
handbook.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from cadrumo.core.concept_lifecycle import ConceptLifecycle
from cadrumo.core.modelo import Modelo
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.external_constants import OutputLanguage

from .. import (
    ConceptDomain,
    GrammaticalGender,
    PartOfSpeech,
    TerminologyHandbook,
    TermStatus,
    load_bundled_terminology_handbook,
    load_terminology_handbook,
)
from ..errors import TerminologyLoadError, TerminologyValidationError
from ._support import write_concept_fragment

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


_FULL_FRAGMENT = """
[concept]
concept_id = "recargo-equivalencia"
domain = "regimen"
lifecycle = "deprecated"
domain_refs = ["modelo:303", "modelo:390"]
legal_refs = ["ley-37-1992:art-148", "ley-37-1992:art-154"]
broader = ["iva"]
related = ["modulos"]
created_at = 2024-01-02
updated_at = 2026-06-09

[concept.seed_provenance]
source = "ubterm"
attribution = "UBTERM Diccionari de fiscalitat (Universitat de Barcelona), CC BY 3.0"
source_entry_id = "fisc-0421"

[language.es]
short_description = "Regimen especial de IVA para comerciantes minoristas."
definition = "Regimen especial para comerciantes minoristas: el proveedor repercute un recargo ademas del IVA."
scope_note = "Solo aplica a quienes cumplen los requisitos de minorista del articulo 149 LIVA."

[language.es.source]
citation = "Articulos 148 a 163 de la Ley 37/1992 del IVA."
authority = "boe"

[[language.es.term]]
label = "recargo de equivalencia"
term_status = "preferred"
part_of_speech = "noun"
grammatical_gender = "masculine"

[[language.es.term]]
label = "RE"
term_status = "admitted"
part_of_speech = "abbreviation"
hidden_search_forms = ["recargo equivalencia", "recargo de equiv"]

[language.en]
short_description = "A special VAT regime for retail traders."
definition = "A special VAT regime for individual retail traders: the supplier charges a surcharge on top of VAT."

[language.en.source]
citation = "Articles 148 to 163 of Law 37/1992 on VAT."
authority = "boe"

[[language.en.term]]
label = "equivalence surcharge"
term_status = "preferred"
part_of_speech = "phrase"
"""

_BROADER_PARENT = """
[concept]
concept_id = "iva"
domain = "concepto"
lifecycle = "approved"
created_at = 2024-01-01
updated_at = 2024-01-01

[language.es]
short_description = "Impuesto sobre el valor anadido."

[[language.es.term]]
label = "IVA"
term_status = "preferred"
part_of_speech = "abbreviation"
"""


def test_full_fragment_round_trips_with_every_field_preserved(tmp_path: Path) -> None:
    concepts = write_concept_fragment(tmp_path, "recargo-equivalencia.toml", _FULL_FRAGMENT)
    write_concept_fragment(tmp_path, "iva.toml", _BROADER_PARENT)

    handbook = load_terminology_handbook(concepts)
    record = handbook.concept("recargo-equivalencia")

    assert record.concept_id == "recargo-equivalencia"
    assert record.domain is ConceptDomain.REGIMEN
    assert record.lifecycle is ConceptLifecycle.DEPRECATED
    assert record.domain_refs == ("modelo:303", "modelo:390")
    assert record.legal_refs == ("ley-37-1992:art-148", "ley-37-1992:art-154")
    assert record.broader == ("iva",)
    assert record.related == ("modulos",)
    assert record.replaced_by is None
    assert record.created_at == date(2024, 1, 2)
    assert record.updated_at == date(2026, 6, 9)

    assert record.seed_provenance is not None
    assert record.seed_provenance.source == "ubterm"
    assert record.seed_provenance.source_entry_id == "fisc-0421"
    assert "CC BY 3.0" in record.seed_provenance.attribution

    assert record.language_codes == (OutputLanguage.ES, OutputLanguage.EN)
    es = record.section(OutputLanguage.ES)
    assert es.short_description.startswith("Regimen especial")
    assert es.definition is not None and "minoristas" in es.definition
    assert es.scope_note is not None and "articulo 149" in es.scope_note
    assert es.source is not None and es.source.authority == "boe"

    preferred = es.terms[0]
    assert preferred.label == "recargo de equivalencia"
    assert preferred.term_status is TermStatus.PREFERRED
    assert preferred.part_of_speech is PartOfSpeech.NOUN
    assert preferred.grammatical_gender is GrammaticalGender.MASCULINE

    abbrev = es.terms[1]
    assert abbrev.term_status is TermStatus.ADMITTED
    assert abbrev.part_of_speech is PartOfSpeech.ABBREVIATION
    assert abbrev.hidden_search_forms == ("recargo equivalencia", "recargo de equiv")


def test_record_is_frozen(tmp_path: Path) -> None:
    concepts = write_concept_fragment(tmp_path, "iva.toml", _BROADER_PARENT)
    handbook = load_terminology_handbook(concepts)
    record = handbook.concept("iva")
    with pytest.raises((TypeError, ValueError)):
        record.lifecycle = ConceptLifecycle.RETIRED  # type: ignore[misc]


def test_scalar_casilla_domain_ref_is_rejected(tmp_path: Path) -> None:
    """Casilla domain refs must not reintroduce a combined scalar notation."""
    casilla_id: CasillaId = validated_casilla_id("00029", surface="terminology handbook fixture")
    legacy_ref = ":".join(("casilla", Modelo.M303.value, casilla_id))
    fragment = _BROADER_PARENT.replace(
        'domain = "concepto"',
        f'domain = "concepto"\ndomain_refs = ["{legacy_ref}"]',
    )
    concepts = write_concept_fragment(tmp_path, "iva.toml", fragment)

    with pytest.raises(TerminologyValidationError, match="scalar casilla references"):
        load_terminology_handbook(concepts)


def test_narrower_is_derived_from_broader_inverse(tmp_path: Path) -> None:
    concepts = write_concept_fragment(tmp_path, "recargo-equivalencia.toml", _FULL_FRAGMENT)
    write_concept_fragment(tmp_path, "iva.toml", _BROADER_PARENT)

    handbook = load_terminology_handbook(concepts)

    parent = handbook.concept("iva")
    child = handbook.concept("recargo-equivalencia")
    assert child.broader == ("iva",)
    assert parent.narrower == ("recargo-equivalencia",)
    # The child carries no derived narrower (it has no children).
    assert child.narrower == ()
    # broader_edges exposes the pre-inversion authoring edges for the seam.
    assert handbook.broader_edges["recargo-equivalencia"] == ("iva",)
    assert handbook.broader_edges["iva"] == ()


def test_authored_narrower_is_rejected(tmp_path: Path) -> None:
    fragment = _BROADER_PARENT.replace(
        'lifecycle = "approved"',
        'lifecycle = "approved"\nnarrower = ["recargo-equivalencia"]',
    )
    concepts = write_concept_fragment(tmp_path, "iva.toml", fragment)
    with pytest.raises(TerminologyValidationError, match="narrower"):
        load_terminology_handbook(concepts)


def test_retired_without_replaced_by_raises(tmp_path: Path) -> None:
    fragment = _BROADER_PARENT.replace('lifecycle = "approved"', 'lifecycle = "retired"')
    concepts = write_concept_fragment(tmp_path, "iva.toml", fragment)
    with pytest.raises(TerminologyValidationError, match="replaced_by"):
        load_terminology_handbook(concepts)


def test_two_preferred_terms_in_one_language_raises(tmp_path: Path) -> None:
    fragment = (
        _BROADER_PARENT
        + """
[[language.es.term]]
label = "impuesto sobre el valor anadido"
term_status = "preferred"
"""
    )
    concepts = write_concept_fragment(tmp_path, "iva.toml", fragment)
    with pytest.raises(TerminologyValidationError, match="preferred"):
        load_terminology_handbook(concepts)


def test_duplicate_concept_id_across_fragments_raises(tmp_path: Path) -> None:
    # Two fragments declaring the same concept_id necessarily differ in filename,
    # so the filename-matches-concept_id guard catches the collision first (a
    # duplicate can only exist via a filename mismatch). Either refusal is correct.
    concepts = write_concept_fragment(tmp_path, "iva.toml", _BROADER_PARENT)
    (concepts / "iva-copy.toml").write_text(_BROADER_PARENT, encoding="utf-8")
    with pytest.raises(TerminologyValidationError, match=r"named|duplicate"):
        load_terminology_handbook(concepts)


def test_filename_not_matching_concept_id_raises(tmp_path: Path) -> None:
    # A fragment whose filename differs from its concept_id would fork into a
    # duplicate file on the next curation write (the write path resolves by
    # concept_id), so the loader refuses the mismatch up front.
    concepts = write_concept_fragment(tmp_path, "wrong-name.toml", _BROADER_PARENT)  # concept_id is "iva"
    with pytest.raises(TerminologyValidationError, match="must be named"):
        load_terminology_handbook(concepts)


def test_missing_short_description_raises(tmp_path: Path) -> None:
    fragment = "\n".join(line for line in _BROADER_PARENT.splitlines() if not line.startswith("short_description"))
    concepts = write_concept_fragment(tmp_path, "iva.toml", fragment)
    with pytest.raises(TerminologyValidationError):
        load_terminology_handbook(concepts)


def test_concept_without_language_section_raises(tmp_path: Path) -> None:
    fragment = """
[concept]
concept_id = "huerfano"
domain = "concepto"
lifecycle = "draft"
created_at = 2026-06-10
updated_at = 2026-06-10
"""
    concepts = write_concept_fragment(tmp_path, "huerfano.toml", fragment)
    with pytest.raises(TerminologyValidationError, match="language"):
        load_terminology_handbook(concepts)


def test_invalid_toml_raises_load_error(tmp_path: Path) -> None:
    concepts = write_concept_fragment(tmp_path, "broken.toml", "this is = not [valid toml")
    with pytest.raises(TerminologyLoadError):
        load_terminology_handbook(concepts)


def test_empty_concepts_dir_raises(tmp_path: Path) -> None:
    concepts = tmp_path / "concepts"
    concepts.mkdir()
    with pytest.raises(TerminologyLoadError, match="no concept fragments"):
        load_terminology_handbook(concepts)


def test_validation_hook_seam_runs_supplied_validators(tmp_path: Path) -> None:
    concepts = write_concept_fragment(tmp_path, "iva.toml", _BROADER_PARENT)
    seen: list[str] = []

    def _record_ids(handbook: TerminologyHandbook) -> None:
        seen.extend(sorted(handbook.by_id))

    def _reject(_: TerminologyHandbook) -> None:
        raise TerminologyValidationError("seam rejected")

    load_terminology_handbook(concepts, validators=[_record_ids])
    assert seen == ["iva"]

    with pytest.raises(TerminologyValidationError, match="seam rejected"):
        load_terminology_handbook(concepts, validators=[_reject])


def test_bundled_handbook_compiles_and_derives_narrower() -> None:
    handbook = load_bundled_terminology_handbook()
    ids = set(handbook.by_id)
    assert {"prorrata", "prorrata-especial", "casilla"} <= ids

    prorrata = handbook.concept("prorrata")
    especial = handbook.concept("prorrata-especial")
    assert especial.broader == ("prorrata",)
    assert "prorrata-especial" in prorrata.narrower

    # The exemplar prorrata concept grounds its legal_refs against real
    # provisions and carries all four language sections.
    assert "ley-37-1992:art-104" in prorrata.legal_refs
    assert set(prorrata.language_codes) == {
        OutputLanguage.ES,
        OutputLanguage.EN,
        OutputLanguage.CA,
        OutputLanguage.HU,
    }
    es = prorrata.section(OutputLanguage.ES)
    assert any(term.term_status is TermStatus.PREFERRED for term in es.terms)
