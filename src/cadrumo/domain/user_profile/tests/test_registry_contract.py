"""User-profile schema coverage checks against committed modelo registry use."""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel, ValidationError

from ....core import BindingSourceKind
from ....core.errors.severity import BaseSeverity
from ...calculations.registry.authority import bundled_authority
from ...calculations.registry.bindings import ProfileSelector
from ...calculations.registry.schema import DataBindingDefinition
from ..loader import load_user_profile_schema
from ..registry_contract import (
    UserProfileRegistryContractIssue,
    build_user_profile_selector_index,
    profile_binding_selectors,
    validate_user_profile_registry_contract,
)
from ..schema import ProfileDerivedSelectorDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

if TYPE_CHECKING:  # pragma: no cover
    from ..schema import ProfileSchemaDefinition

_MODELO_100_ANUALIDADES_YEARS = (2021, 2022, 2023)


def test_registry_contract_issue_uses_base_severity_but_refuses_info() -> None:
    issue = UserProfileRegistryContractIssue(
        severity=BaseSeverity.WARNING,
        modelo_id="303",
        revision_id="2025",
        surface="binding",
        construct_id="binding-iva-regime",
        selector="iva.regime",
        message="profile selector needs review",
    )

    assert issue.severity is BaseSeverity.WARNING
    with pytest.raises(ValueError, match="Input should be"):
        UserProfileRegistryContractIssue.model_validate(
            {
                "severity": BaseSeverity.INFO,
                "modelo_id": "303",
                "revision_id": "2025",
                "surface": "binding",
                "construct_id": "binding-iva-regime",
                "selector": "iva.regime",
                "message": "informational findings are not part of this contract",
            },
        )


def test_schema_selector_index_contains_modelo_profile_namespaces() -> None:
    schema = load_user_profile_schema()

    index = build_user_profile_selector_index(schema)

    assert "tax.id" in index.profile_selectors
    assert "TaxResidenceProfile.ccaa" in index.profile_selectors
    assert "RentaFamilyProfile.descendants.tax_id" in index.profile_selectors
    assert "RentaFamilyProfile.ascendants.cohabiting_descendant_count" in index.profile_selectors
    assert "enrollment.large_company" in index.schedule_predicates
    assert "enrollment.public_administration_budget_gt_6000000" in index.schedule_predicates
    assert "tax.id" not in index.schedule_predicates
    assert not hasattr(index, "export_headers")


def test_anualidades_selector_still_resolves_through_its_derived_pattern() -> None:
    """Dropping the per-year field leaves the selector resolvable via the pattern.

    This is the derived-selector namespace doing its job: the pattern is the
    resolution route that must outlive the per-year field declarations, so a
    schema carrying the pattern but not the field is still a valid contract.
    The companion test below proves the pattern is the ONLY thing holding it
    up, so this is a second route rather than a hole.
    """
    schema = load_user_profile_schema()
    model = bundled_authority().modelo("100")
    failures: list[str] = []

    for year in _MODELO_100_ANUALIDADES_YEARS:
        selector = f"renta_family.anualidades_sin_minimo_descendientes_{year}"
        report = validate_user_profile_registry_contract((model,), _schema_without_field(schema, selector))
        if not report.valid:
            failures.append(f"{year}: {selector!r} should resolve through its derived pattern, got {report.errors!r}")

    assert not failures, "\n".join(failures)


def test_missing_modelo_100_anualidades_selector_is_rejected_for_each_year() -> None:
    """A selector declared by neither a field nor a pattern is still an error.

    Both resolution routes are removed, so this keeps pinning the original
    contract: nothing silently excuses an undeclared profile binding selector.
    """
    schema = load_user_profile_schema()
    model = bundled_authority().modelo("100")
    failures: list[str] = []

    for year in _MODELO_100_ANUALIDADES_YEARS:
        selector = f"renta_family.anualidades_sin_minimo_descendientes_{year}"
        broken_schema = _schema_without_derived_pattern(_schema_without_field(schema, selector), selector)
        report = validate_user_profile_registry_contract((model,), broken_schema)
        if report.valid:
            failures.append(f"{year}: removing {selector!r} unexpectedly left the report valid")
            continue
        if not any(issue.selector == selector for issue in report.errors):
            failures.append(f"{year}: removing {selector!r} did not produce a matching error")

    assert not failures, "\n".join(failures)


def test_every_declared_derived_pattern_matches_a_live_binding_selector() -> None:
    """Anti-rot: a declared pattern nothing consumes is a dead declaration.

    The namespace exists to keep real registry binding selectors resolvable.
    A pattern matching no live selector is either a typo or the residue of a
    retired family, and in both cases it silently widens what the write
    refusal will later cover. The reverse direction -- a live selector no
    pattern or field covers -- is already an ERROR in the contract report.
    """
    schema = load_user_profile_schema()
    live_selectors = _live_profile_binding_selectors()

    unmatched = [
        definition.pattern
        for definition in schema.derived_selectors
        if not any(definition.matches(selector) for selector in live_selectors)
    ]

    assert not unmatched, (
        f"declared derived-selector pattern(s) match no live registry binding selector: {unmatched!r}; "
        f"delete the pattern or fix it to match the selectors it is meant to own"
    )


def test_anti_rot_gate_detects_a_pattern_that_matches_nothing() -> None:
    """Negative control: the anti-rot predicate must fail on a dead pattern.

    The gate above passes today, which on its own cannot distinguish "every
    pattern is live" from "the predicate never fails". A pattern matching no
    live selector is added in memory and the same predicate is required to
    catch it. In memory rather than by editing the committed TOML: a
    mutation window on a tracked file in this worktree is shippable state.
    """
    schema = load_user_profile_schema()
    live_selectors = _live_profile_binding_selectors()
    dead = ProfileDerivedSelectorDefinition.model_validate(
        {
            "pattern": "renta_family.no_such_derived_family_{filing_year}",
            "derived_from": ("renta_family.descendiente",),
            "entry_surface": "aeat config profile descendiente",
            "description": "a pattern no live binding selector consumes",
        },
    )
    rotted = schema.model_copy(update={"derived_selectors": (*schema.derived_selectors, dead)})

    unmatched = [
        definition.pattern
        for definition in rotted.derived_selectors
        if not any(definition.matches(selector) for selector in live_selectors)
    ]

    assert unmatched == ["renta_family.no_such_derived_family_{filing_year}"]


def test_derived_patterns_cover_exactly_the_engine_owned_selectors() -> None:
    """The patterns own the 23 derived selectors and neither operator input.

    ``cotizaciones_ss_madre`` and ``rental_reduccion_art_23_2_tier`` are
    genuine taxpayer input that keep their declarations, so a pattern
    reaching either would later refuse a write the operator must be able to
    make. The count is asserted alongside the exclusions because a pattern
    that silently stopped matching would otherwise leave every gate green.
    """
    schema = load_user_profile_schema()
    live_selectors = _live_profile_binding_selectors()

    covered = {
        selector
        for selector in live_selectors
        if any(definition.matches(selector) for definition in schema.derived_selectors)
    }

    assert len(covered) == 23, sorted(covered)
    assert "tax_residence.state_attribution_ratio" in covered
    assert not [selector for selector in covered if "cotizaciones_ss_madre" in selector]
    assert not [selector for selector in covered if "rental_reduccion_art_23_2_tier" in selector]


def test_aggregate_pattern_does_not_swallow_its_autonomico_sibling() -> None:
    """The terminal anchor keeps the shorter pattern out of the longer's paths.

    ``descendientes_minimos_aggregate_{filing_year}`` is a literal prefix of
    ``..._aggregate_autonomico_{filing_year}``. Without a four-digit
    placeholder and a terminal anchor the shorter pattern matches the
    longer's six selectors, which would make deleting the longer pattern
    undetectable by the anti-rot gate above.
    """
    schema = load_user_profile_schema()
    estatal = _derived_pattern_ending(schema, "aggregate_{filing_year}")
    autonomico = _derived_pattern_ending(schema, "aggregate_autonomico_{filing_year}")

    assert estatal.matches("renta_family.descendientes_minimos_aggregate_2024")
    assert not estatal.matches("renta_family.descendientes_minimos_aggregate_autonomico_2024")
    assert autonomico.matches("renta_family.descendientes_minimos_aggregate_autonomico_2024")
    # A non-year suffix is not a filing year, however plausible it looks.
    assert not estatal.matches("renta_family.descendientes_minimos_aggregate_20244")
    assert not estatal.matches("renta_family.descendientes_minimos_aggregate_totals")


def test_unknown_derived_pattern_placeholder_is_refused() -> None:
    """A placeholder with no declared fragment raises instead of matching nothing.

    The refusal surfaces as a pydantic ``ValidationError`` because the check
    runs inside a model validator and ``UserProfileValidationError`` is a
    ``ValueError``; the originating message is asserted so the test cannot
    pass on an unrelated validation failure.
    """
    with pytest.raises(ValidationError, match="has no declared regex fragment"):
        ProfileDerivedSelectorDefinition.model_validate(
            {
                "pattern": "renta_family.something_{not_a_declared_placeholder}",
                "derived_from": ("renta_family.descendiente",),
                "entry_surface": "aeat config profile descendiente",
                "description": "pattern naming an undeclared placeholder",
            },
        )


def test_profile_binding_selectors_is_public_and_deduplicates_supported_selector_forms() -> None:
    selectors = profile_binding_selectors(
        {
            "profile_key": "tax.id",
            "profile_keys": ("tax.id", "tax.residence.ccaa"),
            "required_when_profile_key": "enrollment.large_company",
            "profile_model": "TaxResidenceProfile",
            "field": "ccaa",
        },
    )

    assert selectors == (
        "tax.id",
        "tax.residence.ccaa",
        "enrollment.large_company",
        "TaxResidenceProfile.ccaa",
    )


def test_profile_binding_selectors_resolves_a_real_hydrated_profile_selector() -> None:
    """The legitimate path: a real ``source = "profile"`` binding still resolves.

    ``binding.selector`` is hydrated into ``ProfileSelector`` at construction
    time by ``DataBindingDefinition``'s discriminated-union field validator
    (never a raw dict), matching the exact object every real caller of
    :func:`profile_binding_selectors` (all pre-filtered to ``source ==
    BindingSourceKind.PROFILE``) actually passes.
    """
    binding = DataBindingDefinition.model_validate(
        {
            "id": "renta-2025-profile-tax-residence-ccaa",
            "source": "profile",
            "selector": {
                "profile_model": "TaxResidenceProfile",
                "field": "ccaa",
                "xsd_attribute": "codigoCADeclaracion",
                "dictionary_field": "ZCCAD",
                "required_when_profile_key": "enrollment.large_company",
                "required_when_value": "S",
            },
            "aggregation": {"op": "copy"},
            "typed_enum": "CCAA",
            "legal_refs": ("orden-hac-277-2026:art-3",),
            "source_refs": ("aeat-dr-100-2025-dictionary",),
        },
    )

    assert not isinstance(binding.selector, dict), (
        "the fix relies on this being an already-hydrated ProfileSelector model, "
        "never a raw mapping -- if this assertion ever fails, the hydration "
        "contract this fix depends on has changed and the fix must be revisited"
    )
    assert profile_binding_selectors(binding.selector) == (
        "enrollment.large_company",
        "TaxResidenceProfile.ccaa",
    )


def test_profile_binding_selectors_ignores_a_non_profile_typed_selector() -> None:
    """A different binding-source family's typed selector never carries a
    profile key: the ``isinstance(selector, ProfileSelector)`` narrowing
    means only a genuine ``ProfileSelector`` reaches the attribute-access
    branch, and every other typed selector shape is a clean no-op rather
    than an attempted (and doomed) dict-style read on a BaseModel.
    """

    class _UnrelatedSelector(BaseModel):
        casilla_id: str

    assert profile_binding_selectors(_UnrelatedSelector(casilla_id="0003")) == ()


def test_a_dropped_profile_selector_field_is_refused_not_silently_missing() -> None:
    """The bite proof: a ``ProfileSelector`` instance that has genuinely lost a
    declared field must fail loud, never silently drop the value.

    Before the fix, :func:`profile_binding_selectors` discarded the model's
    type information via ``model_dump()`` and re-read the resulting plain
    dict with the string literal ``selector.get("required_when_profile_key")``.
    If ``ProfileSelector``'s field of that name (declared at ``_bindings.py``)
    were ever renamed, that read would keep silently returning ``None``
    forever -- permanently indistinguishable from "this binding has no
    conditional gate" -- while construction-time validation kept passing (it
    would just be validating the new name). This simulates that drift
    directly on a real, otherwise-valid ``ProfileSelector`` instance (the
    field is removed from the live instance's ``__dict__``, not stood in with
    a look-alike class) and proves the fixed attribute-access read fails loud
    instead of silently dropping the gate.
    """
    selector = ProfileSelector(
        profile_key="tax.id",
        required_when_profile_key="enrollment.large_company",
        required_when_value="S",
    )
    del selector.__dict__["required_when_profile_key"]

    with pytest.raises(AttributeError, match="required_when_profile_key"):
        profile_binding_selectors(selector)


def test_committed_modelo_profile_selectors_are_declared_by_user_profile_schema() -> None:
    schema = load_user_profile_schema()
    modelos = bundled_authority().modelos

    report = validate_user_profile_registry_contract(modelos, schema)

    blocking = [
        f"{issue.modelo_id}:{issue.revision_id}:{issue.surface}:{issue.construct_id}:{issue.selector}"
        for issue in report.errors
    ]
    assert report.valid, "\n".join(blocking)
    assert all(issue.severity is not BaseSeverity.ERROR for issue in report.issues)
    assert not report.warnings
    assert not report.issues


def test_user_profile_defining_modules_import_before_registry_barrel() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import cadrumo.domain.user_profile.loader as l; "
            "import cadrumo.domain.user_profile.registry_contract as c; "
            "import cadrumo.domain.calculations.registry as r; "
            "assert hasattr(l, 'load_user_profile_schema'); "
            "assert hasattr(c, 'validate_user_profile_registry_contract'); "
            "assert hasattr(r, 'RegistryValidator')",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def _live_profile_binding_selectors() -> frozenset[str]:
    """Every profile-sourced binding selector the committed registry declares."""
    selectors: set[str] = set()
    for modelo in bundled_authority().modelos:
        for revision in modelo.revisions.values():
            for binding in revision.bindings:
                if binding.source != BindingSourceKind.PROFILE:
                    continue
                selectors.update(profile_binding_selectors(binding.selector))
    return frozenset(selectors)


def _derived_pattern_ending(schema: ProfileSchemaDefinition, suffix: str) -> ProfileDerivedSelectorDefinition:
    matches = [definition for definition in schema.derived_selectors if definition.pattern.endswith(suffix)]
    assert len(matches) == 1, f"expected exactly one derived pattern ending {suffix!r}, got {matches!r}"
    return matches[0]


def _schema_without_derived_pattern(
    schema: ProfileSchemaDefinition,
    selector: str,
) -> ProfileSchemaDefinition:
    """Drop every derived pattern that would resolve *selector*."""
    remaining = tuple(definition for definition in schema.derived_selectors if not definition.matches(selector))
    return schema.model_copy(update={"derived_selectors": remaining})


def _schema_without_field(
    schema: ProfileSchemaDefinition,
    path: str,
) -> ProfileSchemaDefinition:
    section_key, field_key = path.split(".", 1)
    sections = []
    for section in schema.sections:
        if section.key != section_key:
            sections.append(section)
            continue
        fields = tuple(field for field in section.fields if field.key != field_key)
        sections.append(section.model_copy(update={"fields": fields}))
    return schema.model_copy(update={"sections": tuple(sections)})
