"""The annual IVA compensation summary carries the canonical content-digest shape.

``IvaCompensationAnnualSummary.source_artefact_sha256`` redeclares, independently
of the domain-side ``IvaCompensationPeriodState`` field, the identity of the
filed Modelo 390 artefact the summary was read from. Both were bounded only to
64 characters, so either could persist a 64-character non-digest beside
otherwise valid compensation history and have it later resolved as if it
content-addressed the artefact. Both are now
:data:`~cadrumo.core.identity.ContentDigest`, and the parity assertion below is
what keeps the two declarations from drifting apart again.

Anti-tautology: every malformed case is exactly 64 characters, so a guard that
only checked length accepts them and fails this test; ``None`` must still be
accepted, so a validator that simply made the field required also fails.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core import Period
from ....domain.iva_compensation import IvaCompensationPeriodState
from .._iva_compensation_history import IvaCompensationAnnualSummary

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_VALID_NIF = "12345678Z"
_PRESENTED_AT = datetime(2025, 4, 20, tzinfo=UTC)
_VALID_DIGEST = "a3f1" * 16
_MALFORMED_DIGESTS = ("z" * 64, "A" * 64, "0123456789ABCDEF" * 4, "-" * 64)


def _annual_summary(digest: str | None) -> IvaCompensationAnnualSummary:
    return IvaCompensationAnnualSummary(
        taxpayer_nif=_VALID_NIF,
        filing_year=2025,
        expediente_id="202539000000001Z",
        status="presented",
        presented_at=_PRESENTED_AT,
        last_period_compensation_amount=Decimal("60.00"),
        generated_not_in_last_period_amount=Decimal("40.00"),
        total_pending_amount=Decimal("100.00"),
        source_observation_key="390:2025:0A",
        source_artefact_sha256=digest,
    )


def _period_state(digest: str | None) -> IvaCompensationPeriodState:
    return IvaCompensationPeriodState(
        taxpayer_nif=_VALID_NIF,
        filing_year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        expediente_id="202530300000001Z",
        status="presented",
        presented_at=_PRESENTED_AT,
        generated_amount=Decimal("100.00"),
        available_end_amount=Decimal("100.00"),
        source_observation_key="303:2025:1T",
        source_artefact_sha256=digest,
    )


@pytest.mark.parametrize("malformed", _MALFORMED_DIGESTS)
def test_annual_summary_refuses_a_non_digest_artefact_identity(malformed: str) -> None:
    with pytest.raises(ValidationError):
        _annual_summary(malformed)


@pytest.mark.parametrize("malformed", ["a" * 63, "a" * 65, ""])
def test_annual_summary_refuses_a_wrong_length_digest(malformed: str) -> None:
    with pytest.raises(ValidationError):
        _annual_summary(malformed)


def test_annual_summary_accepts_the_canonical_digest() -> None:
    assert _annual_summary(_VALID_DIGEST).source_artefact_sha256 == _VALID_DIGEST


def test_annual_summary_keeps_the_declared_absent_case() -> None:
    """``None`` is the deliberate 'no submitted file captured' seed, not a gap."""
    assert _annual_summary(None).source_artefact_sha256 is None


@pytest.mark.parametrize("candidate", [*_MALFORMED_DIGESTS, "a" * 63, _VALID_DIGEST, None])
def test_the_two_declarations_agree_on_every_candidate(candidate: str | None) -> None:
    """The period and annual authorities must accept and refuse the same values.

    They are two independent declarations of one evidence-identity contract.
    Asserting agreement rather than each in isolation is what catches a future
    edit that re-loosens one of them.
    """

    def accepts(build: object, value: str | None) -> bool:
        try:
            build(value)  # type: ignore[operator]
        except ValidationError:
            return False
        return True

    assert accepts(_annual_summary, candidate) == accepts(_period_state, candidate)
