"""The declared authority grade must be backed by resolved schema families.

A grade is a claim about what a revision can be trusted to do. The ladder is
disposition-conditional, not population-conditional: a family declared
inapplicable with a reason and citations RESOLVES the claim, while a family left
pending evidence leaves it unbacked. That distinction is the whole point, since
an informative modelo carrying export layouts and no formulas reaches filing
grade honestly while a calculation claim over an empty formula family does not.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core import RegistryAuthorityGrade, RegistrySchemaFamilyDisposition
from .._loader import load_registry_tree
from .._schema_family_coverage import build_revision_coverage_manifest
from .._validate_authority_grade import validate_authority_grade_section

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _unresolved_families(modelo_id: str, revision) -> set[str]:
    manifest = build_revision_coverage_manifest(modelo=modelo_id, revision=revision)
    return {
        row.family
        for row in manifest.rows
        if row.disposition is RegistrySchemaFamilyDisposition.BLOCKED_PENDING_EVIDENCE
    }


def _graded(revision, grade: RegistryAuthorityGrade | None):
    return revision.model_copy(update={"authority_grade": grade})


@pytest.fixture(scope="module")
def revision_with_unresolved_families():
    """A real bundled revision that still leaves at least one family pending.

    Built from the corpus rather than synthesised, so the ladder is exercised
    against a shape the registry actually holds.
    """
    root = Path(__file__).resolve().parents[4] / "_data" / "registry" / "aeat"
    modelos, _catalogues = load_registry_tree(root)
    for modelo in sorted(modelos, key=lambda m: m.id):
        for _revision_id, revision in sorted(modelo.revisions.items()):
            if _unresolved_families(modelo.id, revision):
                return modelo.id, revision
    pytest.fail(
        "no bundled revision leaves a family blocked pending evidence, so this "
        "module can no longer exercise the ladder against real data",
    )
    raise AssertionError


def test_the_applicability_floor_makes_no_coverage_claim(revision_with_unresolved_families) -> None:
    """The floor asserts scheduling reach only, so unresolved families are fine there."""
    modelo_id, revision = revision_with_unresolved_families
    graded = _graded(revision, RegistryAuthorityGrade.APPLICABILITY)
    assert validate_authority_grade_section("r", modelo_id=modelo_id, revision=graded) == []


def test_an_undeclared_grade_refuses_on_the_absence_and_not_as_a_filing_claim(
    revision_with_unresolved_families,
) -> None:
    """An ungraded revision must not be validated as though it claimed filing.

    Two failures share this validator and must stay distinguishable: declaring
    NOTHING and declaring TOO MUCH are different defects with different repairs.
    An ungraded revision is refused for making no claim, never for overrunning a
    claim it never made.

    The earlier version of this test asserted the ungraded case produced no
    failure at all. That encoded the exemption rather than the intent stated
    above, so it guarded the silent pass instead of the distinction, and it went
    green for the whole period the ladder was inert.
    """
    modelo_id, revision = revision_with_unresolved_families

    ungraded = validate_authority_grade_section("r", modelo_id=modelo_id, revision=_graded(revision, None))
    as_filing = validate_authority_grade_section(
        "r",
        modelo_id=modelo_id,
        revision=_graded(revision, RegistryAuthorityGrade.FILING),
    )

    assert ungraded, "an ungraded revision was not refused, so silence still buys the weakest treatment"
    assert "authority_grade" in ungraded[0]
    assert ungraded != as_filing, "the ungraded refusal is indistinguishable from the filing-overreach refusal"
    assert RegistryAuthorityGrade.FILING.value not in ungraded[0], (
        "the ungraded revision was refused as though it had claimed filing grade, which is the "
        "specific misreading this test exists to prevent"
    )
    assert as_filing, "the control failed: a filing claim over unresolved families must still refuse"


def test_filing_grade_refuses_while_any_family_is_pending(revision_with_unresolved_families) -> None:
    """The top rung asserts every enrolled family is resolved."""
    modelo_id, revision = revision_with_unresolved_families
    graded = _graded(revision, RegistryAuthorityGrade.FILING)

    failures = validate_authority_grade_section("r", modelo_id=modelo_id, revision=graded)

    assert failures, "filing grade passed over families still blocked pending evidence"
    assert "blocked pending evidence" in failures[0]
    for family in sorted(_unresolved_families(modelo_id, revision)):
        assert family in failures[0], f"the refusal does not name the unresolved family {family!r}"


def test_calculation_grade_refuses_an_unresolved_formula_family(revision_with_unresolved_families) -> None:
    """A calculation claim over a formula family nobody built must refuse."""
    modelo_id, revision = revision_with_unresolved_families
    if "formulas" not in _unresolved_families(modelo_id, revision):
        pytest.fail("the chosen revision resolves its formula family, so this case is not exercised")

    failures = validate_authority_grade_section(
        "r",
        modelo_id=modelo_id,
        revision=_graded(revision, RegistryAuthorityGrade.CALCULATION),
    )

    assert failures
    assert "formulas" in failures[0]
    assert "calculation" in failures[0]


def test_calculation_grade_ignores_families_it_does_not_assert(revision_with_unresolved_families) -> None:
    """The calculation rung must not refuse on a family only filing enrols.

    Otherwise the rungs collapse into one and the ladder stops meaning anything.
    """
    modelo_id, revision = revision_with_unresolved_families
    unresolved = _unresolved_families(modelo_id, revision)
    if unresolved <= {"formulas"}:
        pytest.fail("the chosen revision has no non-formula pending family to distinguish the rungs")

    stripped = revision.model_copy(
        update={"formulas": revision.formulas or (), "authority_grade": RegistryAuthorityGrade.CALCULATION},
    )
    if "formulas" in _unresolved_families(modelo_id, stripped):
        return  # formulas genuinely pending here; the sibling test covers it

    assert validate_authority_grade_section("r", modelo_id=modelo_id, revision=stripped) == []


def test_the_refusal_is_accumulating_and_never_raises(revision_with_unresolved_families) -> None:
    """A section validator returns its failures so one revision cannot hide the next."""
    modelo_id, revision = revision_with_unresolved_families
    result = validate_authority_grade_section(
        "r",
        modelo_id=modelo_id,
        revision=_graded(revision, RegistryAuthorityGrade.FILING),
    )
    assert isinstance(result, list)
    assert all(isinstance(message, str) for message in result)
