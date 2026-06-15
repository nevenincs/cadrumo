"""Repo-root pytest conftest.

Hosts the hexagonal marker collection hook from the repo root so every
item gathered under ``src/aeat/...`` passes through the same enforcement
surface. The hook body lives in :mod:`aeat.tests._marker_hook`; this
conftest is a thin wrapper.

The live-test opt-in is read exclusively through
:attr:`aeat.core.config.Settings.live_tests_enabled` (and its Google
companion), which sources ``env/.env`` via pydantic-settings. The single
``aeat.tests.live_gate`` gate is the only live-opt-in reader, so no
``os.environ`` bridging is needed here — the former env-promotion shim was
removed when the scattered raw ``os.environ`` live-gate reads were
centralised onto that Settings-derived surface.

See ``src/aeat/tests/README.md`` and charter ``#116`` for the full taxonomy.
"""

from __future__ import annotations

import pytest

from aeat.tests._marker_hook import apply as _apply_marker_contract


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Delegate to the shared marker-contract enforcer."""
    _apply_marker_contract(config, items)


@pytest.fixture
def fast_lock_acquire(monkeypatch: pytest.MonkeyPatch):
    """Patch ``exclusive_file_lock`` in a target module so it uses ``timeout=0``.

    Lock-contention tests that prove "operation X raises
    :class:`LockAcquisitionError` when the lock is held" only need the
    single non-blocking attempt; the default 30 s wait turns each such
    test into a 30-second standstill. This fixture wraps the imported
    ``exclusive_file_lock`` symbol on a caller-supplied module so the
    contention path raises immediately.

    Returns:
        A callable ``patch(module)`` that installs the short-circuit
        wrapper. Multiple modules may be patched in one test.
    """
    from aeat.core.locks import exclusive_file_lock as _real

    def _patch(module: object) -> None:
        def _short(target, **kwargs):  # type: ignore[no-untyped-def]
            kwargs.setdefault("timeout", 0.0)
            return _real(target, **kwargs)

        monkeypatch.setattr(module, "exclusive_file_lock", _short)

    return _patch
