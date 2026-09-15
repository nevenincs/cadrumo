"""RetencionClave StrEnum hardening for WithholdingObservation.clave.

``WithholdingObservation.clave`` was a free-form ``str`` (1-2 chars) gated only by an
uppercase check, so a typo'd / invalid clave shipped clean -- weakening the
percepciones = (perceptor, clave/subclave) granularity contract. It is now typed as
:class:`cadrumo.core.aggregation.RetencionClave`, the closed Modelo 190 / 193 perceptor
clave catalogue (A-L), and ``subclave`` is a numeric validated string. The M349 / M347
operation "clave" is a DISTINCT taxonomy (:class:`OperationKind349`) and is untouched.

These tests pin: the enum equals the bundled Modelo 190 Diseño de Registros clave set
(A-L, the parity gate); a valid clave constructs; an out-of-set / lowercase / empty
clave is REFUSED; the subclave accepts the numeric AEAT form and refuses non-numeric.
They read the real model and the real enum directly, with no tautological mirror.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core.aggregation import RetencionClave
from ..authority import PinnedAuthorityOperation
from ..governed_fact_scope import validating_governed_facts
from ..withholding_bindings import WithholdingObservation, _retencion_clave_declarations

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ON = date(2024, 3, 15)


@pytest.fixture(autouse=True)
def _authority_scope(operation: PinnedAuthorityOperation) -> Iterator[None]:
    with validating_governed_facts(operation):
        yield


def _m190_dr_claves(operation: PinnedAuthorityOperation) -> frozenset[str]:
    order = _retencion_clave_declarations(_ON, authority=operation)["clave_order"]
    return frozenset(token.strip() for token in order.split(",") if token.strip())


def _observation(*, clave: RetencionClave | str, subclave: str = "") -> WithholdingObservation:
    return WithholdingObservation.model_validate(
        {
            "source_id": "row-1",
            "perceptor_tax_id": "11111111H",
            "transaction_date": date(2024, 3, 15),
            "clave": clave,  # pydantic mode="before" validator coerces str → RetencionClave
            "subclave": subclave,
            "percibido_dinerario": Decimal("1000"),
        }
    )


def test_retencion_clave_projection_matches_m190_dr_clave_set(operation: PinnedAuthorityOperation) -> None:
    """The enum is exactly the M190 DR clave set A-L (the parity gate).

    A new registry clave with no enum member -- or an enum member with no DR clave --
    fails here, keeping the catalogue grounded in the bundled Diseño de Registros.
    """
    declared = _m190_dr_claves(operation)
    projected = {RetencionClave._from_registry(value).value for value in declared}
    assert projected == declared
    # value byte-identical to the stored token (behaviour-preserving lift).
    assert all(RetencionClave._from_registry(value).name == value for value in declared)


def test_withholding_observation_accepts_every_valid_clave(operation: PinnedAuthorityOperation) -> None:
    """Every A-L clave constructs and hydrates to its typed enum member."""
    for clave in sorted(_m190_dr_claves(operation)):
        observation = _observation(clave=clave)
        assert observation.clave.value == clave, clave


def test_withholding_observation_refuses_invalid_clave() -> None:
    """An out-of-set / lowercase / empty / multi-char clave is REFUSED at construction.

    The old free-form field accepted any 1-2 char uppercase string (e.g. "Z", "ZZ");
    the typed enum now refuses everything outside the AEAT A-L catalogue -- the
    hardening that makes the percepciones key trustworthy.
    """
    for bad_clave in ("Z", "ZZ", "1", "a", "", "AA"):
        with pytest.raises(ValidationError):
            _observation(clave=bad_clave)


def test_withholding_observation_accepts_numeric_subclave() -> None:
    """The subclave accepts the empty default and the AEAT numeric form (e.g. 01, 13)."""
    for subclave in ("", "01", "13", "0099"):
        assert _observation(clave="A", subclave=subclave).subclave == subclave, subclave


def test_withholding_observation_refuses_non_numeric_or_overlong_subclave() -> None:
    """A non-numeric or over-length subclave is REFUSED (numeric, max 4 digits)."""
    for bad_subclave in ("XX", "A1", "1.2", "012345"):
        with pytest.raises(ValidationError):
            _observation(clave="A", subclave=bad_subclave)
