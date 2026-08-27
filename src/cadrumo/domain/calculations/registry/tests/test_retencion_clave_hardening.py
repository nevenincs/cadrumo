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

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core.aggregation import RetencionClave
from ..withholding_bindings import WithholdingObservation, WithholdingObservationRequirement

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# The authoritative Modelo 190 perceptor clave set, campo CLAVE DE PERCEPCIÓN of the
# bundled Diseño de Registros (Orden EHA/3127/2009, actualizada por Orden
# HAC/1431/2025): twelve consecutive letters A-L. Modelo 193 reuses the A-D subset.
_M190_DR_CLAVES = frozenset("ABCDEFGHIJKL")


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


def test_retencion_clave_enum_matches_m190_dr_clave_set() -> None:
    """The enum is exactly the M190 DR clave set A-L (the parity gate).

    A new registry clave with no enum member -- or an enum member with no DR clave --
    fails here, keeping the catalogue grounded in the bundled Diseño de Registros.
    """
    assert {member.value for member in RetencionClave} == _M190_DR_CLAVES
    # value byte-identical to the stored token (behaviour-preserving lift).
    assert all(member.value == member.name for member in RetencionClave)


def test_withholding_observation_accepts_every_valid_clave() -> None:
    """Every A-L clave constructs and hydrates to its typed enum member."""
    for clave in sorted(_M190_DR_CLAVES):
        observation = _observation(clave=clave)
        assert observation.clave is RetencionClave(clave), clave


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


def test_withholding_requirement_claves_are_typed() -> None:
    """WithholdingObservationRequirement.claves hydrates raw tokens to typed members."""
    requirement = WithholdingObservationRequirement.model_validate({"binding_ids": ("b1",), "claves": ("A", "G")})
    assert requirement.claves == (RetencionClave.A, RetencionClave.G)
    with pytest.raises(ValidationError):
        WithholdingObservationRequirement.model_validate({"binding_ids": ("b1",), "claves": ("A", "ZZ")})
