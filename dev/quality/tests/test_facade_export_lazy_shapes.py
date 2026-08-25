"""The facade scanner recognises both shipped PEP 562 dispatch shapes.

A lazy facade resolves a name inside ``__getattr__``, so nothing binds it
statically and the scanner has to model the dispatch to know which names the
module can serve. It modelled ONE shape -- string constants compared inline
against ``name`` -- and the tree ships two. The second keeps the names in a
module-level container and tests membership against it:

    _REGISTRY_CONTRACT_EXPORTS = frozenset({"UserProfileSelectorIndex", ...})

    def __getattr__(name):
        if name in _REGISTRY_CONTRACT_EXPORTS:
            ...

Harvesting only the function body reads such a facade as resolving NOTHING, so
every one of its exports is reported unbound. Measured before the fix:
nineteen reports across ``cadrumo.domain.user_profile`` and
``cadrumo.entrypoints.cli``, under the headline that "a clean checkout will
fail to import these packages" -- while a real interpreter resolved all
nineteen, and the facades and their targets were committed and clean.

That matters beyond the noise. This gate's own value is a red result meaning
something; nineteen standing false positives are how a gate gets ignored, and
a red gate also hides the next REAL break in its own output.

The narrowing is deliberate and is the second test below: only containers
``__getattr__`` actually references are harvested. Trusting every module-level
string set would let an unrelated constant list vouch for names the dispatch
never serves.
"""

from __future__ import annotations

import ast

import pytest

from ..facade_export_scan import _lazy_resolvable_names

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: The shape that produced the nineteen false positives.
_CONTAINER_DISPATCH = """
_LAZY_EXPORTS = frozenset({"Alpha", "beta_helper"})


def __getattr__(name):
    if name in _LAZY_EXPORTS:
        from . import _heavy

        return getattr(_heavy, name)
    raise AttributeError(name)
"""

#: The shape the scanner already modelled.
_INLINE_DISPATCH = """
def __getattr__(name):
    if name == "Gamma":
        from ._other import Gamma

        return Gamma
    raise AttributeError(name)
"""

#: A container the dispatch never consults, beside one it does.
_UNREFERENCED_CONTAINER = """
_LAZY_EXPORTS = frozenset({"Alpha"})
_UNRELATED_CONSTANTS = frozenset({"NotDispatched", "AlsoNotDispatched"})


def __getattr__(name):
    if name in _LAZY_EXPORTS:
        from . import _heavy

        return getattr(_heavy, name)
    raise AttributeError(name)
"""

#: No dispatch at all: a module that resolves nothing lazily.
_NO_GETATTR = """
ORDINARY = 1
"""


def _names(source: str) -> set[str]:
    return _lazy_resolvable_names(ast.parse(source))


def test_a_module_level_container_is_recognised() -> None:
    """DISCRIMINATING: the shape whose exports were all reported unbound."""
    assert _names(_CONTAINER_DISPATCH) >= {"Alpha", "beta_helper"}


def test_the_inline_comparison_shape_still_works() -> None:
    """The other direction: repairing one shape must not lose the other.

    ``cadrumo.core`` uses the inline form, and the scanner's own history
    records it going blind to that facade once already.
    """
    assert "Gamma" in _names(_INLINE_DISPATCH)


def test_a_container_the_dispatch_never_reads_is_not_harvested() -> None:
    """ANTI-TAUTOLOGY: the fix must not wave through every module-level string.

    This is what separates modelling the dispatch from trusting the module. If
    an unrelated constant list counted, a facade could export a name nothing
    serves and the scanner would vouch for it -- turning a repaired gate into a
    blind one, which is worse than the false positives it replaced.
    """
    harvested = _names(_UNREFERENCED_CONTAINER)

    assert "Alpha" in harvested
    assert "NotDispatched" not in harvested
    assert "AlsoNotDispatched" not in harvested


def test_a_module_without_a_dispatch_resolves_nothing_lazily() -> None:
    """A facade with no ``__getattr__`` must not acquire lazy names."""
    assert _names(_NO_GETATTR) == set()
