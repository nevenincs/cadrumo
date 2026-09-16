"""Recorded ECB Data Portal answers for suites that must not reach the network.

The test host binds :func:`recorded_ecb_rate_provider` as its exchange-rate
provider, so ledger imports and invoice conversions run the real
:class:`~adapters.outbound.fx.ecb_provider.EcbReferenceRateProvider` parsing and
working-day fallback over bodies the live Data Portal actually returned.

The recording is keyed by the exact request URL, which fixes the currency and
the observation window. A request the recording does not hold refuses with
:class:`~domain.currency.errors.ExchangeRateProviderError`: it never reaches the
live host and never borrows a neighbouring window's rate. The ``aeat_live``
parity test re-fetches every recorded URL and fails when the ECB now answers
differently.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..adapters.outbound.fx.ecb_provider import ECB_EXR_ENDPOINT, EcbReferenceRateProvider
from ..domain.currency.errors import ExchangeRateProviderError
from .inventory import FIXTURES_DIR

RECORDED_ECB_RATES_PATH: Final[Path] = FIXTURES_DIR / "financial" / "ecb-reference-rates.recorded.json"
RECORDING_SCHEMA: Final = "cadrumo-recorded-ecb-answers/v1"


class _Recording(BaseModel):
    """The checked-in recording; its header fields carry the capture provenance."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_id: Literal["cadrumo-recorded-ecb-answers/v1"] = Field(alias="schema")
    endpoint: str
    captured_at: str
    provenance: str
    request_count: int
    answers: dict[str, str]


@cache
def recorded_ecb_answers() -> Mapping[str, str]:
    """Return ``{request_url: response_body}`` from the checked-in recording."""
    try:
        recording = _Recording.model_validate_json(RECORDED_ECB_RATES_PATH.read_text(encoding="utf-8"))
    except ValidationError as error:
        raise ExchangeRateProviderError(f"unreadable ECB recording at {RECORDED_ECB_RATES_PATH}") from error
    if recording.endpoint != ECB_EXR_ENDPOINT:
        raise ExchangeRateProviderError("the ECB recording was captured from a different endpoint")
    if recording.request_count != len(recording.answers):
        raise ExchangeRateProviderError("the ECB recording's request count disagrees with its answers")
    return recording.answers


def recorded_ecb_fetch(url: str) -> str:
    """Answer one Data Portal request from the recording, or refuse."""
    body = recorded_ecb_answers().get(url)
    if body is None:
        raise ExchangeRateProviderError(
            f"no recorded ECB answer for {url!r}; re-record {RECORDED_ECB_RATES_PATH.name} from the live endpoint"
        )
    return body


@cache
def recorded_ecb_rate_provider() -> EcbReferenceRateProvider:
    """Return one process-wide provider over the recording, like the live default."""
    return EcbReferenceRateProvider(fetch=recorded_ecb_fetch)


__all__ = [
    "RECORDED_ECB_RATES_PATH",
    "RECORDING_SCHEMA",
    "recorded_ecb_answers",
    "recorded_ecb_fetch",
    "recorded_ecb_rate_provider",
]
