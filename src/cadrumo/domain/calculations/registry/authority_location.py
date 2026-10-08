"""Select the published authority descriptor without hydrating registry components."""

from __future__ import annotations

from pathlib import Path

from ....core.resources.bundled_data import bundled_path as _bundled_path
from .authority_store import AUTHORITY_DESCRIPTOR_FILENAME, AuthorityDescriptor, AuthorityStoreError
from .errors import AuthorityDescriptorUnavailableError

_BUNDLED_AUTHORITY_DESCRIPTOR_PARTS = ("registry", "authority", AUTHORITY_DESCRIPTOR_FILENAME)


def bundled_authority_descriptor_path() -> Path:
    """Return the selector for the content-addressed SQLite generation.

    Resolution has two arms and no fallback between them. When
    ``cadrumo_authority_root`` is set it is the whole answer: the descriptor
    is read from that directory, and its absence there is a refusal rather
    than a silent slide back to the packaged copy, which would let a
    development checkout answer from a stale generation it believed it had
    replaced. When the setting is unset -- the installed posture -- the
    packaged resource resolves exactly as it always has.

    Returns:
        The descriptor path, which is guaranteed to exist at the moment of
        the call.

    Raises:
        AuthorityDescriptorUnavailableError: When the selected arm carries no
            descriptor. Fail-closed: every registry read follows this
            selector, so an absent authority cannot be answered partially.
    """
    from ....core.config import configured_authority_root

    authority_root = configured_authority_root()
    if authority_root is not None:
        configured = authority_root / _BUNDLED_AUTHORITY_DESCRIPTOR_PARTS[-1]
        if not configured.is_file():
            raise AuthorityDescriptorUnavailableError.for_configured_root(descriptor_path=configured)
        return configured
    packaged = _bundled_path(*_BUNDLED_AUTHORITY_DESCRIPTOR_PARTS)
    if not packaged.is_file():
        raise AuthorityDescriptorUnavailableError.for_packaged_location(descriptor_path=packaged)
    return packaged


def published_authority_generation() -> str | None:
    """Return the logical generation the selector names now, without admitting its database.

    Processes that must serve one authority cohort -- a runtime and the
    frontends connecting to it -- compare this value. An editable install
    keeps its package version while the published generation moves, so the
    version alone cannot tell them apart. ``None`` means no well-formed
    descriptor resolves; admission refuses that case where it reads.
    """
    try:
        return AuthorityDescriptor.read(bundled_authority_descriptor_path()).logical_generation
    except (AuthorityDescriptorUnavailableError, AuthorityStoreError):
        return None
