"""A stopped operation records the registry's failed condition for every frontend that reads its detail."""

from __future__ import annotations

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.errors import RegistryError, RegistryValidationError
from ....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ....domain.calculations.registry.snapshot import build_validated_snapshot
from ....domain.calculations.registry.tests.registry_tree import bundled_registry_tree
from ..error_detail import OperationErrorDetailKind, build_operation_error_detail

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _filing_grade_refusal(operation: PinnedAuthorityOperation) -> tuple[str, str, str, RegistryValidationError]:
    """Ask the first published revision whose declared grade is below filing for filing authority.

    The edition is chosen from the registry, never named, so a revision later raised to filing grade
    hands the refusal to the next one still below it.
    """
    ladder = tuple(RegistryAuthorityGrade)
    modelos, catalogues = bundled_registry_tree()
    with validating_governed_facts(operation):
        for modelo in sorted(modelos, key=lambda candidate: candidate.id):
            for revision in modelo.revisions.values():
                if not revision.is_graded:
                    continue
                declared = revision.effective_authority_grade
                if ladder.index(declared) >= ladder.index(RegistryAuthorityGrade.FILING):
                    continue
                selector = revision.period_selector
                years = selector.years or (() if selector.year_from is None else (selector.year_from,))
                for year in years:
                    for period in selector.periods_for_year(year):
                        try:
                            build_validated_snapshot(
                                modelo,
                                catalogues,
                                filing_year=year,
                                period=period,
                                revision_id=revision.id,
                                grade=RegistryAuthorityGrade.FILING,
                            )
                        except RegistryValidationError as refused:
                            failure = refused.registry_failure
                            if failure is not None and "filing_year" not in failure.facts:
                                return modelo.id, revision.id, declared.value, refused
                        except RegistryError:
                            continue
    pytest.fail("no published revision below filing grade refuses a filing snapshot by its declared grade")


def test_a_registry_authority_refusal_records_its_failed_condition_and_facts(
    operation: PinnedAuthorityOperation,
) -> None:
    modelo_id, revision_id, declared_grade, error = _filing_grade_refusal(operation)

    detail = build_operation_error_detail(error)

    assert detail is not None
    assert detail.kind is OperationErrorDetailKind.REGISTERED_ERROR
    assert detail.error_code == "ERROR_CALCULATIONS_REGISTRY_VALIDATION"
    verdict = detail.precondition_verdict()
    assert verdict is not None
    assert verdict.failed_condition_id == "registry.snapshot.authority_grade.sufficient"
    (evidence,) = verdict.evidence
    assert dict(evidence.values) == {
        "authority_grade_declared": True,
        "declared_authority_grade": declared_grade,
        "modelo": modelo_id,
        "requested_authority_grade": "filing",
        "revision_id": revision_id,
    }


def test_a_registry_error_without_a_classification_records_no_verdict() -> None:
    detail = build_operation_error_detail(RegistryValidationError("unclassified registry contradiction"))

    assert detail is not None
    assert detail.error_code == "ERROR_CALCULATIONS_REGISTRY_VALIDATION"
    assert detail.precondition_verdict() is None
