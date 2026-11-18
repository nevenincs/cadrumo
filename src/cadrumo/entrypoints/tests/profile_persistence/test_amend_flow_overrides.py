"""Amend-flow tests for override validation and the casilla observations an amendment carries."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....application.calculations.tests.filing_evidence import general_m303_filing_evidence
from ....application.modelo.action_errors import (
    AmendmentOverrideCasillaError,
    CalculationRevisionStateError,
)
from ....application.modelo.amendment_actions import amend_modelo_revision
from ....application.modelo.calculation_revision_queries import get_calculation_revision
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.modelos.filing_record import (
    FilingDeclarationKind,
)
from ...adapter_composition_work_ports import (
    build_amendment_action_ports,
    build_calculation_action_ports,
)
from .amend_flow_support import (
    AMEND_EXPENSE_CASILLA,
    AMEND_INCOME_CASILLA,
    M303_PRINTED_RESULT_TOKEN,
    M303_RESULT_CASILLA,
    PRIOR_YEAR,
    PROFILE_ID,
    T4,
    UNKNOWN_AMEND_CASILLA,
    Repos,
    drive_amend_creates_complementaria,
    repos,
    seed_external_baseline,
)

__all__ = ["repos"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_amend_refuses_no_op_overrides(repos: Repos, *, operation: PinnedAuthorityOperation) -> None:
    """Overrides identical to the baseline produce the same content-
    addressed revision id; the action refuses rather than persisting
    a no-op amendment."""

    _wu_repo, _cr_repo, _fr_repo, _, _bv_repo = repos
    _, _, baseline = seed_external_baseline(
        repos, casilla_values={AMEND_INCOME_CASILLA: Decimal("1000")}, operation=operation
    )

    with pytest.raises(CalculationRevisionStateError) as exc_info, bundled_indexed_authority().operation() as operation:
        amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=PROFILE_ID, operation=operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={AMEND_INCOME_CASILLA: Decimal("1000")},
            amendment_kind=FilingDeclarationKind.COMPLEMENTARIA,
            reason="duplicate filing attempt",
            actor="operator-A",
            clock=T4,
        )
    assert exc_info.value.translated_message == "errors.error.error_modelo_calculation_revision_state"


def test_amend_refuses_overrides_with_casilla_ids_not_in_registry(
    repos: Repos, *, operation: PinnedAuthorityOperation
) -> None:
    """An override targeting a casilla id the registry does not declare
    for the baseline modelo / filing_year / period is refused. The
    corrected revision is the legal basis of the complementaria filing;
    fabricated casillas cannot be silently accepted."""

    _wu_repo, _cr_repo, _fr_repo, _, _bv_repo = repos
    _, _, baseline = seed_external_baseline(
        repos, casilla_values={AMEND_INCOME_CASILLA: Decimal("1000")}, operation=operation
    )

    with pytest.raises(AmendmentOverrideCasillaError) as exc_info, bundled_indexed_authority().operation() as operation:
        amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=PROFILE_ID, operation=operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={UNKNOWN_AMEND_CASILLA: Decimal("100")},
            amendment_kind=FilingDeclarationKind.COMPLEMENTARIA,
            reason="fabricated casilla rejected",
            actor="operator-A",
            clock=T4,
        )
    assert exc_info.value.translated_message == "application.modelo.errors.amendment_unknown_casillas"
    assert exc_info.value.context is not None
    casillas_obj = exc_info.value.context.get("casillas", [])
    assert isinstance(casillas_obj, (list, tuple))
    assert UNKNOWN_AMEND_CASILLA in casillas_obj


def test_amend_refuses_printed_number_metadata_token(repos: Repos, *, operation: PinnedAuthorityOperation) -> None:
    """Amendment overrides must not treat a printed number as a casilla reference."""

    _wu_repo, _cr_repo, _fr_repo, _, _bv_repo = repos
    _, _, baseline = seed_external_baseline(
        repos,
        modelo="303",
        filing_year=PRIOR_YEAR,
        period_code="1T",
        casilla_values={M303_RESULT_CASILLA: Decimal("100")},
        filing_instance_evidence=general_m303_filing_evidence(
            Period.from_year_and_code(PRIOR_YEAR, "1T"),
            reference="test:amend:printed-token",
            operation=operation,
        ),
        operation=operation,
    )

    with (
        pytest.raises(AmendmentOverrideCasillaError, match="non-canonical reference tokens") as exc_info,
        bundled_indexed_authority().operation() as operation,
    ):
        amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=PROFILE_ID, operation=operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={M303_PRINTED_RESULT_TOKEN: Decimal("50")},
            amendment_kind=FilingDeclarationKind.COMPLEMENTARIA,
            reason="printed number override rejected",
            actor="operator-A",
            clock=T4,
        )

    assert exc_info.value.translated_message == "application.modelo.errors.amendment_unknown_casillas"
    assert exc_info.value.context is not None
    assert exc_info.value.context.get("casillas") == [M303_PRINTED_RESULT_TOKEN]
    assert "iva.resultado" in str(exc_info.value)


def test_amend_refuses_non_string_override_casilla_keys_without_coercion(
    repos: Repos, *, operation: PinnedAuthorityOperation
) -> None:
    """Malformed override casilla keys fail before registry membership checks."""

    _wu_repo, _cr_repo, _fr_repo, _, _bv_repo = repos
    _, _, baseline = seed_external_baseline(
        repos, casilla_values={AMEND_INCOME_CASILLA: Decimal("1000")}, operation=operation
    )

    with pytest.raises(AmendmentOverrideCasillaError) as exc_info, bundled_indexed_authority().operation() as operation:
        amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=PROFILE_ID, operation=operation),
            from_filing_record_id=baseline.filing_record_id,
            overrides={1: Decimal("100")},
            amendment_kind=FilingDeclarationKind.COMPLEMENTARIA,
            reason="malformed casilla rejected",
            actor="operator-A",
            clock=T4,
        )
    assert exc_info.value.translated_message == "application.modelo.errors.amendment_unknown_casillas"
    assert exc_info.value.context is not None
    assert exc_info.value.context.get("casillas") == ["1"]


def test_amend_revision_carries_casilla_observations(repos: Repos, *, operation: PinnedAuthorityOperation) -> None:
    """The amendment revision preserves regulatory grounding.

    The amend path used to build the corrected `CalculationRevision`
    with no `observations=` argument, defaulting it to `()` — every
    complementaria/sustitutiva amendment discarded all
    `CasillaObservation` provenance. The amendment must now carry one
    typed observation per corrected casilla, synthesised from the
    registry snapshot even when the baseline revision itself carries
    no observations (the externally-imported baseline seeded here)."""

    outcome = drive_amend_creates_complementaria(repos, operation=operation)
    _, _cr_repo, _, _, _ = repos
    with bundled_indexed_authority().operation() as operation:
        new_revision = get_calculation_revision(
            outcome.new_filing.calculation_revision_id,
            ports=build_calculation_action_ports(bucket_id=PROFILE_ID, operation=operation),
        )

    observed = {obs.casilla_id: obs for obs in new_revision.observations}
    assert observed, "amendment revision persisted zero observations — provenance lost"
    assert set(observed) == set(new_revision.casilla_values)
    # the overridden casilla carries the corrected value
    assert observed[AMEND_INCOME_CASILLA].value == Decimal("1100")
    # the non-overridden casilla carries the baseline value
    assert observed[AMEND_EXPENSE_CASILLA].value == new_revision.casilla_values[AMEND_EXPENSE_CASILLA]
