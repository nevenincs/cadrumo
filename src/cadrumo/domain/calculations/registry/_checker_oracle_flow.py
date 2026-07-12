"""Shared verdict-flow helpers for read-only checker oracles.

Provides the :class:`_CheckerBaseModel` base, shared flow helpers, and
the :func:`decode_replay_observation` convenience used by every
:class:`~aeat.domain.calculations.registry._live_parity.BaseCheckerOracle`
subclass (GROI, NIF-IVA, and future sibling checkers).
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel

from ....core import STRICT_FROZEN_CONFIG
from ._errors import RegistryValidationError
from ._live_parity import ParityFieldComparison, decode_replay_json_payload
from ._remote_state_guard import RemoteOperation


class _CheckerBaseModel(BaseModel):
    """Strict frozen base for checker-oracle parity records.

    Every :class:`~aeat.domain.calculations.registry._live_parity.BaseCheckerOracle`
    observation and aggregate result type inherits this base to guarantee a
    consistent strict-frozen-forbid Pydantic config across all checker surfaces.
    """

    model_config = STRICT_FROZEN_CONFIG


def normalize_verdict_mapping(values: Mapping[str, str], *, blank_message: str) -> dict[str, str]:
    """Normalize identifier/verdict mappings and reject blank entries."""
    cleaned: dict[str, str] = {}
    for identifier, verdict in values.items():
        normalized_identifier = identifier.strip().upper()
        normalized_verdict = verdict.strip().lower()
        if not normalized_identifier or not normalized_verdict:
            raise RegistryValidationError(blank_message)
        cleaned[normalized_identifier] = normalized_verdict
    return cleaned


def normalize_expected_verdicts(expected: Mapping[str, object], *, blank_message: str) -> dict[str, str]:
    """Normalize expected identifier/verdict mappings and reject blank entries."""
    values: dict[str, str] = {}
    for identifier, verdict in expected.items():
        normalized_identifier = str(identifier).strip().upper()
        normalized_verdict = str(verdict).strip().lower()
        if not normalized_identifier or not normalized_verdict:
            raise RegistryValidationError(blank_message)
        values[normalized_identifier] = normalized_verdict
    return values


def replay_parse_operation(action: str) -> tuple[RemoteOperation, ...]:
    """Return the single local replay-parse :class:`RemoteOperation` tuple."""
    return (RemoteOperation(kind="local_workbook", action=action),)


def decode_replay_observation[ObservationT: _CheckerBaseModel](
    payload: bytes,
    *,
    surface_label: str,
    observation_type: type[ObservationT],
) -> ObservationT:
    """Decode replay JSON into the requested observation model."""
    document = decode_replay_json_payload(payload, surface_label=surface_label)
    return observation_type.model_validate(
        {"values": dict(document.observed), "raw_evidence_locator": document.raw_evidence_locator},
    )


def observed_verdict(values: Mapping[str, str], key: str) -> str | None:
    """Return the observed verdict for ``key`` after identifier normalization."""
    return values.get(key.upper())


def compare_verdict_field(key: str, expected: str, *, observed: str | None) -> ParityFieldComparison:
    """Compare one expected verdict against one observed verdict and return a :class:`ParityFieldComparison`."""
    if observed is None:
        return ParityFieldComparison(name=key, expected=expected, observed="<missing>", verdict="mismatch")
    normalized_observed = observed.strip().lower()
    return ParityFieldComparison(
        name=key,
        expected=expected,
        observed=normalized_observed,
        verdict="match" if normalized_observed == expected else "mismatch",
    )
