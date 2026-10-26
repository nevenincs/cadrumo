"""Selected revisions may serve snapshots only within their declared authority."""

from __future__ import annotations

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from ..authority import PinnedAuthorityOperation
from ..errors import RegistryValidationError
from ..governed_fact_scope import validating_governed_facts
from ..schema import ModeloDefinition, RegistryCatalogues, RegistrySnapshot
from ..snapshot import build_validated_snapshot
from .registry_tree import bundled_modelo_components

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODEL = "130"
_YEAR = 2026
_PERIOD = "1T"


def _registry_subject(
    grade: RegistryAuthorityGrade | None,
) -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelo, catalogues = bundled_modelo_components(_MODEL)
    revision = next(iter(modelo.revisions.values()))
    revised = revision.model_copy(update={"authority_grade": grade})
    return modelo.model_copy(update={"revisions": {revised.id: revised}}), catalogues


def _snapshot(
    operation: PinnedAuthorityOperation,
    modelo: ModeloDefinition,
    catalogues: RegistryCatalogues,
    grade: RegistryAuthorityGrade,
) -> RegistrySnapshot:
    with validating_governed_facts(operation):
        return build_validated_snapshot(
            modelo,
            catalogues,
            filing_year=_YEAR,
            period=_PERIOD,
            grade=grade,
        )


@pytest.mark.parametrize("requested_grade", list(RegistryAuthorityGrade))
def test_an_ungraded_selected_revision_cannot_satisfy_any_snapshot_grade(
    operation: PinnedAuthorityOperation,
    requested_grade: RegistryAuthorityGrade,
) -> None:
    modelo, catalogues = _registry_subject(None)

    with pytest.raises(
        RegistryValidationError,
        match=rf"declares no authority_grade.*requested {requested_grade.value!r}",
    ):
        _snapshot(operation, modelo, catalogues, requested_grade)


@pytest.mark.parametrize(
    ("declared_grade", "requested_grade"),
    [
        (RegistryAuthorityGrade.APPLICABILITY, RegistryAuthorityGrade.CALCULATION),
        (RegistryAuthorityGrade.APPLICABILITY, RegistryAuthorityGrade.FILING),
        (RegistryAuthorityGrade.CALCULATION, RegistryAuthorityGrade.FILING),
    ],
)
def test_a_selected_revision_cannot_escalate_above_its_declared_grade(
    operation: PinnedAuthorityOperation,
    declared_grade: RegistryAuthorityGrade,
    requested_grade: RegistryAuthorityGrade,
) -> None:
    modelo, catalogues = _registry_subject(declared_grade)

    with pytest.raises(
        RegistryValidationError,
        match=rf"declares {declared_grade.value!r} authority grade.*requested {requested_grade.value!r}",
    ):
        _snapshot(operation, modelo, catalogues, requested_grade)


@pytest.mark.parametrize(
    ("declared_grade", "requested_grade"),
    [
        (RegistryAuthorityGrade.APPLICABILITY, RegistryAuthorityGrade.APPLICABILITY),
        (RegistryAuthorityGrade.CALCULATION, RegistryAuthorityGrade.APPLICABILITY),
        (RegistryAuthorityGrade.CALCULATION, RegistryAuthorityGrade.CALCULATION),
        (RegistryAuthorityGrade.FILING, RegistryAuthorityGrade.APPLICABILITY),
        (RegistryAuthorityGrade.FILING, RegistryAuthorityGrade.CALCULATION),
        (RegistryAuthorityGrade.FILING, RegistryAuthorityGrade.FILING),
    ],
)
def test_equal_or_lower_snapshot_requests_pass_the_grade_boundary(
    operation: PinnedAuthorityOperation,
    declared_grade: RegistryAuthorityGrade,
    requested_grade: RegistryAuthorityGrade,
) -> None:
    modelo, catalogues = _registry_subject(declared_grade)

    snapshot = _snapshot(operation, modelo, catalogues, requested_grade)

    assert snapshot.revision.authority_grade is declared_grade
