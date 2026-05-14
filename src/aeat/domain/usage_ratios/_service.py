"""Load / save helpers for :class:`UsageRatioProfile`.

Usage ratios carry business / personal split percentages. They are
stored as encrypted byte objects in the primary SQL backend at
FINANCIAL sensitivity; no plaintext profile JSON or envelope file lands
on disk.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import ValidationError

from ...adapters.persistence.storage import Envelope, SensitivityClass
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core.logging import get_logger
from ._errors import UsageRatioPersistenceError
from ._model import ELIGIBLE_USAGE_RATIO_CATEGORIES, UsageRatioProfile

__all__ = ["load_usage_ratios", "save_usage_ratios", "usage_ratios_object_key"]

_LOGGER = get_logger(__name__)
_USAGE_RATIO_VERSION = 1
_USAGE_RATIO_NAMESPACE = "aeat.domain.usage_ratios"


def usage_ratios_object_key(bucket_id: str) -> str:
    """Return the secure object key for one profile bucket's usage-ratio profile."""

    trimmed = bucket_id.strip()
    if not trimmed:
        raise UsageRatioPersistenceError("bucket_id must not be blank")
    return f"profile:{trimmed}"


def load_usage_ratios(*, bucket_id: str, objects: SecureObjectRepository | None = None) -> UsageRatioProfile:
    """Load one bucket's persisted usage-ratio profile, or return an empty one."""

    repository = objects or SecureObjectRepository()
    object_key = usage_ratios_object_key(bucket_id)
    try:
        record = repository.load(
            _USAGE_RATIO_NAMESPACE,
            object_key,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_USAGE_RATIO_VERSION,
        )
        if record is None:
            _LOGGER.debug("usage-ratios object not found; returning empty profile bucket_id=%s", bucket_id)
            return UsageRatioProfile()
        envelope = Envelope[UsageRatioProfile].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not SensitivityClass.FINANCIAL:
            raise ClassificationError(
                f"usage-ratio profile object has classification {envelope.classification}; "
                f"consumer expected {SensitivityClass.FINANCIAL}"
            )
        if envelope.schema_version > _USAGE_RATIO_VERSION:
            raise EnvelopeVersionError(
                f"usage-ratio profile object is at version {envelope.schema_version}; "
                f"consumer supports up to {_USAGE_RATIO_VERSION}"
            )
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
    _LOGGER.info("loaded %s usage ratios from secure database bucket_id=%s", len(profile.ratios), bucket_id)
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


def save_usage_ratios(
    profile: UsageRatioProfile,
    *,
    bucket_id: str,
    objects: SecureObjectRepository | None = None,
) -> None:
    """Persist one bucket's usage-ratio profile in the encrypted database."""

    envelope = Envelope[UsageRatioProfile](
        schema_version=_USAGE_RATIO_VERSION,
        written_at=datetime.now(UTC),
        classification=SensitivityClass.FINANCIAL,
        payload=profile,
    )
    object_key = usage_ratios_object_key(bucket_id)
    repository = objects or SecureObjectRepository()
    try:
        repository.save(
            namespace=_USAGE_RATIO_NAMESPACE,
            object_key=object_key,
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
    _LOGGER.info("saved %s usage ratios to secure database bucket_id=%s", len(profile.ratios), bucket_id)
