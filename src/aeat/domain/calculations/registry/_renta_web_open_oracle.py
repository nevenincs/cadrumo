"""Renta WEB Open parity oracle contract for Modelo 100."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from json import JSONDecodeError, loads
from typing import Literal, Protocol

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, field_validator

from ._errors import RegistryValidationError
from ._live_parity import OracleSurfaceKind, ParityFieldComparison, ParityResult, assert_oracle_operations_allowed
from ._remote_state_guard import RemoteOperation, RemoteStateGuardPolicy

RENTA_WEB_OPEN_LANDING_URL = AnyUrl(
    "https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/renta-ayuda-tecnica/renta-web-open.html"
)
RENTA_WEB_OPEN_APP_URL = AnyUrl(
    "https://www2.agenciatributaria.gob.es/wlpl/PARE-RW25/OPEN/index.zul?EJER=2025&TACCESO=COLAB"
)


class RentaWebOpenModel(BaseModel):
    """Strict frozen base for Renta WEB Open parity records."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class RentaWebOpenSyntheticProfile(RentaWebOpenModel):
    """Synthetic identifying data accepted by Renta WEB Open."""

    nif: str = Field(default="12345678Z", min_length=1, max_length=16)
    name: str = Field(default="DECLARANTE PRUEBA", min_length=1, max_length=80)
    civil_status: str = Field(default="SOLTERO/A", min_length=1, max_length=64)
    birth_date: str = Field(default="01/01/1980", min_length=10, max_length=10)
    sex: Literal["Hombre", "Mujer"] = "Hombre"
    autonomous_community: str = Field(default="ANDALUCIA", min_length=1, max_length=80)

    @field_validator("nif", "name", "civil_status", "birth_date", "autonomous_community")
    @classmethod
    def _trimmed(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Renta WEB Open synthetic profile values must not be blank")
        return normalized


class RentaWebOpenLivePayload(RentaWebOpenModel):
    """Payload for a Renta WEB Open parity run."""

    profile: RentaWebOpenSyntheticProfile = Field(default_factory=RentaWebOpenSyntheticProfile)
    app_url: AnyUrl = RENTA_WEB_OPEN_APP_URL
    timeout_ms: int = Field(default=60_000, ge=1_000, le=180_000)


class RentaWebOpenObservation(RentaWebOpenModel):
    """Observed Renta WEB Open outputs returned by a concrete adapter."""

    values: dict[str, str] = Field(default_factory=dict)
    raw_evidence_locator: str | None = Field(default=None, max_length=512)


class RentaWebOpenDriver(Protocol):
    """Execution boundary for live or replay Renta WEB Open adapters."""

    @property
    def mode(self) -> Literal["live", "replay"]: ...

    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> tuple[RemoteOperation, ...]: ...

    def collect_observation(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> RentaWebOpenObservation: ...


class RentaWebOpenReplayDriver:
    """Deterministic local replay driver for captured Renta WEB Open outputs."""

    @property
    def mode(self) -> Literal["replay"]:
        return "replay"

    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> tuple[RemoteOperation, ...]:
        return (RemoteOperation(kind="local_workbook", action="parse-renta-web-open-replay"),)

    def collect_observation(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> RentaWebOpenObservation:
        try:
            document = loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, JSONDecodeError) as exc:
            raise RegistryValidationError("Renta WEB Open replay payload must be UTF-8 JSON") from exc
        if not isinstance(document, dict):
            raise RegistryValidationError("Renta WEB Open replay payload must be a JSON object")
        observed = document.get("observed")
        if not isinstance(observed, dict):
            raise RegistryValidationError("Renta WEB Open replay payload must contain an observed object")
        values: dict[str, str] = {}
        for key, value in observed.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise RegistryValidationError("Renta WEB Open replay observed values must be string keyed strings")
            values[key] = value
        locator = document.get("raw_evidence_locator")
        if locator is not None and not isinstance(locator, str):
            raise RegistryValidationError("Renta WEB Open replay raw_evidence_locator must be a string")
        return RentaWebOpenObservation(values=values, raw_evidence_locator=locator)


class RentaWebOpenOracle:
    """Open-simulator parity oracle for Modelo 100 Renta WEB Open."""

    def __init__(self, *, driver: RentaWebOpenDriver | None = None) -> None:
        self._driver = driver

    @property
    def oracle_id(self) -> str:
        return "modelo-100-renta-web-open"

    @property
    def surface_kind(self) -> OracleSurfaceKind:
        return "open_simulator"

    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> tuple[RemoteOperation, ...]:
        if not expected:
            raise RegistryValidationError(
                "RentaWebOpenOracle.planned_operations requires at least one expected casilla"
            )
        if self._driver is not None:
            return self._driver.planned_operations(payload, expected=expected)
        return (
            RemoteOperation(kind="http", method="GET", url=RENTA_WEB_OPEN_APP_URL),
            RemoteOperation(kind="browser_action", action="requires-renta-web-open-driver"),
        )

    def verify_payload(
        self,
        policy: RemoteStateGuardPolicy,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> ParityResult:
        operations = self.planned_operations(payload, expected=expected)
        try:
            assert_oracle_operations_allowed(self, policy, operations)
        except RegistryValidationError as exc:
            return ParityResult(
                oracle_id=self.oracle_id,
                cross_reference_id=policy.id,
                verdict="blocked",
                narrative=f"Renta WEB Open oracle blocked by remote-state guard: {exc}",
            )
        if self._driver is None:
            return ParityResult(
                oracle_id=self.oracle_id,
                cross_reference_id=policy.id,
                verdict="unverifiable",
                narrative=(
                    "Renta WEB Open browser driver is not configured. Guard preflight passed, "
                    "but no outbound AEAT Sede adapter was available to execute the open simulator."
                ),
            )
        try:
            observation = self._driver.collect_observation(payload, expected=expected)
        except RegistryValidationError as exc:
            return ParityResult(
                oracle_id=self.oracle_id,
                cross_reference_id=policy.id,
                verdict="unverifiable",
                narrative=f"Renta WEB Open driver could not produce comparable observations: {exc}",
            )
        fields = tuple(
            _compare_expected_field(casilla_id, expected_value, observed=observation.values.get(casilla_id))
            for casilla_id, expected_value in sorted(expected.items())
        )
        verdict = _overall_verdict(fields)
        return ParityResult(
            oracle_id=self.oracle_id,
            cross_reference_id=policy.id,
            verdict=verdict,
            narrative=_narrative_for_verdict(verdict, driver_mode=self._driver.mode),
            fields=fields,
            raw_evidence_locator=observation.raw_evidence_locator,
        )


def parse_renta_web_open_live_payload(payload: bytes) -> RentaWebOpenLivePayload:
    """Parse the optional JSON payload for Renta WEB Open verification."""

    if not payload:
        return RentaWebOpenLivePayload()
    try:
        document = loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, JSONDecodeError) as exc:
        raise RegistryValidationError("Renta WEB Open live payload must be UTF-8 JSON") from exc
    if not isinstance(document, dict):
        raise RegistryValidationError("Renta WEB Open live payload must be a JSON object")
    return RentaWebOpenLivePayload.model_validate(document)


def equivalent_renta_web_open_value(expected: str, observed: str) -> bool:
    """Return true when dot or comma decimal renderings represent the same number."""

    if observed == expected:
        return True
    expected_decimal = _parse_decimal_text(expected)
    observed_decimal = _parse_decimal_text(observed)
    return expected_decimal is not None and observed_decimal is not None and expected_decimal == observed_decimal


def _compare_expected_field(name: str, expected: object, *, observed: str | None) -> ParityFieldComparison:
    expected_text = str(expected)
    if observed is None:
        return ParityFieldComparison(name=name, expected=expected_text, observed="", verdict="unverifiable")
    verdict: Literal["match", "mismatch"] = (
        "match" if equivalent_renta_web_open_value(expected_text, observed) else "mismatch"
    )
    return ParityFieldComparison(name=name, expected=expected_text, observed=observed, verdict=verdict)


def _parse_decimal_text(value: str) -> Decimal | None:
    text = value.strip().replace("\xa0", "")
    if not text:
        return None
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _overall_verdict(fields: tuple[ParityFieldComparison, ...]) -> Literal["match", "mismatch", "unverifiable"]:
    if any(field.verdict == "mismatch" for field in fields):
        return "mismatch"
    if any(field.verdict == "unverifiable" for field in fields):
        return "unverifiable"
    return "match"


def _narrative_for_verdict(
    verdict: Literal["match", "mismatch", "unverifiable"],
    *,
    driver_mode: Literal["live", "replay"],
) -> str:
    if verdict == "match":
        return f"Renta WEB Open {driver_mode} parity matched every expected field"
    if verdict == "mismatch":
        return f"Renta WEB Open {driver_mode} parity found at least one mismatched field"
    return f"Renta WEB Open {driver_mode} parity could not observe every expected field"


__all__ = [
    "RENTA_WEB_OPEN_APP_URL",
    "RENTA_WEB_OPEN_LANDING_URL",
    "RentaWebOpenDriver",
    "RentaWebOpenLivePayload",
    "RentaWebOpenObservation",
    "RentaWebOpenOracle",
    "RentaWebOpenReplayDriver",
    "RentaWebOpenSyntheticProfile",
    "equivalent_renta_web_open_value",
    "parse_renta_web_open_live_payload",
]
