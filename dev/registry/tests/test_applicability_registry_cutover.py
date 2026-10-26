"""Prove the applicability registry-resolution cutover mechanism.

Two real-behavior proofs, both against a real scratch
:class:`ValidatedRegistryAuthority` (never a mock/patch), matching the
established fixture shape in ``test_authority.py``:

1. FUNCTION-LEVEL EQUIVALENCE: ``derive_modelo_applicability``'s own
   evaluation logic, reached through :func:`resolve_applicability_rule_from_authority`
   against a registry-authored fragment, returns an identical
   :class:`ModeloApplicability` (verdict, reason, legal_refs) to evaluating
   the same content as a hand-built Python literal, for every representative
   profile.
2. STALENESS: mutating the authoring tree and reloading a FRESH authority
   returns the mutated rule; the ORIGINAL authority instance keeps returning
   what it always did. This is the anti-tautology proof for the deliberate
   no-cache decision -- a `@cache`-wrapped resolver would fail proof 2.

``REGISTRY_RESOLVED_APPLICABILITY_MODELOS`` stays empty in production until
the migrator's ``--apply`` run lands and is verified against the real bundled
tree (tracked separately); this module proves the MECHANISM these tests
exercise directly, not through that module-level switch.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cadrumo.core.modelo import Modelo
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.applicability import (
    ApplicabilityVerdict,
    ModeloApplicabilityRule,
    resolve_applicability_rule_from_authority,
)
from cadrumo.domain.contribuyente.entity_type import EntityType
from cadrumo.domain.contribuyente.renta_codes import FiscalResidency
from cadrumo.domain.deadlines.models import IVARegime, TaxpayerProfile

from ..compiler.authority import compile_validated_authority
from ..conformance.loader_directory_mode_support import write_fragmented_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

#: A legal reference the bundled tree already carries. The planted rule cites
#: it so the staged copy needs no synthetic legal entry and no corpus of its
#: own, which lets the compilation read sources from the bundled root.
_LEGAL_ID = "ley-35-2006:art-17"

#: The modelo this fixture plants into the copied tree. A NEW id, because the
#: real modelos already declare their own applicability rule and a second one
#: on the same revision is refused.
_PLANTED_MODELO = "999"

#: A layout-authority source the bundled tree carries, so the planted modelo
#: satisfies the evidence tier the validator requires without a corpus of its
#: own.
_BUNDLED_SOURCE_ID = "boe-modelo-100-2020-form"

#: An official-guidance source the bundled tree carries; an application link
#: requires that tier specifically.
_BUNDLED_GUIDANCE_SOURCE_ID = "aeat-modelo-184-procedure"
_SOURCE_ID = "test-source-001"
_GUIDANCE_SOURCE_ID = "test-source-002"

_CATALOGUE_TOML = f"""\
[legal."{_LEGAL_ID}"]
evidence_tier = "legal_authority"
authority = "boe"
kind = "ley"
corpus_ref = "corpus/test/test-ley-001.html#a1"
document_id = "BOE-T-001"
article = "1"
permalink = "https://example.com/test"
effective_from = 2025-01-01
review_status = "pending_review"
required_text = ["test provision text"]

[sources."{_SOURCE_ID}"]
evidence_tier = "layout_authority"
authority = "aeat"
kind = "record_design"
corpus_path = "corpus/test/test-source-001.pdf"
sha256 = "44f8354494a5ba03ba1792a8d3e9c534c47a9181980fde7a3f44b06ef2ae7c7f"
bytes = 1000
retrieved_at = 2025-01-01
source_url = "https://example.com/test-source"
review_status = "pending_review"

[sources."{_GUIDANCE_SOURCE_ID}"]
evidence_tier = "official_source_guidance"
authority = "aeat"
kind = "instructions"
corpus_path = "corpus/test/test-source-002.pdf"
sha256 = "44f8354494a5ba03ba1792a8d3e9c534c47a9181980fde7a3f44b06ef2ae7c7f"
bytes = 1000
retrieved_at = 2025-01-01
source_url = "https://example.com/test-source-002"
review_status = "pending_review"
"""

_MANIFEST_TOML = f"""\
[modelo]
id = "{_PLANTED_MODELO}"
tax_domain = "irpf"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["{_LEGAL_ID}"]
source_refs = ["{_BUNDLED_SOURCE_ID}"]
"""


def _revision_toml(*, entity_type: str, applicable_reason: str) -> str:
    return f"""\
[revisions."2025"]
valid_from = 2025-01-01
period_selector = {{ year_from = 2025, periods = ["0A"] }}
# This fixture exists to resolve an APPLICABILITY rule -- whether the modelo is
# due, and to whom -- and is not built to compute amounts or back a filing, so
# that is the rung it declares. An undeclared grade is a refusal now, and it
# lands before the applicability assertions run.
authority_grade = "applicability"
legal_refs = ["{_LEGAL_ID}"]
source_refs = ["{_BUNDLED_SOURCE_ID}"]
orden_aplicabilidad = ["{_LEGAL_ID}"]

[[revisions."2025".application_links]]
id = "test-filing-link"
surface = "filing"
consumer = "cli.app"
requires_snapshot = true
legal_refs = ["{_LEGAL_ID}"]
source_refs = ["{_BUNDLED_GUIDANCE_SOURCE_ID}"]

[[revisions."2025".casillas]]
id = "01"
number = "01"
section = ["test"]
data_type = "integer"
legal_refs = ["{_LEGAL_ID}"]
source_refs = ["{_BUNDLED_SOURCE_ID}"]

[[revisions."2025".workbook_parity_refs]]
id = "test-workbook-001"
workbook_source = "{_BUNDLED_SOURCE_ID}"
fixture_id = "test-fixture-001"
formula_coverage = "record_design_layout"
runner_required = false
tolerance = "0.00"
legal_refs = ["{_LEGAL_ID}"]
source_refs = ["{_BUNDLED_SOURCE_ID}"]

[[revisions."2025".applicability]]
id = "m999-cutover-test"
applicable_entity_types = ["{entity_type}"]
applicable_fiscal_residencies = ["resident_irpf"]
applicable_reason = "{applicable_reason}"
not_applicable_reason = "does not apply"
cuota_bearing = true
legal_refs = ["{_LEGAL_ID}"]
"""


def _write_scratch_tree(root: Path, *, applicable_reason: str) -> None:
    """Stage a compilable tree carrying one planted applicability rule.

    The bundled registry is copied and the planted modelo written into it,
    rather than a narrow tree built from nothing. A compilation validates a
    COMPLETE tree - the profile schema, the governed facts resolved by name,
    the runtime catalogues under ``legal`` and ``iva``, and every legal
    reference those cite - so a tree carrying only this modelo refuses long
    before the rule under test is reached. These cases need a real compilation
    (they prove a tree edit reaches the NEXT one), so the tree has to be real.

    Sources still resolve from the copy's own corpus below, which is why the
    corpus files are written here as before.
    """
    registry_root = root / "registry" / "aeat"
    shutil.copytree(bundled_path("registry"), root / "registry", dirs_exist_ok=True)
    legal_dir = registry_root / "legal"
    revision_dir = registry_root / "modelos" / _PLANTED_MODELO / "revisions" / "2025"
    revision_dir.mkdir(parents=True, exist_ok=True)
    legal_dir.mkdir(parents=True, exist_ok=True)
    # Nothing else is written: the copied tree carries its own legal catalogue,
    # supported-filing-years declaration and corpus, and adding a second copy of
    # any of them is a duplicate declaration the load refuses.
    (registry_root / "modelos" / _PLANTED_MODELO / "manifest.toml").write_text(_MANIFEST_TOML, encoding="utf-8")
    write_fragmented_revision(
        revision_dir,
        _revision_toml(entity_type="natural_person", applicable_reason=applicable_reason),
    )


def _literal_equivalent_rule() -> ModeloApplicabilityRule:
    """The Python-literal shape the fragment above transcribes, for the equivalence proof."""
    return ModeloApplicabilityRule(
        modelo=Modelo(_PLANTED_MODELO),
        applicable_entity_types=frozenset({EntityType.from_registry("natural_person")}),
        applicable_fiscal_residencies=frozenset({FiscalResidency.from_registry("resident_irpf")}),
        applicable_reason="applies",
        not_applicable_reason="does not apply",
        cuota_bearing=True,
        legal_refs=(_LEGAL_ID,),
    )


def _representative_profiles() -> tuple[TaxpayerProfile, ...]:
    return (
        TaxpayerProfile(
            tax_id="12345678Z",
            entity_type=EntityType.from_registry("natural_person"),
            fiscal_residency=FiscalResidency.from_registry("resident_irpf"),
            iva_regime=IVARegime("NO_APLICA"),
        ),
        TaxpayerProfile(
            tax_id="B12345674", entity_type=EntityType.from_registry("legal_entity"), iva_regime=IVARegime("NO_APLICA")
        ),
        TaxpayerProfile(tax_id="12345678Z", iva_regime=IVARegime("NO_APLICA")),
    )


def test_registry_resolved_rule_matches_the_literal_it_transcribes_per_profile(tmp_path: Path) -> None:
    """Condition 1: identical verdict, reason and legal_refs for every representative profile.

    Not "hydrated fragment equals literal" at the data layer (the fragment-family proof already
    proves that) -- this evaluates BOTH through the real
    ``ModeloApplicabilityRule.evaluate`` and compares the
    ``ModeloApplicability`` results the application actually consumes.
    """
    _write_scratch_tree(tmp_path, applicable_reason="applies")
    authority = compile_validated_authority(tmp_path / "registry" / "aeat", bundled_path())

    registry_rule = resolve_applicability_rule_from_authority(authority, Modelo(_PLANTED_MODELO))
    literal_rule = _literal_equivalent_rule()

    for profile in _representative_profiles():
        registry_result = registry_rule.evaluate(profile)
        literal_result = literal_rule.evaluate(profile)
        assert registry_result.verdict == literal_result.verdict, profile
        assert registry_result.reason == literal_result.reason, profile
        assert registry_result.legal_refs == literal_result.legal_refs, profile


def test_registry_resolved_rule_verdicts_are_not_trivially_uniform() -> None:
    """Control: the profile set above must actually exercise more than one verdict.

    Without this, the equivalence proof above could pass vacuously because
    every profile lands on the same verdict either way.
    """
    literal_rule = _literal_equivalent_rule()
    verdicts = {literal_rule.evaluate(profile).verdict for profile in _representative_profiles()}
    assert verdicts == {
        ApplicabilityVerdict.APPLICABLE,
        ApplicabilityVerdict.NOT_APPLICABLE,
        ApplicabilityVerdict.INCOMPLETE,
    }


def test_a_fresh_authority_sees_a_mutated_applicability_rule(tmp_path: Path) -> None:
    """Condition 2: staleness is seen -- a tree edit reaches the NEXT resolution.

    Anti-tautology proof for the deliberate no-``@cache`` decision: a
    ``@cache``-wrapped resolver would return ``original_result`` again here
    instead of the mutated one, and this assertion would catch it.
    """
    _write_scratch_tree(tmp_path, applicable_reason="applies (original)")
    registry_root = tmp_path / "registry" / "aeat"

    original_authority = compile_validated_authority(registry_root, bundled_path())
    original_rule = resolve_applicability_rule_from_authority(original_authority, Modelo(_PLANTED_MODELO))
    assert original_rule.applicable_reason == "applies (original)"

    fragment_path = (
        registry_root / "modelos" / _PLANTED_MODELO / "revisions" / "2025" / "applicability" / "0001-applicability.toml"
    )
    assert fragment_path.is_file()
    fragment_path.write_text(
        fragment_path.read_text(encoding="utf-8").replace("applies (original)", "applies (mutated)"),
        encoding="utf-8",
    )

    mutated_authority = compile_validated_authority(registry_root, bundled_path())
    assert mutated_authority is not original_authority, (
        "the fingerprint-keyed authority cache must key a new instance on the mutated content, or this proof is vacuous"
    )
    mutated_rule = resolve_applicability_rule_from_authority(mutated_authority, Modelo(_PLANTED_MODELO))
    assert mutated_rule.applicable_reason == "applies (mutated)"

    # The ORIGINAL authority instance must keep answering what it always did --
    # staleness is seen by resolving fresh, never by an existing instance mutating.
    replayed_rule = resolve_applicability_rule_from_authority(original_authority, Modelo(_PLANTED_MODELO))
    assert replayed_rule.applicable_reason == "applies (original)"
