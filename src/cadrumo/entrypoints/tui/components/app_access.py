"""Static narrowing for Textual's unparameterised ``app`` accessor."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from textual.app import App

__all__ = ["TypedAppAccess"]


class TypedAppAccess:
    """Narrow the inherited ``app`` accessor to a parameterised ``App``.

    Textual declares its shared accessor as ``getters.app(App)`` against the
    bare generic, so every ``self.app`` read resolves as ``App[Unknown]`` and
    poisons the type of whatever it is passed to. The framework's documented
    remedy, ``app = getters.app(MyApp)``, binds a descriptor that asserts the
    running app's concrete class -- but these screens are mounted by more than
    one host app, so that assertion would be a new runtime failure mode.

    This mixin instead states the accessor's type for the checker only. It adds
    no runtime behaviour: the class body is empty outside ``TYPE_CHECKING``, and
    the inherited accessor keeps serving every read.
    """

    if TYPE_CHECKING:

        @property
        def app(self) -> App[object]:
            """The running Textual app, parameterised for static consumers."""
            ...
