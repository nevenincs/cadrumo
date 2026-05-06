"""Load / save helpers for :class:`UsageRatioProfile`.

Usage ratios carry business / personal split percentages. They are
stored as encrypted byte objects in the primary SQL backend at
FINANCIAL sensitivity; no plaintext profile JSON or envelope file lands
on disk.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from ...adapters.persistence.storage import Envelope, SensitivityClass
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core.logging import get_logger
from ._errors import UsageRatioPersistenceError
from ._model import ELIGIBLE_USAGE_RATIO_CATEGORIES, UsageRatioProfile

__all__ = ["load_usage_ratios", "save_usage_ratios"]

_LOGGER = get_logger(__name__)
_USAGE_RATIO_VERSION = 1
_USAGE_RATIO_NAMESPACE = "aeat.domain.usage_ratios"
_USAGE_RATIO_OBJECT_KEY = "profile"


def load_usage_ratios(path: Path) -> UsageRatioProfile:
    """Load the operator's persisted usage-ratio profile, or return an empty one."""

    del path
    objects = SecureObjectRepository()
    try:
        record = objects.load(
            _USAGE_RATIO_NAMESPACE,
            _USAGE_RATIO_OBJECT_KEY,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_USAGE_RATIO_VERSION,
        )
        if record is None:
            _LOGGER.debug("usage-ratios object not found; returning empty profile")
            return UsageRatioProfile()
        envelope = Envelope[UsageRatioProfile].model_validate_json(record.payload.decode("utf-8"))
    except ValidationError as exc:
        _LOGGER.error("usage-ratios object validation failed", exc_info=True)
        raise UsageRatioPersistenceError(
            f"invalid usage-ratio profile object\n{_summarise_validation_errors(exc)}"
        ) from exc
    except (ClassificationError, EnvelopeVersionError) as exc:
        _LOGGER.error("usage-ratios object integrity error", exc_info=True)
        raise UsageRatioPersistenceError(
            f"usage-ratio profile object integrity error: {exc.__class__.__name__}: {exc}"
        ) from exc
    profile = envelope.payload
    _LOGGER.info("loaded %s usage ratios from secure database", len(profile.ratios))
    return profile


def _summarise_validation_errors(exc: ValidationError) -> str:
    """Render a short, operator-legible summary of a pydantic validation failure."""

    lines: list[str] = []
    for error in exc.errors():
        loc = error.get("loc", ())
        location = ".".join(str(part) for part in loc)
        message = error.get("msg", "validation error")
        if error.get("type") == "enum" and len(loc) >= 3 and loc[0] == "ratios" and loc[-1] == "[key]":
            offending_key = loc[1]
            eligible = ", ".join(sorted(c.value for c in ELIGIBLE_USAGE_RATIO_CATEGORIES))
            lines.append(f"  - ratios.{offending_key}: unknown ratio key; eligible categories are: {eligible}")
            continue
        if message.startswith("Value error, "):
            message = message[len("Value error, ") :]
        lines.append(f"  - {location}: {message}" if location else f"  - {message}")
    return "\n".join(lines) if lines else "  - validation error"


def save_usage_ratios(profile: UsageRatioProfile, path: Path) -> None:
    """Persist the operator's usage-ratio profile in the encrypted database."""

    del path
    envelope = Envelope[UsageRatioProfile](
        schema_version=_USAGE_RATIO_VERSION,
        written_at=datetime.now(UTC),
        classification=SensitivityClass.FINANCIAL,
        payload=profile,
    )
    try:
        SecureObjectRepository().save(
            namespace=_USAGE_RATIO_NAMESPACE,
            object_key=_USAGE_RATIO_OBJECT_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_USAGE_RATIO_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )
    except OSError as exc:
        _LOGGER.error("usage-ratios database write failed", exc_info=True)
        raise UsageRatioPersistenceError(
            f"unable to write usage-ratio profile: {exc.__class__.__name__}: {exc}"
        ) from exc
    _LOGGER.info("saved %s usage ratios to secure database", len(profile.ratios))
