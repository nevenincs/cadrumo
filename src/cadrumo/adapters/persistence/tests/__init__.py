"""Test-only support for persistence adapter suites.

Carries the runtime-profile fixture factories for tests in *other* packages, so
a cross-package consumer resolves here rather than reaching into a private
submodule. Suites inside this package import the submodule directly.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
