"""Provider-neutral object-name presentation helpers.

The local filesystem and Google Drive providers share an operator-facing object
name while retaining their own namespace validation, HMAC admissibility, and
ownership rules. Callers validate those provider-specific constraints before
using this module; these helpers only render a safe, bounded name.
"""

from __future__ import annotations

HMAC_PREFIX_LENGTH = 8
_DEFAULT_LABEL = "object"
LABEL_MAX_LENGTH = 64


def provider_object_hmac_prefix(object_key_hmac: str) -> str:
    """Return the fixed-width HMAC prefix used in an operator-visible object name."""
    return object_key_hmac[:HMAC_PREFIX_LENGTH]


def sanitize_provider_object_label(label: str) -> str:
    """Return the bounded human-readable component of a provider object name."""
    cleaned = label.strip()
    if not cleaned:
        return _DEFAULT_LABEL
    safe = "".join(character if character.isalnum() or character in "-_." else "-" for character in cleaned)
    return safe[:LABEL_MAX_LENGTH] or _DEFAULT_LABEL


def build_provider_object_name(object_key_hmac: str, label: str, *, extension: str) -> str:
    """Build ``<hmac-prefix>--<sanitized-label><extension>`` for a provider object."""
    return f"{provider_object_hmac_prefix(object_key_hmac)}--{sanitize_provider_object_label(label)}{extension}"
