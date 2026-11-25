"""Pure application contracts for operator state-projection refusal messages and readiness grade."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from cadrumo.application.state_projection import (
    registry_readiness_refusal,
    registry_readiness_revision_mismatch_refusal,
    resolve_modelo_readiness_registry,
)
from cadrumo.application.state_projection_models import ModeloReadinessRequest, ModeloRegistryRefusalCause
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_references import TemporalProjectionDirection
from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition, projected_exercise

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "100"
_PERIOD = "0A"
_QUARTER = "4T"


class _UnavailableAuthority:
    def reachable_authority_grade(self, *args: object, **kwargs: object) -> RegistryAuthorityGrade:
        return RegistryAuthorityGrade.FILING

    def snapshot(self, *args: object, **kwargs: object) -> None:
        raise FileNotFoundError("private-authority-path")


class _DifferentRevisionAuthority:
    def reachable_authority_grade(self, *args: object, **kwargs: object) -> RegistryAuthorityGrade:
        return RegistryAuthorityGrade.FILING

    def snapshot(self, *args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(revision=SimpleNamespace(id="actual"))


def test_registry_readiness_refusals_have_no_authored_describe_command() -> None:
    request = ModeloReadinessRequest(modelo="303", revision_id="rev", filing_year=2025)
    first = registry_readiness_refusal(request, period_token=_QUARTER, exc=RuntimeError("missing"))
    second = registry_readiness_revision_mismatch_refusal(
        request,
        period_token=_QUARTER,
        resolved_revision_id="resolved",
    )
    for refusal in (first, second):
        assert "aeat app modelo describe" not in refusal


@pytest.mark.parametrize("language", sorted(SUPPORTED_OUTPUT_LANGUAGES))
def test_registry_readiness_refusals_are_worded_in_every_output_language(language: str) -> None:
    request = ModeloReadinessRequest(modelo="303", revision_id="requested-revision", filing_year=2025)
    with override_settings(cadrumo_output_language=language):
        unresolved = registry_readiness_refusal(request, period_token=_QUARTER, exc=FileNotFoundError("private"))
        reasoned = registry_readiness_refusal(
            request, period_token=_QUARTER, exc=RegistryValidationError("the registry has no such edition")
        )
        mismatch = registry_readiness_revision_mismatch_refusal(
            request, period_token=_QUARTER, resolved_revision_id="resolved-revision"
        )

    for refusal in (unresolved, reasoned, mismatch):
        assert "303" in refusal
        assert "2025" in refusal
        assert _QUARTER in refusal
        assert "application.modelo.errors" not in refusal, "the catalogue key was echoed instead of words"
        assert "%{" not in refusal
    assert "private" not in unresolved
    assert "the registry has no such edition" in reasoned
    assert "requested-revision" in mismatch
    assert "resolved-revision" in mismatch
    assert len({unresolved, mismatch}) == 2


def test_unavailable_snapshot_carries_closed_cause_separate_from_refusal_prose() -> None:
    request = ModeloReadinessRequest(modelo="303", revision_id="wanted", filing_year=2025)
    resolution = resolve_modelo_readiness_registry(
        request,
        period=Period.from_year_and_code(2025, "1T"),
        operation=cast(PinnedAuthorityOperation, _UnavailableAuthority()),
    )
    assert resolution.snapshot is None
    assert resolution.cause is ModeloRegistryRefusalCause.SNAPSHOT_UNAVAILABLE
    assert resolution.refusal
    assert "private-authority-path" not in resolution.cause.value
    assert "private-authority-path" not in resolution.refusal


def test_revision_mismatch_carries_distinct_closed_cause() -> None:
    request = ModeloReadinessRequest(modelo="303", revision_id="wanted", filing_year=2025)
    resolution = resolve_modelo_readiness_registry(
        request,
        period=Period.from_year_and_code(2025, "1T"),
        operation=cast(PinnedAuthorityOperation, _DifferentRevisionAuthority()),
    )
    assert resolution.snapshot is None
    assert resolution.cause is ModeloRegistryRefusalCause.REVISION_MISMATCH
    assert resolution.refusal


def _request(operation: PinnedAuthorityOperation, filing_year: int) -> ModeloReadinessRequest:
    revision_id = operation.reading_snapshot(_MODELO, filing_year=filing_year, period=_PERIOD).revision.id
    return ModeloReadinessRequest(modelo=_MODELO, revision_id=revision_id, filing_year=filing_year)


def test_readiness_of_a_projected_year_resolves_at_the_grade_the_year_reaches(
    operation: PinnedAuthorityOperation,
) -> None:
    year = projected_exercise(_MODELO)

    resolution = resolve_modelo_readiness_registry(
        _request(operation, year), period=Period.from_year_and_code(year, _PERIOD), operation=operation
    )

    assert resolution.refusal == ""
    assert resolution.cause is None
    snapshot = resolution.snapshot
    assert snapshot is not None
    assert snapshot.filing_year == year
    assert snapshot.authored_filing_year == newest_authored_edition(_MODELO)
    assert snapshot.revision_projection_direction is TemporalProjectionDirection.FORWARD
    assert operation.reachable_authority_grade(_MODELO, filing_year=year, period=_PERIOD) is (
        RegistryAuthorityGrade.CALCULATION
    )


def test_readiness_of_the_newest_authored_year_resolves_unchanged(operation: PinnedAuthorityOperation) -> None:
    year = newest_authored_edition(_MODELO)

    resolution = resolve_modelo_readiness_registry(
        _request(operation, year), period=Period.from_year_and_code(year, _PERIOD), operation=operation
    )

    assert resolution.refusal == ""
    snapshot = resolution.snapshot
    assert snapshot is not None
    assert snapshot.filing_year == year
    assert snapshot.revision_projection_direction is TemporalProjectionDirection.AUTHORED
    assert snapshot.revision.id == _request(operation, year).revision_id


def test_readiness_refused_by_the_registry_serves_words_not_a_bare_english_line(
    operation: PinnedAuthorityOperation,
) -> None:
    below_floor = operation.supported_filing_years().floor - 1
    request = ModeloReadinessRequest(modelo=_MODELO, revision_id="any-revision", filing_year=below_floor)

    with override_settings(cadrumo_output_language="es"):
        resolution = resolve_modelo_readiness_registry(
            request, period=Period.from_year_and_code(below_floor, _PERIOD), operation=operation
        )

    assert resolution.snapshot is None
    assert resolution.cause is ModeloRegistryRefusalCause.SNAPSHOT_UNAVAILABLE
    assert resolution.refusal.startswith("No se pudieron resolver las definiciones del modelo 100")
    assert str(below_floor) in resolution.refusal
