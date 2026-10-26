"""Async-context-safe Settings overrides for test fixtures.

``cadrumo.core.config.override_settings`` is the canonical entry point
for pinning Settings field values inside a synchronous ``with`` block.
It uses :meth:`contextvars.ContextVar.reset` with a token captured at
enter time, which is the standard pattern for ``contextmanager``-based
ContextVar mutation.

That pattern is *not* safe when the contextmanager is entered inside a
pytest fixture's setup and exited in the fixture's teardown — pytest-
asyncio runs the test body in a child asyncio Task with its own
:class:`contextvars.Context` copy, and the token captured by
``override_settings`` is no longer valid in the fixture's parent
context when teardown runs. The standard library raises
``ValueError: <Token> was created in a different Context`` and the
test errors at teardown.

This module exposes an async-context-safe equivalent: tests obtain a
factory that pushes Settings overrides through a token-less
``ContextVar.set`` call. The prior value is captured once at fixture
entry and restored once at fixture teardown with another plain
``set``, sidestepping the token-context requirement. The trade-off is
that overrides only nest one level deep — if a test needs nested
overrides, ``override_settings`` is still the right tool inside the
test body.

Use this module when a pytest fixture needs to push Settings
overrides on behalf of its tests; use ``override_settings`` directly
when a synchronous test body wants nested or local overrides.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager

from ..core.config import Settings, load_settings, settings_override

__all__ = [
    "SettingsFactory",
    "settings_factory",
]


#: Factory callable signature: accepts arbitrary Settings field overrides
#: and returns a freshly-constructed Settings instance with the merged
#: values registered as the current ContextVar value. Each invocation
#: replaces the prior ContextVar value; the fixture restores the saved
#: prior on teardown.
SettingsFactory = Callable[..., Settings]


@contextmanager
def settings_factory() -> Generator[SettingsFactory]:
    """Yield a Settings factory bound to an async-context-safe ContextVar scope.

    Usage from a pytest fixture::

        @pytest.fixture
        def _settings(...) -> Iterator[SettingsFactory]:
            with settings_factory() as factory:
                yield factory

        # Test body:
        def test_x(_settings) -> None:
            settings = _settings(cadrumo_certificate_path=tmp_path / "cert.p12")
            ...

    Inside the with-block, calls to the yielded factory merge the
    supplied overrides onto the current effective Settings, validate
    the merged dict through :class:`Settings.model_validate`, and
    register the result as the active ContextVar value. The prior
    value (whatever was in the slot at ``settings_factory`` entry) is
    captured once and restored on exit, including on exception.

    The factory's return value is the merged Settings instance; tests
    that need only side-effecting state changes can ignore the return
    value, while tests that want to interrogate the merged Settings
    can bind the return.
    """
    saved_prior = settings_override.get()
    applied = False

    def factory(**overrides: object) -> Settings:
        nonlocal applied
        current = load_settings()
        merged = current.model_dump()
        merged.update(overrides)
        new_settings = Settings.model_validate(merged)
        explicit_fields = current.model_fields_set | set(overrides.keys())
        object.__setattr__(new_settings, "__pydantic_fields_set__", explicit_fields)
        settings_override.set(new_settings)
        applied = True
        return new_settings

    try:
        yield factory
    finally:
        if applied:
            settings_override.set(saved_prior)
