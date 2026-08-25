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

from pathlib import Path

import pytest

from .....core import Modelo
from .....domain.deadlines import EntityType, FiscalResidency, IVARegime, TaxpayerProfile
from .. import (
    ApplicabilityVerdict,
    ValidatedRegistryAuthority,
    resolve_applicability_rule_from_authority,
)
from ..applicability import ModeloApplicabilityRule
from ._loader_directory_mode_support import write_extracted_corpus_sidecar, write_fragmented_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL_ID = "test-ley-001:art-1"
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
review_status = "reviewed"

[sources."{_GUIDANCE_SOURCE_ID}"]
evidence_tier = "official_source_guidance"
authority = "aeat"
kind = "instructions"
corpus_path = "corpus/test/test-source-002.pdf"
sha256 = "44f8354494a5ba03ba1792a8d3e9c534c47a9181980fde7a3f44b06ef2ae7c7f"
bytes = 1000
retrieved_at = 2025-01-01
source_url = "https://example.com/test-source-002"
review_status = "reviewed"
"""

_MANIFEST_TOML = f"""\
[modelo]
id = "100"
tax_domain = "irpf"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["{_LEGAL_ID}"]
source_refs = ["{_SOURCE_ID}"]
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
source_refs = ["{_SOURCE_ID}"]
orden_aplicabilidad = ["{_LEGAL_ID}"]

[[revisions."2025".application_links]]
id = "test-filing-link"
surface = "filing"
consumer = "cli.app"
requires_snapshot = true
legal_refs = ["{_LEGAL_ID}"]
source_refs = ["{_GUIDANCE_SOURCE_ID}"]

[[revisions."2025".casillas]]
id = "01"
number = "01"
section = ["test"]
data_type = "integer"
legal_refs = ["{_LEGAL_ID}"]
source_refs = ["{_SOURCE_ID}"]

[[revisions."2025".workbook_parity_refs]]
id = "test-workbook-001"
workbook_source = "{_SOURCE_ID}"
fixture_id = "test-fixture-001"
formula_coverage = "record_design_layout"
runner_required = false
tolerance = "0.00"
legal_refs = ["{_LEGAL_ID}"]
source_refs = ["{_SOURCE_ID}"]

[[revisions."2025".applicability]]
id = "m100-cutover-test"
applicable_entity_types = ["{entity_type}"]
applicable_fiscal_residencies = ["resident_irpf"]
applicable_reason = "{applicable_reason}"
not_applicable_reason = "does not apply"
cuota_bearing = true
legal_refs = ["{_LEGAL_ID}"]
"""


def _write_scratch_tree(root: Path, *, applicable_reason: str) -> None:
    registry_root = root / "registry" / "aeat"
    legal_dir = registry_root / "legal"
    revision_dir = registry_root / "modelos" / "100" / "revisions" / "2025"
    revision_dir.mkdir(parents=True)
    legal_dir.mkdir(parents=True)
    corpus_file = root / "corpus" / "test" / "test-source-001.pdf"
    corpus_file.parent.mkdir(parents=True)
    corpus_file.write_bytes(b"x" * 1000)
    (corpus_file.parent / "test-source-002.pdf").write_bytes(b"x" * 1000)
    legal_corpus = corpus_file.parent / "test-ley-001.html"
    legal_corpus.write_text("<html>test provision text</html>", encoding="utf-8")
    write_extracted_corpus_sidecar(legal_corpus, anchor="a1", text="test provision text")

    (legal_dir / "catalogue.toml").write_text(_CATALOGUE_TOML, encoding="utf-8")
    # The loader requires every authoring tree to declare its supported
    # filing years, so a scratch tree omitting it fails to load before the
    # applicability rule this test mutates can be observed at all.
    (legal_dir / "supported-filing-years.toml").write_text(
        "[supported_filing_years]\nyears = [2025]\n",
        encoding="utf-8",
    )
    (registry_root / "modelos" / "100" / "manifest.toml").write_text(_MANIFEST_TOML, encoding="utf-8")

    write_fragmented_revision(
        revision_dir,
        _revision_toml(entity_type="natural_person", applicable_reason=applicable_reason),
    )


def _literal_equivalent_rule() -> ModeloApplicabilityRule:
    """The Python-literal shape the fragment above transcribes, for the equivalence proof."""
    return ModeloApplicabilityRule(
        modelo=Modelo.M100,
        applicable_entity_types=frozenset({EntityType.NATURAL_PERSON}),
        applicable_fiscal_residencies=frozenset({FiscalResidency.RESIDENT_IRPF}),
        applicable_reason="applies",
        not_applicable_reason="does not apply",
        cuota_bearing=True,
        legal_refs=(_LEGAL_ID,),
    )


def _representative_profiles() -> tuple[TaxpayerProfile, ...]:
    return (
        TaxpayerProfile(
            tax_id="12345678Z",
            entity_type=EntityType.NATURAL_PERSON,
            fiscal_residency=FiscalResidency.RESIDENT_IRPF,
            iva_regime=IVARegime.NO_APLICA,
        ),
        TaxpayerProfile(tax_id="B12345674", entity_type=EntityType.LEGAL_ENTITY, iva_regime=IVARegime.NO_APLICA),
        TaxpayerProfile(tax_id="12345678Z", iva_regime=IVARegime.NO_APLICA),
    )


def test_registry_resolved_rule_matches_the_literal_it_transcribes_per_profile(tmp_path: Path) -> None:
    """Condition 1: identical verdict, reason and legal_refs for every representative profile.

    Not "hydrated fragment equals literal" at the data layer (the fragment-family proof already
    proves that) -- this evaluates BOTH through the real
    ``ModeloApplicabilityRule.evaluate`` and compares the
    ``ModeloApplicability`` results the application actually consumes.
    """
    _write_scratch_tree(tmp_path, applicable_reason="applies")
    authority = ValidatedRegistryAuthority.load(tmp_path / "registry" / "aeat", source_root=tmp_path)

    registry_rule = resolve_applicability_rule_from_authority(authority, Modelo.M100)
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

    original_authority = ValidatedRegistryAuthority.load(registry_root, source_root=tmp_path)
    original_rule = resolve_applicability_rule_from_authority(original_authority, Modelo.M100)
    assert original_rule.applicable_reason == "applies (original)"

    fragment_path = (
        registry_root / "modelos" / "100" / "revisions" / "2025" / "applicability" / "0001-applicability.toml"
    )
    assert fragment_path.is_file()
    fragment_path.write_text(
        fragment_path.read_text(encoding="utf-8").replace("applies (original)", "applies (mutated)"),
        encoding="utf-8",
    )

    mutated_authority = ValidatedRegistryAuthority.load(registry_root, source_root=tmp_path)
    assert mutated_authority is not original_authority, (
        "the fingerprint-keyed authority cache must key a new instance on the mutated content, or this proof is vacuous"
    )
    mutated_rule = resolve_applicability_rule_from_authority(mutated_authority, Modelo.M100)
    assert mutated_rule.applicable_reason == "applies (mutated)"

    # The ORIGINAL authority instance must keep answering what it always did --
    # staleness is seen by resolving fresh, never by an existing instance mutating.
    replayed_rule = resolve_applicability_rule_from_authority(original_authority, Modelo.M100)
    assert replayed_rule.applicable_reason == "applies (original)"
