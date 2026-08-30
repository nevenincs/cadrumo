"""Refusals: the exception hierarchy, its error-code registry, and severity.

Inert namespace. Every contract is reached at its own defining module:
:mod:`~cadrumo.core.errors.hierarchy` for :class:`CadrumoError` and the tree
beneath it, ``error_codes`` for the registry that binds a code to each
subclass and renders the envelope, ``not_found`` for the core not-found
refusal, and ``severity`` for the shared severity scale. The declarations
themselves live under ``registry``.

This namespace did not merely re-export. It DEFINED the hierarchy while also
re-exporting the registry, and that bundling is what forced the workarounds
around it: :mod:`cadrumo.core.json_contract` needs only
:class:`~hierarchy.CadrumoError`, but importing it pulled the envelope model in
too, so the registry deferred three imports and the namespace carried an
attribute hook to rebuild the model on first access. Splitting the hierarchy
from the registry points the dependency one way and removes the reason for all
four.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
