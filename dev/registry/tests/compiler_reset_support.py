"""Keep the authorities a test session already holds usable across a test that resets the compiler.

A compiler reset forgets every compiled authority's source root, so an
authority a session- or module-scoped fixture built before the reset would
refuse every later source-evidence read with ``RegistrySnapshotError``. A test
that resets the compiler on purpose restores those registrations when it ends.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from ..compiler import authority_state


@contextmanager
def held_authorities_kept_registered() -> Generator[None]:
    """Re-register, on exit, every authority that was registered on entry and is still alive."""
    with authority_state.state_lock:
        held = dict(authority_state.authority_sources)
    try:
        yield
    finally:
        with authority_state.state_lock:
            for key, (reference, source_root) in held.items():
                if reference() is not None:
                    authority_state.authority_sources.setdefault(key, (reference, source_root))
