"""Real-behaviour tests for the Terminology Handbook validation gates.

Each gate is exercised with a passing case and a failing case that actually
trips the gate's error (anti-tautology: the failing fixture is constructed so
removing the gate would let it through). The
bundled exemplar handbook (prorrata / prorrata-especial / casilla) must
pass the full default inventory, including legal-ref resolution against
the real registry legal catalogue.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .. import (
    TerminologyHandbook,
    approved_completeness_validator,
    default_handbook_validators,
    id_uniqueness_validator,
    legal_refs_resolve_validator,
    lifecycle_replaced_by_validator,
    load_bundled_terminology_handbook,
    load_terminology_handbook,
    relation_integrity_validator,
)
from .._validators import _bundled_legal_ref_ids
from ..errors import TerminologyValidationError
from ._support import write_concept_fragment

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


# A small synthetic legal catalogue id-set so the legal-ref gate is unit
# testable without loading the full registry.
_SYNTHETIC_LEGAL = frozenset({"ley-37-1992:art-104", "ley-37-1992:art-102"})


_APPROVED = """
[concept]
concept_id = "prorrata"
domain = "concepto"
lifecycle = "approved"
legal_refs = ["ley-37-1992:art-104"]
created_at = 2024-02-03
updated_at = 2026-06-09

[language.es]
short_description = "Porcentaje de IVA soportado deducible."
definition = "Regla que determina la parte deducible del IVA soportado en actividad mixta."

[language.es.source]
citation = "Articulo 104 de la Ley 37/1992 del IVA."
authority = "boe"

[[language.es.term]]
label = "prorrata"
term_status = "preferred"
part_of_speech = "noun"
grammatical_gender = "feminine"

[language.en]
short_description = "The deductible proportion of input VAT."

[[language.en.term]]
label = "pro rata"
term_status = "preferred"
"""

_DRAFT = """
[concept]
concept_id = "modulos"
domain = "regimen"
lifecycle = "draft"
created_at = 2026-06-10
updated_at = 2026-06-10

[language.es]
short_description = "Regimen de estimacion objetiva."

[[language.es.term]]
label = "modulos"
term_status = "preferred"
"""


def _handbook(tmp_path: Path, fragments: dict[str, str]) -> TerminologyHandbook:
    concepts: Path | None = None
    for name, content in fragments.items():
        concepts = write_concept_fragment(tmp_path, name, content)
    assert concepts is not None
    return load_terminology_handbook(concepts)


# --------------------------------------------------------------------------
# Gate 1: id uniqueness
# --------------------------------------------------------------------------
def test_id_uniqueness_passes_on_distinct_ids(tmp_path: Path) -> None:
    handbook = _handbook(tmp_path, {"prorrata.toml": _APPROVED, "modulos.toml": _DRAFT})
    id_uniqueness_validator()(handbook)


def test_id_uniqueness_fails_on_duplicate(tmp_path: Path) -> None:
    handbook = _handbook(tmp_path, {"prorrata.toml": _APPROVED})
    # Construct a handbook with a duplicated record bypassing the loader's
    # own per-fragment dedupe so the GATE itself is what trips.
    record = handbook.concept("prorrata")
    doubled = TerminologyHandbook(concepts=(record, record))
    with pytest.raises(TerminologyValidationError, match="duplicate concept_id"):
        id_uniqueness_validator()(doubled)


# --------------------------------------------------------------------------
# Gate 2: legal_refs resolve
# --------------------------------------------------------------------------
def test_legal_refs_resolve_passes_against_catalogue(tmp_path: Path) -> None:
    handbook = _handbook(tmp_path, {"prorrata.toml": _APPROVED})
    legal_refs_resolve_validator(_SYNTHETIC_LEGAL)(handbook)


def test_legal_refs_resolve_fails_on_unknown_ref(tmp_path: Path) -> None:
    fragment = _APPROVED.replace('legal_refs = ["ley-37-1992:art-104"]', 'legal_refs = ["ley-37-1992:art-999"]')
    handbook = _handbook(tmp_path, {"prorrata.toml": fragment})
    with pytest.raises(TerminologyValidationError, match="ley-37-1992:art-999"):
        legal_refs_resolve_validator(_SYNTHETIC_LEGAL)(handbook)


# --------------------------------------------------------------------------
# Gate 3: relation integrity
# --------------------------------------------------------------------------
def test_relation_integrity_passes_when_targets_exist(tmp_path: Path) -> None:
    child = _DRAFT.replace('lifecycle = "draft"', 'lifecycle = "draft"\nrelated = ["prorrata"]')
    handbook = _handbook(tmp_path, {"prorrata.toml": _APPROVED, "modulos.toml": child})
    relation_integrity_validator()(handbook)


def test_relation_integrity_fails_on_dangling_target(tmp_path: Path) -> None:
    child = _DRAFT.replace('lifecycle = "draft"', 'lifecycle = "draft"\nbroader = ["does-not-exist"]')
    handbook = _handbook(tmp_path, {"modulos.toml": child})
    with pytest.raises(TerminologyValidationError, match="does-not-exist"):
        relation_integrity_validator()(handbook)


# --------------------------------------------------------------------------
# Gate 4: lifecycle / replaced_by integrity
# --------------------------------------------------------------------------
def test_lifecycle_passes_when_replacement_is_live(tmp_path: Path) -> None:
    retired = """
[concept]
concept_id = "viejo"
domain = "concepto"
lifecycle = "retired"
replaced_by = "prorrata"
created_at = 2020-01-01
updated_at = 2026-06-10

[language.es]
short_description = "Concepto retirado."

[[language.es.term]]
label = "viejo"
term_status = "deprecated"
"""
    handbook = _handbook(tmp_path, {"prorrata.toml": _APPROVED, "viejo.toml": retired})
    lifecycle_replaced_by_validator()(handbook)


def test_lifecycle_fails_when_replacement_is_itself_retired(tmp_path: Path) -> None:
    retired_a = """
[concept]
concept_id = "viejo-a"
domain = "concepto"
lifecycle = "retired"
replaced_by = "viejo-b"
created_at = 2020-01-01
updated_at = 2026-06-10

[language.es]
short_description = "Retirado A."

[[language.es.term]]
label = "viejo a"
term_status = "deprecated"
"""
    retired_b = """
[concept]
concept_id = "viejo-b"
domain = "concepto"
lifecycle = "retired"
replaced_by = "prorrata"
created_at = 2020-01-01
updated_at = 2026-06-10

[language.es]
short_description = "Retirado B."

[[language.es.term]]
label = "viejo b"
term_status = "deprecated"
"""
    handbook = _handbook(
        tmp_path,
        {"prorrata.toml": _APPROVED, "viejo-a.toml": retired_a, "viejo-b.toml": retired_b},
    )
    with pytest.raises(TerminologyValidationError, match="is itself retired"):
        lifecycle_replaced_by_validator()(handbook)


def test_lifecycle_fails_on_replaced_by_cycle(tmp_path: Path) -> None:
    # Two retired concepts pointing at each other form a successor cycle.
    a = """
[concept]
concept_id = "ciclo-a"
domain = "concepto"
lifecycle = "retired"
replaced_by = "ciclo-b"
created_at = 2020-01-01
updated_at = 2026-06-10

[language.es]
short_description = "Ciclo A."

[[language.es.term]]
label = "ciclo a"
term_status = "deprecated"
"""
    b = """
[concept]
concept_id = "ciclo-b"
domain = "concepto"
lifecycle = "retired"
replaced_by = "ciclo-a"
created_at = 2020-01-01
updated_at = 2026-06-10

[language.es]
short_description = "Ciclo B."

[[language.es.term]]
label = "ciclo b"
term_status = "deprecated"
"""
    handbook = _handbook(tmp_path, {"ciclo-a.toml": a, "ciclo-b.toml": b})
    with pytest.raises(TerminologyValidationError, match="cycle"):
        lifecycle_replaced_by_validator()(handbook)


def test_lifecycle_passes_deprecated_pointing_at_live_successor(tmp_path: Path) -> None:
    deprecated = """
[concept]
concept_id = "antiguo"
domain = "concepto"
lifecycle = "deprecated"
replaced_by = "prorrata"
created_at = 2020-01-01
updated_at = 2026-06-10

[language.es]
short_description = "Concepto desaconsejado."

[[language.es.term]]
label = "antiguo"
term_status = "deprecated"
"""
    handbook = _handbook(tmp_path, {"prorrata.toml": _APPROVED, "antiguo.toml": deprecated})
    lifecycle_replaced_by_validator()(handbook)


# --------------------------------------------------------------------------
# Gate 5: approved-concept completeness
# --------------------------------------------------------------------------
def test_approved_completeness_passes_on_complete_concept(tmp_path: Path) -> None:
    handbook = _handbook(tmp_path, {"prorrata.toml": _APPROVED})
    approved_completeness_validator()(handbook)


def test_approved_completeness_exempts_draft(tmp_path: Path) -> None:
    # A draft with no es definition and no source must NOT trip the gate.
    handbook = _handbook(tmp_path, {"modulos.toml": _DRAFT})
    approved_completeness_validator()(handbook)


def test_approved_completeness_fails_without_es_definition(tmp_path: Path) -> None:
    fragment = "\n".join(line for line in _APPROVED.splitlines() if not line.startswith("definition"))
    handbook = _handbook(tmp_path, {"prorrata.toml": fragment})
    with pytest.raises(TerminologyValidationError, match="no definition"):
        approved_completeness_validator()(handbook)


def test_approved_completeness_fails_without_es_source(tmp_path: Path) -> None:
    fragment = _APPROVED.replace(
        '[language.es.source]\ncitation = "Articulo 104 de la Ley 37/1992 del IVA."\nauthority = "boe"\n',
        "",
    )
    handbook = _handbook(tmp_path, {"prorrata.toml": fragment})
    with pytest.raises(TerminologyValidationError, match="no source citation"):
        approved_completeness_validator()(handbook)


# --------------------------------------------------------------------------
# Full inventory + bundled exemplars
# --------------------------------------------------------------------------
def test_default_inventory_runs_through_the_loader_seam(tmp_path: Path) -> None:
    concepts = write_concept_fragment(tmp_path, "prorrata.toml", _APPROVED)
    handbook = load_terminology_handbook(concepts, validators=default_handbook_validators(_SYNTHETIC_LEGAL))
    assert handbook.concept("prorrata").lifecycle.value == "approved"


def test_default_inventory_trips_on_a_bad_handbook(tmp_path: Path) -> None:
    bad = _APPROVED.replace('lifecycle = "approved"', 'lifecycle = "approved"\nbroader = ["ghost"]')
    concepts = write_concept_fragment(tmp_path, "prorrata.toml", bad)
    with pytest.raises(TerminologyValidationError, match="ghost"):
        load_terminology_handbook(concepts, validators=default_handbook_validators(_SYNTHETIC_LEGAL))


def test_bundled_exemplars_pass_every_gate_against_real_catalogue() -> None:
    """The shipped handbook passes every gate against the real legal catalogue.

    Reads the catalogue through the module's own ``_bundled_legal_ref_ids``
    rather than re-deriving it here. The duplicate derivation reached for the
    validated authority, so this test refused whenever the registry refused for
    reasons unrelated to the handbook -- and it kept doing so after the helper
    it exercises had been moved off that dependency, because the copy was what
    ran.
    """
    handbook = load_bundled_terminology_handbook()
    legal_ids = _bundled_legal_ref_ids()
    for validate in default_handbook_validators(legal_ids):
        validate(handbook)


def test_bundled_exemplars_legal_refs_resolve_in_default_catalogue() -> None:
    # The default (no-arg) legal gate pulls the real bundled catalogue;
    # the exemplar prorrata legal_refs must resolve there.
    handbook = load_bundled_terminology_handbook()
    legal_refs_resolve_validator()(handbook)
