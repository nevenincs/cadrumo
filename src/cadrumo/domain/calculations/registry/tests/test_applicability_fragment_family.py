"""Prove the ``applicability`` schema family.

Covers the whole chain a fragment family needs: SCHEMA_FAMILY enrolment,
real fragmented-directory loading, the inline-manifest refusal every section
field gets for free from the loader's shape-derived classification,
hydration into the runtime :class:`ModeloApplicabilityRule`, and the
accumulate-never-raise section validator.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core import Modelo
from .. import ApplicabilityRuleDefinition, ModeloRevision, RegistryLoadError, RegistryValidationError
from .._applicability import ModeloApplicabilityRule, hydrate_applicability_rule
from .._loader import load_modelo_directory
from .._schema_base import schema_family_enrollment_failures, schema_family_fields
from .._validate_applicability_section import validate_applicability_section
from ._referential_integrity_support import REFERENCE_LEGAL_ID, minimal_legal_ref, minimal_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MANIFEST_TEXT = (
    "[modelo]\n"
    'id = "999"\n'
    'tax_domain = "iva"\n'
    'cadence = "annual"\n'
    'jurisdiction = "ES-AEAT"\n'
    f'legal_refs = ["{REFERENCE_LEGAL_ID}"]\n'
    'source_refs = ["aeat-manual"]\n'
)
_REVISION_MANIFEST_TEXT = (
    '[revisions."2025"]\n'
    "valid_from = 2025-01-01\n"
    'period_selector = { years = [2025], periods = ["0A"] }\n'
    f'legal_refs = ["{REFERENCE_LEGAL_ID}"]\n'
    'source_refs = ["aeat-manual"]\n'
)
_FRAGMENT_TEXT = f"""
[[revisions."2025".applicability]]
id = "m999-seed"
applicable_entity_types = ["natural_person"]
applicable_fiscal_residencies = ["resident_irpf"]
applicable_reason = "applies"
not_applicable_reason = "does not apply"
cuota_bearing = true
legal_refs = ["{REFERENCE_LEGAL_ID}"]
""".lstrip()


def _write_directory_modelo(root: Path, *, inline_in_manifest: bool = False) -> Path:
    target = root / "999"
    (target).mkdir(parents=True)
    (target / "manifest.toml").write_text(_MANIFEST_TEXT, encoding="utf-8", newline="\n")
    revision_dir = target / "revisions" / "2025"
    revision_dir.mkdir(parents=True)
    if inline_in_manifest:
        (revision_dir / "revision.toml").write_text(
            _REVISION_MANIFEST_TEXT + _FRAGMENT_TEXT, encoding="utf-8", newline="\n"
        )
    else:
        (revision_dir / "revision.toml").write_text(_REVISION_MANIFEST_TEXT, encoding="utf-8", newline="\n")
        fragment_dir = revision_dir / "applicability"
        fragment_dir.mkdir()
        (fragment_dir / "0001-applicability.toml").write_text(_FRAGMENT_TEXT, encoding="utf-8", newline="\n")
    return target


def test_applicability_is_enrolled_as_a_schema_family() -> None:
    """The new field must be marked SCHEMA_FAMILY and enrolment must be complete."""
    assert "applicability" in schema_family_fields(ModeloRevision)
    assert schema_family_enrollment_failures(ModeloRevision) == ()


def test_a_fragmented_directory_modelo_loads_the_applicability_rule(tmp_path: Path) -> None:
    """A real fragment file under ``applicability/`` populates the revision family.

    Proves the loader's shape-derived section classification (never manually
    listed) actually reaches a brand-new family, not just that the pydantic
    model parses in isolation.
    """
    target = _write_directory_modelo(tmp_path)
    definition = load_modelo_directory(target)
    revision = definition.revisions["2025"]

    assert len(revision.applicability) == 1
    rule = revision.applicability[0]
    assert isinstance(rule, ApplicabilityRuleDefinition)
    assert rule.id == "m999-seed"
    assert rule.applicable_entity_types == ("natural_person",)
    assert rule.legal_refs == (REFERENCE_LEGAL_ID,)


def test_an_inline_applicability_table_in_the_manifest_is_a_hard_load_error(tmp_path: Path) -> None:
    """A revision.toml declaring ``applicability`` inline must be refused.

    The fragmented-layout invariant is derived from the schema shape, so this
    is the anti-tautology proof that the new family did not silently stay
    exempt from a refusal every OTHER section field already gets.
    """
    target = _write_directory_modelo(tmp_path, inline_in_manifest=True)
    with pytest.raises(RegistryLoadError, match="applicability"):
        load_modelo_directory(target)


def test_hydrate_applicability_rule_round_trips_every_axis() -> None:
    """A validated fragment hydrates into the exact runtime rule it describes."""
    fragment = ApplicabilityRuleDefinition(
        id="m999-seed",
        applicable_entity_types=("natural_person", "legal_entity"),
        required_income_categories=("actividad_economica",),
        required_estimation_regimes=("directa_normal",),
        applicable_fiscal_residencies=("resident_irpf",),
        applicable_iva_regimes=("GENERAL",),
        required_payer_fact="pays_withheld_income",
        applicable_reason="applies",
        not_applicable_reason="does not apply",
        cuota_bearing=True,
        legal_refs=(REFERENCE_LEGAL_ID,),
    )

    hydrated = hydrate_applicability_rule(Modelo.M100, fragment)

    from .....domain.deadlines import EntityType, FiscalResidency, IrpfEstimationRegime, IrpfIncomeCategory, IVARegime
    from .._applicability_payer_facts import PayerFact

    assert hydrated == ModeloApplicabilityRule(
        modelo=Modelo.M100,
        applicable_entity_types=frozenset({EntityType.NATURAL_PERSON, EntityType.LEGAL_ENTITY}),
        required_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        required_estimation_regimes=frozenset({IrpfEstimationRegime.DIRECTA_NORMAL}),
        applicable_fiscal_residencies=frozenset({FiscalResidency.RESIDENT_IRPF}),
        applicable_iva_regimes=frozenset({IVARegime.GENERAL}),
        required_payer_fact=PayerFact.PAYS_WITHHELD_INCOME,
        applicable_reason="applies",
        not_applicable_reason="does not apply",
        cuota_bearing=True,
        legal_refs=(REFERENCE_LEGAL_ID,),
    )


def test_hydrate_applicability_rule_names_the_unknown_token() -> None:
    """An unrecognised token raises a RegistryValidationError naming it, not a raw KeyError/ValueError."""
    fragment = ApplicabilityRuleDefinition(
        id="m999-bad",
        applicable_entity_types=("not_a_real_entity_type",),
        applicable_reason="applies",
        not_applicable_reason="does not apply",
        legal_refs=(REFERENCE_LEGAL_ID,),
    )

    with pytest.raises(RegistryValidationError, match="not_a_real_entity_type"):
        hydrate_applicability_rule(Modelo.M100, fragment)


def test_validate_applicability_section_accumulates_without_raising() -> None:
    """The validator collects both an unresolved legal ref and a bad token in one pass."""
    revision = minimal_revision().model_copy(
        update={
            "applicability": (
                ApplicabilityRuleDefinition(
                    id="m999-a",
                    applicable_entity_types=("natural_person",),
                    applicable_reason="applies",
                    not_applicable_reason="does not apply",
                    legal_refs=("ley-does-not-exist:art-1",),
                ),
                ApplicabilityRuleDefinition(
                    id="m999-b",
                    applicable_entity_types=("bogus_entity_type",),
                    applicable_reason="applies",
                    not_applicable_reason="does not apply",
                    legal_refs=(REFERENCE_LEGAL_ID,),
                ),
            ),
        },
    )
    legal_refs = {REFERENCE_LEGAL_ID: minimal_legal_ref()}

    failures = validate_applicability_section(
        prefix="modelo 100 revision 2025",
        modelo=Modelo.M100.value,
        revision=revision,
        legal_refs=legal_refs,
    )

    assert any("ley-does-not-exist:art-1" in failure for failure in failures)
    assert any("bogus_entity_type" in failure for failure in failures)
    assert any("2 applicability rules" in failure for failure in failures)
