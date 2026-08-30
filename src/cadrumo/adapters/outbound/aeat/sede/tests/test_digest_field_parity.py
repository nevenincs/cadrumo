"""Every sede digest field validates identically to the canonical alias.

Three records in the sede schema carry a SHA-256 of some captured payload —
:class:`SedeCapture.pdf_sha256`, :class:`FiledDeclaracionArtefact.sha256`, and
:class:`IvaCompensationWalletObservation.raw_sha256`. Each declared its own
copy of the hex-64 pattern, so the shape had three spellings and, at the
whitespace-wrapped input, three of them answered differently from the one
canonical :data:`~core.identity.ContentDigest` alias every other
digest-bearing record in the tree uses.

What these tests defend is that parity, not the regex: they compare each field
against the canonical alias on the same inputs rather than restating the
pattern, so a future field that re-declares the shape diverges here instead of
in a caller.

Each record is built ONCE with a known-good payload and only the digest
varies. Building the whole record inside the refusal catch would let a
mistake in the surrounding fixture read as "the field refused this digest",
and every case would then agree with a canonical alias that refused nothing.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from ......core.period import Period
from ......core.identity import ContentDigest
from ......tests.aeat_literal_fixtures import (
    ACCESO_DR_DETAIL_PATH_FIXTURE,
    KATA_COTEJO_DOC_ID_PATH_FIXTURE,
    KATA_COTEJO_ID_PATH_FIXTURE,
    aeat_url,
)
from ..schema import (
    Expediente,
    FiledDeclaracionArtefact,
    IvaCompensationWalletObservation,
    JustificanteRef,
    SedeCapture,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_DIGEST = "3a" * 32
_CAPTURED_AT = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)
_EXPEDIENTE_ID = "202310013522456T"
_DETAIL_URL = aeat_url("sede", ACCESO_DR_DETAIL_PATH_FIXTURE)

_EXPEDIENTE = Expediente(
    expediente_id=_EXPEDIENTE_ID,
    modelo="100",
    ejercicio=2023,
    category_path=("Agencia Estatal de Administración Tributaria", "Modelo 100"),
    detail_url=_DETAIL_URL,
)
_REF = JustificanteRef(
    csv="ABCDEFGHIJKLMNOP",
    expediente_id=_EXPEDIENTE_ID,
    cotejo_url=aeat_url("sede", KATA_COTEJO_ID_PATH_FIXTURE),
    pdf_url=aeat_url("sede", KATA_COTEJO_DOC_ID_PATH_FIXTURE),
)

_SEDE_CAPTURE_BASE: Mapping[str, Any] = {
    "expediente": _EXPEDIENTE,
    "ref": _REF,
    "pdf_bytes": b"%PDF-1.4",
    "captured_at": _CAPTURED_AT,
}
_ARTEFACT_BASE: Mapping[str, Any] = {
    "kind": "declaration_pdf",
    "source_url": _DETAIL_URL,
    "content_type": "application/pdf",
    "byte_count": 8,
    "captured_at": _CAPTURED_AT,
}
_WALLET_BASE: Mapping[str, Any] = {
    "taxpayer_nif": "12345678Z",
    "authenticated_identity": "12345678Z",
    "target_year": 2026,
    "target_period": Period.from_year_and_code(2026, "1T"),
    "total_pending": Decimal("0"),
    "source_url": _DETAIL_URL,
    "captured_at": _CAPTURED_AT,
}


class _CanonicalDigestHolder(BaseModel):
    """The canonical alias, standing in for every other digest-bearing record."""

    digest: ContentDigest


def _read(build: Callable[[str], BaseModel], attribute: str, value: str) -> str | None:
    """Return the stored digest, or ``None`` when the model refused ``value``."""
    try:
        model = build(value)
    except ValidationError:
        return None
    stored = getattr(model, attribute)
    return None if stored is None else str(stored)


def _canonical(value: str) -> str | None:
    return _read(lambda raw: _CanonicalDigestHolder(digest=raw), "digest", value)


def _sede_capture(value: str) -> str | None:
    return _read(lambda raw: SedeCapture(**_SEDE_CAPTURE_BASE, pdf_sha256=raw), "pdf_sha256", value)


def _artefact(value: str) -> str | None:
    return _read(lambda raw: FiledDeclaracionArtefact(**_ARTEFACT_BASE, sha256=raw), "sha256", value)


def _wallet(value: str) -> str | None:
    return _read(
        lambda raw: IvaCompensationWalletObservation(**_WALLET_BASE, raw_sha256=raw),
        "raw_sha256",
        value,
    )


_FIELDS = (
    pytest.param(_sede_capture, id="SedeCapture.pdf_sha256"),
    pytest.param(_artefact, id="FiledDeclaracionArtefact.sha256"),
    pytest.param(_wallet, id="IvaCompensationWalletObservation.raw_sha256"),
)

_CANDIDATES = (
    pytest.param(_DIGEST, id="canonical"),
    pytest.param(f"  {_DIGEST}  ", id="whitespace-wrapped"),
    pytest.param(f"\t{_DIGEST}\n", id="tab-and-newline-wrapped"),
    pytest.param(_DIGEST.upper(), id="uppercase-hex"),
    pytest.param("z" * 64, id="non-hex"),
    pytest.param(_DIGEST[:-1], id="too-short"),
    pytest.param(f"{_DIGEST}a", id="too-long"),
    pytest.param("", id="empty"),
)


@pytest.mark.parametrize("build", _FIELDS)
@pytest.mark.parametrize("candidate", _CANDIDATES)
def test_the_field_answers_exactly_as_the_canonical_alias_does(
    build: Callable[[str], str | None],
    candidate: str,
) -> None:
    """Accept-or-refuse AND the accepted value agree with the canonical alias.

    The accepted VALUE is asserted, not only the accept/refuse verdict: the
    canonical alias trims, so a field that merely refused the same inputs
    could still store a differently-normalised digest and content-address a
    payload under a key nothing else would compute.
    """
    assert build(candidate) == _canonical(candidate)


def test_the_fixtures_accept_a_good_digest_at_all() -> None:
    """The positive control the parity assertions rest on.

    Without it, a broken surrounding fixture would make every record refuse
    every candidate, and the parity above would hold against a canonical alias
    that refused nothing — passing while measuring nothing.
    """
    assert _canonical(_DIGEST) == _DIGEST
    assert _sede_capture(_DIGEST) == _DIGEST
    assert _artefact(_DIGEST) == _DIGEST
    assert _wallet(_DIGEST) == _DIGEST


def test_the_canonical_alias_trims_rather_than_refusing() -> None:
    """Pin the behaviour the parity assertions are measured against.

    Parity would hold vacuously if the canonical alias itself stopped
    trimming: every field would refuse the wrapped digest together and the
    tests would still pass.
    """
    assert _canonical(f"  {_DIGEST}  ") == _DIGEST
    assert _canonical(_DIGEST.upper()) is None


def test_an_absent_wallet_digest_is_still_permitted() -> None:
    """``raw_sha256`` is optional, and typing it must not make it required.

    The wallet observation legitimately carries no raw digest when the reader
    did not retain the response body, which is a different state from a
    malformed one.
    """
    observation = IvaCompensationWalletObservation(**_WALLET_BASE)

    assert observation.raw_sha256 is None
