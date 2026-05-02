"""Atomic load / save helpers for :class:`UsageRatioProfile`.

The profile carries business / personal split percentages — classified
``FINANCIAL`` per the default policy table — so both helpers route through the
encrypted-envelope writers in :mod:`aeat.adapters.persistence.storage`. The
on-disk record is always AES-256-GCM ciphertext keyed under HKDF context
``aeat.domain.usage_ratios.profile.v1``; no plaintext split percentage ever
lands on disk.
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
_HKDF_CONTEXT_USAGE_RATIOS = b"aeat.domain.usage_ratios.profile.v1"
_USAGE_RATIO_VERSION = 1


def load_usage_ratios(path: Path) -> UsageRatioProfile:
    """Load the operator's persisted usage-ratio profile, or return an empty one.

    A missing file is not an error — it is the virgin state — so this helper
    returns an empty :class:`UsageRatioProfile` in that case. The on-disk
    record is an :class:`aeat.adapters.persistence.storage.Envelope` carrying
    a ciphertext payload classified
    :class:`aeat.adapters.persistence.storage.SensitivityClass.FINANCIAL` and
    keyed under HKDF context ``aeat.domain.usage_ratios.profile.v1``.

    Args:
        path: Filesystem path of the usage-ratio envelope file.

    Returns:
        The validated profile, or an empty one when ``path`` does not exist.

    Raises:
        :exc:`aeat.domain.usage_ratios.UsageRatioPersistenceError`: If the
            file cannot be read or its payload fails validation.
    """
    from ...adapters.persistence.storage import (
        Envelope,
        SensitivityClass,
        load_encrypted_envelope,
    )
    from ...adapters.persistence.storage.crypto._encrypted_columns import _resolve_master_key_provider

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
    """Render a short, operator-legible summary of a pydantic validation failure.

    The default ``str(ValidationError)`` is verbose and includes pydantic doc
    URLs; this helper extracts one human-readable line per error with the
    offending path (e.g. ``ratios.suministros_home_office_luz``) and the
    message. Two specific rewrites are applied:

    * Unknown dict-key enum errors for ``ratios`` are replaced with a tailored
      list of the eligible categories taken from
      :data:`ELIGIBLE_USAGE_RATIO_CATEGORIES`, sparing the operator pydantic's
      default dump of every :class:`aeat.domain.categories.SpendingCategory`
      member.
    * The pydantic ``"Value error, "`` prefix is stripped where it adds noise.

    Args:
        exc: The :class:`pydantic.ValidationError` raised while loading the
            envelope payload.

    Returns:
        A multi-line summary suitable for embedding in a
        :class:`UsageRatioPersistenceError` message.
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
    """Persist the operator's usage-ratio profile atomically through the substrate.

    The on-disk record is an
    :class:`aeat.adapters.persistence.storage.Envelope` at
    :class:`aeat.adapters.persistence.storage.SensitivityClass.FINANCIAL`
    class, written via
    :func:`aeat.adapters.persistence.storage.save_encrypted_envelope` under an
    exclusive file lock; no plaintext business / personal split percentage
    lands on disk.

    Args:
        profile: The profile to persist.
        path: Destination envelope file.

    Raises:
        :exc:`aeat.domain.usage_ratios.UsageRatioPersistenceError`: If the
            write cannot be completed.
    """
    from ...adapters.persistence.storage import (
        Envelope,
        SensitivityClass,
        exclusive_file_lock,
        save_encrypted_envelope,
    )
    from ...adapters.persistence.storage.crypto._encrypted_columns import _resolve_master_key_provider

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
