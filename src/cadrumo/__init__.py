"""Import-light root package for Cadrumo.

Concrete capabilities live behind layer facades: :mod:`core` for shared primitives
and runtime context, :mod:`domain` for business authorities,
:mod:`application` for use-case orchestration, :mod:`adapters` for
inbound, outbound, and persistence infrastructure, and :mod:`entrypoints`
for operator transports such as the Typer CLI.

Importing ``cadrumo`` must not configure logging, load registries, open storage, or
materialise browser/PDF integrations. The ``pikepdf._core`` bridge logger is
silenced via the ``loggers`` block in
:func:`core.logging.configure_logging` rather than by bootstrap-time side
effects here, keeping logger policy in one auditable location.

The root deliberately exports no runtime symbols. Import the canonical
defining module for each capability instead of treating this package as a
barrel; this keeps importing ``cadrumo`` inert.

See Also:
    :mod:`core.resources`
        Bundled registry and corpus resource boundary used after a concrete
        capability imports the relevant layer.
    :mod:`core.logging`
        Central logging configuration surface kept out of package import
        side effects.
    :mod:`application.operator_surface`
        Backend-owned capability contract for operator and automation surfaces.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
