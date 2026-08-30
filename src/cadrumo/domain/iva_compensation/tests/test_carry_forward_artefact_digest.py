"""IVA compensation period states carry the canonical content-digest shape.

``IvaCompensationPeriodState.source_artefact_sha256`` identifies the filed
artefact the state was read from and flows into compensation history and the
annual cross-check. Bounded only to 64 characters it accepted any 64-character
string, so a non-digest was persistable beside otherwise valid history and
later resolvable as if it content-addressed the artefact. It is now
:data:`~cadrumo.core.identity.ContentDigest`.

The application-side twin of this contract --
``IvaCompensationAnnualSummary.source_artefact_sha256``, which redeclared the
same field independently -- is covered by
``application/calculations/tests/test_iva_compensation_artefact_digest.py``.

Anti-tautology: ``"z" * 64`` and ``"A" * 64`` both satisfy the previous length
bound exactly, so a guard that only checked length accepts them and fails this
test. ``None`` must still be accepted -- it is the declared "no submitted file
captured" case for registry-observation and manually seeded states -- so a
validator that simply made the field required also fails.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core import IvaCompensationStateProvenance, Period
from ..carry_forward import IvaCompensationPeriodState

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_VALID_NIF = "12345678Z"
_PRESENTED_AT = datetime(2025, 4, 20, tzinfo=UTC)
_VALID_DIGEST = "a3f1" * 16

#: Each is exactly 64 characters, so only a hex/case check tells them from a
#: real digest.
_MALFORMED_DIGESTS = ("z" * 64, "A" * 64, "0123456789ABCDEF" * 4, "-" * 64)


def _period_state(digest: str | None) -> IvaCompensationPeriodState:
    return IvaCompensationPeriodState(
        provenance=IvaCompensationStateProvenance.AEAT_CAPTURE,
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
def test_period_state_refuses_a_non_digest_artefact_identity(malformed: str) -> None:
    with pytest.raises(ValidationError):
        _period_state(malformed)


@pytest.mark.parametrize("malformed", ["a" * 63, "a" * 65, ""])
def test_period_state_refuses_a_wrong_length_digest(malformed: str) -> None:
    with pytest.raises(ValidationError):
        _period_state(malformed)


def test_period_state_accepts_the_canonical_digest() -> None:
    assert _period_state(_VALID_DIGEST).source_artefact_sha256 == _VALID_DIGEST


def test_period_state_keeps_the_declared_absent_case() -> None:
    """``None`` is the deliberate 'no submitted file captured' seed, not a gap."""
    assert _period_state(None).source_artefact_sha256 is None
