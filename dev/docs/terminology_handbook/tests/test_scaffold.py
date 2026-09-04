"""Real-behaviour tests for the msgmerge three-outcome scaffold engine.

The PRESERVE anti-clobber proof is the whole point of the step: a curated
concept's prose must survive a re-scaffold byte-for-byte. Tests use a
controlled candidate set for determinism plus one pass over the real
enrolment sources.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import iter_directory
from cadrumo.core.external_constants import OutputLanguage

from .._enrolment import EnrolmentCandidate, SeedLabel, collect_enrolment_candidates
from .._scaffold import ScaffoldAction, build_scaffold_plan, scaffold_handbook
from .._serialize import serialise_concept
from ..enums import ConceptDomain
from ..errors import TerminologyValidationError
from ..loader import load_terminology_handbook
from ._support import write_concept_fragment

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


_TODAY = date(2026, 6, 10)

_CURATED = """
[concept]
concept_id = "modelo-303"
domain = "modelo"
lifecycle = "approved"
domain_refs = ["modelo:303"]
legal_refs = ["ley-37-1992:art-104"]
related = ["prorrata"]
created_at = 2024-01-02
updated_at = 2026-05-01

[language.es]
short_description = "Autoliquidacion periodica del IVA."
definition = "Declaracion-liquidacion periodica del IVA que presentan los sujetos pasivos en regimen general."
scope_note = "Se presenta trimestral o mensualmente segun el volumen de operaciones."

[language.es.source]
citation = "Articulos 164 y 167 de la Ley 37/1992 del IVA."
authority = "boe"

[[language.es.term]]
label = "modelo 303"
term_status = "preferred"
part_of_speech = "noun"

[[language.es.term]]
label = "autoliquidacion de IVA"
term_status = "admitted"
hidden_search_forms = ["303"]

[language.en]
short_description = "Periodic VAT self-assessment return."

[[language.en.term]]
label = "form 303"
term_status = "preferred"
"""

_PRORRATA = """
[concept]
concept_id = "prorrata"
domain = "concepto"
lifecycle = "approved"
legal_refs = ["ley-37-1992:art-104"]
created_at = 2024-01-02
updated_at = 2026-05-01

[language.es]
short_description = "Porcentaje de IVA deducible en actividad mixta."
definition = "Regla que determina la parte deducible del IVA soportado."

[language.es.source]
citation = "Articulo 104 LIVA."
authority = "boe"

[[language.es.term]]
label = "prorrata"
term_status = "preferred"
"""


# A deprecated concept populating the three optional fields the curated round-trip
# leaves at their defaults: seed_provenance, a term grammatical_gender, and
# replaced_by (valid only on a deprecated/retired lifecycle).
_DEPRECATED_FULLY_POPULATED = """
[concept]
concept_id = "recargo-equivalencia"
domain = "regimen"
lifecycle = "deprecated"
replaced_by = "iva-domestic-general-21"
domain_refs = ["modelo:303", "modelo:390"]
legal_refs = ["ley-37-1992:art-148"]
created_at = 2024-01-02
updated_at = 2026-06-09

[concept.seed_provenance]
source = "ubterm"
attribution = "UBTERM Diccionari de fiscalitat (Universitat de Barcelona), CC BY 3.0"
source_entry_id = "fisc-0421"

[language.es]
short_description = "Regimen especial de IVA para comerciantes minoristas."
definition = "Regimen especial para comerciantes minoristas en el que el proveedor repercute un recargo."

[language.es.source]
citation = "Articulos 148 a 163 de la Ley 37/1992 del IVA."
authority = "boe"

[[language.es.term]]
label = "recargo de equivalencia"
term_status = "preferred"
part_of_speech = "noun"
grammatical_gender = "masculine"

[language.en]
short_description = "A special VAT regime for retail traders."

[[language.en.term]]
label = "equivalence surcharge"
term_status = "preferred"
"""


def _candidate(concept_id: str, domain: ConceptDomain, ref: str) -> EnrolmentCandidate:
    return EnrolmentCandidate(concept_id=concept_id, domain=domain, domain_refs=(ref,))


# --------------------------------------------------------------------------
# SCAFFOLD-EMPTY on an empty tree
# --------------------------------------------------------------------------
def test_scaffold_empty_tree_creates_expected_drafts(tmp_path: Path) -> None:
    concepts = tmp_path / "concepts"
    candidates = {
        "modelo-303": _candidate("modelo-303", ConceptDomain.MODELO, "modelo:303"),
        "iva-domestic-general-21": _candidate(
            "iva-domestic-general-21",
            ConceptDomain.REGIMEN,
            "iva-category:domestic_general",
        ),
    }
    plan = scaffold_handbook(concepts, candidates, today=_TODAY, apply=True)

    assert plan.counts[ScaffoldAction.SCAFFOLD_EMPTY] == 2
    handbook = load_terminology_handbook(concepts)
    assert set(handbook.by_id) == {"modelo-303", "iva-domestic-general-21"}
    draft = handbook.concept("modelo-303")
    assert draft.lifecycle.value == "draft"
    assert draft.domain_refs == ("modelo:303",)


def test_scaffold_empty_invents_no_prose(tmp_path: Path) -> None:
    concepts = tmp_path / "concepts"
    candidates = {"modelo-303": _candidate("modelo-303", ConceptDomain.MODELO, "modelo:303")}
    scaffold_handbook(concepts, candidates, today=_TODAY, apply=True)

    handbook = load_terminology_handbook(concepts)
    es = handbook.concept("modelo-303").section(OutputLanguage.ES)
    # No fuzzy auto-fill: no definition, no scope_note, no terms invented.
    assert es.definition is None
    assert es.scope_note is None
    assert es.source is None
    assert es.terms == ()
    # The required short_description is a visible curation marker, not prose.
    assert "sin curar" in es.short_description


def test_scaffold_empty_seeds_one_preferred_term_from_source_label(tmp_path: Path) -> None:
    concepts = tmp_path / "concepts"
    candidate = EnrolmentCandidate(
        concept_id="modelo-303",
        domain=ConceptDomain.MODELO,
        domain_refs=("modelo:303",),
        seed_labels=(SeedLabel(language=OutputLanguage.ES, label="modelo 303"),),
    )
    scaffold_handbook(concepts, {"modelo-303": candidate}, today=_TODAY, apply=True)

    handbook = load_terminology_handbook(concepts)
    es = handbook.concept("modelo-303").section(OutputLanguage.ES)
    assert len(es.terms) == 1
    assert es.terms[0].label == "modelo 303"
    assert es.terms[0].term_status.value == "preferred"
    # Still no invented prose.
    assert es.definition is None


# --------------------------------------------------------------------------
# PRESERVE: the anti-clobber proof (the whole point)
# --------------------------------------------------------------------------
def test_preserve_keeps_curated_prose_verbatim(tmp_path: Path) -> None:
    concepts = write_concept_fragment(tmp_path, "modelo-303.toml", _CURATED)
    before = load_terminology_handbook(concepts).concept("modelo-303")

    candidates = {"modelo-303": _candidate("modelo-303", ConceptDomain.MODELO, "modelo:303")}
    scaffold_handbook(concepts, candidates, today=_TODAY, apply=True)

    after = load_terminology_handbook(concepts).concept("modelo-303")
    # Every curated field survives byte-for-byte.
    assert after.lifecycle == before.lifecycle
    assert after.legal_refs == before.legal_refs
    assert after.related == before.related
    assert after.created_at == before.created_at
    assert after.updated_at == before.updated_at  # untouched: PRESERVE does not restamp
    es_before = before.section(OutputLanguage.ES)
    es_after = after.section(OutputLanguage.ES)
    assert es_after.definition == es_before.definition
    assert es_after.short_description == es_before.short_description
    assert es_after.scope_note == es_before.scope_note
    assert es_after.terms == es_before.terms
    assert es_after.source == es_before.source
    # Full record equality is the strict anti-clobber assertion.
    assert after == before


def test_preserve_refreshes_only_machine_domain_refs_additively(tmp_path: Path) -> None:
    concepts = write_concept_fragment(tmp_path, "modelo-303.toml", _CURATED)
    # The source now carries an extra domain_ref the curated fragment lacks.
    candidate = EnrolmentCandidate(
        concept_id="modelo-303",
        domain=ConceptDomain.MODELO,
        domain_refs=("modelo:303", "modelo:390"),
    )
    plan = scaffold_handbook(concepts, {"modelo-303": candidate}, today=_TODAY, apply=True)

    assert plan.counts[ScaffoldAction.PRESERVE] == 1
    after = load_terminology_handbook(concepts).concept("modelo-303")
    # Additive: the curated ref is kept, the new source ref appended.
    assert after.domain_refs == ("modelo:303", "modelo:390")
    # No curated prose touched.
    assert after.section(OutputLanguage.ES).definition is not None


# --------------------------------------------------------------------------
# RETIRE: tombstone, never delete
# --------------------------------------------------------------------------
def test_retire_tombstones_vanished_source_with_successor(tmp_path: Path) -> None:
    # A deprecated concept already names a successor; when its source
    # vanishes the engine tombstones it as retired pointing at that successor.
    curated_with_successor = _CURATED.replace(
        'lifecycle = "approved"',
        'lifecycle = "deprecated"',
    ).replace('related = ["prorrata"]', 'related = ["prorrata"]\nreplaced_by = "prorrata"')
    concepts = write_concept_fragment(tmp_path, "modelo-303.toml", curated_with_successor)
    write_concept_fragment(tmp_path, "prorrata.toml", _PRORRATA)

    candidates = {"prorrata": _candidate("prorrata", ConceptDomain.CONCEPTO, "topic:x")}
    plan = scaffold_handbook(concepts, candidates, today=_TODAY, apply=True)

    assert plan.counts[ScaffoldAction.RETIRE] == 1
    after = load_terminology_handbook(concepts)
    # The vanished concept is NOT deleted.
    assert "modelo-303" in after.by_id
    retired = after.concept("modelo-303")
    assert retired.lifecycle.value == "retired"
    assert retired.replaced_by == "prorrata"
    assert retired.updated_at == _TODAY


def test_retire_without_successor_flags_operator_and_never_deletes(tmp_path: Path) -> None:
    # A scaffold-managed concept (modelo-303 prefix) whose source vanished and
    # which has no replaced_by to infer.
    managed = _CURATED.replace('related = ["prorrata"]', "")
    concepts = write_concept_fragment(tmp_path, "modelo-303.toml", managed)
    plan = scaffold_handbook(concepts, {}, today=_TODAY, apply=True)

    retire_entries = plan.by_action(ScaffoldAction.RETIRE)
    assert len(retire_entries) == 1
    entry = retire_entries[0]
    assert entry.concept_id == "modelo-303"
    assert entry.needs_replaced_by is True
    after = load_terminology_handbook(concepts)
    # Never deleted; downgraded to deprecated (a valid no-successor tombstone-pending state).
    assert "modelo-303" in after.by_id
    assert after.concept("modelo-303").lifecycle.value == "deprecated"


def test_hand_authored_concept_is_never_retired_by_scaffold(tmp_path: Path) -> None:
    # prorrata has no scaffold-source prefix: an empty candidate set must
    # leave it UNCHANGED, never retire it (it is human-managed vocabulary).
    concepts = write_concept_fragment(tmp_path, "prorrata.toml", _PRORRATA)
    plan = scaffold_handbook(concepts, {}, today=_TODAY, apply=True)

    assert plan.counts[ScaffoldAction.RETIRE] == 0
    assert plan.counts[ScaffoldAction.UNCHANGED] == 1
    after = load_terminology_handbook(concepts).concept("prorrata")
    assert after.lifecycle.value == "approved"


# --------------------------------------------------------------------------
# Idempotence
# --------------------------------------------------------------------------
def test_second_scaffold_run_is_a_noop(tmp_path: Path) -> None:
    concepts = write_concept_fragment(tmp_path, "modelo-303.toml", _CURATED)
    candidates = {"modelo-303": _candidate("modelo-303", ConceptDomain.MODELO, "modelo:303")}

    scaffold_handbook(concepts, candidates, today=_TODAY, apply=True)
    first = (concepts / "modelo-303.toml").read_text(encoding="utf-8")
    second_plan = scaffold_handbook(concepts, candidates, today=_TODAY, apply=True)
    second = (concepts / "modelo-303.toml").read_text(encoding="utf-8")

    assert second_plan.is_empty
    assert first == second


def test_check_mode_does_not_write(tmp_path: Path) -> None:
    concepts = tmp_path / "concepts"
    candidates = {"modelo-303": _candidate("modelo-303", ConceptDomain.MODELO, "modelo:303")}
    plan = scaffold_handbook(concepts, candidates, today=_TODAY, apply=False)

    assert plan.counts[ScaffoldAction.SCAFFOLD_EMPTY] == 1
    # --check seam: the plan is computed but nothing is written.
    assert not concepts.exists() or not any(iter_directory(concepts, pattern="*.toml"))


# --------------------------------------------------------------------------
# Serializer round-trip
# --------------------------------------------------------------------------
def test_serialise_round_trips_a_curated_concept(tmp_path: Path) -> None:
    concepts = write_concept_fragment(tmp_path, "modelo-303.toml", _CURATED)
    original = load_terminology_handbook(concepts).concept("modelo-303")

    rendered = serialise_concept(original)
    (concepts / "modelo-303.toml").write_text(rendered, encoding="utf-8")
    reloaded = load_terminology_handbook(concepts).concept("modelo-303")

    assert reloaded == original


def test_serialise_round_trips_seed_provenance_gender_and_replaced_by(tmp_path: Path) -> None:
    """A deprecated concept's seed_provenance, grammatical_gender, and replaced_by survive a round-trip.

    The curated-concept round-trip above leaves these three optional fields at
    their defaults, so a serialise-drops-field / load-re-defaults-field
    regression on any of them is invisible there. This fixture populates all
    three with non-default values (per the anti-default roundtrip discipline)
    so such a regression surfaces as strict inequality.
    """
    concepts = write_concept_fragment(tmp_path, "recargo-equivalencia.toml", _DEPRECATED_FULLY_POPULATED)
    original = load_terminology_handbook(concepts).concept("recargo-equivalencia")

    # Guard the fixture is not vacuous: the three fields are actually present.
    assert original.seed_provenance is not None
    assert original.replaced_by is not None
    assert any(term.grammatical_gender is not None for lang in original.languages for term in lang.terms)

    rendered = serialise_concept(original)
    (concepts / "recargo-equivalencia.toml").write_text(rendered, encoding="utf-8")
    reloaded = load_terminology_handbook(concepts).concept("recargo-equivalencia")

    assert reloaded == original


def test_serialise_round_trip_equality_is_not_tautological(tmp_path: Path) -> None:
    """Anti-tautology proof for the serialise round-trip boundary.

    The round-trip tests above would be vacuous if load ignored the on-disk
    payload. This proves it does not: a value mutation on the serialised TOML
    surfaces as strict inequality on reload, and deleting the required
    ``[concept]`` table makes the loader raise rather than silently re-default
    (per the anti-tautology clause of the roundtrip discipline).
    """
    concepts = write_concept_fragment(tmp_path, "recargo-equivalencia.toml", _DEPRECATED_FULLY_POPULATED)
    original = load_terminology_handbook(concepts).concept("recargo-equivalencia")
    rendered = serialise_concept(original)
    toml_path = concepts / "recargo-equivalencia.toml"

    # Value mutation loads cleanly but must NOT compare equal — proves the
    # equality assertion actually reads the on-disk value.
    mutated = rendered.replace(
        "Regimen especial de IVA para comerciantes minoristas.",
        "A different short description that the round-trip must notice.",
    )
    assert mutated != rendered
    toml_path.write_text(mutated, encoding="utf-8")
    assert load_terminology_handbook(concepts).concept("recargo-equivalencia") != original

    # Structural corruption (drop the [concept] table) must raise, not re-default.
    toml_path.write_text(rendered.replace("[concept]\n", "", 1), encoding="utf-8")
    with pytest.raises(TerminologyValidationError):
        load_terminology_handbook(concepts)


def test_build_plan_is_deterministically_ordered(tmp_path: Path) -> None:
    candidates = {
        "modelo-303": _candidate("modelo-303", ConceptDomain.MODELO, "modelo:303"),
        "iva-domestic-general-21": _candidate(
            "iva-domestic-general-21",
            ConceptDomain.REGIMEN,
            "iva-category:domestic_general",
        ),
    }
    plan = build_scaffold_plan(candidates, {}, today=_TODAY)
    ids = [entry.concept_id for entry in plan.entries]
    assert ids == sorted(ids)


# --------------------------------------------------------------------------
# Real enrolment sources (concept-grade granularity)
# --------------------------------------------------------------------------
def test_real_enrolment_candidates_are_concept_grade_and_bounded() -> None:
    candidates = collect_enrolment_candidates()
    # Bounded concept-grade set, not per-casilla (18,885) nor per-legal (262).
    assert 0 < len(candidates) < 1000
    # Every REGISTRY-BACKED modelo enrols exactly one concept, and no
    # non-registry one does. This loop previously ran over the whole ``Modelo``
    # enum, which is a typing device rather than a glossary: it necessarily
    # carries every code the codebase mentions, including the 76 members the
    # codebase itself declares in NON_REGISTRY_MODELOS as having no registry
    # definition. Enrolling those made the Handbook report 118 unenrolled
    # concepts against a committed 117 and would have tripled the curation
    # ratchet, entirely as a side effect of a typing change made elsewhere.
    #
    # The assertion this replaces was about GRANULARITY -- modelos are the
    # concept-grade axis, unlike casillas -- and that intent is unchanged here.
    # What narrowed is which modelos, not the axis.
    from cadrumo.core.modelo import NON_REGISTRY_MODELOS, Modelo

    for modelo in Modelo:
        concept_id = f"modelo-{modelo.value}"
        if modelo in NON_REGISTRY_MODELOS:
            assert concept_id not in candidates, (
                f"{concept_id} has no registry definition, so it is an identifier the code "
                "references rather than a concept a taxpayer looks up"
            )
        else:
            assert concept_id in candidates
    # No legal-provision concepts are scaffolded (projected at compile time).
    assert not any(c.domain is ConceptDomain.LEGAL for c in candidates.values())
