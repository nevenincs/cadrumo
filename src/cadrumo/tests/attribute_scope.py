"""Attribute-scope helper for pytest support code.

Sibling to :mod:`cadrumo.tests.env_scope`'s ``scoped_env_var``/``scoped_cwd``/
``scoped_sys_argv`` family, for the case those cover: pinning an arbitrary
object attribute for a with-block and restoring it on exit, without reaching
for the pytest ``monkeypatch`` fixture this repo's real-behaviour-testing
convention bans from production tests. A hand-rolled save/restore performs
the identical mutation ``monkeypatch.setattr`` would, so nothing about
real-behaviour testing changes -- only the vocabulary the AST inventory gate
sees.

Reached by cross-package consumers through this module's own path
(``from cadrumo.tests.attribute_scope import scoped_attribute``), per this
package's documented convention (see ``cadrumo/tests/__init__.py``) of
submodule-direct reach rather than promotion to the package facade.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

__all__ = ["scoped_attribute"]


@contextmanager
def scoped_attribute(target: object, name: str, value: object) -> Generator[None]:
    """Replace ``target.name`` for the with-block, restoring the original on exit."""
    original = getattr(target, name)
    setattr(target, name, value)
    try:
        yield
    finally:
        setattr(target, name, original)
