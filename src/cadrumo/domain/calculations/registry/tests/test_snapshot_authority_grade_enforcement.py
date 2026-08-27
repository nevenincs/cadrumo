"""Selected revisions may serve snapshots only within their declared authority."""

from __future__ import annotations

from dataclasses import replace

import pytest

from .....core import RegistryAuthorityGrade
from .....tests.registry_tree import bundled_registry_tree
from .._snapshot_internals import _build_validated_snapshot
from ..authority import ValidatedRegistryAuthority
from ..errors import RegistryValidationError
from ..schema import ModeloDefinition, ModeloRevision, RegistryCatalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODEL = "130"
_YEAR = 2026
_PERIOD = "1T"


def _registry_subject(
    grade: RegistryAuthorityGrade | None,
) -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = bundled_registry_tree()
    modelo = next(candidate for candidate in modelos if candidate.id == _MODEL)
    revision = next(iter(modelo.revisions.values()))
    revised = revision.model_copy(update={"authority_grade": grade})
    return modelo.model_copy(update={"revisions": {revised.id: revised}}), catalogues


def _snapshot(
    modelo: ModeloDefinition,
    catalogues: RegistryCatalogues,
    grade: RegistryAuthorityGrade,
):
    return _build_validated_snapshot(
        modelo,
        catalogues,
        filing_year=_YEAR,
        period=_PERIOD,
        grade=grade,
    )


@pytest.mark.parametrize("requested_grade", list(RegistryAuthorityGrade))
def test_an_ungraded_selected_revision_cannot_satisfy_any_snapshot_grade(
    requested_grade: RegistryAuthorityGrade,
) -> None:
    modelo, catalogues = _registry_subject(None)

    with pytest.raises(
        RegistryValidationError,
        match=rf"declares no authority_grade.*requested {requested_grade.value!r}",
    ):
        _snapshot(modelo, catalogues, requested_grade)


@pytest.mark.parametrize(
    ("declared_grade", "requested_grade"),
    [
        (RegistryAuthorityGrade.APPLICABILITY, RegistryAuthorityGrade.CALCULATION),
        (RegistryAuthorityGrade.APPLICABILITY, RegistryAuthorityGrade.FILING),
        (RegistryAuthorityGrade.CALCULATION, RegistryAuthorityGrade.FILING),
    ],
)
def test_a_selected_revision_cannot_escalate_above_its_declared_grade(
    declared_grade: RegistryAuthorityGrade,
    requested_grade: RegistryAuthorityGrade,
) -> None:
    modelo, catalogues = _registry_subject(declared_grade)

    with pytest.raises(
        RegistryValidationError,
        match=rf"declares {declared_grade.value!r} authority grade.*requested {requested_grade.value!r}",
    ):
        _snapshot(modelo, catalogues, requested_grade)


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
    declared_grade: RegistryAuthorityGrade,
    requested_grade: RegistryAuthorityGrade,
) -> None:
    modelo, catalogues = _registry_subject(declared_grade)

    snapshot = _snapshot(modelo, catalogues, requested_grade)

    assert snapshot.revision.authority_grade is declared_grade


def test_the_authority_facade_refuses_a_mutated_lower_grade_revision(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """A real selected revision mutation must bite through the public facade."""
    control = registry_authority.snapshot(_MODEL, filing_year=_YEAR, period=_PERIOD)
    assert control.revision.authority_grade is RegistryAuthorityGrade.FILING

    original = registry_authority.modelo(_MODEL)
    selected: ModeloRevision = next(iter(original.revisions.values()))
    downgraded = selected.model_copy(update={"authority_grade": RegistryAuthorityGrade.CALCULATION})
    mutated = original.model_copy(update={"revisions": {downgraded.id: downgraded}})
    authority = replace(
        registry_authority,
        modelos=tuple(mutated if modelo.id == _MODEL else modelo for modelo in registry_authority.modelos),
        _modelos_by_id={**registry_authority._modelos_by_id, _MODEL: mutated},
        _snapshots={},
    )

    with pytest.raises(
        RegistryValidationError,
        match=r"declares 'calculation' authority grade.*requested 'filing'",
    ):
        authority.snapshot(_MODEL, filing_year=_YEAR, period=_PERIOD)
