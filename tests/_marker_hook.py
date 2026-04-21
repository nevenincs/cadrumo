"""Shared pytest collection hook enforcing the nine-marker taxonomy.

This module is test-infrastructure, not a production module. It is imported
from both the repo-root ``conftest.py`` and ``tests/conftest.py`` so that
items collected under ``src/aeat/`` and ``tests/`` alike pass through the
same enforcement surface.

Contract enforced by :func:`apply` on every collected item:

- Each item must carry exactly one access marker from
  ``{unit, live_read, live_write}``. Zero or more than one raises
  :class:`pytest.UsageError`.
- Each item must carry at least one ``domain_*`` marker at module level.
- Items carrying ``live_write`` are DROPPED (not skipped) from the
  collection unless all three bypass factors are active:

  1. ``AEAT_LIVE_WRITE_UNSAFE_BYPASS=1`` in the process environment.
  2. ``AEAT_LIVE_WRITE_UNSAFE_BYPASS_CONFIRM`` equals byte-for-byte the
     phrase ``I ACCEPT THE RISK OF FILING A LIVE TAX RETURN``.
  3. ``sys.stdin.isatty()`` returns truthy (interactive terminal).

Drop-not-skip semantics exist because charter ``#116`` rule ``R1`` demands
structural invisibility for the live-write path, not visible deferral:
skipped items still surface in reports as would-have-run deferrals and
are one env-var flip from executing.

Double-invocation tolerance: the repo-root ``conftest.py`` and the
``tests/conftest.py`` both delegate to :func:`apply`. Items collected
under ``tests/`` may pass through the hook twice. This is safe because
:func:`apply` enforces invariants on items it receives and filters
``items`` in-place; a second pass over already-validated items is a
no-op because their marker sets are identical.

The hook never consults ``AEAT_LIVE_SUBMIT_ENABLED``. Charter ``R3``
(env gate) and ``R5`` (``SubmissionEngine.__init__`` runtime refusal)
remain the canonical write-prevention guards; this layer is additive
defence in depth.
"""

from __future__ import annotations

import os
import sys

import pytest

_LIVE_WRITE_BYPASS_ENV = "AEAT_LIVE_WRITE_UNSAFE_BYPASS"
_LIVE_WRITE_CONFIRM_ENV = "AEAT_LIVE_WRITE_UNSAFE_BYPASS_CONFIRM"
_LIVE_WRITE_CONFIRM_PHRASE = "I ACCEPT THE RISK OF FILING A LIVE TAX RETURN"

_ACCESS_MARKERS = frozenset({"unit", "live_read", "live_write"})


def _live_write_bypass_active() -> bool:
    """Return True iff all three live-write bypass factors hold.

    Returns:
        ``True`` when the bypass env var is set to ``"1"``, the confirm
        env var equals the exact confirmation phrase byte-for-byte, and
        stdin is attached to an interactive TTY. Any missing factor
        returns ``False``.
    """
    if os.environ.get(_LIVE_WRITE_BYPASS_ENV) != "1":
        return False
    if os.environ.get(_LIVE_WRITE_CONFIRM_ENV) != _LIVE_WRITE_CONFIRM_PHRASE:
        return False
    return bool(sys.stdin.isatty())


def apply(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Apply the nine-marker taxonomy contract to the collected items.

    Raises :class:`pytest.UsageError` for items missing exactly one access
    marker or at least one domain marker. Drops ``live_write`` items when
    the three-factor bypass is inactive. Emits a single session-level
    warning when the first ``live_write`` drop occurs.

    Args:
        config: The active :class:`pytest.Config` from the collection hook.
        items: The mutable collection items list; filtered in-place.
    """
    remaining: list[pytest.Item] = []
    bypass_active = _live_write_bypass_active()
    warned = False
    for item in items:
        owned = {m.name for m in item.iter_markers()}
        access = owned & _ACCESS_MARKERS
        if len(access) != 1:
            raise pytest.UsageError(
                f"{item.nodeid}: must carry exactly one of "
                f"{{unit, live_read, live_write}}, found {sorted(access) or 'none'}"
            )
        if not any(name.startswith("domain_") for name in owned):
            raise pytest.UsageError(f"{item.nodeid}: must carry at least one domain_* marker")
        if "live_write" in access and not bypass_active:
            if not warned:
                message = "live_write items dropped at collection (charter #116 R1); three-factor bypass inactive"
                issue = getattr(config, "issue_config_time_warning", None)
                if callable(issue):
                    issue(pytest.PytestWarning(message), stacklevel=2)
                else:  # pragma: no cover - older pytest compatibility
                    import warnings

                    warnings.warn(message, pytest.PytestWarning, stacklevel=2)
                warned = True
            continue
        remaining.append(item)
    items[:] = remaining
