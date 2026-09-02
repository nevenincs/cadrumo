"""Renta WEB Open parity oracle contract for Modelo 100."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from json import JSONDecodeError, loads
from typing import Final, Literal, Protocol

from pydantic import AnyUrl, BaseModel, Field, field_validator

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.config import Settings
from ....core.decimal.coercion import coerce_finite_european_decimal, normalize_decimal_separators
from ....core.identity import AeatBoxNumber
from ....core.models import STRICT_FROZEN_CONFIG
from .checker_oracle_flow import CheckerDriverMode, CheckerDriverModeValue
from .errors import RegistryValidationError
from .external_grounding import (
    BUNDLED_ORACLE_EVIDENCE_LOCATOR_MAX_LENGTH,
    require_bundled_oracle_evidence_locator,
)
from .ids import OracleId
from .live_parity import (
    OracleSurfaceKind,
    ParityFieldComparison,
    ParityFieldVerdict,
    ParityResult,
    ParityVerdictKind,
    assert_oracle_operations_allowed,
    decode_replay_json_payload,
)
from .remote_state_guard import RemoteOperation, RemoteStateGuardPolicy

_RENTA_WEB_OPEN_DEFAULT_YEAR: Final[int] = 2025
_RENTA_WEB_OPEN_ORACLE_ID: OracleId = "modelo-100-renta-web-open"
_RENTA_REPLAY_SURFACE_LABEL: Final[str] = "Renta WEB Open replay"


class RentaWebOpenModel(BaseModel):
    """Strict frozen base for Renta WEB Open parity records."""

    model_config = STRICT_FROZEN_CONFIG


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
            raise RegistryValidationError("Renta WEB Open synthetic profile values must not be blank")
        return normalized


class RentaWebOpenDisplayOverride(RentaWebOpenModel):
    """One browser-coordinate override keyed externally by canonical casilla id."""

    display_number: AeatBoxNumber
    value: str = Field(max_length=128)

    @field_validator("display_number", "value")
    @classmethod
    def _trimmed(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise RegistryValidationError("Renta WEB Open display overrides must not contain blank strings")
        return trimmed


class RentaWebOpenLivePayload(RentaWebOpenModel):
    """Payload for a Renta WEB Open parity run.

    Browser-visible labels and display numbers are external UI coordinates.
    They are never output keys. ``summary_labels_by_casilla_id`` maps the
    canonical registry casilla id to the Renta WEB summary label to scrape.
    ``scrape_display_numbers_by_casilla_id`` maps the canonical registry
    casilla id to a browser-visible display number that the driver should
    navigate to and read. ``display_overrides_by_casilla_id`` is also keyed
    by canonical casilla id; the nested display number is only the external
    browser coordinate used to reach AEAT's input widget.
    """

    profile: RentaWebOpenSyntheticProfile = Field(default_factory=RentaWebOpenSyntheticProfile)
    app_url: AnyUrl = Field(
        default_factory=lambda: AnyUrl(
            Settings.external_constants().aeat.oracles.renta_web_open_app_template.format(
                year=_RENTA_WEB_OPEN_DEFAULT_YEAR,
            ),
        ),
    )
    timeout_ms: int = Field(default=60_000, ge=1_000, le=180_000)
    display_overrides_by_casilla_id: dict[CasillaId, RentaWebOpenDisplayOverride] = Field(default_factory=dict)
    summary_labels_by_casilla_id: dict[CasillaId, str] = Field(default_factory=dict)
    scrape_display_numbers_by_casilla_id: dict[CasillaId, str] = Field(default_factory=dict)


class RentaWebOpenObservation(RentaWebOpenModel):
    """Observed Renta WEB Open outputs returned by a concrete adapter."""

    values: dict[CasillaId, str] = Field(default_factory=dict)
    # Bound shared with the bundled-oracle grounding contract: this observation
    # carries the locator straight off a Renta corpus capture that grounding
    # also reads, so a locator grounding accepts must survive the whole replay
    # path rather than being refused one model later.
    raw_evidence_locator: str | None = Field(
        default=None,
        max_length=BUNDLED_ORACLE_EVIDENCE_LOCATOR_MAX_LENGTH,
    )


class RentaWebOpenDriver(Protocol):
    """Execution boundary for live or replay Renta WEB Open adapters."""

    @property
    def mode(self) -> CheckerDriverModeValue:
        """Identify whether this driver talks to a real surface or replays a capture.

        Returns:
            Either ``"live"`` (the driver scrapes the public Renta WEB Open
            simulator, AEAT's online estimator for the IRPF income-tax
            declaration filed on Modelo 100, a tax form) or ``"replay"`` (the
            driver decodes a previously captured JSON payload). The oracle uses
            the value only to phrase its result narrative.
        """
        ...

    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[CasillaId, object],
    ) -> tuple[RemoteOperation, ...]:
        """Describe the remote work this driver would perform, without performing it.

        The remote-state guard inspects the returned operations before any are
        executed, so a driver must declare its full plan up front.

        Args:
            payload: Raw request bytes; for the live driver this carries the
                optional JSON capture configuration, for the replay driver the
                captured observation document.
            expected: Mapping of expected canonical casilla ids to their
                expected values.

        Returns:
            The ordered :class:`RemoteOperation` tuple the driver intends to run.
        """
        ...

    def collect_observation(
        self,
        payload: bytes,
        *,
        expected: Mapping[CasillaId, object],
    ) -> RentaWebOpenObservation:
        """Execute the driver and return the observed Modelo 100 outputs.

        Args:
            payload: Raw request bytes carrying the live capture configuration
                or the replay document.
            expected: Mapping of expected canonical casilla ids to their
                expected values, available to scope scraping.

        Returns:
            A :class:`RentaWebOpenObservation` whose ``values`` maps
            canonical casilla ids to their observed string renderings, plus
            an optional evidence locator pointing at the captured source.
        """
        ...


class RentaWebOpenReplayDriver:
    """Deterministic local replay driver for captured Renta WEB Open outputs."""

    @property
    def mode(self) -> Literal[CheckerDriverMode.REPLAY]:
        """Report this driver as a replay surface.

        Returns:
            Always ``"replay"``: this driver decodes a captured JSON document
            rather than scraping the live Renta WEB Open simulator, so the
            oracle can run deterministically offline.
        """
        return CheckerDriverMode.REPLAY

    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[CasillaId, object],
    ) -> tuple[RemoteOperation, ...]:
        """Declare the single local-parse operation this replay driver performs.

        Replay never touches the network: it parses a captured workbook-style
        JSON document, so the plan is one ``local_workbook`` operation regardless
        of the request.

        Args:
            payload: Raw request bytes (the captured document is read in
                ``collect_observation``; this method ignores its contents).
            expected: Mapping of expected canonical casilla ids to expected values;
                unused, present to satisfy the ``RentaWebOpenDriver`` protocol.

        Returns:
            A one-element tuple holding the local-parse :class:`RemoteOperation`.
        """
        return (RemoteOperation(kind="local_workbook", action="parse-renta-web-open-replay"),)

    def collect_observation(
        self,
        payload: bytes,
        *,
        expected: Mapping[CasillaId, object],
    ) -> RentaWebOpenObservation:
        """Decode the captured replay payload into observed Modelo 100 outputs.

        Args:
            payload: UTF-8 JSON bytes holding a previously captured Renta WEB
                Open observation document.
            expected: Mapping of expected canonical casilla ids to expected values;
                unused, present to satisfy the ``RentaWebOpenDriver`` protocol.

        Returns:
            A :class:`RentaWebOpenObservation` carrying the decoded casilla values
            and the document's raw evidence locator.

        Raises:
            RegistryValidationError: If the payload is not decodable as the
                expected replay JSON document.
        """
        document = decode_replay_json_payload(payload, surface_label=_RENTA_REPLAY_SURFACE_LABEL)
        if not document.observed_by_casilla_id:
            raise RegistryValidationError(
                "Renta WEB Open replay payload must declare observed_by_casilla_id keyed by canonical casilla.id",
            )
        # The generic replay envelope makes the evidence locator optional; the
        # bundled Renta corpus contract requires it. This corpus is read by
        # both, so the driver re-applies the grounding contract from its one
        # declaration rather than accepting a Renta capture with no provenance
        # that grounding would refuse.
        raw_evidence_locator = require_bundled_oracle_evidence_locator(
            document.raw_evidence_locator,
            surface_label=_RENTA_REPLAY_SURFACE_LABEL,
        )
        return RentaWebOpenObservation(
            values=dict(document.observed_by_casilla_id),
            raw_evidence_locator=raw_evidence_locator,
        )


class RentaWebOpenOracle:
    """Open-simulator parity oracle for Modelo 100 Renta WEB Open."""

    def __init__(self, *, driver: RentaWebOpenDriver | None = None) -> None:
        """Construct the oracle, optionally injecting a Renta WEB Open driver for replay."""
        self._driver = driver

    @property
    def oracle_id(self) -> OracleId:
        """Return the stable identifier for this parity oracle.

        Returns:
            The constant ``"modelo-100-renta-web-open"``, stamped onto every
            ``ParityResult`` so a verdict can be traced back to the oracle that
            produced it.
        """
        return _RENTA_WEB_OPEN_ORACLE_ID

    @property
    def surface_kind(self) -> OracleSurfaceKind:
        """Classify the external surface this oracle compares against.

        Returns:
            The ``OracleSurfaceKind`` ``"open_simulator"``: Renta WEB Open is
            AEAT's public, unauthenticated estimator for the Modelo 100 income
            declaration, distinct from authenticated filing surfaces. The
            remote-state guard reads this to scope which operations are allowed.
        """
        return "open_simulator"

    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> tuple[RemoteOperation, ...]:
        """Describe the remote operations a parity run would perform, without running them.

        When a driver is configured the call delegates to it. Otherwise the
        oracle returns a placeholder plan (an HTTP GET against the simulator URL
        plus a browser action marked as requiring a driver) so the guard can
        still preflight an unconfigured oracle.

        Args:
            payload: Raw request bytes forwarded to the driver when present.
            expected: Mapping of expected canonical casilla ids to their
                expected values. Must be non-empty.

        Returns:
            The ordered :class:`RemoteOperation` tuple the run intends to perform.

        Raises:
            RegistryValidationError: If ``expected`` is empty, since a parity
                run with no expected casilla has nothing to verify.
        """
        if not expected:
            raise RegistryValidationError(
                "RentaWebOpenOracle.planned_operations requires at least one expected casilla",
            )
        expected_values = validate_renta_web_open_expected_casilla_values(expected)
        if self._driver is not None:
            return self._driver.planned_operations(payload, expected=expected_values)
        template = Settings.external_constants().aeat.oracles.renta_web_open_app_template
        app_url = AnyUrl(template.format(year=_RENTA_WEB_OPEN_DEFAULT_YEAR))
        return (
            RemoteOperation(kind="http", method="GET", url=app_url),
            RemoteOperation(kind="browser_action", action="requires-renta-web-open-driver"),
        )

    def verify_payload(
        self,
        policy: RemoteStateGuardPolicy,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> ParityResult:
        """Run a Renta WEB Open parity check and return a typed verdict.

        The remote-state guard first authorizes the planned operations. A
        blocked plan yields a ``"blocked"`` result; an unconfigured driver yields
        an ``"unverifiable"`` result after a passing preflight. With a driver, each
        expected canonical casilla id is compared against its observed value,
        and the per-field verdicts are combined into one overall verdict.

        Args:
            policy: The remote-state guard policy authorizing the run; its id is
                recorded as the result's cross-reference.
            payload: Raw request bytes passed to the driver.
            expected: Mapping of expected canonical casilla ids to expected
                values to compare against the observation.

        Returns:
            A :class:`ParityResult` carrying the verdict (``"match"``, ``"mismatch"``,
            ``"unverifiable"``, or ``"blocked"``), a human-readable narrative,
            the per-casilla comparisons, and any raw evidence locator.
        """
        expected_values = validate_renta_web_open_expected_casilla_values(expected)
        operations = self.planned_operations(payload, expected=expected_values)
        try:
            assert_oracle_operations_allowed(self, policy, operations)
        except RegistryValidationError as exc:
            return ParityResult(
                oracle_id=self.oracle_id,
                cross_reference_id=policy.id,
                verdict=ParityVerdictKind.BLOCKED,
                narrative=f"Renta WEB Open oracle blocked by remote-state guard: {exc}",
            )
        if self._driver is None:
            return ParityResult(
                oracle_id=self.oracle_id,
                cross_reference_id=policy.id,
                verdict=ParityVerdictKind.UNVERIFIABLE,
                narrative=(
                    "Renta WEB Open browser driver is not configured. Guard preflight passed, "
                    "but no outbound AEAT Sede adapter was available to execute the open simulator."
                ),
            )
        try:
            observation = self._driver.collect_observation(payload, expected=expected_values)
        except RegistryValidationError as exc:
            return ParityResult(
                oracle_id=self.oracle_id,
                cross_reference_id=policy.id,
                verdict=ParityVerdictKind.UNVERIFIABLE,
                narrative=f"Renta WEB Open driver could not produce comparable observations: {exc}",
            )
        fields = tuple(
            _compare_expected_field(casilla_id, expected_value, observed=observation.values.get(casilla_id))
            for casilla_id, expected_value in sorted(expected_values.items())
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
    """Parse the optional JSON payload and return a :class:`RentaWebOpenLivePayload`."""
    if not payload:
        return RentaWebOpenLivePayload()
    try:
        document = loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, JSONDecodeError) as exc:
        raise RegistryValidationError("Renta WEB Open live payload must be UTF-8 JSON") from exc
    if not isinstance(document, dict):
        raise RegistryValidationError("Renta WEB Open live payload must be a JSON object")
    return RentaWebOpenLivePayload.model_validate(document)


def validate_renta_web_open_expected_casilla_ids[ExpectedKey](
    expected: Mapping[ExpectedKey, object],
) -> frozenset[CasillaId]:
    """Return expected keys validated as canonical ``casilla.id`` values.

    Renta WEB Open browser labels and display numbers are UI coordinates only.
    They must be carried by the live payload's explicit casilla-id-keyed maps,
    never by the oracle ``expected`` comparison surface.
    """
    return frozenset(validate_renta_web_open_expected_casilla_values(expected))


def validate_renta_web_open_expected_casilla_values[ExpectedKey](
    expected: Mapping[ExpectedKey, object],
) -> dict[CasillaId, object]:
    """Return expected values re-keyed by validated canonical ``casilla.id``."""
    invalid_keys: list[str] = []
    casilla_values: dict[CasillaId, object] = {}
    for key, value in expected.items():
        if not isinstance(key, str):
            invalid_keys.append(repr(key))
            continue
        try:
            casilla_values[validated_casilla_id(key, surface="Renta WEB Open expected casilla key")] = value
        except ValueError:
            invalid_keys.append(key)
    if invalid_keys:
        sample = ", ".join(repr(key) for key in sorted(invalid_keys)[:5])
        raise RegistryValidationError(
            "Renta WEB Open expected values must be keyed by canonical casilla.id; "
            f"labels and display-number aliases are not accepted (invalid keys: {sample})",
        )
    return casilla_values


def equivalent_renta_web_open_value(expected: str, observed: str) -> bool:
    """Return true when dot or comma decimal renderings represent the same number.

    A non-finite numeric token is never a parity match, even against an identical
    string. Declaring ``"NaN"`` equal to ``"NaN"`` would certify a corrupt
    magnitude as verified against the oracle, which is the one thing a parity
    gate exists to prevent; the plain string comparison stays for genuinely
    non-numeric captured text.
    """
    if _is_non_finite_numeric_text(expected) or _is_non_finite_numeric_text(observed):
        return False
    if observed == expected:
        return True
    expected_decimal = _parse_decimal_text(expected)
    observed_decimal = _parse_decimal_text(observed)
    return expected_decimal is not None and observed_decimal is not None and expected_decimal == observed_decimal


def _is_non_finite_numeric_text(value: str) -> bool:
    """Whether the text is a numeric token ``Decimal`` accepts but no amount may carry."""
    text = value.strip().replace("\xa0", "")
    if not text:
        return False
    if "," in text:
        text = normalize_decimal_separators(text, strip_thousands=True)
    try:
        return not Decimal(text).is_finite()
    except InvalidOperation:
        return False


def _compare_expected_field(casilla_id: CasillaId, expected: object, *, observed: str | None) -> ParityFieldComparison:
    expected_text = str(expected)
    if observed is None:
        return ParityFieldComparison(
            name=casilla_id, expected=expected_text, observed="", verdict=ParityVerdictKind.UNVERIFIABLE
        )
    verdict: Literal[ParityVerdictKind.MATCH, ParityVerdictKind.MISMATCH] = (
        ParityVerdictKind.MATCH
        if equivalent_renta_web_open_value(expected_text, observed)
        else ParityVerdictKind.MISMATCH
    )
    return ParityFieldComparison(name=casilla_id, expected=expected_text, observed=observed, verdict=verdict)


def _parse_decimal_text(value: str) -> Decimal | None:
    """Parse a captured Renta WEB amount, refusing non-finite tokens.

    ``Decimal`` accepts ``"NaN"`` and ``"Infinity"``, so calling it directly let
    those tokens through as if they were amounts: the parity comparison reported
    ``Infinity == Infinity`` as a match and replay serialization wrote the token
    back out as an expectation. Delegating to the canonical
    :func:`coerce_finite_european_decimal` applies the same ``is_finite()`` gate
    every other amount boundary uses; the local pre-cleaning only strips the
    non-breaking spaces the AEAT capture embeds.
    """
    text = value.strip().replace("\xa0", "")
    if not text:
        return None
    return coerce_finite_european_decimal(text)


def serialize_renta_web_open_replay_decimal(value: str) -> str | None:
    """Render a captured Renta WEB amount as a fixed-point replay expectation."""
    parsed = _parse_decimal_text(value)
    return None if parsed is None else format(parsed, "f")


def _overall_verdict(fields: tuple[ParityFieldComparison, ...]) -> ParityFieldVerdict:
    if any(field.verdict == ParityVerdictKind.MISMATCH for field in fields):
        return ParityVerdictKind.MISMATCH
    if any(field.verdict == ParityVerdictKind.UNVERIFIABLE for field in fields):
        return ParityVerdictKind.UNVERIFIABLE
    return ParityVerdictKind.MATCH


def _narrative_for_verdict(
    verdict: ParityFieldVerdict,
    *,
    driver_mode: CheckerDriverModeValue,
) -> str:
    if verdict == ParityVerdictKind.MATCH:
        return f"Renta WEB Open {driver_mode} parity matched every expected field"
    if verdict == ParityVerdictKind.MISMATCH:
        return f"Renta WEB Open {driver_mode} parity found at least one mismatched field"
    return f"Renta WEB Open {driver_mode} parity could not observe every expected field"


__all__ = [
    "RentaWebOpenDisplayOverride",
    "RentaWebOpenDriver",
    "RentaWebOpenLivePayload",
    "RentaWebOpenObservation",
    "RentaWebOpenOracle",
    "RentaWebOpenReplayDriver",
    "RentaWebOpenSyntheticProfile",
    "equivalent_renta_web_open_value",
    "parse_renta_web_open_live_payload",
    "serialize_renta_web_open_replay_decimal",
    "validate_renta_web_open_expected_casilla_ids",
    "validate_renta_web_open_expected_casilla_values",
]
