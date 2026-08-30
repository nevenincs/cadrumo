"""Behaviour + anti-tautology coverage for the M100 attribution-received advisory.

The advisory guards the manual cross-bucket régimen-de-atribución handoff:
casilla 1577 stays relation-canonical, so a non-blocking advisory surfaces when the
``attribution_received`` profile facts and the atribución casilla disagree. The
anti-tautology test flips exactly one input at a time and asserts the finding count
flips with it, so a broken always-fire / always-silent advisory fails.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core import Modelo, Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.verification_report import ModeloVerificationFinding, ModeloVerificationFindingKind, ModeloVerificationFindingSeverity
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from .._attribution_received_advisory import _attribution_received_omission_advisory_findings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLOCK = datetime(2026, 7, 9, tzinfo=UTC)
_CASILLA_1577 = "1577"
_BASE = Decimal("58100.00")
_FILING_YEAR = 2024
_M100_CODE = ModeloCode(Modelo.M100.value)


@pytest.fixture(scope="module")
def snapshot() -> RegistrySnapshot:
    return bundled_authority().snapshot("100", filing_year=_FILING_YEAR, period="0A")


def _work_unit(modelo: ModeloCode = _M100_CODE, *, filing_year: int = _FILING_YEAR) -> WorkUnit:
    bucket_id = "attribution-advisory-bucket"
    period = Period.from_year_and_code(filing_year, "0A")
    revision_id = "r" + "0" * 63
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _profile(*facts: UserProfileFact) -> UserProfileRecord:
    return UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="11111111-1111-4111-8111-111111111111",
        facts=facts,
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _received_facts(*, year: int = _FILING_YEAR, base: Decimal = _BASE, index: int = 0) -> tuple[UserProfileFact, ...]:
    return (
        UserProfileFact(path=f"attribution_received.{index}.entity_nif", value="B12345678"),
        UserProfileFact(path=f"attribution_received.{index}.entity_name", value="Sociedad Civil Ejemplo"),
        UserProfileFact(path=f"attribution_received.{index}.share_pct", value=Decimal("50")),
        UserProfileFact(path=f"attribution_received.{index}.base_imponible_attributed", value=base),
        UserProfileFact(path=f"attribution_received.{index}.filing_year", value=str(year)),
    )


def _run(
    snapshot: RegistrySnapshot,
    *,
    facts: tuple[UserProfileFact, ...],
    casilla_1577: Decimal | None,
) -> tuple[ModeloVerificationFinding, ...]:
    casilla_values = {} if casilla_1577 is None else {_CASILLA_1577: casilla_1577}
    return _attribution_received_omission_advisory_findings(
        work_unit=_work_unit(),
        snapshot=snapshot,
        casilla_values=casilla_values,
        profile_record=_profile(*facts),
    )


def test_facts_present_casilla_empty_fires_advisory(snapshot: RegistrySnapshot) -> None:
    findings = _run(snapshot, facts=_received_facts(), casilla_1577=None)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind is ModeloVerificationFindingKind.ADVISORY
    assert finding.severity is ModeloVerificationFindingSeverity.WARNING
    assert finding.casilla_id == _CASILLA_1577
    assert finding.message_locale_key == "application.modelo.findings.attribution_received_unfolded"
    assert finding.message_facts["casilla_id"] == _CASILLA_1577
    assert finding.message_facts["total_base"] == Decimal("58100.00")
    assert {"ley-35-2006:art-86", "ley-35-2006:art-89"} <= set(finding.legal_refs)


def test_casilla_present_no_facts_fires_capture_advisory(snapshot: RegistrySnapshot) -> None:
    findings = _run(snapshot, facts=(), casilla_1577=_BASE)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity is ModeloVerificationFindingSeverity.WARNING
    assert finding.casilla_id == _CASILLA_1577
    # Assertions are locale-robust (this application-layer test runs under the
    # default es output language, and the message routes through tr()):
    # the interpolated casilla id and the machine-token fact-group name survive
    # every locale, as does the Modelo 184 provenance reference in the message.
    assert finding.message_locale_key == "application.modelo.findings.attribution_received_uncaptured"
    assert finding.message_facts["casilla_id"] == _CASILLA_1577
    assert finding.message_facts["casilla_value"] == _BASE
    assert "next_action" not in finding.model_dump(mode="json")


def test_both_present_is_silent(snapshot: RegistrySnapshot) -> None:
    assert _run(snapshot, facts=_received_facts(), casilla_1577=_BASE) == ()


def test_both_absent_is_silent(snapshot: RegistrySnapshot) -> None:
    assert _run(snapshot, facts=(), casilla_1577=None) == ()


def test_facts_for_other_year_do_not_count(snapshot: RegistrySnapshot) -> None:
    # Facts stamped for 2023 must not satisfy a 2024 verification: casilla empty +
    # no 2024 facts is the clean "not a member this year" state, not an omission.
    assert _run(snapshot, facts=_received_facts(year=2023), casilla_1577=None) == ()


def test_non_m100_modelo_is_scoped_out(snapshot: RegistrySnapshot) -> None:
    findings = _attribution_received_omission_advisory_findings(
        work_unit=_work_unit(ModeloCode(Modelo.M130.value)),
        snapshot=snapshot,
        casilla_values={},
        profile_record=_profile(*_received_facts()),
    )
    assert findings == ()


def test_advisory_is_not_tautological(snapshot: RegistrySnapshot) -> None:
    """Flipping exactly one input flips the outcome — the advisory reads both.

    A broken always-fire advisory would fire on the clean states; a broken
    always-silent advisory would stay silent on the omission states. Holding one
    input fixed and flipping the other must move the finding count, proving the
    logic genuinely consults both the profile facts and the casilla value.
    """
    facts = _received_facts()

    # Hold facts present; flip only the casilla (empty -> present): fire -> silent.
    assert len(_run(snapshot, facts=facts, casilla_1577=None)) == 1
    assert _run(snapshot, facts=facts, casilla_1577=_BASE) == ()

    # Hold casilla empty; flip only the facts (present -> absent): fire -> silent.
    assert len(_run(snapshot, facts=facts, casilla_1577=None)) == 1
    assert _run(snapshot, facts=(), casilla_1577=None) == ()
