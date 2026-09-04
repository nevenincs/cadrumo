"""Real-behaviour tests for curation verbs, audit, and the --check gate.

Curation verbs mutate a controlled fixture tree, prove idempotence, prove
the tree stays loader-valid, and prove an invalid mutation is REFUSED
rather than written. The audit reports correct counts on a fixture with a
deliberately-incomplete draft. ``--check`` (scaffold dry-run) detects
drift and reports clean on a synced fixture. The ratified cli_verbs=False
granularity (82 concepts) is pinned by a regression test.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from cadrumo.core.external_constants import OutputLanguage

from .._curation import (
    CurationError,
    audit_handbook,
    relate_concepts,
    remove_term,
    retire_concept,
    set_language_field,
    set_term,
)
from .._enrolment import EnrolmentCandidate, collect_enrolment_candidates
from .._scaffold import ScaffoldAction, scaffold_handbook
from ..enums import ConceptDomain, TermStatus
from ..loader import load_terminology_handbook

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_TODAY = date(2026, 6, 10)

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

_DRAFT = """
[concept]
concept_id = "modelo-303"
domain = "modelo"
lifecycle = "draft"
domain_refs = ["modelo:303"]
created_at = 2026-06-01
updated_at = 2026-06-01

[language.es]
short_description = "(sin curar) draft pendiente de definicion"
"""


def _tree(tmp_path: Path, fragments: dict[str, str]) -> Path:
    concepts = tmp_path / "concepts"
    concepts.mkdir(exist_ok=True)
    for name, content in fragments.items():
        (concepts / name).write_text(content, encoding="utf-8")
    return concepts


def _candidate(concept_id: str, domain: ConceptDomain, ref: str) -> EnrolmentCandidate:
    return EnrolmentCandidate(concept_id=concept_id, domain=domain, domain_refs=(ref,))


# --------------------------------------------------------------------------
# set
# --------------------------------------------------------------------------
def test_set_definition_writes_and_stays_loader_valid(tmp_path: Path) -> None:
    concepts = _tree(tmp_path, {"modelo-303.toml": _DRAFT})
    set_language_field(
        "modelo-303",
        OutputLanguage.ES,
        "definition",
        "Autoliquidacion periodica del IVA en regimen general.",
        concepts_dir=concepts,
        today=_TODAY,
    )
    after = load_terminology_handbook(concepts).concept("modelo-303")
    assert after.section(OutputLanguage.ES).definition == "Autoliquidacion periodica del IVA en regimen general."


def test_set_short_description_is_idempotent(tmp_path: Path) -> None:
    concepts = _tree(tmp_path, {"modelo-303.toml": _DRAFT})
    args = ("modelo-303", OutputLanguage.ES, "short_description", "Autoliquidacion del IVA.")
    set_language_field(*args, concepts_dir=concepts, today=_TODAY)
    first = (concepts / "modelo-303.toml").read_text(encoding="utf-8")
    set_language_field(*args, concepts_dir=concepts, today=_TODAY)
    second = (concepts / "modelo-303.toml").read_text(encoding="utf-8")
    assert first == second


def test_set_source_attaches_citation(tmp_path: Path) -> None:
    concepts = _tree(tmp_path, {"modelo-303.toml": _DRAFT})
    set_language_field(
        "modelo-303",
        OutputLanguage.ES,
        "source",
        "Articulos 164 y 167 LIVA.",
        concepts_dir=concepts,
        today=_TODAY,
        source_authority="boe",
    )
    section = load_terminology_handbook(concepts).concept("modelo-303").section(OutputLanguage.ES)
    assert section.source is not None
    assert section.source.citation == "Articulos 164 y 167 LIVA."
    assert section.source.authority == "boe"


def test_set_unknown_field_is_refused(tmp_path: Path) -> None:
    concepts = _tree(tmp_path, {"modelo-303.toml": _DRAFT})
    with pytest.raises(CurationError, match="unknown language field"):
        set_language_field("modelo-303", OutputLanguage.ES, "nonsense", "x", concepts_dir=concepts)


def test_set_on_unknown_concept_is_refused(tmp_path: Path) -> None:
    concepts = _tree(tmp_path, {"modelo-303.toml": _DRAFT})
    with pytest.raises(CurationError, match="unknown concept"):
        set_language_field("ghost", OutputLanguage.ES, "definition", "x", concepts_dir=concepts)


def test_set_term_replaces_same_label_idempotently(tmp_path: Path) -> None:
    concepts = _tree(tmp_path, {"modelo-303.toml": _DRAFT})
    set_term("modelo-303", OutputLanguage.ES, "modelo 303", TermStatus.PREFERRED, concepts_dir=concepts, today=_TODAY)
    first = (concepts / "modelo-303.toml").read_text(encoding="utf-8")
    set_term("modelo-303", OutputLanguage.ES, "modelo 303", TermStatus.PREFERRED, concepts_dir=concepts, today=_TODAY)
    second = (concepts / "modelo-303.toml").read_text(encoding="utf-8")
    assert first == second
    terms = load_terminology_handbook(concepts).concept("modelo-303").section(OutputLanguage.ES).terms
    assert [t.label for t in terms] == ["modelo 303"]


def test_set_two_preferred_terms_is_refused(tmp_path: Path) -> None:
    concepts = _tree(tmp_path, {"prorrata.toml": _PRORRATA})
    # prorrata already has a preferred term; adding a second preferred must refuse.
    with pytest.raises(CurationError, match="refused"):
        set_term("prorrata", OutputLanguage.ES, "regla de prorrata", TermStatus.PREFERRED, concepts_dir=concepts)


def test_remove_term_drops_the_named_term_and_keeps_the_rest(tmp_path: Path) -> None:
    concepts = _tree(tmp_path, {"prorrata.toml": _PRORRATA})
    args = ("prorrata", OutputLanguage.ES, "regla de prorrata")
    set_term(*args, TermStatus.ADMITTED, concepts_dir=concepts, today=_TODAY)
    remove_term(*args, concepts_dir=concepts, today=_TODAY)
    terms = load_terminology_handbook(concepts).concept("prorrata").section(OutputLanguage.ES).terms
    labels = [term.label for term in terms]
    assert "regla de prorrata" not in labels
    assert "prorrata" in labels  # the preferred term survives the removal


def test_remove_term_refuses_a_label_not_present(tmp_path: Path) -> None:
    concepts = _tree(tmp_path, {"prorrata.toml": _PRORRATA})
    with pytest.raises(CurationError, match="to remove"):
        remove_term("prorrata", OutputLanguage.ES, "no existe", concepts_dir=concepts)


# --------------------------------------------------------------------------
# relate
# --------------------------------------------------------------------------
def test_relate_adds_and_removes_edge(tmp_path: Path) -> None:
    concepts = _tree(tmp_path, {"prorrata.toml": _PRORRATA, "modelo-303.toml": _DRAFT})
    relate_concepts("modelo-303", "related", "prorrata", concepts_dir=concepts, today=_TODAY)
    after = load_terminology_handbook(concepts).concept("modelo-303")
    assert "prorrata" in after.related

    relate_concepts("modelo-303", "related", "prorrata", remove=True, concepts_dir=concepts, today=_TODAY)
    after = load_terminology_handbook(concepts).concept("modelo-303")
    assert "prorrata" not in after.related


def test_relate_is_idempotent(tmp_path: Path) -> None:
    concepts = _tree(tmp_path, {"prorrata.toml": _PRORRATA, "modelo-303.toml": _DRAFT})
    relate_concepts("modelo-303", "broader", "prorrata", concepts_dir=concepts, today=_TODAY)
    first = (concepts / "modelo-303.toml").read_text(encoding="utf-8")
    relate_concepts("modelo-303", "broader", "prorrata", concepts_dir=concepts, today=_TODAY)
    second = (concepts / "modelo-303.toml").read_text(encoding="utf-8")
    assert first == second


def test_relate_dangling_target_is_refused(tmp_path: Path) -> None:
    concepts = _tree(tmp_path, {"modelo-303.toml": _DRAFT})
    with pytest.raises(CurationError, match="refused"):
        relate_concepts("modelo-303", "broader", "does-not-exist", concepts_dir=concepts)


def test_relate_unknown_relation_is_refused(tmp_path: Path) -> None:
    concepts = _tree(tmp_path, {"modelo-303.toml": _DRAFT})
    with pytest.raises(CurationError, match="unknown relation"):
        relate_concepts("modelo-303", "sibling", "prorrata", concepts_dir=concepts)


# --------------------------------------------------------------------------
# retire
# --------------------------------------------------------------------------
def test_retire_tombstones_with_successor_and_never_deletes(tmp_path: Path) -> None:
    concepts = _tree(tmp_path, {"prorrata.toml": _PRORRATA, "modelo-303.toml": _DRAFT})
    retire_concept("modelo-303", "prorrata", concepts_dir=concepts, today=_TODAY)
    after = load_terminology_handbook(concepts)
    assert "modelo-303" in after.by_id
    retired = after.concept("modelo-303")
    assert retired.lifecycle.value == "retired"
    assert retired.replaced_by == "prorrata"


def test_retire_self_reference_is_refused(tmp_path: Path) -> None:
    concepts = _tree(tmp_path, {"modelo-303.toml": _DRAFT})
    # replaced_by == concept_id is rejected by the schema validator -> refused.
    with pytest.raises(CurationError):
        retire_concept("modelo-303", "modelo-303", concepts_dir=concepts)


def test_retire_pointing_at_retired_successor_is_refused(tmp_path: Path) -> None:
    retired_target = _PRORRATA.replace('lifecycle = "approved"', 'lifecycle = "retired"\nreplaced_by = "modelo-303"')
    concepts = _tree(tmp_path, {"prorrata.toml": retired_target, "modelo-303.toml": _DRAFT})
    with pytest.raises(CurationError, match="refused"):
        retire_concept("modelo-303", "prorrata", concepts_dir=concepts)


# --------------------------------------------------------------------------
# audit
# --------------------------------------------------------------------------
def test_audit_counts_drafts_empty_descriptions_and_seed_coverage(tmp_path: Path) -> None:
    seeded = _PRORRATA.replace(
        "updated_at = 2026-05-01\n",
        'updated_at = 2026-05-01\n\n[concept.seed_provenance]\nsource = "iate"\nattribution = "IATE (c) EU"\n',
    )
    concepts = _tree(tmp_path, {"prorrata.toml": seeded, "modelo-303.toml": _DRAFT})
    report = audit_handbook(concepts)

    assert report.total_concepts == 2
    assert report.draft_count == 1
    assert report.approved_count == 1
    # The draft carries the (sin curar) placeholder -> empty short_description.
    assert "modelo-303" in report.empty_short_description
    assert report.empty_short_description["modelo-303"] == ("es",)
    # prorrata's curated short_description is not flagged.
    assert "prorrata" not in report.empty_short_description
    assert report.seeded_count == 1
    assert report.hand_authored_count == 1
    assert report.is_clean


def test_audit_flags_retired_without_replaced_by_via_loaded_state(tmp_path: Path) -> None:
    # A deprecated concept that names no successor is a valid load state; an
    # audit over a clean fixture reports no structural defects.
    concepts = _tree(tmp_path, {"prorrata.toml": _PRORRATA})
    report = audit_handbook(concepts)
    assert report.retired_without_replaced_by == ()
    assert report.is_clean


# --------------------------------------------------------------------------
# --check (scaffold dry-run)
# --------------------------------------------------------------------------
def test_check_reports_clean_on_synced_fixture(tmp_path: Path) -> None:
    concepts = tmp_path / "concepts"
    candidates = {"modelo-303": _candidate("modelo-303", ConceptDomain.MODELO, "modelo:303")}
    # Materialise the expected draft, then a --check pass must be drift-free.
    scaffold_handbook(concepts, candidates, today=_TODAY, apply=True)
    plan = scaffold_handbook(concepts, candidates, today=_TODAY, apply=False)
    assert plan.is_empty


def test_check_detects_drift_on_missing_concept(tmp_path: Path) -> None:
    concepts = tmp_path / "concepts"
    candidates = {"modelo-303": _candidate("modelo-303", ConceptDomain.MODELO, "modelo:303")}
    plan = scaffold_handbook(concepts, candidates, today=_TODAY, apply=False)
    assert not plan.is_empty
    assert plan.counts[ScaffoldAction.SCAFFOLD_EMPTY] == 1


# --------------------------------------------------------------------------
# ratified granularity regression
# --------------------------------------------------------------------------
def test_default_enrolment_excludes_cli_verbs_and_is_bounded() -> None:
    candidates = collect_enrolment_candidates()
    # Candidates are every registry entity that COULD become a concept; the
    # concept-grade curation happens downstream. The set tracks the registry:
    # 73 modelo + 18 regimen + 21 periodo + 14 concepto = 126. Update this count
    # when the registry gains an entity.
    #
    # The modelo term was 149 -- the whole ``Modelo`` enum -- until it was
    # narrowed to the 73 members carrying a registry definition. The enum is a
    # typing device that necessarily includes every code the codebase mentions,
    # so 76 retired or code-referenced-only forms were being offered as glossary
    # concepts. That is why this count sat at 202 while only 117 concepts were
    # committed: the gap was not curation backlog, it was mostly candidates that
    # should never have been candidates.
    assert len(candidates) == 126
    # The real structural invariants -- no verb/legal enrolment, and no domain
    # outside the four concept-grade families -- must hold regardless of count.
    allowed = {ConceptDomain.MODELO, ConceptDomain.REGIMEN, ConceptDomain.PERIODO, ConceptDomain.CONCEPTO}
    assert {c.domain for c in candidates.values()} <= allowed
    assert not any(c.domain is ConceptDomain.CLI_VERB for c in candidates.values())
    assert not any(c.domain is ConceptDomain.LEGAL for c in candidates.values())


def test_cli_verbs_toggle_still_available() -> None:
    with_cli = collect_enrolment_candidates(cli_verbs=True)
    assert any(c.domain is ConceptDomain.CLI_VERB for c in with_cli.values())


def test_bundled_handbook_audit_is_structurally_clean() -> None:
    # The real committed tree must carry no structural defect (dangling
    # relations, retired-without-replaced_by). This gate is green today and
    # remains independent of scaffold --check drift.
    report = audit_handbook()
    assert report.is_clean
    assert report.dangling_relations == {}
    assert report.retired_without_replaced_by == ()
