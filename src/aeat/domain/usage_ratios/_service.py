"""Atomic load/save helpers for :class:`UsageRatioProfile` (issue #259).

The profile carries business / personal split percentages — FINANCIAL
class per the default policy table. Both helpers route through the
substrate's encrypted-envelope writers so the on-disk record is always
AES-256-GCM ciphertext under HKDF context
``aeat.domain.financial.usage_ratios.profile.v1``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from ...core.logging import get_logger
from ._errors import UsageRatioPersistenceError
from ._model import ELIGIBLE_USAGE_RATIO_CATEGORIES, UsageRatioProfile

__all__ = ["load_usage_ratios", "save_usage_ratios"]

_LOGGER = get_logger(__name__)
_HKDF_CONTEXT_USAGE_RATIOS = b"aeat.domain.financial.usage_ratios.profile.v1"
_USAGE_RATIO_VERSION = 1


def load_usage_ratios(path: Path) -> UsageRatioProfile:
    """Load Kent's persisted usage-ratio profile, or return an empty one.

    A missing file is not an error — it is the virgin state — so this helper
    returns an empty :class:`UsageRatioProfile` in that case. The on-disk
    record is a :class:`CipherEnvelope` written under HKDF context
    ``aeat.domain.financial.usage_ratios.profile.v1`` at FINANCIAL class.

    Args:
        path: Filesystem path of the usage-ratio envelope file.

    Returns:
        The validated profile, or an empty one when ``path`` does not exist.

    Raises:
        UsageRatioPersistenceError: If the file cannot be read or its
            payload is invalid.
    """
    from ...adapters.persistence.storage import (
        Envelope,
        SensitivityClass,
        load_encrypted_envelope,
    )
    from ...adapters.persistence.storage._encrypted_columns import _resolve_master_key_provider

    target = path.resolve()
    if not target.exists():
        _LOGGER.info("usage-ratios file not found at %s; returning empty profile", target)
        return UsageRatioProfile()
    try:
        envelope = load_encrypted_envelope(
            target,
            Envelope[UsageRatioProfile],
            expected_class=SensitivityClass.FINANCIAL,
            master_key_provider=_resolve_master_key_provider(),
            hkdf_context=_HKDF_CONTEXT_USAGE_RATIOS,
            max_supported_version=_USAGE_RATIO_VERSION,
        )
    except ValidationError as exc:
        raise UsageRatioPersistenceError(
            f"invalid usage-ratio profile envelope: {target}\n{_summarise_validation_errors(exc)}"
        ) from exc
    except OSError as exc:
        raise UsageRatioPersistenceError(
            f"unable to read usage-ratio profile: {target}: {exc.__class__.__name__}: {exc}"
        ) from exc
    profile = envelope.payload
    _LOGGER.info("loaded %s usage ratios from %s", len(profile.ratios), target)
    return profile


def _summarise_validation_errors(exc: ValidationError) -> str:
    """Render a short, Kent-legible summary of a pydantic validation failure.

    The default ``str(ValidationError)`` is verbose and includes pydantic doc
    URLs; this helper extracts one human-readable line per error with the
    offending path (e.g. ``ratios.suministros_home_office_luz``) and the
    message. Two specific rewrites are applied for Kent's benefit:

    * Unknown dict-key enum errors for ``ratios`` are replaced with a
      tailored list of the twelve eligible categories (instead of pydantic's
      default dump of all 38 ``SpendingCategory`` values).
    * The pydantic ``"Value error, "`` / ``"Input should be "`` prefixes
      are stripped where they add noise.
    """
    lines: list[str] = []
    for error in exc.errors():
        loc = error.get("loc", ())
        location = ".".join(str(part) for part in loc)
        message = error.get("msg", "validation error")
        # Detect the pydantic "dict-key failed enum validation" shape.
        # Example loc: ("ratios", "foo", "[key]"); type: "enum".
        if error.get("type") == "enum" and len(loc) >= 3 and loc[0] == "ratios" and loc[-1] == "[key]":
            offending_key = loc[1]
            eligible = ", ".join(sorted(c.value for c in ELIGIBLE_USAGE_RATIO_CATEGORIES))
            lines.append(f"  - ratios.{offending_key}: unknown ratio key; eligible categories are: {eligible}")
            continue
        # Strip pydantic's leading "Value error, " on custom validator errors.
        if message.startswith("Value error, "):
            message = message[len("Value error, ") :]
        lines.append(f"  - {location}: {message}" if location else f"  - {message}")
    return "\n".join(lines) if lines else "  - validation error"


def save_usage_ratios(profile: UsageRatioProfile, path: Path) -> None:
    """Persist Kent's usage-ratio profile atomically through the substrate.

    The on-disk record is a :class:`CipherEnvelope` at FINANCIAL class
    written via :func:`save_encrypted_envelope`; no plaintext business /
    personal split percentage lands on disk.

    Args:
        profile: The profile to persist.
        path: Destination envelope file.

    Raises:
        UsageRatioPersistenceError: If the write cannot be completed.
    """
    from ...adapters.persistence.storage import (
        Envelope,
        SensitivityClass,
        exclusive_file_lock,
        save_encrypted_envelope,
    )
    from ...adapters.persistence.storage._encrypted_columns import _resolve_master_key_provider

    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_target = target.with_suffix(".lock")
    try:
        with exclusive_file_lock(lock_target):
            envelope = Envelope[UsageRatioProfile](
                schema_version=_USAGE_RATIO_VERSION,
                written_at=datetime.now(UTC),
                classification=SensitivityClass.FINANCIAL,
                payload=profile,
            )
            save_encrypted_envelope(
                envelope,
                target,
                master_key_provider=_resolve_master_key_provider(),
                hkdf_context=_HKDF_CONTEXT_USAGE_RATIOS,
            )
    except OSError as exc:
        raise UsageRatioPersistenceError(
            f"unable to write usage-ratio profile: {target}: {exc.__class__.__name__}: {exc}"
        ) from exc
    _LOGGER.info("saved %s usage ratios to %s", len(profile.ratios), target)
