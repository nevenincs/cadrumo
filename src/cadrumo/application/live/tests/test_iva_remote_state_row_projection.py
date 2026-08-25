"""Row-projection behaviour for the live IVA remote-state surfaces.

A carry-forward lot inherits its filing subject from the source period state,
which may itself declare none. These tests pin how that absent subject is
projected onto the CLI-safe row, whose ``taxpayer_ref`` is a required ``str``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....adapters.outbound.aeat.sede import IvaCompensationWalletObservation
from ....core import Period
from ....core.identity import tax_id_identity_token
from ....domain.iva_compensation import (
    IvaCompensationCarryForwardLot,
    IvaCompensationExpiryReviewState,
)
from ....tests.aeat_literal_fixtures import IVA_WALLET_SOURCE_URL_FIXTURE
from ..iva_remote_state import _carry_forward_lot_row, _taxpayer_ref

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: A checksum-valid synthetic NIF, used only to prove the populated branch
#: still pseudonymises. It never reaches storage or an AEAT surface.
_SYNTHETIC_NIF = "00000001R"


def _lot(taxpayer_nif: str | None) -> IvaCompensationCarryForwardLot:
    return IvaCompensationCarryForwardLot(
        taxpayer_nif=taxpayer_nif,
        source_filing_year=2026,
        source_period=Period.model_validate({"filing_year": 2026, "code": "1T"}),
        generated_amount=Decimal("100.00"),
        applied_amount=Decimal("40.00"),
        remaining_amount=Decimal("60.00"),
        age_years=1,
        expiry_review_state=IvaCompensationExpiryReviewState.ACTIVE,
        source_observation_key="observation-key-1",
    )


def test_a_lot_carrying_a_subject_projects_a_pseudonymised_digest_ref() -> None:
    """The positive control: a populated subject still becomes a ``sha256:`` digest ref.

    Without this the absent-subject assertion below could pass against a
    projection that had stopped pseudonymising altogether.
    """
    row = _carry_forward_lot_row(_lot(_SYNTHETIC_NIF))

    assert row.taxpayer_ref.startswith("sha256:")
    assert _SYNTHETIC_NIF not in row.taxpayer_ref


def test_a_subjectless_lot_projects_an_explicit_marker_not_a_digest() -> None:
    """A lot whose source state declared no subject projects without raising.

    The absent case must stay distinguishable from every real subject: it is
    not a ``sha256:`` value, so it can neither be read as a pseudonymised
    taxpayer nor collide with one.
    """
    row = _carry_forward_lot_row(_lot(None))

    assert not row.taxpayer_ref.startswith("sha256:")
    assert row.taxpayer_ref


def test_the_absent_marker_is_shared_by_subjectless_lots_but_never_by_a_real_subject() -> None:
    """Two subjectless lots agree, and neither is confusable with a populated one."""
    absent_ref = _carry_forward_lot_row(_lot(None)).taxpayer_ref
    other_absent_ref = _carry_forward_lot_row(_lot(None)).taxpayer_ref
    populated_ref = _carry_forward_lot_row(_lot(_SYNTHETIC_NIF)).taxpayer_ref

    assert absent_ref == other_absent_ref
    assert absent_ref != populated_ref


# ------------------------------------- the subject that is present but empty


@pytest.mark.parametrize("blank", ["", " ", "\xa0", "  \t "])
def test_a_subject_that_normalises_to_nothing_takes_the_absent_exit(blank: str) -> None:
    """A blank subject is the absent case one step later, not a real one.

    The canonical identity token trims and uppercases, so every one of these
    normalises to ``""``. Hashing that yields the sha256 of the empty string --
    a value shaped exactly like a real subject's ref and worn by every blank
    row at once, which is the collision the absent marker exists to avoid.
    """
    ref = _taxpayer_ref(blank)

    assert not ref.startswith("sha256:")
    assert ref == _taxpayer_ref(None)


def test_the_blank_subject_is_reachable_through_the_wallet_observation() -> None:
    """The guard upstream does not exclude the state the branch above handles.

    Without this the blank branch could be guarding a state nothing can occupy.
    ``taxpayer_nif`` is constrained ``min_length=1`` on the RAW string, which a
    non-breaking space satisfies -- and ``\\xa0`` is what parsing an AEAT page
    produces. The guard and the normalisation that empties it live in separate
    modules, so neither is locally wrong.
    """
    observation = IvaCompensationWalletObservation(
        taxpayer_nif="\xa0",
        authenticated_identity=_SYNTHETIC_NIF,
        target_year=2026,
        target_period=Period.model_validate({"filing_year": 2026, "code": "1T"}),
        total_pending=Decimal("0"),
        source_url=IVA_WALLET_SOURCE_URL_FIXTURE,
        captured_at=datetime(2026, 4, 1, tzinfo=UTC),
    )

    # Full validation ran -- model_construct would have proved nothing here.
    assert observation.taxpayer_nif == "\xa0"
    assert tax_id_identity_token(observation.taxpayer_nif) == ""
    assert _taxpayer_ref(observation.taxpayer_nif) == _taxpayer_ref(None)
